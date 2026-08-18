"""
fuel_simulator.py
=================

Physics-grounded synthetic fuel data generator for the
Fuel Quality Monitor AI (Arduino UNO Q / QRB2210).

Generates labelled sensor vectors matching the SensorManager
reading format:

    { temp, ethanol, wif, turbidity, density }

Labels:
    0 = GOOD        (fuel within spec for its declared blend)
    1 = SUSPECT     (borderline: high water absorption, mild
                     particulates, off-blend ethanol)
    2 = ADULTERATED (free water, solvent/kerosene dilution,
                     heavy particulates)

Physics used
------------
* Density of petrol at 15 C  : 720 - 775 kg/m3 (BIS IS 2796 band)
* Density of ethanol at 15 C : 789.4 kg/m3
* Density of kerosene at 15C : 790 - 820 kg/m3 (common adulterant)
* Blend density  : linear volumetric mixing rule (adequate for
                   gasoline-ethanol at these accuracies)
* Temperature    : density falls ~0.85 kg/m3 per +1 C for petrol,
                   ~0.85 for ethanol (close enough to share)
* Water          : petrol is immiscible with water. Ethanol blends
                   hold dissolved water up to a saturation point
                   (~0.3-0.6% v/v for E10, rising with ethanol%),
                   after which phase separation dumps free water
                   that the WIF sensor sees.
* Turbidity      : clean fuel is optically clear (< 5 NTU-equiv
                   counts). Suspended solids / phase-separated
                   emulsion raise it sharply.
"""

import numpy as np

RNG = np.random.default_rng(42)

# ------------------------------------------------------------------
# Physical constants
# ------------------------------------------------------------------
RHO_ETHANOL_15 = 789.4          # kg/m3
RHO_KEROSENE_15 = 805.0         # kg/m3 (midpoint)
DENSITY_TEMP_COEFF = 0.85       # kg/m3 per degC (falls as temp rises)
REF_TEMP = 15.0                 # reference temperature (degC)

GOOD, SUSPECT, ADULTERATED = 0, 1, 2
LABELS = {0: "GOOD", 1: "SUSPECT", 2: "ADULTERATED"}


def _petrol_base_density():
    """Base gasoline density at 15 C within the BIS spec band."""
    return RNG.uniform(722.0, 772.0)


def _blend_density_15(rho_petrol, ethanol_frac, kerosene_frac=0.0,
                      water_frac=0.0):
    """Linear volumetric mixing rule at 15 C."""
    petrol_frac = 1.0 - ethanol_frac - kerosene_frac - water_frac
    return (petrol_frac * rho_petrol
            + ethanol_frac * RHO_ETHANOL_15
            + kerosene_frac * RHO_KEROSENE_15
            + water_frac * 998.0)


def _to_temp(rho15, temp):
    """Shift density from 15 C to the given fuel temperature."""
    return rho15 - DENSITY_TEMP_COEFF * (temp - REF_TEMP)


def _sensor_noise(reading):
    """Apply per-sensor noise consistent with cheap automotive sensors."""
    return {
        "temp": reading["temp"] + RNG.normal(0, 0.5),
        "ethanol": np.clip(reading["ethanol"] + RNG.normal(0, 1.2), 0, 100),
        "wif": np.clip(reading["wif"] + RNG.normal(0, 1.5), 0, 100),
        "turbidity": np.clip(reading["turbidity"] + RNG.normal(0, 2.0), 0, 100),
        "density": reading["density"] + RNG.normal(0, 1.0),
    }


# ------------------------------------------------------------------
# Scenario generators
# ------------------------------------------------------------------
def gen_good():
    """In-spec fuel: E0-E20 blends (India: E10/E20 common), also E85."""
    # Weight toward realistic Indian pump blends
    ethanol_pct = RNG.choice(
        [RNG.uniform(0, 2), RNG.uniform(8, 12), RNG.uniform(18, 22),
         RNG.uniform(80, 87)],
        p=[0.15, 0.35, 0.35, 0.15],
    )
    e = ethanol_pct / 100.0
    temp = RNG.uniform(18, 55)
    rho15 = _blend_density_15(_petrol_base_density(), e)

    # Dissolved water well below saturation -> WIF sensor near floor
    wif = RNG.uniform(0, 4) + 0.05 * ethanol_pct
    turbidity = RNG.uniform(0, 6)

    return {
        "temp": temp,
        "ethanol": ethanol_pct,
        "wif": wif,
        "turbidity": turbidity,
        "density": _to_temp(rho15, temp),
    }, GOOD


