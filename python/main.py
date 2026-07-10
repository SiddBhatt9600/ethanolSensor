from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI

import json

from hbManager import HbManager
from sensorManager import SensorManager

###############################################################
# Logger / Bridge
###############################################################

logger = Logger("fuel-quality-monitor")
bridge = Bridge

###############################################################
# Managers
###############################################################

hbManager = HbManager(bridge, logger)
hbManager.start()

sensorManager = SensorManager(bridge, logger)
sensorManager.start()

###############################################################
# WebUI
###############################################################

ui = WebUI()


def get_sensor_data():
    """
    Returns the latest 10 continuous sensor readings.
    """
    return sensorManager.get_latest_history()


def get_button_capture():
    """
    Returns the latest button capture (5 samples + average).
    """
    return sensorManager.get_latest_capture()

ui.expose_api("GET", "/api/sensors", get_sensor_data)
ui.expose_api("GET", "/api/button_capture", get_button_capture)

###############################################################
# Bridge callback
###############################################################

def record_sensor_values():
    logger.info("Button pressed. Starting capture.")
    return sensorManager.trigger_capture()


try:
    Bridge.provide(
        "record_sensor_values",
        record_sensor_values
    )

    logger.info(
        "Bridge provider 'record_sensor_values' registered."
    )

except RuntimeError:

    logger.info(
        "'record_sensor_values' already registered."
    )

###############################################################
# Application
###############################################################

logger.info("Fuel Quality Monitor Started")

App.run()