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
from aiManager import AiManager
from features import extract, expected_density15
from fuelQualityModel import FuelQualityModel
from fuel_simulator import generate_dataset, LABELS

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

for reading in (good_e10, free_water, kero):
    r = model.predict(reading)
    check(f"probs sum to 1 ({r['verdict']})",
          abs(sum(r["probs"].values()) - 1.0) < 0.01)
    check(f"explain fields complete ({r['verdict']})",
          all(k in r["explain"] for k in
              ("density15", "expected_density15",
               "rho_residual", "signals")))

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
          ("timestamp", "verdict", "confidence", "probs",
           "explain", "anomalies")),
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
print(f"\n{'=' * 50}")
print(f"RESULT: {PASS} passed, {FAIL} failed")
print("=" * 50)
sys.exit(1 if FAIL else 0)
