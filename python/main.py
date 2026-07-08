from arduino.app_utils import *
import time
import json
from hbManager import HbManager
from sensorManager import SensorManager
from arduino.app_bricks.web_ui import WebUI

logger = Logger("read-hb-state")
bridge = Bridge

hbInst = HbManager(bridge, logger)
hbInst.start()

mainInst = SensorManager(bridge, logger)
mainInst.start()

def get_sensor_data():

    with open("sensor_history.json") as f:
        history = json.load(f)

    return history[-10:]

ui = WebUI()

ui.expose_api("GET", "/api/sensors", get_sensor_data)

App.run()