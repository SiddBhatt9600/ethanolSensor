import json
import os
import threading
import time
import zoneinfo
from collections import deque
from datetime import datetime

import mileageEstimator
from fuelQualityModel import FuelQualityModel

MAX_AI_RECORDS = 1000


CAPTURE_POLL_INTERVAL = 1  # seconds
ANOMALY_WINDOW = 30       # readings kept for drift detection
ANOMALY_Z = 3.0           # z-score threshold


class AiManager:

    def __init__(self, sensor_manager, logger,
                 weights_path=None):

        self.sensor_manager = sensor_manager
        self.logger = logger

        # Optional — set via set_imu_manager() after construction so
        # main.py's existing manager startup order doesn't need to
        # change. Mileage estimation works without it (driver-
        # behavior term just reports "unavailable").
        self.imu_manager = None

        if weights_path is None:

            #
            # Weights live next to this file; the app's working
            # directory is not guaranteed to be python/.
            #
            weights_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "model_weights.json"
            )

        self.model = FuelQualityModel(weights_path)

        self._running = False
        self._thread = None
        self._lock = threading.Lock()

        #
        # Verdict history cache
        #
        self.verdict_cache = []

        #
        # Rolling window for anomaly / refuel-drift detection
        #
        self.window = deque(maxlen=ANOMALY_WINDOW)

        self.next_infer = time.time()

        # Timestamp of the last button capture already scored, so
        # the worker only reacts to a NEW capture rather than
        # re-scoring the same one every poll tick.
        self._last_capture_timestamp = None

    ###########################################################
    #
    # Utility Functions
    #
    ###########################################################

    def _timestamp(self):

        return datetime.now(
            zoneinfo.ZoneInfo("Asia/Kolkata")
        ).isoformat()

    ###########################################################

    def set_imu_manager(self, imu_manager):
        """Wire up the IMU manager for the mileage estimator's
        driver-behavior term. Optional — call after both managers
        exist in main.py."""

        self.imu_manager = imu_manager

    ###########################################################

    def _mileage(self, reading, verdict):

        imu_stats = None

        if self.imu_manager is not None:

            try:
                imu_stats = self.imu_manager.get_statistics()

            except Exception:
                imu_stats = None

        return mileageEstimator.estimate(reading, verdict, imu_stats)

    ###########################################################
    #
    # JSON Helpers
    #
    ###########################################################

    def save_verdict(self, verdict):

        filename = "ai_history.json"

        history = []

        if os.path.exists(filename):

            try:

                with open(filename, "r") as fp:

                    history = json.load(fp)

            except Exception:

                history = []

        history.append(verdict)

        history = history[-MAX_AI_RECORDS:]

        with open(filename, "w") as fp:

            json.dump(history, fp, indent=4)

    ###########################################################
    #
    # Anomaly Detection (refuel drift)
    #
    ###########################################################

    def check_anomaly(self, reading):

        keys = ["ethanol", "wif", "turbidity", "density"]

        anomalies = []

        if len(self.window) >= 10:

            for key in keys:

                # Defensive: window entries can predate the
                # sensorManager plausibility gate (e.g. loaded from
                # an older sensor_history.json). Skip anything that
                # isn't a real number instead of letting float()
                # raise and killing the whole verdict for this cycle.
                values = [
                    float(r[key]) for r in self.window
                    if isinstance(r.get(key), (int, float))
                ]

                if len(values) < 5:
                    continue

                current = reading.get(key)
                if not isinstance(current, (int, float)):
                    continue

                mean = sum(values) / len(values)

                var = sum((v - mean) ** 2 for v in values) / len(values)

                std = var ** 0.5

                if std < 1e-6:
                    continue

                z = abs(float(current) - mean) / std

                if z > ANOMALY_Z:

                    anomalies.append({

                        "type": "drift",

                        "parameter": key,

                        "z_score": round(z, 2),

                        "baseline_mean": round(mean, 2),

                        "value": round(float(reading[key]), 2),

                        "reason": None

                    })

        self.window.append(reading)

        return anomalies

    ###########################################################
    #
    # Inference
    #
    ###########################################################

    def _awaiting_density_verdict(self, reading):
        """Density is user-entered (no board sensor); until the user
        submits one, temp/ethanol/wif/turbidity still update live but
        there is nothing to classify yet. Returning this explicit
        placeholder (same shape as a real verdict) instead of just
        skipping the cycle keeps the dashboard honest — it shows
        "enter density" rather than silently re-displaying whatever
        verdict happened to be computed before density went missing."""

        return {
            "timestamp": self._timestamp(),
            "reading": reading,
            "verdict": "AWAITING_DENSITY",
            "confidence": 0.0,
            "probs": {"GOOD": 0.0, "SUSPECT": 0.0, "ADULTERATED": 0.0},
            "blend": None,
            "explain": {
                "density15": None,
                "expected_density15": None,
                "rho_residual": None,
                "signals": [
                    "Enter fuel density (hydrometer reading) from "
                    "the app to get an AI verdict."
                ],
            },
            "anomalies": [],
            "mileage": None,
        }

    def infer(self, reading):

        # Defense in depth: sensorManager now rejects implausible/
        # None readings before they're stored, but a reading loaded
        # from an old sensor_history.json (written before that fix)
        # could still have a stray None. Fail with a clear message
        # instead of a cryptic float(None) crash deep in numpy.
        required = ["temp", "ethanol", "wif", "turbidity", "density"]
        if not all(isinstance(reading.get(k), (int, float))
                   for k in required):
            raise ValueError(
                f"Cannot classify reading with missing/invalid "
                f"fields: {reading}"
            )

        result = self.model.predict(reading)

        anomalies = self.check_anomaly(reading)

        # Anomalies must always be present whenever there is any
        # suspicion or adulteration. Drift (z-score) anomalies only
        # fire on a SUDDEN change against the rolling baseline, so
        # fuel that has been consistently bad for a while (no drift
        # event, it just IS the new baseline) would otherwise show
        # an empty anomalies list next to a SUSPECT/ADULTERATED
        # verdict. Fold in the same reasons already computed for the
        # "Why" explanation as "quality"-type entries whenever the
        # verdict isn't GOOD, so the list is never misleadingly empty.
        if result["verdict"] != "GOOD":
            for reason in result["explain"]["signals"]:
                anomalies.append({
                    "type": "quality",
                    "parameter": "quality",
                    "z_score": None,
                    "baseline_mean": None,
                    "value": None,
                    "reason": reason,
                })

        mileage = self._mileage(reading, result["verdict"])

        verdict = {

            "timestamp": self._timestamp(),

            "reading": reading,

            "verdict": result["verdict"],

            "confidence": result["confidence"],

            "probs": result["probs"],

            "blend": result["blend"],

            "explain": result["explain"],

            "anomalies": anomalies,

            "mileage": mileage

        }

        return verdict

    ###########################################################

    def infer_capture(self, capture):

        """
        Scores a button capture (10-sample average) on demand.
        Called via REST when the app requests a spot verdict.
        """

        avg = capture.get("average", {})

        required = ["temp", "ethanol", "wif", "turbidity", "density"]

        # Check values are real numbers, not just that the keys
        # exist — SensorManager.average() can leave a key present
        # but None if every sample in the capture window was
        # rejected (e.g. probe out of the fuel for that capture).
        if not all(isinstance(avg.get(k), (int, float)) for k in required):

            return {

                "error": "no valid capture available"

            }

        result = self.model.predict(avg)

        anomalies = []
        if result["verdict"] != "GOOD":
            for reason in result["explain"]["signals"]:
                anomalies.append({
                    "type": "quality",
                    "parameter": "quality",
                    "z_score": None,
                    "baseline_mean": None,
                    "value": None,
                    "reason": reason,
                })

        mileage = self._mileage(avg, result["verdict"])

        return {

            "timestamp": self._timestamp(),

            "source": "button_capture",

            "average": avg,

            "reading": avg,

            "verdict": result["verdict"],

            "confidence": result["confidence"],

            "probs": result["probs"],

            "blend": result["blend"],

            "explain": result["explain"],

            "anomalies": anomalies,

            "mileage": mileage

        }

    ###########################################################
    #
    # Worker Thread
    #
    ###########################################################

    def _worker(self):
        """Every value the dashboard shows — cards, verdict, verdict
        history — comes exclusively from a button-triggered capture
        now, not a time-based continuous poll. So this loop just
        watches for a NEW completed capture (by timestamp) and scores
        its 10-sample average the moment one lands, instead of
        re-scoring whatever the background sensor loop last saw
        on a fixed timer regardless of whether it changed."""

        while self._running:

            now = time.time()

            if now >= self.next_infer:

                capture = self.sensor_manager.get_latest_capture()
                capture_ts = capture.get("timestamp") if capture else None

                if capture_ts and capture_ts != self._last_capture_timestamp:

                    avg = capture.get("average", {})
                    core_fields = ["temp", "ethanol", "wif", "turbidity"]

                    if all(
                        isinstance(avg.get(k), (int, float))
                        for k in core_fields
                    ):

                        self._last_capture_timestamp = capture_ts

                        reading = dict(avg)
                        reading.setdefault("timestamp", capture_ts)

                        try:

                            if reading.get("density") is None:
                                verdict = self._awaiting_density_verdict(reading)
                            else:
                                verdict = self.infer(reading)

                            with self._lock:

                                self.verdict_cache.append(verdict)

                                self.verdict_cache = \
                                    self.verdict_cache[-MAX_AI_RECORDS:]

                            self.save_verdict(verdict)

                            self.logger.info(

                                f"AI Verdict : {verdict['verdict']} "
                                f"({verdict['confidence']})"

                            )

                            if verdict["anomalies"]:

                                self.logger.info(

                                    f"AI Anomaly : {verdict['anomalies']}"

                                )

                        except Exception as e:

                            self.logger.exception(e)

                    else:

                        self._last_capture_timestamp = capture_ts

                        self.logger.warning(
                            "Button capture had no usable sensor "
                            "readings (probe in air / disconnected?) "
                            "— skipping AI verdict for this capture."
                        )

                self.next_infer = now + CAPTURE_POLL_INTERVAL

            time.sleep(0.25)

    ###########################################################
    #
    # Public APIs
    #
    ###########################################################

    def start(self):

        if self._running:
            return

        self.verdict_cache.clear()

        self.window.clear()

        self._last_capture_timestamp = None

        with open("ai_history.json", "w") as fp:
            json.dump([], fp, indent=4)

        self._running = True

        self.next_infer = time.time()

        self._thread = threading.Thread(

            target=self._worker,

            name="AiManager",

            daemon=True

        )

        self._thread.start()

        self.logger.info(
            "AiManager Started."
        )

    ###########################################################

    def stop(self):

        self._running = False

        if (

            self._thread is not None

            and

            threading.current_thread() != self._thread

        ):

            self._thread.join()

        self._thread = None

        self.logger.info(
            "AiManager Stopped."
        )

    ###########################################################
    #
    # REST APIs
    #
    ###########################################################

    def get_latest_verdicts(self, count=10):

        with self._lock:

            return self.verdict_cache[-count:]

    ###########################################################

    def get_current_verdict(self):

        with self._lock:

            if not self.verdict_cache:

                return {

                    "verdict": "UNKNOWN",

                    "confidence": 0

                }

            return self.verdict_cache[-1]
