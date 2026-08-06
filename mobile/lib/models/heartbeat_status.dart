/// Mirrors HbManager.get_status() (python/hbManager.py),
/// served via /api/heartbeat.
class HeartbeatStatus {
  final num heartbeat;
  final int missed;

  const HeartbeatStatus({required this.heartbeat, required this.missed});

  factory HeartbeatStatus.fromJson(Map<String, dynamic> json) => HeartbeatStatus(
        heartbeat: (json['heartbeat'] as num?) ?? 0,
        missed: (json['missed'] as num?)?.toInt() ?? 0,
      );
}
