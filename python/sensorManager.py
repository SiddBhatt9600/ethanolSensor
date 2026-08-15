import json
import os
import threading
import time
import statistics
import math
import zoneinfo
from datetime import datetime

MAX_SENSOR_RECORDS = 1000

CONTINUOUS_INTERVAL = 10      # seconds
CAPTURE_INTERVAL = 0.1        # 100 ms
CAPTURE_SAMPLE_COUNT = 5

# The MCU's readTurbidityRaw() returns raw 12-bit ADC counts
# (0-4095). scale_turbidity() first converts that to a plain 0-100
# index (no direction assumed yet).
TURBIDITY_ADC_MAX = 4095.0

# Field calibration (2 Aug 2026, real hardware, real fuel samples):
# this sensor reads HIGHER when fuel is CLEARER — the opposite of
# the original guess, and the opposite of the physics simulator's
# training convention (features.py / fuel_simulator.py train with
# LOW turbidity = clean, HIGH = dirty). Observed bands on the 0-100
# scaled index:
#   >= 35        -> clean
#   30 - 35      -> suspicious / mild haze
#   < 30          -> adulterated / heavy particulates
# calibrate_turbidity() inverts and remaps these observed bands onto
# the simulator's scale (clean ~0-6, suspect ~12-30, adulterated
# ~40-100) so the feature reaching the model means what the model
# was trained to interpret. Re-run the dip test and adjust these
# three constants if the sensor or wiring changes.
TURBIDITY_FIELD_CLEAN = 35.0
TURBIDITY_FIELD_SUSPECT = 30.0

# User-submitted density is kept in memory (SensorManager.user_density)
# but also mirrored to this file so a process restart during a demo
# doesn't silently drop back to "no density entered" and freeze the
# AI verdict on a stale cached reading.
USER_DENSITY_FILE = "user_density.json"


