import 'sensor_reading.dart';

/// Mirrors SensorManager.save_capture() / get_latest_capture()
/// (python/sensorManager.py), served via /api/button_capture.
class ButtonCapture {
  final String? timestamp;
  final List<SensorReading> samples;
  final SensorReading average;

  const ButtonCapture({
    this.timestamp,
    required this.samples,
    required this.average,
  });

  factory ButtonCapture.fromJson(Map<String, dynamic> json) => ButtonCapture(
        timestamp: json['timestamp'] as String?,
        samples: ((json['samples'] as List?) ?? [])
            .map((e) => SensorReading.fromJson(e as Map<String, dynamic>))
            .toList(),
        average: SensorReading.fromJson(
          (json['average'] as Map<String, dynamic>?) ?? const {},
        ),
      );
}
