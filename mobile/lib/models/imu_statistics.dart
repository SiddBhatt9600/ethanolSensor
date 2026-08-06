/// Mirrors ImuManager.get_statistics() (python/imuManager.py),
/// served via /api/imu_statistics.
class AxisStat {
  final double min;
  final double max;
  final double avg;
  final double rms;

  const AxisStat({required this.min, required this.max, required this.avg, required this.rms});

  factory AxisStat.fromJson(Map<String, dynamic> json) => AxisStat(
        min: (json['min'] as num?)?.toDouble() ?? 0,
        max: (json['max'] as num?)?.toDouble() ?? 0,
        avg: (json['avg'] as num?)?.toDouble() ?? 0,
        rms: (json['rms'] as num?)?.toDouble() ?? 0,
      );
}

class AxisGroup {
  final AxisStat x;
  final AxisStat y;
  final AxisStat z;

  const AxisGroup({required this.x, required this.y, required this.z});

  factory AxisGroup.fromJson(Map<String, dynamic> json) => AxisGroup(
        x: AxisStat.fromJson((json['x'] as Map<String, dynamic>?) ?? const {}),
        y: AxisStat.fromJson((json['y'] as Map<String, dynamic>?) ?? const {}),
        z: AxisStat.fromJson((json['z'] as Map<String, dynamic>?) ?? const {}),
      );
}

class ImuStatistics {
  final int sampleCount;
  final int? totalSamples;
  final AxisGroup? accelerometer;
  final AxisGroup? gyroscope;

  const ImuStatistics({
    required this.sampleCount,
    this.totalSamples,
    this.accelerometer,
    this.gyroscope,
  });

  factory ImuStatistics.fromJson(Map<String, dynamic> json) => ImuStatistics(
        sampleCount: (json['sampleCount'] as num?)?.toInt() ?? 0,
        totalSamples: (json['totalSamples'] as num?)?.toInt(),
        accelerometer: json['accelerometer'] != null
            ? AxisGroup.fromJson(json['accelerometer'] as Map<String, dynamic>)
            : null,
        gyroscope: json['gyroscope'] != null
            ? AxisGroup.fromJson(json['gyroscope'] as Map<String, dynamic>)
            : null,
      );
}
