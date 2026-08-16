import json

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
###############################################################
# WebUI and Instantiate imuManager with it
###############################################################

ui = WebUI()

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


def trigger_button_capture():
    """
    Starts a 5-sample button capture on demand from the phone app /
    web dashboard, exactly like the physical button — lets a capture
    be triggered from the UI when the physical button isn't handy
    (e.g. desk testing) without touching the board.
    """
    logger.info("Capture requested from UI. Starting capture.")
    return {"capture_started": sensorManager.trigger_capture()}


def get_user_density():
    """
    Returns the last user-submitted density + when it was set.
    """
    return sensorManager.get_user_density()


def set_user_density(*args, density=None, **kwargs):
    """
    Sets the manually-measured density (no board sensor exists —
    this is entered by the user via the phone app / web dashboard
    and applies to every reading, continuous and button-capture,
    until updated again).

    Deliberately defensive about *how* WebUI hands us the POST body:
    a typed keyword parameter (density=...) was the original
    assumption, but that was never confirmed against the real
    framework and field testing showed density submitted from the
    dashboard silently not taking effect — the only way to actually
    change it was hand-editing sensorManager's persisted density
    file and restarting, which only works because restart forces a
    reload from that file. That means the request body was never
    reaching sensorManager.set_user_density() at all. So every
    plausible calling shape is handled here: a bound `density`
    kwarg, a dict body passed positionally, a raw JSON string body,
    or a bare numeric/string positional value.
    """
    value = density

    if value is None and args:
        candidate = args[0]

        if isinstance(candidate, dict):
            value = candidate.get("density")

        elif isinstance(candidate, (bytes, str)):
            try:
                parsed = json.loads(candidate)
                value = (
                    parsed.get("density")
                    if isinstance(parsed, dict) else parsed
                )
            except (json.JSONDecodeError, TypeError):
                value = candidate

        else:
            value = candidate

    if value is None:
        value = kwargs.get("density")

    if value is None:
        return {"error": "no 'density' value received in request body"}

    return sensorManager.set_user_density(value)


ui.expose_api("GET", "/api/sensors", get_sensor_data)
ui.expose_api("GET", "/api/button_capture", get_button_capture)
ui.expose_api("GET", "/api/ai/verdicts", get_ai_verdicts)
ui.expose_api("GET", "/api/ai/current", get_current_verdict)
ui.expose_api("GET", "/api/ai/capture_verdict", get_capture_verdict)
ui.expose_api("GET", "/api/user/density", get_user_density)
ui.expose_api("POST", "/api/user/density", set_user_density)
ui.expose_api("POST", "/api/button_capture/trigger", trigger_button_capture)

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
