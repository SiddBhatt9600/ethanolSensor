"""
features.py
===========

Shared feature engineering for the fuel quality classifier.
Used identically at training time (train_model.py) and at
inference time on the QRB2210 (fuelQualityModel.py) so there
is zero train/serve skew.

Input : one sensor reading dict {temp, ethanol, wif, turbidity, density}
Output: numpy feature vector (6,)

Features
--------
0. ethanol      (%)
1. wif          (raw water-in-fuel sensor value)
2. turbidity    (raw)
3. density15    (density temperature-corrected back to 15 C)
4. rho_residual (measured density15 minus the density physics
                 predicts for this ethanol% -> exposes kerosene
                 or water that ethanol% alone cannot explain)
5. temp         (degC; lets the model learn residual sensor
                 temperature effects)
"""

import numpy as np

RHO_ETHANOL_15 = 789.4
RHO_PETROL_NOMINAL_15 = 747.0     # midpoint of BIS petrol band
DENSITY_TEMP_COEFF = 0.85
REF_TEMP = 15.0

FEATURE_NAMES = [
    "ethanol", "wif", "turbidity", "density15", "rho_residual", "temp",
]


def expected_density15(ethanol_pct):
    """Physics-predicted blend density at 15 C for a clean
    petrol-ethanol mix with nominal petrol."""
    e = ethanol_pct / 100.0
    return (1.0 - e) * RHO_PETROL_NOMINAL_15 + e * RHO_ETHANOL_15


def extract(reading):
    """reading: dict with temp, ethanol, wif, turbidity, density."""
    temp = float(reading["temp"])
    ethanol = float(reading["ethanol"])
    wif = float(reading["wif"])
    turbidity = float(reading["turbidity"])
    density = float(reading["density"])

    density15 = density + DENSITY_TEMP_COEFF * (temp - REF_TEMP)
    rho_residual = density15 - expected_density15(ethanol)

    return np.array(
        [ethanol, wif, turbidity, density15, rho_residual, temp],
        dtype=np.float64,
    )


def extract_batch(readings):
    return np.vstack([extract(r) for r in readings])
