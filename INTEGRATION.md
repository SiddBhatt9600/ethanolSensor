# Integrating the AI Layer into main.py

> **Status (12 Jul): DONE.** The files below live in `python/`,
> `main.py` exposes the three endpoints, the dashboard shows the
> verdict panel, and the sketch generates scenario-coherent values.
> Verify with `python3 python/test_ai.py` and `python3
> python/local_demo.py`. This document is kept as the reference
> for what was integrated.

These files sit in the `python/` folder next to `sensorManager.py`:

```
features.py
fuelQualityModel.py
aiManager.py
model_weights.json
```

Only dependency beyond the stock image: `numpy`
(`pip3 install numpy` on the UNO Q if not present).

## main.py changes

```python
from aiManager import AiManager

# ... after sensorManager is created and started:
aiManager = AiManager(sensorManager, logger)
aiManager.start()

# New REST APIs for the app / WebUI:
def get_ai_verdicts():
    """Latest 10 continuous AI verdicts."""
    return aiManager.get_latest_verdicts()

def get_current_verdict():
    """Most recent verdict (for the app's status card)."""
    return aiManager.get_current_verdict()

def get_capture_verdict():
    """Runs the model on the latest button capture average."""
    return aiManager.infer_capture(sensorManager.get_latest_capture())

ui.expose_api("GET", "/api/ai/verdicts", get_ai_verdicts)
ui.expose_api("GET", "/api/ai/current", get_current_verdict)
ui.expose_api("GET", "/api/ai/capture_verdict", get_capture_verdict)
```

That's it. The AI layer only reads from SensorManager's public APIs,
so nothing in Turjasu's or Siddhartha's code changes.

## What the endpoints return

`/api/ai/current`:
```json
{
  "timestamp": "...",
  "verdict": "ADULTERATED",
  "confidence": 0.98,
  "probs": {"GOOD": 0.01, "SUSPECT": 0.01, "ADULTERATED": 0.98},
  "explain": {
    "density15": 771.2,
    "expected_density15": 751.2,
    "rho_residual": 20.0,
    "signals": ["free water detected in fuel", "..."]
  },
  "anomalies": [
    {"parameter": "wif", "z_score": 5.4,
     "baseline_mean": 3.1, "value": 42.0}
  ]
}
```

The `explain.signals` strings are written for direct display in the
mobile app UI and for narrating the demo video.

## Note for the sketch (temporary, until real sensors arrive)

**Done.** The sketch now derives all five values from one scenario
(mirroring fuel_simulator.py's gen_good / gen_suspect /
gen_adulterated physics) and rotates GOOD → SUSPECT → ADULTERATED
every 90 s, so demos show every verdict and the refuel-drift
anomaly detector fires on each transition. When real sensors
arrive, replace the `refreshReading()` simulation with actual
sensor reads — the getter names and types stay the same.
