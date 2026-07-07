from arduino.app_utils import *
import time
from hbManager import HbManager

logger = Logger("read-hb-state")
bridge = Bridge

hbInst = HbManager(bridge, logger)

hbInst.start()

def loop():
    # Main application work goes here
    time.sleep(1)

App.run(user_loop=loop)