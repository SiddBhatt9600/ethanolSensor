import json
import os
import threading
import time
import statistics
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

        #
        # Continuous history cache
        #
        self.history_cache = []

        #
        # Button capture state
        #
        self.capture_active = False
        self.capture_pending = False
        self.capture_samples = []

        #
        # Scheduler
        #
        self.next_continuous = time.time()
        self.next_capture = 0

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
    #
    # JSON Helpers
    #
    ###########################################################

    def clear_button_json(self):

        with open("sensor_history_button.json", "w") as fp:

            json.dump([], fp, indent=4)

    ###########################################################

    def save_history(self, reading):

        filename = "sensor_history.json"

        history = []

        if os.path.exists(filename):

            try:

                with open(filename, "r") as fp:

                    history = json.load(fp)

            except Exception:

                history = []

        history.append(reading)

        history = history[-MAX_SENSOR_RECORDS:]

        with open(filename, "w") as fp:

            json.dump(history, fp, indent=4)

    ###########################################################

    def save_capture(self):

        avg = {

            "temp":
            round(
                statistics.mean(
                    x["temp"] for x in self.capture_samples
                ),
                2
            ),

            "ethanol":
            round(
                statistics.mean(
                    x["ethanol"] for x in self.capture_samples
                ),
                2
            ),

            "wif":
            round(
                statistics.mean(
                    x["wif"] for x in self.capture_samples
                ),
                2
            ),

            "turbidity":
            round(
                statistics.mean(
                    x["turbidity"] for x in self.capture_samples
                ),
                2
            ),

            "density":
            round(
                statistics.mean(
                    x["density"] for x in self.capture_samples
                ),
                2
            )
        }

        output = {

            "timestamp": self._timestamp(),

            "samples": self.capture_samples,

            "average": avg
        }

        with open("sensor_history_button.json", "w") as fp:

            json.dump(output, fp, indent=4)

    ###########################################################
    #
    # Sensor Reading
    #
    ###########################################################

    def readSensors(self):

        try:

            return {

                "timestamp": self._timestamp(),

                "temp":
                self.bridge.call("getFuelTemp"),

                "ethanol":
                self.bridge.call("getethanolPercentage"),

                "wif":
                self.bridge.call("getwif"),

                "turbidity":
                self.bridge.call("getturbidity"),

                "density":
                round(
                    self.bridge.call("getdensity"),
                    2
                )
            }

        except Exception as e:

            self.logger.exception(e)

            return None

    ###########################################################
    #
    # Continuous Logger
    #
    ###########################################################

    def log_continuous(self):

        reading = self.readSensors()

        if reading is None:
            return

        self.history_cache.append(reading)

        self.history_cache = self.history_cache[-MAX_SENSOR_RECORDS:]

        self.save_history(reading)

        self.logger.info(
            f"Continuous Reading : {reading}"
        )

    ###########################################################
    #
    # Capture Control
    #
    ###########################################################

    def trigger_capture(self):

        with self._lock:

            #
            # Already recording?
            #
            if self.capture_active:

                self.logger.info(
                    "Capture already running."
                )

                return False

            #
            # Less than five readings?
            #
            if len(self.history_cache) < 5:

                self.capture_pending = True

                self.logger.info(
                    "Capture queued until 5 continuous readings are available."
                )

                return True

            #
            # Fresh capture
            #
            self.clear_button_json()

            self.capture_samples = []

            self.capture_active = True

            self.next_capture = time.time()

            self.logger.info(
                "Capture Started."
            )

            return True

    #####################################################

        ###########################################################
    #
    # Worker Thread
    #
    ###########################################################

    def _worker(self):

        while self._running:

            now = time.time()

            ###################################################
            # Continuous Logging
            ###################################################

            if now >= self.next_continuous:

                self.log_continuous()

                self.next_continuous = now + CONTINUOUS_INTERVAL

            ###################################################
            # Queued Capture
            ###################################################

            with self._lock:

                if (
                    self.capture_pending and
                    len(self.history_cache) >= 5
                ):

                    self.logger.info(
                        "Queued capture started."
                    )

                    self.capture_pending = False

                    self.capture_active = True

                    self.capture_samples = []

                    self.clear_button_json()

                    self.next_capture = now

            ###################################################
            # Capture Scheduler
            ###################################################

            with self._lock:

                capture_running = self.capture_active

            if capture_running and now >= self.next_capture:

                reading = self.readSensors()

                if reading is not None:

                    self.capture_samples.append(reading)

                    self.logger.info(

                        f"Capture Sample "
                        f"{len(self.capture_samples)}/"
                        f"{CAPTURE_SAMPLE_COUNT}"

                    )

                    self.next_capture = now + CAPTURE_INTERVAL

                    if len(self.capture_samples) >= CAPTURE_SAMPLE_COUNT:

                        self.save_capture()

                        with self._lock:

                            self.capture_active = False

                            self.capture_pending = False

                        self.logger.info(
                            "Capture Completed."
                        )

            ###################################################

            time.sleep(0.25)

    ###########################################################
    #
    # Public APIs
    #
    ###########################################################

    def start(self):

        if self._running:
            return

        self.history_cache.clear()

        self.capture_samples.clear()

        self.capture_active = False
        self.capture_pending = False

        with open("sensor_history.json", "w") as fp:
            json.dump([], fp, indent=4)

        self.clear_button_json()

        self._running = True

        self.next_continuous = time.time()

        self._thread = threading.Thread(

            target=self._worker,

            name="SensorManager",

            daemon=True

        )

        self._thread.start()

        self.logger.info(
            "SensorManager Started."
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
            "SensorManager Stopped."
        )

    ###########################################################
    #
    # REST APIs
    #
    ###########################################################

    def get_latest_history(self, count=10):

        return self.history_cache[-count:]

    ###########################################################

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