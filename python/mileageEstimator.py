"""
mileageEstimator.py
====================

Fuel-economy impact estimate for the dashboard.

IMPORTANT — what this is and is not: this is NOT a trained model.
There is no ground-truth mileage/dyno dataset for this vehicle to
train on (that would require metered fuel + metered distance over
many trips, which we don't have before submission). Inventing one
would be worse than not having the feature at all.

Instead this is a transparent, physics/published-data formula that
combines three effects known to affect real-world mileage:

  1. Ethanol energy-content penalty
     Ethanol's volumetric calorific value is ~34% lower than
     petrol's, so higher-ethanol blends need more fuel volume for
     the same energy / distance. Government and SIAM/ARAI studies
     on India's E20 rollout report real-world economy loss in the
     ~6-7% range for E20 (less than the pure energy-content delta
     would suggest, because engines are re-tuned / compression
     adjusted for ethanol blends). We use that empirical figure,
     scaled linearly with measured ethanol %, not the raw
     thermodynamic number.

  2. Fuel-quality penalty (from our own AI verdict)
     Adulterated or water-contaminated fuel burns less completely
     (fouled injectors, incomplete combustion, reduced effective
     calorific value). No dyno data exists for OUR contamination
     scenarios either, so these are conservative, clearly-labelled
     heuristic penalties, not measurements.

  3. Driver-behavior penalty (from the BMI323 IMU)
     Harsh acceleration/braking measurably increases fuel
     consumption in published driving-style studies. This term is
     wired up but reports "insufficient calibrated IMU data" until
     the IMU is actually delivering readings AND we've collected
     real driving data to calibrate raw-count thresholds against —
     both currently blocked (see AI_PLAN.md). Shipping a made-up
     threshold today would be a worse look than an honest "not yet
     available".

Every number this module produces is estimated, not measured, and
the output says so.
"""

# Baseline economy for the reference vehicle, at clean E0 fuel and
# smooth driving. Not vehicle-specific — presented as "vs baseline"
# because we have no per-vehicle calibration.
DEFAULT_BASELINE_KMPL = 18.0

# Empirical ethanol economy penalty, scaled to the commonly cited
# ~6-7% real-world loss at E20 (SIAM/ARAI-style figures), applied
# linearly with measured ethanol %.
ETHANOL_PENALTY_AT_E20 = 0.065          # 6.5% loss at 20% ethanol
ETHANOL_PENALTY_PER_PCT = ETHANOL_PENALTY_AT_E20 / 20.0

# Heuristic fuel-quality penalties — not measured, kept conservative.
VERDICT_PENALTY = {
    "GOOD": 0.0,
    "SUSPECT": 0.05,
    "ADULTERATED": 0.15,
    "UNKNOWN": 0.0,
}

# IMU placeholder detection: the BMI323 read-failure code (0xFFFF
# cast to int16) surfaces as -1 on every axis. Treat that pattern,
# or an empty buffer, as "no usable IMU data" rather than a real
# (impossibly still) reading.
_IMU_ERROR_VALUE = -1


def _imu_is_available(imu_stats):
    if not imu_stats or imu_stats.get("sampleCount", 0) == 0:
        return False

    accel = imu_stats.get("accelerometer", {})
    for axis in ("x", "y", "z"):
        a = accel.get(axis, {})
        if a.get("min") != _IMU_ERROR_VALUE or a.get("max") != _IMU_ERROR_VALUE:
            return True

    return False


def estimate(reading, verdict, imu_stats=None,
             baseline_kmpl=DEFAULT_BASELINE_KMPL):
    """
    reading: dict with at least "ethanol"
    verdict: "GOOD" / "SUSPECT" / "ADULTERATED" / "UNKNOWN"
    imu_stats: output of ImuManager.get_statistics(), or None

    Returns a dict with the estimate, its breakdown, and honest
    notes about what could not be computed yet.
    """

    ethanol_pct = float(reading.get("ethanol", 0.0))
    notes = []

    ethanol_penalty = min(
        ethanol_pct * ETHANOL_PENALTY_PER_PCT,
        0.35,                       # clamp: never claim >35% loss
    )

    quality_penalty = VERDICT_PENALTY.get(verdict, 0.0)

    driving_penalty = 0.0
    if _imu_is_available(imu_stats):
        # Calibration pending real driving data — see module
        # docstring. Wired up, intentionally inert for now.
        notes.append(
            "IMU is delivering data, but driver-behavior scoring "
            "is not yet calibrated against real driving sessions — "
            "contributing 0% until that calibration exists."
        )
    else:
        notes.append(
            "IMU has no valid data yet (sensor read failure or "
            "empty buffer) — driver-behavior term not included."
        )

    total_penalty = min(
        ethanol_penalty + quality_penalty + driving_penalty,
        0.60,                        # clamp: sanity cap
    )

    estimated_kmpl = round(baseline_kmpl * (1.0 - total_penalty), 2)

    return {
        "baseline_kmpl": baseline_kmpl,
        "estimated_kmpl": estimated_kmpl,
        "total_penalty_pct": round(total_penalty * 100, 1),
        "breakdown": {
            "ethanol_blend_pct": round(ethanol_penalty * 100, 1),
            "fuel_quality_pct": round(quality_penalty * 100, 1),
            "driving_behavior_pct": round(driving_penalty * 100, 1),
        },
        "notes": notes,
        "disclaimer": (
            "Estimate from published ethanol-economy figures and "
            "the AI fuel-quality verdict, not measured on this "
            "vehicle. Not a certified mileage figure."
        ),
    }
