"""
local_demo.py
=============

Full-stack demo of the Fuel Quality Monitor WITHOUT the UNO Q.

Runs the real SensorManager and AiManager against a MockBridge
that reproduces the MCU sketch's scenario simulation, and serves
the real web dashboard (assets/) plus every REST endpoint that
main.py exposes on the board. Dev-machine only — main.py is what
runs on the UNO Q.

Run:   python3 local_demo.py        (needs numpy only)
Open:  http://localhost:8000

Demo controls (also work from a second terminal / browser tab):
  http://localhost:8000/api/demo/press_button        simulate button
  http://localhost:8000/api/demo/scenario?set=good
  http://localhost:8000/api/demo/scenario?set=suspect
  http://localhost:8000/api/demo/scenario?set=adulterated
  http://localhost:8000/api/demo/scenario?set=auto   rotate (default)

Intervals are shortened (2 s instead of 10 s) so the dashboard
fills quickly. On the board the real cadence applies.
"""

import json
import os
import random
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import aiManager as aiManagerModule
import sensorManager as sensorManagerModule
from aiManager import AiManager
from sensorManager import SensorManager

# Faster cadence for the demo
sensorManagerModule.CONTINUOUS_INTERVAL = 2
aiManagerModule.AI_INTERVAL = 2

SCENARIO_ROTATE_S = 60
PORT = 8000

ASSETS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "assets"
)


# ------------------------------------------------------------------
# Mock Bridge — mirrors sketch/sketch.ino's scenario engine
# ------------------------------------------------------------------
class MockBridge:

    SCENARIOS = ("good", "suspect", "adulterated")

    def __init__(self):
        self.mode = "auto"                 # or a fixed scenario name
        self.scenario = "good"
        self._hb = 0
        self._last_rotate = time.time()
        self._last_reading = 0.0
        self._lock = threading.Lock()
        self._refresh()

    def set_mode(self, mode):
        with self._lock:
            self.mode = mode
            if mode in self.SCENARIOS:
                self.scenario = mode
            self._last_rotate = time.time()
            self._refresh()

    def _refresh(self):
        temp = random.uniform(24, 42)
        petrol15 = random.uniform(735, 762)
        kerosene = water = 0.0

        if self.scenario == "good":
            ethanol = random.choice(
                [random.uniform(9, 11), random.uniform(18, 22)])
            wif = random.uniform(0, 4)
            turbidity = random.uniform(0, 6)
        elif self.scenario == "suspect":
            ethanol = random.uniform(10, 22)
            water = random.uniform(0.004, 0.009)
            wif = random.uniform(9, 20)
            turbidity = random.uniform(5, 14)
        else:  # adulterated
            if random.random() < 0.5:
                ethanol = random.uniform(0, 12)
                kerosene = random.uniform(0.15, 0.32)
                wif = random.uniform(0, 6)
                turbidity = random.uniform(0, 10)
            else:
                ethanol = random.uniform(8, 22)
                water = random.uniform(0.02, 0.05)
                wif = random.uniform(35, 90)
                turbidity = random.uniform(25, 65)

        e = ethanol / 100.0
        rho15 = ((1.0 - e - kerosene - water) * petrol15
                 + e * 789.4 + kerosene * 805.0 + water * 998.0)

        self._reading = {
            "temp": int(round(temp)),
            "ethanol": int(round(ethanol)),
            "wif": int(round(wif)),
            "turbidity": int(round(turbidity)),
            "density": rho15 - 0.85 * (temp - 15.0),
        }

    def _tick(self):
        now = time.time()
        if (self.mode == "auto"
                and now - self._last_rotate >= SCENARIO_ROTATE_S):
            self._last_rotate = now
            idx = self.SCENARIOS.index(self.scenario)
            self.scenario = self.SCENARIOS[(idx + 1) % 3]
            print(f"[demo] scenario -> {self.scenario.upper()}")
        if now - self._last_reading >= 2.0:
            self._last_reading = now
            self._refresh()

    def call(self, name, *args):
        with self._lock:
            self._tick()
            if name == "getHbState":
                self._hb += 1
                return self._hb
            key = {
                "getFuelTemp": "temp",
                "getethanolPercentage": "ethanol",
                "getwif": "wif",
                "getturbidity": "turbidity",
                "getdensity": "density",
            }[name]
            value = self._reading[key]
            if key == "density":
                value += random.uniform(-0.5, 0.5)
            return value


class ConsoleLogger:
    def info(self, msg):
        print(f"[info] {msg}")

    def exception(self, e):
        import traceback
        print(f"[error] {e}")
        traceback.print_exc()


# ------------------------------------------------------------------
# Managers (the real ones)
# ------------------------------------------------------------------
bridge = MockBridge()
logger = ConsoleLogger()

sensor_manager = SensorManager(bridge, logger)
sensor_manager.start()

ai_manager = AiManager(sensor_manager, logger)
ai_manager.start()


# ------------------------------------------------------------------
# HTTP server: real dashboard + the same REST APIs as main.py
# ------------------------------------------------------------------
MIME = {".html": "text/html", ".css": "text/css",
        ".js": "application/javascript", ".json": "application/json"}


class DemoHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass                                   # keep console readable

    def _json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/sensors":
            return self._json(sensor_manager.get_latest_history())

        if path == "/api/button_capture":
            return self._json(sensor_manager.get_latest_capture())

        if path == "/api/ai/verdicts":
            return self._json(ai_manager.get_latest_verdicts())

        if path == "/api/ai/current":
            return self._json(ai_manager.get_current_verdict())

        if path == "/api/ai/capture_verdict":
            return self._json(ai_manager.infer_capture(
                sensor_manager.get_latest_capture()))

        if path == "/api/demo/press_button":
            started = sensor_manager.trigger_capture()
            return self._json({"capture_started": started})

        if path == "/api/demo/scenario":
            mode = parse_qs(parsed.query).get("set", ["auto"])[0]
            if mode not in ("auto",) + MockBridge.SCENARIOS:
                return self._json({"error": "unknown scenario"}, 400)
            bridge.set_mode(mode)
            return self._json({"scenario": mode})

        # static assets
        if path == "/":
            path = "/index.html"
        filename = os.path.normpath(
            os.path.join(ASSETS_DIR, path.lstrip("/")))
        if (filename.startswith(os.path.abspath(ASSETS_DIR) + os.sep)
                or os.path.dirname(filename) == os.path.abspath(ASSETS_DIR)) \
                and os.path.isfile(filename):
            ext = os.path.splitext(filename)[1]
            with open(filename, "rb") as fp:
                body = fp.read()
            self.send_response(200)
            self.send_header(
                "Content-Type", MIME.get(ext, "application/octet-stream"))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self._json({"error": "not found"}, 404)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), DemoHandler)
    print("=" * 60)
    print(f"Fuel Quality Monitor demo:  http://localhost:{PORT}")
    print("Scenario rotates GOOD -> SUSPECT -> ADULTERATED every "
          f"{SCENARIO_ROTATE_S}s (auto mode).")
    print("Force one:  /api/demo/scenario?set=adulterated")
    print("Button:     /api/demo/press_button")
    print("Ctrl+C to stop.")
    print("=" * 60)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        ai_manager.stop()
        sensor_manager.stop()
