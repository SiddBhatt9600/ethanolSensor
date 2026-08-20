import json
import math
import os
import threading
import time
import zoneinfo
from collections import deque
from datetime import datetime

import mileageEstimator
from fuelQualityModel import FuelQualityModel

MAX_AI_RECORDS = 1000

AI_HISTORY_FILE = "ai_history.json"


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

    def save_verdict(self):
        """Mirror the in-memory verdict cache to disk.

        The cache is already the capped, ordered history this file is
        meant to contain, so it is dumped directly rather than being
        re-read and re-appended each time. start() truncates the file,
        so it is a per-session log, not durable storage.
        """
        with self._lock:
            snapshot = list(self.verdict_cache)

        with open(AI_HISTORY_FILE, "w") as fp:
            json.dump(snapshot, fp, indent=4)

    ###########################################################
    #
    # Anomaly Detection (refuel drift)
    #
    ###########################################################

    def record_and_check_anomaly(self, reading):
        """Compare this reading against the rolling baseline, then fold
        it into that baseline.

        Note the side effect: the reading is appended to self.window
        before returning, so calling this twice with the same reading
        pollutes the baseline with a duplicate. It is called exactly
        once per scored reading, from _score().
        """

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

                # A flat baseline has no meaningful z-score; dividing
                # by it would make any change look infinitely anomalous.
                if std < 1e-6:
                    continue

                z = abs(float(current) - mean) / std

                if z > ANOMALY_Z:
                    anomalies.append({
                        "type": "drift",
                        "parameter": key,
                        "z_score": round(z, 2),
                        "baseline_mean": round(mean, 2),
                        "value": round(float(current), 2),
                        "reason": None,
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

    REQUIRED_FIELDS = ["temp", "ethanol", "wif", "turbidity", "density"]

    @staticmethod
    def _has_scorable_fields(reading):
        """Every field the model needs is present AND a finite number.

        Checking the values rather than just the keys matters:
        SensorManager.average() leaves a key present but None when
        every sample in a capture window was rejected (probe out of
        the fuel), and readings loaded from an old history file can
        carry a stray None from before the plausibility gate existed.

        Finiteness is checked separately because isinstance(x, float)
        is True for NaN — and a NaN slipping through would compare
        False against every threshold and be judged clean. See
        fuelQualityModel._require_finite().
        """
        for key in AiManager.REQUIRED_FIELDS:
            value = reading.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return False
            if not math.isfinite(float(value)):
                return False
        return True

    @staticmethod
    def _quality_anomalies(result):
        """The verdict's own reasons, restated as anomaly entries.

        Drift (z-score) anomalies only fire on a SUDDEN change against
        the rolling baseline, so fuel that has been consistently bad
        for a while — no drift event, it simply IS the baseline now —
        would otherwise show an empty anomalies list next to a
        SUSPECT/ADULTERATED verdict. Folding the explanation in here
        keeps that list from being misleadingly empty.
        """
        if result["verdict"] == "GOOD":
            return []

        return [
            {
                "type": "quality",
                "parameter": "quality",
                "z_score": None,
                "baseline_mean": None,
                "value": None,
                "reason": reason,
            }
            for reason in result["explain"]["signals"]
        ]

    def _score(self, reading, track_drift):
        """Shared scoring core behind both public entry points, so the
        two can never disagree about the same reading.

        track_drift owns the rolling baseline: only the worker path
        passes True. The on-demand capture path passes False because
        the worker has already folded that same capture into the
        window — letting both record it would count one capture twice
        and skew the baseline it is measured against.
        """
        result = self.model.predict(reading)

        anomalies = (
            self.record_and_check_anomaly(reading) if track_drift else []
        )
        anomalies.extend(self._quality_anomalies(result))

        return {
            "timestamp": self._timestamp(),
            "reading": reading,
            "verdict": result["verdict"],
            "confidence": result["confidence"],
            "probs": result["probs"],
            "model_probs": result.get("model_probs"),
            "blend": result["blend"],
            "explain": result["explain"],
            "anomalies": anomalies,
            "mileage": self._mileage(reading, result["verdict"]),
        }

    def infer(self, reading):
        """Score one reading and fold it into the drift baseline.
        Raises ValueError on an unscorable reading — the caller (the
        worker) treats that as a bug worth logging, not a normal
        outcome."""

        if not self._has_scorable_fields(reading):
            raise ValueError(
                f"Cannot classify reading with missing/invalid "
                f"fields: {reading}"
            )

        return self._score(reading, track_drift=True)

    ###########################################################

    def infer_capture(self, capture):
        """Score a button capture (10-sample average) on demand.
        Called via REST when the app requests a spot verdict, where an
        unusable capture is a normal thing to report rather than raise
        on."""

        avg = capture.get("average", {})

        if not self._has_scorable_fields(avg):
            return {"error": "no valid capture available"}

        verdict = self._score(avg, track_drift=False)
        verdict["source"] = "button_capture"
        # Alias kept for the dashboard's shared renderer, which reads
        # "average" for capture verdicts and "reading" for live ones.
        verdict["average"] = avg

        return verdict

    ###########################################################
    #
    # Worker Thread
    #
    ###########################################################

    # Core sensors that must be present for a capture to be worth
    # scoring. Density is excluded on purpose: it is user-entered, and
    # a capture without it still produces a useful "awaiting density"
    # card rather than being thrown away.
    CORE_CAPTURE_FIELDS = ["temp", "ethanol", "wif", "turbidity"]

    def _handle_new_capture(self, capture_ts, avg):
        """Score one freshly-landed capture and record the verdict."""

        if not all(isinstance(avg.get(k), (int, float))
                   for k in self.CORE_CAPTURE_FIELDS):
            self.logger.warning(
                "Button capture had no usable sensor readings "
                "(probe in air / disconnected?) — skipping AI verdict "
                "for this capture."
            )
            return

        reading = dict(avg)
        reading.setdefault("timestamp", capture_ts)

        if reading.get("density") is None:
            verdict = self._awaiting_density_verdict(reading)
        else:
            verdict = self.infer(reading)

        with self._lock:
            self.verdict_cache.append(verdict)
            self.verdict_cache = self.verdict_cache[-MAX_AI_RECORDS:]

        self.save_verdict()

        self.logger.info(
            f"AI Verdict : {verdict['verdict']} ({verdict['confidence']})"
        )
        if verdict["anomalies"]:
            self.logger.info(f"AI Anomaly : {verdict['anomalies']}")

    def _worker(self):
        """Every value the dashboard shows — cards, verdict, verdict
        history — comes exclusively from a button-triggered capture
        now, not a time-based continuous poll. So this loop just
        watches for a NEW completed capture (by timestamp) and scores
        its 10-sample average the moment one lands, instead of
        re-scoring whatever the background sensor loop last saw
        on a fixed timer regardless of whether it changed."""

        while self._running:

            capture = self.sensor_manager.get_latest_capture()
            capture_ts = capture.get("timestamp") if capture else None

            if capture_ts and capture_ts != self._last_capture_timestamp:

                # Marked as seen before scoring, not after: a capture
                # that throws must not be retried forever on every tick.
                self._last_capture_timestamp = capture_ts

                try:
                    self._handle_new_capture(capture_ts,
                                             capture.get("average", {}))
                except Exception as e:
                    self.logger.exception(e)

            time.sleep(CAPTURE_POLL_INTERVAL)

    ###########################################################
    #
    # Public APIs
    #
    ###########################################################

    def start(self):

        if self._running:
            return

        # Under the lock: get_latest_verdicts()/get_current_verdict()
        # can be serving a REST request on another thread while this
        # resets the cache.
        with self._lock:
            self.verdict_cache.clear()
            self.window.clear()
            self._last_capture_timestamp = None

        with open(AI_HISTORY_FILE, "w") as fp:
            json.dump([], fp, indent=4)

        self._running = True

        self._thread = threading.Thread(
            target=self._worker,
            name="AiManager",
            daemon=True,
        )
        self._thread.start()

        self.logger.info("AiManager Started.")

    ###########################################################

    def stop(self):

        self._running = False

        # Guard against joining from inside the worker itself, which
        # would deadlock.
        if (self._thread is not None
                and threading.current_thread() != self._thread):
            self._thread.join()

        self._thread = None

        self.logger.info("AiManager Stopped.")

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
                return {"verdict": "UNKNOWN", "confidence": 0}

            return self.verdict_cache[-1]
