/// Mirrors the sample dict built by ImuManager.record()
/// (python/imuManager.py), served via /api/imu_capture and
/// /api/imu_history (and pushed live as the "imu_sample" WS event).
class ImuSample {
  final String? timestamp;
  final double? epoch;
  final int ax;
  final int ay;
  final int az;
  final int gx;
  final int gy;
  final int gz;

  const ImuSample({
    this.timestamp,
    this.epoch,
    required this.ax,
    required this.ay,
    required this.az,
    required this.gx,
    required this.gy,
    required this.gz,
  });

  factory ImuSample.fromJson(Map<String, dynamic> json) => ImuSample(
        timestamp: json['timestamp'] as String?,
        epoch: (json['epoch'] as num?)?.toDouble(),
        ax: (json['ax'] as num?)?.toInt() ?? 0,
        ay: (json['ay'] as num?)?.toInt() ?? 0,
        az: (json['az'] as num?)?.toInt() ?? 0,
        gx: (json['gx'] as num?)?.toInt() ?? 0,
        gy: (json['gy'] as num?)?.toInt() ?? 0,
        gz: (json['gz'] as num?)?.toInt() ?? 0,
      );
}
