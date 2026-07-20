from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI

from hbManager import HbManager
from sensorManager import SensorManager
from aiManager import AiManager
from imuManager import ImuManager

###############################################################
# Logger / Bridge
###############################################################

logger = Logger("fuel-quality-monitor")
bridge = Bridge

###############################################################
# WebUI
###############################################################

ui = WebUI()

###############################################################
# Managers
###############################################################

hbManager = HbManager(bridge, logger)
hbManager.start()

sensorManager = SensorManager(bridge, logger)
sensorManager.start()

aiManager = AiManager(sensorManager, logger)
aiManager.start()

imuManager = ImuManager(logger, ui)
imuManager.start()

aiManager.set_imu_manager(imuManager)


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

def get_ai_verdicts():
    """
    Returns the latest 10 continuous AI verdicts.
    """
    return aiManager.get_latest_verdicts()


def get_current_verdict():
    """
    Returns the most recent AI verdict (status card).
    """
    return aiManager.get_current_verdict()


def get_capture_verdict():
    """
    Runs the model on the latest button capture average.
    """
    return aiManager.infer_capture(
        sensorManager.get_latest_capture()
    )


ui.expose_api("GET", "/api/sensors", get_sensor_data)
ui.expose_api("GET", "/api/button_capture", get_button_capture)
ui.expose_api("GET", "/api/ai/verdicts", get_ai_verdicts)
ui.expose_api("GET", "/api/ai/current", get_current_verdict)
ui.expose_api("GET", "/api/ai/capture_verdict", get_capture_verdict)

###############################################################
# Bridge callback
###############################################################

def record_sensor_values():
    logger.info("Button pressed. Starting capture.")
    return sensorManager.trigger_capture()

ui.expose_api(
    "GET",
    "/api/imu_capture",
    imuManager.get_latest_samples
)

ui.expose_api(
    "GET",
    "/api/imu_statistics",
    imuManager.get_statistics
)

ui.expose_api(
    "GET",
    "/api/imu_history",
    imuManager.get_last_30_minutes
)

ui.expose_api(
    "GET",
    "/api/heartbeat",
    hbManager.get_status
)

def record_imu_values(ax: int, ay: int, az: int, gx: int , gy: int, gz: int):
    # logger.info(f"record_imu_values called with raw a-values: ax={ax}, ay={ay}, az={az}")
    # logger.info(f"record_imu_values called with raw g-values: gx={gx}, gy={gy}, gz={gz}")
    imuManager.record(
        ax,
        ay,
        az,
        gx,
        gy,
        gz
    )

try:
    Bridge.provide("record_sensor_values", record_sensor_values)
    logger.info(
        "Bridge provider 'record_sensor_values' registered."
    )

except RuntimeError:
    logger.exception(
        "'record_sensor_values' already registered."
    )

try:
    Bridge.provide("record_imu_values",record_imu_values)
    logger.info(
        "Bridge provider 'record_imu_values' registered."
    )

except RuntimeError:
    logger.exception(
        "'record_imu_values' already registered."
    )

###############################################################
# Application
###############################################################

logger.info("Fuel Quality Monitor Started")

App.run()