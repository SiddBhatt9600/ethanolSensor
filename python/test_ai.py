"""
test_ai.py
==========

Self-contained test suite for the AI layer. Needs only numpy —
no pytest, no sklearn — so it runs both on the dev machine and
on the UNO Q itself as a deployment smoke test.

Run:  python3 test_ai.py

Checks:
  1. model_weights.json loads and matches the 6-16-16-3 topology
  2. feature engineering produces the documented physics values
  3. accuracy on freshly generated (unseen-seed) simulator data
  4. hand-built obvious scenarios get the right verdict + signals
  5. inference latency budget
  6. AiManager end-to-end: worker thread, verdict cache, JSON log,
     refuel-drift anomaly, capture verdict, REST payload shapes
"""

import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import aiManager as aiManagerModule
import fuel_simulator
import mileageEstimator
from aiManager import AiManager
from features import extract, expected_density15
from fuelQualityModel import FuelQualityModel, classify_blend
from fuel_simulator import generate_dataset, LABELS
from sensorManager import SensorManager

PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


# ------------------------------------------------------------------
# 1. Model file loads
# ------------------------------------------------------------------
print("\n[1] Model file")

model = FuelQualityModel(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "model_weights.json")
)

shapes = [(W.shape, b.shape) for W, b in model.layers]
check("topology is 6-16-16-3",
      shapes == [((6, 16), (16,)), ((16, 16), (16,)), ((16, 3), (3,))],
      str(shapes))
check("labels are GOOD/SUSPECT/ADULTERATED",
      set(model.labels.values()) == {"GOOD", "SUSPECT", "ADULTERATED"})
check("recorded test accuracy > 0.90",
      model.train_accuracy and model.train_accuracy > 0.90,
      str(model.train_accuracy))

# ------------------------------------------------------------------
# 2. Feature engineering physics
# ------------------------------------------------------------------
print("\n[2] Feature engineering")

# E10 at 25 C: density15 must be density + 0.85*(25-15)
r = {"temp": 25.0, "ethanol": 10.0, "wif": 2.0,
     "turbidity": 3.0, "density": 742.0}
f = extract(r)
check("density15 temperature correction",
      abs(f[3] - (742.0 + 0.85 * 10.0)) < 1e-9, str(f[3]))
check("expected_density15(E10) ≈ 751.24",
      abs(expected_density15(10.0) - 751.24) < 0.01,
      str(expected_density15(10.0)))
check("rho_residual = density15 - expected",
      abs(f[4] - (f[3] - expected_density15(10.0))) < 1e-9)

# ------------------------------------------------------------------
# 3. Accuracy on fresh simulator data (different RNG seed)
# ------------------------------------------------------------------
print("\n[3] Accuracy on unseen-seed data")

fuel_simulator.RNG = np.random.default_rng(20260712)   # not train seed
rows, y = generate_dataset(n_per_class=1500)

correct = 0
inv = {v: k for k, v in LABELS.items()}
per_class = {0: [0, 0], 1: [0, 0], 2: [0, 0]}
for reading, label in zip(rows, y):
    pred = inv[model.predict(reading)["verdict"]]
    per_class[label][1] += 1
    if pred == label:
        correct += 1
        per_class[label][0] += 1

acc = correct / len(rows)
print(f"  accuracy on 4500 fresh samples: {acc:.4f}")
for cls in range(3):
    hit, tot = per_class[cls]
    print(f"    {LABELS[cls]:<12} {hit}/{tot}  ({hit / tot:.3f})")
check("fresh-data accuracy > 0.90", acc > 0.90, f"{acc:.4f}")

# ------------------------------------------------------------------
# 4. Obvious hand-built scenarios
# ------------------------------------------------------------------
print("\n[4] Hand-built scenarios")

good_e10 = {"temp": 30, "ethanol": 10, "wif": 1,
            "turbidity": 2, "density": 738.5}
res = model.predict(good_e10)
check("clean E10 -> GOOD", res["verdict"] == "GOOD", res["verdict"])
check("clean E10 signal says in-spec",
      "all parameters within spec" in res["explain"]["signals"])

free_water = {"temp": 30, "ethanol": 12, "wif": 60,
              "turbidity": 45, "density": 748.0}
res = model.predict(free_water)
check("free water -> ADULTERATED",
      res["verdict"] == "ADULTERATED", res["verdict"])
check("free water signal present",
      any("water" in s for s in res["explain"]["signals"]),
      str(res["explain"]["signals"]))

