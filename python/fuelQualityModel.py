"""
fuelQualityModel.py
===================

On-device fuel quality inference for the QRB2210 (Debian Linux).
Depends only on numpy + model_weights.json. No sklearn, no TFLite,
nothing heavy to install on the UNO Q.

Usage:
    model = FuelQualityModel("model_weights.json")
    result = model.predict(reading_dict)
    # -> {"verdict": "GOOD", "confidence": 0.97,
    #     "probs": {...}, "explain": {...}}
"""

import json
import numpy as np

from features import extract, expected_density15, FEATURE_NAMES

# The MCU's getdensity() is currently hardcoded to 750 (no density
# sensor wired yet). Flag readings that land suspiciously close to
# that fixed value so the dashboard doesn't imply precision the
# hardware isn't providing. Remove once a real density sensor is
# integrated.
_HARDCODED_DENSITY_PLACEHOLDER = 750.0
_HARDCODED_DENSITY_TOLERANCE = 0.05

# Standard Indian pump blends: nominal ethanol % and accepted band.
# E20 is the current national rollout blend; verifying the pump
# actually dispenses in-band E20 is a headline feature.
STANDARD_BLENDS = [
    ("E0",  0.0,  0.0,  2.0),
    ("E5",  5.0,  4.0,  7.0),
    ("E10", 10.0, 8.0,  12.0),
    ("E20", 20.0, 18.0, 22.0),
    ("E85", 85.0, 80.0, 87.0),
]


def classify_blend(ethanol_pct):
    """Maps measured ethanol % to the nearest standard blend and
    says whether it is inside that blend's accepted band."""
    e = float(ethanol_pct)
    for name, nominal, lo, hi in STANDARD_BLENDS:
        if lo <= e <= hi:
            return {
                "nearest": name,
                "measured": round(e, 1),
                "in_spec": True,
            }
    name = min(STANDARD_BLENDS, key=lambda b: abs(e - b[1]))[0]
    return {
        "nearest": name,
        "measured": round(e, 1),
        "in_spec": False,
    }


class FuelQualityModel:

    def __init__(self, weights_path="model_weights.json"):

        with open(weights_path, "r") as fp:
            m = json.load(fp)

        self.labels = {int(k): v for k, v in m["labels"].items()}
        self.mean = np.array(m["scaler_mean"])
        self.scale = np.array(m["scaler_scale"])
        self.layers = [
            (np.array(l["W"]), np.array(l["b"])) for l in m["layers"]
        ]
        self.train_accuracy = m.get("test_accuracy")

    # -------------------------------------------------------------

    def _forward(self, x):

        h = (x - self.mean) / self.scale

        for i, (W, b) in enumerate(self.layers):
            h = h @ W + b
            if i < len(self.layers) - 1:
                h = np.maximum(h, 0.0)          # relu

        # softmax
        h = h - h.max()
        e = np.exp(h)
        return e / e.sum()

    # -------------------------------------------------------------

    def predict(self, reading):
        """
        reading: dict with temp, ethanol, wif, turbidity, density
        Returns verdict + confidence + a human-readable explanation
        of which physical signals drove it.
        """

        x = extract(reading)
        probs = self._forward(x)
        idx = int(np.argmax(probs))
        verdict = self.labels[idx]

        rho_residual = float(x[FEATURE_NAMES.index("rho_residual")])

        signals = self._signals(reading, rho_residual)

        # The MLP can flag fuel from the joint sensor pattern before
        # any single-sensor threshold trips; say so instead of
        # showing a contradictory "within spec".
        if verdict != "GOOD" and signals == ["all parameters within spec"]:
            signals = [
                "no single sensor out of range, but the combined "
                f"pattern matches the {verdict} profile "
                f"(density residual {rho_residual:+.1f} kg/m3)"
            ]

        explain = {
            "density15": round(float(x[3]), 2),
            "expected_density15":
                round(expected_density15(float(reading["ethanol"])), 2),
            "rho_residual": round(rho_residual, 2),
            "signals": signals,
        }

        return {
            "verdict": verdict,
            "confidence": round(float(probs[idx]), 3),
            "probs": {
                self.labels[i]: round(float(p), 3)
                for i, p in enumerate(probs)
            },
            "blend": classify_blend(reading["ethanol"]),
            "explain": explain,
        }

    # -------------------------------------------------------------

    @staticmethod
    def _signals(reading, rho_residual):
        """Plain-language reasons, for the app UI and demo video."""

        s = []

        if abs(float(reading["density"]) - _HARDCODED_DENSITY_PLACEHOLDER) \
                < _HARDCODED_DENSITY_TOLERANCE:
            s.append("density sensor not connected — reading a fixed "
                     "reference value, kerosene/solvent detection is "
                     "degraded until it is wired up")

        eth_val = float(reading["ethanol"])
        wif_val = float(reading["wif"])

        if wif_val > 25:
            s.append("free water detected in fuel")
        elif wif_val > 8:
            # E10/E20 blends are hygroscopic: dissolved water climbs
            # toward saturation, then phase-separates. Call out the
            # blend-specific risk instead of a generic warning.
            if 8 <= eth_val <= 25:
                s.append("ethanol blend absorbing water — "
                         "phase separation risk (E10/E20 blends "
                         "are hygroscopic)")
            else:
                s.append("elevated water content")

        if float(reading["turbidity"]) > 40:
            s.append("heavy suspended particulates")
        elif float(reading["turbidity"]) > 12:
            s.append("mild haze / particulates")

        # Natural petrol density spans roughly +/-25 kg/m3 around
        # nominal, so only flag residuals clearly outside that band.
        if rho_residual > 28:
            s.append("density too high for ethanol blend "
                     "(possible kerosene/solvent or water)")
        elif rho_residual < -32:
            s.append("density too low for ethanol blend")

        blend = classify_blend(eth_val)
        if not blend["in_spec"]:
            s.append(f"measured ethanol {blend['measured']}% is "
                     f"outside every standard blend band "
                     f"(nearest {blend['nearest']}) — possible "
                     f"over/under-blending at the pump")

        if not s:
            s.append("all parameters within spec")

        return s
