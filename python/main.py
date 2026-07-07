from arduino.app_utils import *
import time
from hbManager import HbManager
from sensorManager import SensorManager

logger = Logger("read-hb-state")
bridge = Bridge

hbInst = HbManager(bridge, logger)
hbInst.start()

mainInst = SensorManager(bridge, logger)
mainInst.start()

App.run()