def gen_suspect():
    """Borderline fuel: near-saturation water, mild solids, off-blend."""
    mode = RNG.integers(0, 4)
    temp = RNG.uniform(18, 55)

    if mode == 0:
        # High dissolved water in an ethanol blend, near phase-sep
        ethanol_pct = RNG.uniform(8, 25)
        e = ethanol_pct / 100.0
        w = RNG.uniform(0.004, 0.010)           # 0.4-1.0 % v/v water
        rho15 = _blend_density_15(_petrol_base_density(), e, water_frac=w)
        wif = RNG.uniform(8, 22)
        turbidity = RNG.uniform(4, 15)          # slight haze
    elif mode == 1:
        # Mild particulate contamination (dirty storage tank)
        ethanol_pct = RNG.choice([RNG.uniform(8, 12), RNG.uniform(18, 22)])
        e = ethanol_pct / 100.0
        rho15 = _blend_density_15(_petrol_base_density(), e)
        wif = RNG.uniform(0, 6)
        turbidity = RNG.uniform(12, 30)
    elif mode == 2:
        # Off-blend ethanol: pump declares E10/E20, sensor reads way off
        ethanol_pct = RNG.uniform(30, 55)
        e = ethanol_pct / 100.0
        rho15 = _blend_density_15(_petrol_base_density(), e)
        wif = RNG.uniform(1, 8)
        turbidity = RNG.uniform(0, 10)
    else:
        # Pure/near-pure ethanol (90-100%) with dissolved water
        ethanol_pct = RNG.uniform(90, 100)
        e = ethanol_pct / 100.0
        w = RNG.uniform(0.05, 0.15)             # 5-15% v/v water
        rho15 = _blend_density_15(_petrol_base_density(), e, water_frac=w)
        wif = RNG.uniform(8, 18)                # water present but not free
        turbidity = RNG.uniform(2, 10)

    return {
        "temp": temp,
        "ethanol": ethanol_pct,
        "wif": wif,
        "turbidity": turbidity,
        "density": _to_temp(rho15, temp),
    }, SUSPECT


def gen_adulterated():
    """Clear adulteration: free water, kerosene cut, or heavy solids."""
    mode = RNG.integers(0, 4)
    temp = RNG.uniform(18, 55)

    if mode == 0:
        # Free water / phase separation
        ethanol_pct = RNG.uniform(5, 25)
        e = ethanol_pct / 100.0
        w = RNG.uniform(0.015, 0.06)            # 1.5-6 % v/v
        rho15 = _blend_density_15(_petrol_base_density(), e, water_frac=w)
        wif = RNG.uniform(30, 95)
        turbidity = RNG.uniform(20, 70)         # emulsion haze
    elif mode == 1:
        # Kerosene dilution (classic Indian adulteration)
        ethanol_pct = RNG.uniform(0, 15)
        e = ethanol_pct / 100.0
        k = RNG.uniform(0.10, 0.35)             # 10-35 % kerosene
        rho15 = _blend_density_15(_petrol_base_density(), e,
                                  kerosene_frac=k)
        wif = RNG.uniform(0, 8)
        turbidity = RNG.uniform(0, 12)          # kerosene mixes clear!
    elif mode == 2:
        # Heavy particulate / sludge contamination
        ethanol_pct = RNG.uniform(0, 25)
        e = ethanol_pct / 100.0
        rho15 = _blend_density_15(_petrol_base_density(), e) \
            + RNG.uniform(1, 6)                 # solids raise density
        wif = RNG.uniform(2, 20)
        turbidity = RNG.uniform(45, 100)
    else:
        # Pure ethanol (95-100%) with excessive water (free water layer)
        ethanol_pct = RNG.uniform(95, 100)
        e = ethanol_pct / 100.0
        w = RNG.uniform(0.15, 0.35)             # 15-35% v/v water
        rho15 = _blend_density_15(_petrol_base_density(), e, water_frac=w)
        wif = RNG.uniform(20, 70)               # free water present
        turbidity = RNG.uniform(8, 25)

    return {
        "temp": temp,
        "ethanol": ethanol_pct,
        "wif": wif,
        "turbidity": turbidity,
        "density": _to_temp(rho15, temp),
    }, ADULTERATED


# ------------------------------------------------------------------
# Dataset builder
# ------------------------------------------------------------------
GENERATORS = [gen_good, gen_suspect, gen_adulterated]


def generate_dataset(n_per_class=4000):
    rows, labels = [], []
    for gen in GENERATORS:
        for _ in range(n_per_class):
            reading, y = gen()
            reading = _sensor_noise(reading)
            rows.append(reading)
            labels.append(y)
    return rows, np.array(labels)


if __name__ == "__main__":
    rows, y = generate_dataset(5)
    for r, lab in zip(rows, y):
        print(LABELS[lab], {k: round(float(v), 2) for k, v in r.items()})
