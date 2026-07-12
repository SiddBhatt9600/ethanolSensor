import json
import os
import threading
import time
import zoneinfo
from datetime import datetime

MAX_HB_RECORDS = 1000
HB_REQUEST_TIMEOUT = 20


class HbManager:
    def __init__(self, bridge, logger):
        self.LAST_RESPONSE = 0
        self.MISSED_HB = 0
        self.bridge = bridge
        self.logger = logger

        self._running = False
        self._thread = None

    def clear_json(self):
        filename = "sensor_history.json"
    
        with open(filename, "w") as f:
            json.dump([], f, indent=4)

    def save_json(self, hb_value):
        filename = "hb_history.json"

        history = []

        if os.path.exists(filename):
            try:
                with open(filename, "r") as f:
                    history = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                history = []

        history.append({
            "timestamp": datetime.now(zoneinfo.ZoneInfo("Asia/Kolkata")).isoformat(),
            "heartbeat": hb_value,
            "missed_hb": self.MISSED_HB
        })

        # Keep only the latest 1000 records
        if len(history) > MAX_HB_RECORDS:
            history = history[-MAX_HB_RECORDS:]

        with open(filename, "w") as f:
            json.dump(history, f, indent=4)

    def get_status(self):
        return {
            "heartbeat": self.LAST_RESPONSE,
            "missed": self.MISSED_HB
        }

    def get_hb_state(self):
        try:
            data = self.bridge.call("getHbState")

            if data > self.LAST_RESPONSE:
                self.logger.debug(f"Received HB = {data}")
                print("Received HB =", data)

                self.LAST_RESPONSE = data
                self.save_json(data)

            else:
                self.MISSED_HB += 1
                self.logger.error(
                    f"Did not receive HB in time, last known HB: {self.LAST_RESPONSE}"
                )
                # TODO: Recovery mechanism

        except Exception as e:
            self.logger.exception(f"getHbState: Error: {e}")
            print("getHbState: Error:", e)

    def _worker(self):
        while self._running:
            self.get_hb_state()
            time.sleep(HB_REQUEST_TIMEOUT)

    def start(self):
        self.clear_json()
        if self._thread is None or not self._thread.is_alive():
            self._running = True
            self._thread = threading.Thread(
                target=self._worker,
                daemon=True
            )
            self._thread.start()

    def stop(self):
        self._running = False

        if self._thread is not None:
            self._thread.join()