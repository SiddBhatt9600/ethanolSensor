import 'sensor_reading.dart';

/// Mirrors AiManager.infer() / infer_capture() (python/aiManager.py),
/// served via /api/ai/current, /api/ai/verdicts and /api/ai/capture_verdict.

class Probs {
  final double good;
  final double suspect;
  final double adulterated;

  const Probs({required this.good, required this.suspect, required this.adulterated});

  factory Probs.fromJson(Map<String, dynamic> json) => Probs(
        good: (json['GOOD'] as num?)?.toDouble() ?? 0,
        suspect: (json['SUSPECT'] as num?)?.toDouble() ?? 0,
        adulterated: (json['ADULTERATED'] as num?)?.toDouble() ?? 0,
      );
}

class BlendInfo {
  final bool inSpec;
  final String nearest;
  final double measured;

  const BlendInfo({required this.inSpec, required this.nearest, required this.measured});

  factory BlendInfo.fromJson(Map<String, dynamic> json) => BlendInfo(
        inSpec: json['in_spec'] as bool? ?? false,
        nearest: json['nearest'] as String? ?? '',
        measured: (json['measured'] as num?)?.toDouble() ?? 0,
      );
}

class ExplainInfo {
  final List<String> signals;
  final double? density15;
  final double? expectedDensity15;
  final double? rhoResidual;

  const ExplainInfo({
    required this.signals,
    this.density15,
    this.expectedDensity15,
    this.rhoResidual,
  });

  factory ExplainInfo.fromJson(Map<String, dynamic> json) => ExplainInfo(
        signals: ((json['signals'] as List?) ?? []).map((e) => e.toString()).toList(),
        density15: (json['density15'] as num?)?.toDouble(),
        expectedDensity15: (json['expected_density15'] as num?)?.toDouble(),
        rhoResidual: (json['rho_residual'] as num?)?.toDouble(),
      );
}

/// "drift" entries are real rolling z-score events (a SUDDEN change
/// vs. the recent baseline). "quality" entries are synthesized by
/// AiManager.infer() whenever the verdict isn't GOOD, so the
/// anomalies list is never misleadingly empty for fuel that's been
/// consistently bad rather than suddenly changed — see reason
/// instead of the z-score fields in that case.
class AnomalyInfo {
  final String type;
  final String parameter;
  final double? zScore;
  final double? baselineMean;
  final double? value;
  final String? reason;

  const AnomalyInfo({
    this.type = 'drift',
    required this.parameter,
    this.zScore,
    this.baselineMean,
    this.value,
    this.reason,
  });

  bool get isQuality => type == 'quality';

  factory AnomalyInfo.fromJson(Map<String, dynamic> json) => AnomalyInfo(
        type: json['type'] as String? ?? 'drift',
        parameter: json['parameter'] as String? ?? '',
        zScore: (json['z_score'] as num?)?.toDouble(),
        baselineMean: (json['baseline_mean'] as num?)?.toDouble(),
        value: (json['value'] as num?)?.toDouble(),
        reason: json['reason'] as String?,
      );
}

class MileageBreakdown {
  final double ethanolBlendPct;
  final double fuelQualityPct;
  final double drivingBehaviorPct;

  const MileageBreakdown({
    required this.ethanolBlendPct,
    required this.fuelQualityPct,
    required this.drivingBehaviorPct,
  });

  factory MileageBreakdown.fromJson(Map<String, dynamic> json) => MileageBreakdown(
        ethanolBlendPct: (json['ethanol_blend_pct'] as num?)?.toDouble() ?? 0,
        fuelQualityPct: (json['fuel_quality_pct'] as num?)?.toDouble() ?? 0,
        drivingBehaviorPct: (json['driving_behavior_pct'] as num?)?.toDouble() ?? 0,
      );
}

class MileageInfo {
  final double estimatedKmpl;
  final double baselineKmpl;
  final double totalPenaltyPct;
  final MileageBreakdown breakdown;
  final List<String> notes;
  final String disclaimer;

  const MileageInfo({
    required this.estimatedKmpl,
    required this.baselineKmpl,
    required this.totalPenaltyPct,
    required this.breakdown,
    required this.notes,
    required this.disclaimer,
  });

  factory MileageInfo.fromJson(Map<String, dynamic> json) => MileageInfo(
        estimatedKmpl: (json['estimated_kmpl'] as num?)?.toDouble() ?? 0,
        baselineKmpl: (json['baseline_kmpl'] as num?)?.toDouble() ?? 0,
        totalPenaltyPct: (json['total_penalty_pct'] as num?)?.toDouble() ?? 0,
        breakdown: MileageBreakdown.fromJson(
          (json['breakdown'] as Map<String, dynamic>?) ?? const {},
        ),
        notes: ((json['notes'] as List?) ?? []).map((e) => e.toString()).toList(),
        disclaimer: json['disclaimer'] as String? ?? '',
      );
}

class AiVerdict {
  final String? timestamp;
  final SensorReading? reading;
  final String verdict;
  final double confidence;
  final Probs? probs;
  final BlendInfo? blend;
  final ExplainInfo? explain;
  final List<AnomalyInfo> anomalies;
  final MileageInfo? mileage;

  const AiVerdict({
    this.timestamp,
    this.reading,
    required this.verdict,
    required this.confidence,
    this.probs,
    this.blend,
    this.explain,
    this.anomalies = const [],
    this.mileage,
  });

  factory AiVerdict.fromJson(Map<String, dynamic> json) => AiVerdict(
        timestamp: json['timestamp'] as String?,
        reading: json['reading'] != null
            ? SensorReading.fromJson(json['reading'] as Map<String, dynamic>)
            : null,
        verdict: json['verdict'] as String? ?? 'UNKNOWN',
        confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
        probs: json['probs'] != null ? Probs.fromJson(json['probs'] as Map<String, dynamic>) : null,
        blend: json['blend'] != null ? BlendInfo.fromJson(json['blend'] as Map<String, dynamic>) : null,
        explain:
            json['explain'] != null ? ExplainInfo.fromJson(json['explain'] as Map<String, dynamic>) : null,
        anomalies: ((json['anomalies'] as List?) ?? [])
            .map((e) => AnomalyInfo.fromJson(e as Map<String, dynamic>))
            .toList(),
        mileage:
            json['mileage'] != null ? MileageInfo.fromJson(json['mileage'] as Map<String, dynamic>) : null,
      );
}
