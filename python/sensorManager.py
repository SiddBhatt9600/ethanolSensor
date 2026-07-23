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


class SensorManager:

    def __init__(self, bridge, logger):
        self.bridge = bridge
        self.logger = logger

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

    # Utility Functions
    def _timestamp(self):
        return datetime.now(
            zoneinfo.ZoneInfo("Asia/Kolkata")
        ).isoformat()

    # JSON Helpers
    def clear_button_json(self):
        with open("sensor_history_button.json", "w") as fp:
            json.dump([], fp, indent=4)

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

    def readSensors(self):
        try:
            return {
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
                "turbidity":
                self.sanitize(
                    round(
                        self.bridge.call("getturbidity"),
                        2
                    )
                ),
                "density":
                self.sanitize(
                    round(
                        self.bridge.call("getdensity"),
                        2
                    )
                )
            }

        except Exception as e:
            self.logger.exception(e)
            return None
        
    # Continuous Logger
    def log_continuous(self):
        reading = self.readSensors()
        if reading is None:
            return

        ##################################################
        # Continuous History
        ##################################################

        self.history_cache.append(reading)

        self.history_cache = self.history_cache[
            -MAX_SENSOR_RECORDS:
        ]

        self.save_history()

        ##################################################
        # Button Capture
        ##################################################

        with self._lock:

            if self.capture_pending:
                self.capture_samples.append(reading)
                self.logger.info(
                    f"Capture Sample "
                    f"{len(self.capture_samples)}/"
                    f"{CAPTURE_SAMPLE_COUNT}"
                )

                if (len(self.capture_samples) >= CAPTURE_SAMPLE_COUNT):
                    self.save_capture()
                    self.capture_pending = False
                    self.capture_samples = []
                    self.logger.info(
                        "Capture Completed."
                    )

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
                "Button pressed. Waiting for next "
                f"{CAPTURE_SAMPLE_COUNT} continuous readings."
            )

            self.clear_button_json()
            self.capture_samples = []

            self.capture_pending = True

            return True

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
        if not os.path.exists(
            "sensor_history_button.json"
        ):
            return {
                "samples": [],
                "average": {}
            }
        try:
            with open(
                "sensor_history_button.json",
                "r"
            ) as fp:
                return json.load(fp)

        except Exception:
            return {
                "samples": [],
                "average": {}
            }
