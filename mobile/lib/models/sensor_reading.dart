/// Mirrors the reading dict built by SensorManager.readSensors()
/// (python/sensorManager.py) and served via /api/sensors,
/// /api/button_capture and the "reading"/"average" fields of AI verdicts.
class SensorReading {
  final String? timestamp;
  final double? temp;
  final double? ethanol;
  final double? wif;
  final double? turbidity;
  final double? density;

  const SensorReading({
    this.timestamp,
    this.temp,
    this.ethanol,
    this.wif,
    this.turbidity,
    this.density,
  });

  factory SensorReading.fromJson(Map<String, dynamic> json) => SensorReading(
        timestamp: json['timestamp'] as String?,
        temp: (json['temp'] as num?)?.toDouble(),
        ethanol: (json['ethanol'] as num?)?.toDouble(),
        wif: (json['wif'] as num?)?.toDouble(),
        turbidity: (json['turbidity'] as num?)?.toDouble(),
        density: (json['density'] as num?)?.toDouble(),
      );
}
