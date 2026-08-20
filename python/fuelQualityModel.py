"""
fuelQualityModel.py
===================

On-device fuel quality judgement for the QRB2210 (Debian Linux).
Depends only on numpy + model_weights.json. No sklearn, no TFLite,
nothing heavy to install on the UNO Q.

How the verdict is decided
--------------------------
By the physical thresholds in _threshold_verdict(), not by the MLP.
The thresholds are a pure function of the sensor readings, which makes
them monotonic (more contamination can only ever move the verdict
toward ADULTERATED) and auditable (every verdict traces to one named
constant, and each constant is the same one the matching _signals()
message is written against).

The trained MLP still runs on every reading and its output is reported
as `model_probs` for comparison, but it does not move the verdict. It
was measured to be non-monotonic and unreliable outside its training
distribution — it called an E85 sample carrying 20% water GOOD, and
ranked 15% water as less severe than 9% at the same ethanol level.
Letting it override the thresholds in either direction reproduced
exactly those faults, so it does not get a vote. See test_ai.py
section [3b], which fails if that regresses.

Usage:
    model = FuelQualityModel("model_weights.json")
    result = model.predict(reading_dict)
    # -> {"verdict": "GOOD", "confidence": 1.0, "probs": {...},
    #     "model_probs": {...}, "blend": {...}, "explain": {...}}

`confidence` is 1.0 whenever the thresholds decide, which is always —
the decision is a rule, not an estimate. `model_probs` carries the
MLP's actual (uncertain) distribution.
"""

import json
import math

import numpy as np

from features import extract, expected_density15, FEATURE_NAMES

STANDARD_DENSITY_BAND = (725.0, 775.0)

# Physical decision thresholds. These — not the MLP — decide the
# verdict; see _threshold_verdict(). Each one is the same number the
# matching _signals() message is written against, so the badge the
# user sees can never contradict the explanation printed under it.
#
# Water-in-fuel (%). Above FREE_WATER, water is present as a separate
# undissolved phase, which no petrol-ethanol blend can carry in
# solution. Above WATER_BUILDUP it is climbing toward saturation.
FREE_WATER_WIF_THRESHOLD = 25.0
WATER_BUILDUP_WIF_THRESHOLD = 8.0

# Turbidity (model feature scale, 0 = clear, 100 = opaque). Note this
# is the remapped feature, NOT the board's raw index — see
# SensorManager.calibrate_turbidity(), whose raw scale is inverted.
HEAVY_TURBIDITY_THRESHOLD = 40.0
MILD_TURBIDITY_THRESHOLD = 12.0

# Ethanol % range over which a blend is hygroscopic enough for the
# phase-separation warning to be the more useful wording. Affects the
# explanation text only, never the verdict.
HYGROSCOPIC_BLEND_RANGE = (8.0, 25.0)

# Density residual (measured density15 minus what the blend's ethanol %
# predicts, kg/m3). Natural petrol spans roughly +/-25 around nominal,
# so only residuals clearly outside that are worth mentioning.
# Informational only — see the note in _signals().
RHO_RESIDUAL_HIGH = 28.0
RHO_RESIDUAL_LOW = -32.0

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


def _nearest_blend(ethanol_pct):
    """(name, gap) for the standard blend closest to this reading.

    gap is how many ethanol percentage points the reading sits outside
    that blend's accepted band, or 0.0 when it is inside one.
    """
    e = float(ethanol_pct)
    for name, _, lo, hi in STANDARD_BLENDS:
        if lo <= e <= hi:
            return name, 0.0
    name, _, lo, hi = min(STANDARD_BLENDS, key=lambda b: abs(e - b[1]))
    return name, (lo - e if e < lo else e - hi)


def classify_blend(ethanol_pct):
    """Maps measured ethanol % to the nearest standard blend and
    says whether it is inside that blend's accepted band."""
    name, gap = _nearest_blend(ethanol_pct)
    return {
        "nearest": name,
        "measured": round(float(ethanol_pct), 1),
        "in_spec": gap == 0.0,
    }


# How far (in ethanol percentage points) a reading must sit outside its
# nearest standard blend's band before it counts as a real off-blend
# problem rather than sensor noise. Simulated/real ethanol sensor noise
# (~1.2% std dev) can push a genuinely clean E10/E20/E85 sample a couple
# of points past its band edge; a wide margin here avoids downgrading
# those to SUSPECT while still catching pure/near-pure ethanol (13+
# points past E85's 87% edge) and genuine over/under-blending.
BLEND_MARGIN_PCT = 3.0


def blend_gap(ethanol_pct):
    """Percentage points the reading sits outside its nearest standard
    blend's accepted band. 0 if inside the band."""
    return _nearest_blend(ethanol_pct)[1]


REQUIRED_READING_FIELDS = ("temp", "ethanol", "wif", "turbidity", "density")


def _require_finite(reading):
    """Reject a reading carrying NaN/Inf before any comparison runs.

    This is a safety gate, not a formality. Every IEEE-754 comparison
    against NaN is False, so a NaN wif/turbidity/ethanol would fall
    through every threshold in _threshold_verdict() and come out the
    far end as GOOD — a glitching sensor silently reporting clean
    fuel. Failing loudly is the only acceptable behaviour here: a
    reading that cannot be measured is not a reading that passed.

    SensorManager.sanitize() already maps NaN to None upstream, but
    an isinstance(x, float) check does not exclude NaN, and json.load()
    reconstructs NaN from a history file written by an older build, so
    this backstop earns its place.
    """
    for field in REQUIRED_READING_FIELDS:
        value = reading.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(
                f"Cannot judge reading: {field}={value!r} is not a number"
            )
        if not math.isfinite(float(value)):
            raise ValueError(
                f"Cannot judge reading: {field}={value!r} is not finite"
            )


