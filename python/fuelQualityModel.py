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
            "explain": explain,
        }

    # -------------------------------------------------------------

    @staticmethod
    def _signals(reading, rho_residual):
        """Plain-language reasons, for the app UI and demo video."""

        s = []

        if float(reading["wif"]) > 25:
            s.append("free water detected in fuel")
        elif float(reading["wif"]) > 8:
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

        eth = float(reading["ethanol"])
        if 25 < eth < 60:
            s.append("ethanol % outside standard blend bands")

        if not s:
            s.append("all parameters within spec")

        return s