# 30% kerosene into E0 on a 765 base: rho15 = 0.70*765 + 0.30*805
# = 777.0 -> residual +30, clearly outside natural petrol variation
kero = {"temp": 30, "ethanol": 0, "wif": 2,
        "turbidity": 4, "density": 777.0 - 0.85 * 15}
res = model.predict(kero)
check("30% kerosene cut -> ADULTERATED",
      res["verdict"] == "ADULTERATED", res["verdict"])
check("kerosene flagged via density residual",
      any("density too high" in s for s in res["explain"]["signals"]),
      str(res["explain"]["signals"]))

# Documented limitation (AI_PLAN.md): moderate kerosene into a
# light petrol base stays inside the clean density envelope and is
# NOT detectable from a snapshot — drift detection is the mitigation.
kero_hidden = {"temp": 30, "ethanol": 0, "wif": 2, "turbidity": 4,
               "density": (0.75 * 725 + 0.25 * 805) - 0.85 * 15}
res = model.predict(kero_hidden)
check("hidden kerosene case behaves as documented (not flagged)",
      res["verdict"] == "GOOD", res["verdict"])

watery = {"temp": 30, "ethanol": 15, "wif": 15,
          "turbidity": 8, "density": 744.0}
res = model.predict(watery)
check("near-saturation water -> SUSPECT",
      res["verdict"] == "SUSPECT", res["verdict"])
check("hygroscopic-blend water risk signal present",
      any("phase separation risk" in s
          for s in res["explain"]["signals"]),
      str(res["explain"]["signals"]))

# Density sensor not wired yet on the real board -> getdensity()
# returns a hardcoded 750. Must be flagged, not silently trusted.
no_density_sensor = {"temp": 30, "ethanol": 10, "wif": 2,
                      "turbidity": 3, "density": 750.0}
res = model.predict(no_density_sensor)
check("hardcoded density placeholder is flagged",
      any("density sensor not connected" in s
          for s in res["explain"]["signals"]),
      str(res["explain"]["signals"]))

# ------------------------------------------------------------------
# 4b. E20 blend verification (topical: India's E20 rollout)
# ------------------------------------------------------------------
print("\n[4b] Blend verification")

check("E20 in band",
      classify_blend(20.4) == {"nearest": "E20", "measured": 20.4,
                               "in_spec": True},
      str(classify_blend(20.4)))
check("E33 sold as E20 -> OFF-SPEC",
      classify_blend(33.0)["in_spec"] is False
      and classify_blend(33.0)["nearest"] == "E20",
      str(classify_blend(33.0)))

overblend = {"temp": 30, "ethanol": 33, "wif": 3,
             "turbidity": 4, "density": 748.0}
res = model.predict(overblend)
check("over-blend surfaced in predict() payload",
      res["blend"]["in_spec"] is False, str(res["blend"]))
check("over-blend flagged in signals",
      any("over/under-blending" in s
          for s in res["explain"]["signals"]),
      str(res["explain"]["signals"]))

# ------------------------------------------------------------------
# 4c. Turbidity ADC scaling (real board returns raw 0-4095 counts)
# ------------------------------------------------------------------
print("\n[4c] Turbidity ADC scaling")

class _NullLogger:
    def info(self, *a, **k):
        pass

    def exception(self, *a, **k):
        pass


sm = SensorManager(None, _NullLogger())
check("raw 0 -> 0%", sm.scale_turbidity(0) == 0.0)
check("raw 4095 -> 100%", sm.scale_turbidity(4095) == 100.0)
check("raw 410 (as seen in real sensor_history.json) -> ~10%",
      abs(sm.scale_turbidity(410) - 10.01) < 0.1,
      str(sm.scale_turbidity(410)))
check("out-of-range raw clamps to 100%", sm.scale_turbidity(9000) == 100.0)
check("None passes through", sm.scale_turbidity(None) is None)

for reading in (good_e10, free_water, kero):
    r = model.predict(reading)
    check(f"probs sum to 1 ({r['verdict']})",
          abs(sum(r["probs"].values()) - 1.0) < 0.01)
    check(f"explain fields complete ({r['verdict']})",
          all(k in r["explain"] for k in
              ("density15", "expected_density15",
               "rho_residual", "signals")))

# ------------------------------------------------------------------
# 4d. Mileage estimator (formula-based, not trained — see module
#     docstring for why there is no ground-truth data to train on)
# ------------------------------------------------------------------
print("\n[4d] Mileage estimator")

e0 = mileageEstimator.estimate({"ethanol": 0}, "GOOD")
e20 = mileageEstimator.estimate({"ethanol": 20}, "GOOD")
check("E0 has zero ethanol penalty",
      e0["breakdown"]["ethanol_blend_pct"] == 0.0, str(e0))
