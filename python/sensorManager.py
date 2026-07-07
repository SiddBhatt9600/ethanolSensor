import json
import os
import threading
import time
import zoneinfo
from datetime import datetime

MAX_SENSOR_RECORDS = 1000

class SensorManager:
    def __init__(self, bridge, logger):
        self.bridge = bridge
        self.logger = logger

        self._running = False
        self._thread = None
        self.sensorReadings = {
            "temp": [],
            "wif": [],
            "ethanolLevels": [],
            "turbidity": [],
            "density": []
        }

    def clear_json(self):
        filename = "sensor_history.json"
    
        with open(filename, "w") as f:
            json.dump([], f, indent=4)
        
    def save_json(self):
        filename = "sensor_history.json"
    
        history = []

        if os.path.exists(filename):
            try:
                with open(filename, "r") as f:
                    history = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                history = []

        history.append({
            "timestamp": datetime.now(zoneinfo.ZoneInfo("Asia/Kolkata")).isoformat(),
            "sensorReadings": self.sensorReadings
        })

        # Keep only the latest 1000 records
        if len(history) > MAX_SENSOR_RECORDS:
            history = history[-MAX_SENSOR_RECORDS:]

        with open(filename, "w") as f:
            json.dump(history, f, indent=4)


    def readSensors(self):
        try:
            fuelTemp = self.bridge.call("getFuelTemp")
            self.sensorReadings["temp"].append(fuelTemp)

            ethPercen = self.bridge.call("getethanolPercentage")
            self.sensorReadings["ethanolLevels"].append(ethPercen)

            wifPer = self.bridge.call("getwif")
            self.sensorReadings["wif"].append(wifPer)

            turbidityVal = self.bridge.call("getturbidity")
            self.sensorReadings["turbidity"].append(turbidityVal)

            densityVal = round(self.bridge.call("getdensity"), 2)
            self.sensorReadings["density"].append(densityVal)

            print("Sensor temp stored:", self.sensorReadings)
            self.save_json()
            if len(self.sensorReadings) > MAX_SENSOR_RECORDS:
                self.sensorReadings.pop(0)
        except Exception as e:
            self.logger.exception(f"sensorReadings: Error: {e}")
            print("sensorReadings: Error:", e)
    
    def _worker(self):
        while self._running:
            self.readSensors()
            time.sleep(10)

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
