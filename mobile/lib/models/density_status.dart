/// Mirrors SensorManager.get_user_density() (python/sensorManager.py),
/// served via GET /api/user/density. There is no board density
/// sensor — this is the last value the user submitted (phone app or
/// web dashboard) via POST /api/user/density.
class DensityStatus {
  final double? density;
  final String? timestamp;

  const DensityStatus({this.density, this.timestamp});

  bool get isSet => density != null;

  factory DensityStatus.fromJson(Map<String, dynamic> json) => DensityStatus(
        density: (json['density'] as num?)?.toDouble(),
        timestamp: json['timestamp'] as String?,
      );
}
