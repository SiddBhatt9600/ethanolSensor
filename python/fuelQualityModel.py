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

# There is no density sensor on the board — density is measured by
# the user (e.g. with a hydrometer) and entered via the phone app or
# web dashboard (SensorManager.set_user_density()). Standard petrol
# density at 15C sits in the 725-775 kg/m3 band (BIS IS 2796).
# predict() gates on this band directly, before the model runs at
# all: outside it, the reading is called ADULTERATED immediately (see
# _reject_density_out_of_range()); inside it, with nothing else
# wrong, an in-band value also wins over the finer ethanol-vs-density
# residual physics (see the tradeoff note in predict()).
STANDARD_DENSITY_BAND = (725.0, 775.0)

ALL_CLEAR_SIGNAL = "Everything looks normal."

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
        of which physical signals drove it. Density is gated first:
        outside 725-775 kg/m3, this returns ADULTERATED immediately
        without running the model (see _reject_density_out_of_range).
        """

        x = extract(reading)
        rho_residual = float(x[FEATURE_NAMES.index("rho_residual")])

        density_val = float(reading["density"])
        density_in_band = (
            STANDARD_DENSITY_BAND[0] <= density_val <= STANDARD_DENSITY_BAND[1]
        )

        if not density_in_band:
            return self._reject_density_out_of_range(
                reading, density_val, x, rho_residual
            )
        
        wif_val = float(reading["wif"])
        if wif_val > 10:
            return self._reject_wif_adulterated(
                reading, wif_val, x, rho_residual
            )

        if wif_val > 5:
            return self._reject_wif_suspect(
                reading, wif_val, x, rho_residual
            )

        probs = self._forward(x)
        idx = int(np.argmax(probs))
        verdict = self.labels[idx]

        signals = self._signals(reading, rho_residual)

        # The MLP can flag fuel from the joint sensor pattern before
        # any single-sensor threshold trips; say so instead of
        # showing a contradictory "within spec".
        if verdict != "GOOD" and signals == [ALL_CLEAR_SIGNAL]:
            signals = [
                "No single reading looks unusual on its own, but "
                f"the overall pattern still looks {verdict.lower()}."
            ]

        eth_val = float(reading["ethanol"])
        turbidity_val = float(reading["turbidity"])

        # Density is already known to be in-band here (the gate above
        # returned early otherwise) — this override only needs to
        # check the other three signals now.
        other_problem = (
            turbidity_val > 12
            or not classify_blend(eth_val)["in_spec"]
        )

        if verdict != "GOOD" and not other_problem:
            good_idx = next(
                i for i, name in self.labels.items() if name == "GOOD"
            )
            probs = np.zeros_like(probs)
            probs[good_idx] = 1.0
            idx = good_idx
            verdict = "GOOD"
            signals = [ALL_CLEAR_SIGNAL]

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

    def _reject_density_out_of_range(self, reading, density_val, x, rho_residual):
        """Short-circuit path for predict() — a density outside the
        standard band skips the model entirely and calls ADULTERATED
        directly. Still fills in the same response shape (density15,
        residual, blend) as the normal path so callers don't need to
        special-case this."""

        adulterated_idx = next(
            i for i, name in self.labels.items() if name == "ADULTERATED"
        )
        probs = np.zeros(len(self.labels))
        probs[adulterated_idx] = 1.0

        signal = (
            f"Density reading ({density_val:.1f} kg/m3) is outside "
            f"the normal range for petrol "
            f"({STANDARD_DENSITY_BAND[0]:.0f}-"
            f"{STANDARD_DENSITY_BAND[1]:.0f} kg/m3), so this is called "
            f"adulterated without running any further checks."
        )

        return {
            "verdict": "ADULTERATED",
            "confidence": 1.0,
            "probs": {
                self.labels[i]: round(float(p), 3)
                for i, p in enumerate(probs)
            },
            "blend": classify_blend(reading["ethanol"]),
            "explain": {
                "density15": round(float(x[3]), 2),
                "expected_density15":
                    round(expected_density15(float(reading["ethanol"])), 2),
                "rho_residual": round(rho_residual, 2),
                "signals": [signal],
            },
        }

    # -------------------------------------------------------------

    def _reject_wif_adulterated(self, reading, wif_val, x, rho_residual):
        """Short-circuit path for critically high WIF."""

        adulterated_idx = next(
            i for i, name in self.labels.items()
            if name == "ADULTERATED"
        )

        probs = np.zeros(len(self.labels))
        probs[adulterated_idx] = 1.0

        signal = (
            f"Water-in-fuel level ({wif_val:.1f}%) is above the "
            f"critical threshold of 10%, so this is called adulterated."
        )

        return {
            "verdict": "ADULTERATED",
            "confidence": 1.0,
            "probs": {
                self.labels[i]: round(float(p), 3)
                for i, p in enumerate(probs)
            },
            "blend": classify_blend(reading["ethanol"]),
            "explain": {
                "density15": round(float(x[3]), 2),
                "expected_density15":
                    round(expected_density15(
                        float(reading["ethanol"])
                    ), 2),
                "rho_residual": round(rho_residual, 2),
                "signals": [signal],
            },
        }


    def _reject_wif_suspect(self, reading, wif_val, x, rho_residual):
        """Short-circuit path for elevated WIF."""

        suspect_idx = next(
            i for i, name in self.labels.items()
            if name == "SUSPECT"
        )

        probs = np.zeros(len(self.labels))
        probs[suspect_idx] = 1.0

        signal = (
            f"Water-in-fuel level ({wif_val:.1f}%) is above the "
            f"suspicious threshold of 5%, so this is called suspicious."
        )

        return {
            "verdict": "SUSPECT",
            "confidence": 1.0,
            "probs": {
                self.labels[i]: round(float(p), 3)
                for i, p in enumerate(probs)
            },
            "blend": classify_blend(reading["ethanol"]),
            "explain": {
                "density15": round(float(x[3]), 2),
                "expected_density15":
                    round(expected_density15(
                        float(reading["ethanol"])
                    ), 2),
                "rho_residual": round(rho_residual, 2),
                "signals": [signal],
            },
        }
    
    @staticmethod
    def _signals(reading, rho_residual):
        """Plain-language reasons, for the app UI and demo video —
        written for the person looking at the dashboard, not for a
        developer reading the code.

        Only ever called on a reading whose density is already
        confirmed in-band (predict() short-circuits out-of-band
        density before reaching here — see
        _reject_density_out_of_range()), so there's no density-band
        check in here anymore; it could never fire.
        """

        s = []

        eth_val = float(reading["ethanol"])
        wif_val = float(reading["wif"])

        # WIF is independent of ethanol percentage.
        # >10% -> ADULTERATED
        # >5%  -> SUSPECT
        if wif_val > 10:
            s.append(
                f"Water-in-fuel level ({wif_val:.1f}%) is critically high."
            )
        elif wif_val > 5:
            s.append(
                f"Water-in-fuel level ({wif_val:.1f}%) is elevated."
            )

        if float(reading["turbidity"]) > 40:
            s.append(
                "The fuel looks very cloudy, with lots of solid particles."
            )
        elif float(reading["turbidity"]) > 12:
            s.append("The fuel looks slightly cloudy.")

        # Natural petrol density spans roughly +/-25 kg/m3 around
        # nominal, so only flag residuals clearly outside that band.
        if rho_residual > 28:
            s.append(
                "Fuel density is too high for this ethanol level. "
                "Could be kerosene, another solvent, or water mixed in."
            )
        elif rho_residual < -32:
            s.append(
                "Fuel density is too low for this ethanol level, "
                "which is unusual for a clean blend."
            )

        blend = classify_blend(eth_val)
        if not blend["in_spec"]:
            s.append(
                f"Ethanol level ({blend['measured']}%) doesn't "
                f"match any standard blend (closest is "
                f"{blend['nearest']}). Possible over/under-"
                f"blending at the pump."
            )

        if not s:
            s.append(ALL_CLEAR_SIGNAL)

        return s
    