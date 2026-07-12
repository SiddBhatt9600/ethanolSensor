import json
import os
import threading
import time
import zoneinfo
from collections import deque
from datetime import datetime

from fuelQualityModel import FuelQualityModel

MAX_AI_RECORDS = 1000

AI_INTERVAL = 10          # seconds, matches continuous sensor cadence
ANOMALY_WINDOW = 30       # readings kept for drift detection
ANOMALY_Z = 3.0           # z-score threshold


class AiManager:

    def __init__(self, sensor_manager, logger,
                 weights_path=None):

        self.sensor_manager = sensor_manager
        self.logger = logger

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

                values = [float(r[key]) for r in self.window]

                mean = sum(values) / len(values)

                var = sum((v - mean) ** 2 for v in values) / len(values)

                std = var ** 0.5

                if std < 1e-6:
                    continue

                z = abs(float(reading[key]) - mean) / std

                if z > ANOMALY_Z:

                    anomalies.append({

                        "parameter": key,

                        "z_score": round(z, 2),

                        "baseline_mean": round(mean, 2),

                        "value": round(float(reading[key]), 2)

                    })

        self.window.append(reading)

        return anomalies

    ###########################################################
    #
    # Inference
    #
    ###########################################################

    def infer(self, reading):

        result = self.model.predict(reading)

        anomalies = self.check_anomaly(reading)

        verdict = {

            "timestamp": self._timestamp(),

            "reading": reading,

            "verdict": result["verdict"],

            "confidence": result["confidence"],

            "probs": result["probs"],

            "explain": result["explain"],

            "anomalies": anomalies

        }

        return verdict

    ###########################################################

    def infer_capture(self, capture):

        """
        Scores a button capture (5-sample average) on demand.
        Called via REST when the app requests a spot verdict.
        """

        avg = capture.get("average", {})

        required = ["temp", "ethanol", "wif", "turbidity", "density"]

        if not all(k in avg for k in required):

            return {

                "error": "no valid capture available"

            }

        result = self.model.predict(avg)

        return {

            "timestamp": self._timestamp(),

            "source": "button_capture",

            "average": avg,

            "verdict": result["verdict"],

            "confidence": result["confidence"],

            "probs": result["probs"],

            "explain": result["explain"]

        }

    ###########################################################
    #
    # Worker Thread
    #
    ###########################################################

    def _worker(self):

        while self._running:

            now = time.time()

            if now >= self.next_infer:

                latest = self.sensor_manager.get_latest_history(1)

                if latest:

                    reading = latest[-1]

                    try:

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

                self.next_infer = now + AI_INTERVAL

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