class SensorManager:

    def __init__(self, bridge, logger, density_file=None):
        self.bridge = bridge
        self.logger = logger

        # Overridable so tests can point separate SensorManager
        # instances at isolated files instead of sharing (and
        # leaking state through) the real USER_DENSITY_FILE.
        self.density_file = density_file or USER_DENSITY_FILE

        self._running = False
        self._thread = None
        self._lock = threading.Lock()

        # Continuous history cache
        self.history_cache = []

        # Button capture state
        self.capture_active = False
        self.capture_pending = False
        self.capture_samples = []

        # Scheduler
        self.next_continuous = time.time()
        self.next_capture = 0

        # Density is user-entered (phone app / web dashboard), not
        # read from the board — there is no density sensor on the
        # MCU. Whatever the user last submitted applies to every
        # reading (continuous + button capture) until they update
        # it again, same mental model as "measure once with a
        # hydrometer, use it for this tank of fuel".
        self.user_density = None
        self.user_density_timestamp = None

        self._load_user_density()

    # Utility Functions
    def _timestamp(self):
        return datetime.now(
            zoneinfo.ZoneInfo("Asia/Kolkata")
        ).isoformat()

    # JSON Helpers
    def clear_button_json(self):

        with open("sensor_history_button.json", "w") as fp:
            json.dump({"samples": [], "average": {}}, fp, indent=4)

    ###########################################################

    def save_history(self):
        self.history_cache = self.history_cache[-MAX_SENSOR_RECORDS:]
        with open("sensor_history.json", "w") as fp:
            json.dump(
                self.history_cache,
                fp,
                indent=4
            )

    ###########################################################
    
    def average(self, key):
        values = [
            x[key]
            for x in self.capture_samples
            if x[key] is not None
        ]

        if not values:
            return None

        return round(
            statistics.mean(values),
            2
        )

    def save_capture(self):
        output = {
            "timestamp": self._timestamp(),
            "samples": self.capture_samples,

            "average": {
                "temp":
                self.average("temp"),

                "ethanol":
                self.average("ethanol"),

                "wif":
                self.average("wif"),

                "turbidity":
                self.average("turbidity"),

                "turbidity_raw":
                self.average("turbidity_raw"),

                "density":
                self.average("density")
            }
        }

        with open(
            "sensor_history_button.json",
            "w"
        ) as fp:

            json.dump(
                output,
                fp,
                indent=4
            )

    # Sensor Reading
    ###########################################################

    def sanitize(self, value):
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return None
        return value

    # Physically-possible ranges for the board-read sensors. A
    # reading outside these bounds (or missing/NaN, already turned
    # into None by sanitize()) is rejected before it ever reaches
    # history or the AI. This is the main guard against garbage from
    # a disconnected sensor or a probe held in air instead of fuel:
    # values that float outside a sane liquid-fuel envelope get
    # dropped here instead of crashing feature extraction downstream
    # (float(None) raises) or feeding the model an input it was
    # never trained on.
    #
    # Density is deliberately NOT in this dict: it is user-entered
    # (no board sensor exists for it), so it must not gate whether
    # the other four live sensor readings get stored/displayed. A
    # reading with no density yet is still a real, valid sensor
    # reading — it just can't be scored by the AI until density is
    # supplied (see AiManager). Gating everything on density used to
    # mean that after any restart (density resets to unset) every
    # continuous reading was rejected outright, freezing the whole
    # dashboard on stale cached data.
    CORE_PLAUSIBLE_RANGE = {
        "temp": (-20.0, 150.0),
        "ethanol": (0.0, 100.0),
        "wif": (0.0, 100.0),
        "turbidity": (0.0, 100.0),
    }

    # Sanity band for a *user-entered* density value — independent of
    # the tighter 725-775 kg/m3 "standard fuel" band used for the
    # actual adulteration judgement (see fuelQualityModel.
    # STANDARD_DENSITY_BAND). This one only exists to catch obvious
    # fat-finger/garbage entries (e.g. a unit mixup); it does not
    # reject the rest of the reading, only the density field itself.
    DENSITY_SANITY_RANGE = (500.0, 1000.0)

    def _load_user_density(self):
        if not os.path.exists(self.density_file):
            return

        try:
            with open(self.density_file, "r") as fp:
                data = json.load(fp)

            self.user_density = data.get("density")
            self.user_density_timestamp = data.get("timestamp")

            self.logger.info(
                f"Restored user-submitted density "
                f"{self.user_density} kg/m3 from disk"
            )

        except Exception as e:
            self.logger.warning(
                f"Failed to restore saved user density: {e}"
            )

    def set_user_density(self, value):
        """Called from the REST endpoint the phone app / web
        dashboard posts a manually-measured density to. No board
        density sensor exists — this is the only source of density.
        Persisted to disk so a process restart mid-demo doesn't lose
        it and silently freeze the AI verdict.

        Rejects obviously-implausible values (unit mixups, typos)
        right here with a clear error, instead of silently storing
        them and having readSensors()/sanitize_density() discard them
        later — that used to make the dashboard show "density in use"
        for a value that was actually never reaching the AI."""

        try:
            density = round(float(value), 2)
        except (TypeError, ValueError):
            return {"error": f"'{value}' is not a numeric density value"}

        lo, hi = self.DENSITY_SANITY_RANGE
        if math.isnan(density) or math.isinf(density) or not (lo <= density <= hi):
            return {
                "error": (
                    f"{value} kg/m3 is outside the plausible liquid-fuel "
                    f"density range ({lo:.0f}-{hi:.0f} kg/m3) — check the "
                    f"value and try again"
                )
            }

        with self._lock:
            self.user_density = density
            self.user_density_timestamp = self._timestamp()

            with open(self.density_file, "w") as fp:
                json.dump({
                    "density": self.user_density,
                    "timestamp": self.user_density_timestamp,
                }, fp, indent=4)

        self.logger.info(
            f"User-supplied density set to {self.user_density} kg/m3"
        )

        return {
            "density": self.user_density,
            "timestamp": self.user_density_timestamp,
        }

    def get_user_density(self):
        with self._lock:
            return {
                "density": self.user_density,
                "timestamp": self.user_density_timestamp,
            }

    def is_core_plausible(self, reading):
        """Gates whole-reading acceptance on the four board-read
        sensors only. Density is checked separately (sanitize_density)
        and never causes the rest of the reading to be dropped."""
        for key, (lo, hi) in self.CORE_PLAUSIBLE_RANGE.items():
            value = reading.get(key)
            if not isinstance(value, (int, float)):
                return False
            if not (lo <= value <= hi):
                return False
        return True

    def sanitize_density(self, value):
        """A missing, NaN, or out-of-sane-range density becomes None
        (AI verdict simply waits for a real one) instead of dropping
        the temp/ethanol/wif/turbidity readings that came in fine."""
        if value is None:
            return None
        if not isinstance(value, (int, float)):
            return None
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        lo, hi = self.DENSITY_SANITY_RANGE
        if not (lo <= value <= hi):
            return None
        return value

    def scale_turbidity(self, raw):
        """Raw 12-bit ADC counts (0-4095) -> plain 0-100 index.
        No direction/meaning assumed yet — see calibrate_turbidity()
        for the field-calibrated remap onto the model's convention.

        NOT currently called from readSensors(): the MCU's
        getturbidity() already does this ADC->0-100 scaling itself
        (readTurbidityPercent() in sketch.ino), so the bridge value
        readSensors() receives is already a plain 0-100 index. Kept
        here in case the MCU ever goes back to exposing a raw ADC
        RPC (e.g. readTurbidityRaw)."""

        if raw is None:
            return None

        pct = (float(raw) / TURBIDITY_ADC_MAX) * 100.0

        return round(max(0.0, min(100.0, pct)), 2)

    def calibrate_turbidity(self, raw_pct):
        """Maps the sensor's observed 0-100 turbidity index onto the
        0-100 turbidity feature the AI model was trained on (LOW =
        clean, HIGH = dirty), using the field-calibrated bands in
        TURBIDITY_FIELD_CLEAN / TURBIDITY_FIELD_SUSPECT above."""

        if raw_pct is None:
            return None

        if raw_pct >= TURBIDITY_FIELD_CLEAN:
            span = max(1e-6, 100.0 - TURBIDITY_FIELD_CLEAN)
            frac = max(0.0, min(1.0, (raw_pct - TURBIDITY_FIELD_CLEAN) / span))
            return round(6.0 - frac * 6.0, 2)                # 35->6, 100->0

        elif raw_pct >= TURBIDITY_FIELD_SUSPECT:
            span = TURBIDITY_FIELD_CLEAN - TURBIDITY_FIELD_SUSPECT
            frac = (TURBIDITY_FIELD_CLEAN - raw_pct) / span
            return round(12.0 + frac * 18.0, 2)               # 35->12, 30->30

        else:
            span = max(1e-6, TURBIDITY_FIELD_SUSPECT)
            frac = max(0.0, min(1.0, (TURBIDITY_FIELD_SUSPECT - raw_pct) / span))
            return round(40.0 + frac * 60.0, 2)               # 30->40, 0->100

    def readSensors(self):
        try:
            reading = {
                "timestamp": self._timestamp(),
                "temp":
                self.sanitize(
                    round(
                        self.bridge.call("readDS18B20TempC"),
                        2
                    )
                ),
                "ethanol":
                self.sanitize(
                    round(
                        self.bridge.call("getethanolPercentage"),
                        2
                    )
                ),
                "wif":
                self.sanitize(
                    round(
                        self.bridge.call("getwif"),
                        2
                    )
                ),

                "density": self.user_density
            }

            turbidity_raw = self.sanitize(
                round(float(self.bridge.call("getturbidity")), 2)
            )

            reading["turbidity_raw"] = turbidity_raw
            reading["turbidity"] = self.sanitize(
                self.calibrate_turbidity(turbidity_raw)
            )

            if not self.is_core_plausible(reading):
                self.logger.warning(
                    f"Rejected implausible sensor reading "
                    f"(probe in air / disconnected?): {reading}"
                )
                return None

            sanitized_density = self.sanitize_density(reading["density"])
            if reading["density"] is not None and sanitized_density is None:
                self.logger.warning(
                    f"Discarding implausible user-entered density "
                    f"{reading['density']} (outside "
                    f"{self.DENSITY_SANITY_RANGE} kg/m3 sanity band); "
                    f"other sensor values still recorded"
                )
            reading["density"] = sanitized_density

            return reading

        except Exception as e:
            self.logger.exception(e)
            return None
    def _record_history(self, reading):
        with self._lock:
            self.history_cache.append(reading)

            self.history_cache = self.history_cache[
                -MAX_SENSOR_RECORDS:
            ]

            self.save_history()

    def log_continuous(self):
        reading = self.readSensors()
        if reading is None:
            return

        self._record_history(reading)

        self.logger.info(
            f"Continuous Reading : {reading}"
        )

    # Capture Control
    def trigger_capture(self):
        with self._lock:
            if self.capture_pending:

                self.logger.info(
                    "Capture already pending."
                )
                return False

            self.logger.info(
                f"Button pressed. Capturing {CAPTURE_SAMPLE_COUNT} "
                f"fresh readings now."
            )

            self.clear_button_json()
            self.capture_samples = []

            self.capture_pending = True

        threading.Thread(
            target=self._run_capture,
            daemon=True,
            name="SensorManager-Capture"
        ).start()

        return True

    def _run_capture(self):
        samples = []
        attempts = 0
        max_attempts = CAPTURE_SAMPLE_COUNT * 10

        while len(samples) < CAPTURE_SAMPLE_COUNT and attempts < max_attempts:
            attempts += 1

            reading = self.readSensors()

            if reading is not None:
                samples.append(reading)
                self._record_history(reading)

                self.logger.info(
                    f"Capture Sample {len(samples)}/{CAPTURE_SAMPLE_COUNT}"
                )

            time.sleep(CAPTURE_INTERVAL)

        with self._lock:
            self.capture_samples = samples
            self.capture_pending = False

        if len(samples) < CAPTURE_SAMPLE_COUNT:
            self.logger.warning(
                f"Capture finished with only {len(samples)}/"
                f"{CAPTURE_SAMPLE_COUNT} valid readings after "
                f"{attempts} attempts (probe in air / disconnected?)."
            )

        self.save_capture()

        self.logger.info("Capture Completed.")

    ###########################################################
    #
    # Worker Thread

    def _worker(self):
        while self._running:
            now = time.time()

            if now >= self.next_continuous:
                self.log_continuous()

                self.next_continuous = (
                    now +
                    CONTINUOUS_INTERVAL
                )
            time.sleep(0.25)

    # Public APIs

    def start(self):
        ##################################################
        # Load previous history if available
        ##################################################

        if os.path.exists("sensor_history.json"):
            try:
                with open("sensor_history.json", "r") as fp:
                    self.history_cache = json.load(fp)

            except Exception as e:
                self.logger.warning(
                    f"Failed to load previous history: {e}"
                )
                self.history_cache = []

        else:
            self.history_cache = []

        ##################################################
        # Reset button capture only
        ##################################################

        self.clear_button_json()

        self.capture_pending = False
        self.capture_samples = []

        ##################################################
        # Start worker
        ##################################################

        self._running = True
        self.next_continuous = time.time()
        
        self._thread = threading.Thread(
            target=self._worker,
            daemon=True,
            name="SensorManager"
        )

        self._thread.start()

    ###########################################################

    def stop(self):
        self._running = False
        if (self._thread is not None and threading.current_thread() != self._thread):
            self._thread.join()

        self._thread = None

        self.logger.info(
            "SensorManager Stopped."
        )

    # REST APIs
    def get_latest_history(self, count=10):
        return self.history_cache[-count:]

    def get_latest_capture(self):
        empty = {"samples": [], "average": {}}

        if not os.path.exists(
            "sensor_history_button.json"
        ):
            return empty
        try:
            with open(
                "sensor_history_button.json",
                "r"
            ) as fp:
                data = json.load(fp)

            if not isinstance(data, dict):
                return empty

            return data

        except Exception:
            return empty