check("E20 loses ~6.5% to ethanol blend",
      abs(e20["breakdown"]["ethanol_blend_pct"] - 6.5) < 0.01,
      str(e20))
check("estimated_kmpl < baseline_kmpl when penalty > 0",
      e20["estimated_kmpl"] < e20["baseline_kmpl"], str(e20))

good_est = mileageEstimator.estimate({"ethanol": 10}, "GOOD")
adult_est = mileageEstimator.estimate({"ethanol": 10}, "ADULTERATED")
check("ADULTERATED estimate worse than GOOD at same blend",
      adult_est["estimated_kmpl"] < good_est["estimated_kmpl"],
      f"good={good_est['estimated_kmpl']} "
      f"adult={adult_est['estimated_kmpl']}")

no_imu = mileageEstimator.estimate({"ethanol": 10}, "GOOD", imu_stats=None)
check("no IMU -> driving penalty is 0 and it says so",
      no_imu["breakdown"]["driving_behavior_pct"] == 0.0
      and any("IMU" in n for n in no_imu["notes"]),
      str(no_imu))

error_imu_stats = {
    "sampleCount": 5,
    "accelerometer": {"x": {"min": -1, "max": -1},
                       "y": {"min": -1, "max": -1},
                       "z": {"min": -1, "max": -1}},
}
error_est = mileageEstimator.estimate(
    {"ethanol": 10}, "GOOD", imu_stats=error_imu_stats)
check("all -1 IMU stats (BMI323 read failure) treated as unavailable",
      any("no valid data" in n for n in error_est["notes"]),
      str(error_est["notes"]))

check("mileage payload never omits the disclaimer",
      "disclaimer" in e20 and len(e20["disclaimer"]) > 0)

# ------------------------------------------------------------------
# 5. Latency
# ------------------------------------------------------------------
print("\n[5] Latency")

t0 = time.perf_counter()
N = 2000
for _ in range(N):
    model.predict(good_e10)
per_call_ms = (time.perf_counter() - t0) / N * 1000
print(f"  {per_call_ms:.3f} ms per inference (this machine)")
check("inference < 5 ms", per_call_ms < 5.0, f"{per_call_ms:.3f} ms")

# ------------------------------------------------------------------
# 6. AiManager end-to-end (fake sensor manager + logger)
# ------------------------------------------------------------------
print("\n[6] AiManager end-to-end")


class FakeLogger:
    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def exception(self, e):
        print(f"  LOGGED EXCEPTION: {e}")


class FakeSensorManager:
    """Serves scripted readings like SensorManager would."""

    def __init__(self):
        self.reading = dict(good_e10, timestamp="t")
        self.capture = {"timestamp": "t",
                        "samples": [dict(good_e10)] * 5,
                        "average": dict(good_e10)}

    def get_latest_history(self, count=10):
        return [self.reading]

    def get_latest_capture(self):
        return self.capture


fake_sm = FakeSensorManager()
mgr = AiManager(fake_sm, FakeLogger())

# 6a. synchronous inference + drift detection:
# 15 stable GOOD readings, then a free-water spike
for i in range(15):
    r = dict(good_e10, timestamp=f"t{i}")
    r["wif"] = 1 + 0.1 * (i % 3)          # tiny variation
    r["density"] = 738.5 + 0.2 * (i % 3)
    verdict = mgr.infer(r)
check("stable window -> no anomalies", verdict["anomalies"] == [])
check("stable window -> GOOD", verdict["verdict"] == "GOOD")

spike = dict(free_water, timestamp="t99")
verdict = mgr.infer(spike)
anom_params = [a["parameter"] for a in verdict["anomalies"]]
check("water spike -> drift anomaly on wif",
      "wif" in anom_params, str(anom_params))
check("water spike -> ADULTERATED",
      verdict["verdict"] == "ADULTERATED", verdict["verdict"])

# 6b. capture verdict
cap = mgr.infer_capture(fake_sm.get_latest_capture())
check("capture verdict is GOOD", cap.get("verdict") == "GOOD", str(cap))
check("capture verdict tagged as button_capture",
      cap.get("source") == "button_capture")
check("empty capture returns error",
      "error" in mgr.infer_capture({"samples": [], "average": {}}))

# 6c. worker thread + REST payloads + JSON log
aiManagerModule.AI_INTERVAL = 0.05
mgr2 = AiManager(fake_sm, FakeLogger())
mgr2.start()
time.sleep(1.0)
mgr2.stop()

verdicts = mgr2.get_latest_verdicts()
check("worker produced multiple verdicts", len(verdicts) >= 3,
      str(len(verdicts)))