def _threshold_verdict(reading):
    """The verdict implied by the physical thresholds alone.

    This is the authoritative decision path (see predict()). It is a
    pure function of the raw sensor values, which makes it monotonic
    by construction: adding water, haze, or blend error can only ever
    move the verdict toward ADULTERATED, never back toward GOOD. The
    MLP is not monotonic and cannot be relied on for that on its own —
    it was observed calling an E85 sample with 20% water GOOD, and
    calling 15% water less severe than 9% at the same ethanol level.
    """
    wif = float(reading["wif"])
    turbidity = float(reading["turbidity"])
    ethanol = float(reading["ethanol"])

    if wif > FREE_WATER_WIF_THRESHOLD:
        return "ADULTERATED"
    if turbidity > HEAVY_TURBIDITY_THRESHOLD:
        return "ADULTERATED"

    if wif > WATER_BUILDUP_WIF_THRESHOLD:
        return "SUSPECT"
    if turbidity > MILD_TURBIDITY_THRESHOLD:
        return "SUSPECT"
    if blend_gap(ethanol) > BLEND_MARGIN_PCT:
        return "SUSPECT"

    return "GOOD"


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

        _require_finite(reading)

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

        probs = self._forward(x)

        # The physical thresholds alone decide the verdict. The MLP's
        # opinion is reported in model_probs for transparency but does
        # not move the badge.
        #
        # Rationale: the thresholds are monotonic and auditable, and each
        # one matches a _signals() message, so the badge can never
        # contradict the explanation printed under it. The MLP is neither
        # monotonic nor reliable at the edges of its training
        # distribution — it was observed calling an E85 sample carrying
        # 20% water GOOD, and ranking 15% water as less severe than 9% at
        # the same ethanol level. Letting it override in either direction
        # reintroduced exactly that non-monotonicity, so it does not get a
        # vote. It is also trained purely on simulator output, so its
        # judgement carries no information about real fuel that these
        # thresholds do not already encode.
        model_probs = {
            self.labels[i]: round(float(p), 3) for i, p in enumerate(probs)
        }

        verdict = _threshold_verdict(reading)
        idx = next(i for i, name in self.labels.items() if name == verdict)
        probs = np.zeros_like(probs)
        probs[idx] = 1.0

        signals = (
            [ALL_CLEAR_SIGNAL] if verdict == "GOOD"
            else self._signals(reading, rho_residual)
        )

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
            "model_probs": model_probs,
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

        # Reported for transparency only — the verdict above does not
        # depend on it. Kept the same type as on the normal path so
        # callers never have to handle a null here.
        raw = self._forward(x)
        model_probs = {
            self.labels[i]: round(float(p), 3) for i, p in enumerate(raw)
        }

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
            "model_probs": model_probs,
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

    @staticmethod
    def _signals(reading, rho_residual):
        """Plain-language reasons, for the app UI and demo video —
        written for the person looking at the dashboard, not for a
        developer reading the code.

        Every threshold here is the same named constant
        _threshold_verdict() decides on, so the explanation can never
        describe a problem the verdict ignored, or stay silent about
        one it acted on. Only ever called on a reading whose density is
        already known to be in band — predict() short-circuits an
        out-of-band density before reaching here (see
        _reject_density_out_of_range), so there is no density-band
        check in here; it could never fire.
        """

        s = []

        eth_val = float(reading["ethanol"])
        wif_val = float(reading["wif"])
        turbidity_val = float(reading["turbidity"])

        if wif_val > FREE_WATER_WIF_THRESHOLD:
            s.append("Free water was found in the fuel.")
        elif wif_val > WATER_BUILDUP_WIF_THRESHOLD:
            # E10/E20 blends are hygroscopic: dissolved water climbs
            # toward saturation, then phase-separates. Call out the
            # blend-specific risk instead of a generic warning.
            if HYGROSCOPIC_BLEND_RANGE[0] <= eth_val <= HYGROSCOPIC_BLEND_RANGE[1]:
                s.append("Water is building up in this ethanol blend, "
                         "raising the phase separation risk common "
                         "with E10/E20 fuel.")
            else:
                s.append("There's more water in the fuel than normal.")

        if turbidity_val > HEAVY_TURBIDITY_THRESHOLD:
            s.append("The fuel looks very cloudy, with lots of solid particles.")
        elif turbidity_val > MILD_TURBIDITY_THRESHOLD:
            s.append("The fuel looks slightly cloudy.")

        # Informational only — the residual deliberately does NOT drive
        # the verdict. Field testing showed the 15C temperature
        # correction pushing this past threshold for fuel whose raw
        # density sits comfortably in band at ordinary room
        # temperature, so gating on it produced false ADULTERATED
        # calls. The raw-density band check wins instead; this text
        # just surfaces the hint, and the number itself is always
        # available in explain.rho_residual.
        if rho_residual > RHO_RESIDUAL_HIGH:
            s.append("Fuel density is too high for this ethanol level. "
                     "Could be kerosene, another solvent, or water "
                     "mixed in.")
        elif rho_residual < RHO_RESIDUAL_LOW:
            s.append("Fuel density is too low for this ethanol level, "
                     "which is unusual for a clean blend.")

        blend = classify_blend(eth_val)
        if blend_gap(eth_val) > BLEND_MARGIN_PCT:
            s.append(f"Ethanol level ({blend['measured']}%) doesn't "
                     f"match any standard blend (closest is "
                     f"{blend['nearest']}). Possible over/under-"
                     f"blending at the pump.")

        if not s:
            s.append(ALL_CLEAR_SIGNAL)

        return s