current = mgr2.get_current_verdict()
check("current verdict has full payload",
      all(k in current for k in
          ("timestamp", "verdict", "confidence", "probs", "blend",
           "explain", "anomalies", "mileage")),
      str(list(current.keys())))
check("ai_history.json written",
      os.path.exists("ai_history.json"))
with open("ai_history.json") as fp:
    hist = json.load(fp)
check("ai_history.json holds the verdicts", len(hist) == len(verdicts) or
      len(hist) >= 3, str(len(hist)))
check("REST payload JSON-serializable",
      json.dumps(current) is not None)

# ------------------------------------------------------------------
# 7. Robustness against implausible readings ("probe in air",
#    disconnected sensor, NaN/Inf, stale pre-fix history)
# ------------------------------------------------------------------
print("\n[7] Robustness against implausible readings")

import sensorManager as sensorManagerModule
from sensorManager import SensorManager


class ScriptedBridge:
    """Returns whatever canned value is queued for each RPC name."""

    def __init__(self, values):
        self.values = values

    def call(self, name, *args):
        return self.values[name]


# 7a. NaN density (e.g. a disconnected density sensor) is rejected,
# not passed through to crash feature extraction later.
bad_bridge = ScriptedBridge({
    "readDS18B20TempC": 30.0,
    "getethanolPercentage": 10.0,
    "getwif": 2.0,
    "readTurbidityRaw": 100,
    "getdensity": float("nan"),
})
sm = SensorManager(bad_bridge, FakeLogger())
check("NaN density reading is rejected, not crashed",
      sm.readSensors() is None)

# 7b. A railed-high ethanol reading (stuck ADC / probe not in fuel)
# is outside 0-100% and gets rejected.
railed_bridge = ScriptedBridge({
    "readDS18B20TempC": 25.0,
    "getethanolPercentage": 4095.0,
    "getwif": 2.0,
    "readTurbidityRaw": 100,
    "getdensity": 750.0,
})
sm2 = SensorManager(railed_bridge, FakeLogger())
check("out-of-range (railed) ethanol reading is rejected",
      sm2.readSensors() is None)

# 7c. A normal reading still passes through untouched.
good_bridge = ScriptedBridge({
    "readDS18B20TempC": 30.0,
    "getethanolPercentage": 10.0,
    "getwif": 2.0,
    "readTurbidityRaw": 100,
    "getdensity": 750.0,
})
sm3 = SensorManager(good_bridge, FakeLogger())
check("a normal reading is still accepted",
      sm3.readSensors() is not None)

# 7d. AiManager.infer() fails loudly and clearly (ValueError) on a
# reading with a missing field, instead of a cryptic numpy crash.
mgr3 = AiManager(fake_sm, FakeLogger())
try:
    mgr3.infer({"temp": 30, "ethanol": 10, "wif": 2,
                "turbidity": 3, "density": None})
    check("infer() rejects a None field with ValueError", False,
          "no exception raised")
except ValueError:
    check("infer() rejects a None field with ValueError", True)
except Exception as e:
    check("infer() rejects a None field with ValueError", False,
          f"wrong exception type: {type(e).__name__}: {e}")

# 7e. infer_capture() returns a clean error (not a crash) when a
# capture's average has a present-but-None field — e.g. every
# sample in that capture window was rejected as implausible.
broken_capture = {
    "timestamp": "t",
    "samples": [],
    "average": {"temp": 30, "ethanol": 10, "wif": 2,
                "turbidity": 3, "density": None},
}
result = mgr3.infer_capture(broken_capture)
check("infer_capture() with a None field returns a clean error",
      "error" in result, str(result))

# 7f. check_anomaly() tolerates a corrupted historical window entry
# (e.g. loaded from an old sensor_history.json predating the
# plausibility gate) instead of crashing the whole verdict cycle.
mgr4 = AiManager(fake_sm, FakeLogger())
for i in range(9):
    mgr4.window.append(dict(good_e10, wif=1 + 0.1 * i))
mgr4.window.append({"temp": 30, "ethanol": 10, "wif": None,
                     "turbidity": 3, "density": 738.5})
try:
    mgr4.check_anomaly(dict(good_e10, wif=1.5))
    check("check_anomaly tolerates a corrupted window entry", True)
except Exception as e:
    check("check_anomaly tolerates a corrupted window entry", False,
          f"{type(e).__name__}: {e}")

# ------------------------------------------------------------------
print(f"\n{'=' * 50}")
print(f"RESULT: {PASS} passed, {FAIL} failed")
print("=" * 50)
sys.exit(1 if FAIL else 0)
