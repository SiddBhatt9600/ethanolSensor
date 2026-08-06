import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/ai_verdict.dart';
import '../models/button_capture.dart';
import '../models/density_status.dart';
import '../models/heartbeat_status.dart';
import '../models/imu_sample.dart';
import '../models/imu_statistics.dart';
import '../models/sensor_reading.dart';

/// Thrown for network/HTTP failures (device unreachable, bad status, etc).
class ApiException implements Exception {
  final String message;
  ApiException(this.message);
  @override
  String toString() => message;
}

/// Thrown specifically for /api/ai/capture_verdict returning
/// {"error": "..."} — see AiManager.infer_capture (python/aiManager.py) —
/// which means no button capture is available yet, not a network failure.
class ApiCaptureError implements Exception {
  final String message;
  ApiCaptureError(this.message);
  @override
  String toString() => message;
}

/// Thin REST client for the Fuel Quality Monitor's on-device APIs
/// (see README.md "REST APIs" table). One instance is bound to a
/// single device base URL (e.g. http://192.168.1.50:8000).
class ApiClient {
  final String baseUrl;
  final http.Client _http = http.Client();
  static const _timeout = Duration(seconds: 6);

  ApiClient(this.baseUrl);

  Future<dynamic> _getJson(String path) async {
    final uri = Uri.parse('$baseUrl$path');
    late final http.Response response;
    try {
      response = await _http.get(uri).timeout(_timeout);
    } catch (e) {
      throw ApiException('Could not reach $baseUrl ($e)');
    }
    if (response.statusCode != 200) {
      throw ApiException('$path returned HTTP ${response.statusCode}');
    }
    try {
      return jsonDecode(response.body);
    } catch (e) {
      throw ApiException('$path returned invalid JSON');
    }
  }

  Future<dynamic> _postJson(String path, Map<String, dynamic> body) async {
    final uri = Uri.parse('$baseUrl$path');
    late final http.Response response;
    try {
      response = await _http
          .post(uri,
              headers: {'Content-Type': 'application/json'},
              body: jsonEncode(body))
          .timeout(_timeout);
    } catch (e) {
      throw ApiException('Could not reach $baseUrl ($e)');
    }
    dynamic decoded;
    try {
      decoded = jsonDecode(response.body);
    } catch (e) {
      throw ApiException('$path returned invalid JSON');
    }
    if (response.statusCode != 200) {
      final msg = (decoded is Map && decoded['error'] != null)
          ? decoded['error'] as String
          : 'HTTP ${response.statusCode}';
      throw ApiException('$path failed: $msg');
    }
    return decoded;
  }

  Future<List<SensorReading>> getSensors() async {
    final data = await _getJson('/api/sensors') as List;
    return data.map((e) => SensorReading.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<ButtonCapture> getButtonCapture() async {
    final data = await _getJson('/api/button_capture') as Map<String, dynamic>;
    return ButtonCapture.fromJson(data);
  }

  Future<AiVerdict> getAiCurrent() async {
    final data = await _getJson('/api/ai/current') as Map<String, dynamic>;
    return AiVerdict.fromJson(data);
  }

  Future<List<AiVerdict>> getAiVerdicts() async {
    final data = await _getJson('/api/ai/verdicts') as List;
    return data.map((e) => AiVerdict.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// Throws [ApiCaptureError] if the device has no capture to score yet.
  Future<AiVerdict> getCaptureVerdict() async {
    final data = await _getJson('/api/ai/capture_verdict') as Map<String, dynamic>;
    if (data.containsKey('error')) {
      throw ApiCaptureError(data['error'] as String);
    }
    return AiVerdict.fromJson(data);
  }

  Future<List<ImuSample>> getImuCapture() async {
    final data = await _getJson('/api/imu_capture') as List;
    return data.map((e) => ImuSample.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<ImuStatistics> getImuStatistics() async {
    final data = await _getJson('/api/imu_statistics') as Map<String, dynamic>;
    return ImuStatistics.fromJson(data);
  }

  Future<HeartbeatStatus> getHeartbeat() async {
    final data = await _getJson('/api/heartbeat') as Map<String, dynamic>;
    return HeartbeatStatus.fromJson(data);
  }

  /// There is no board density sensor — density is user-entered and
  /// applies to every reading (continuous + button capture) until
  /// updated again. See python/sensorManager.py set_user_density().
  Future<DensityStatus> getUserDensity() async {
    final data = await _getJson('/api/user/density') as Map<String, dynamic>;
    return DensityStatus.fromJson(data);
  }

  Future<DensityStatus> submitDensity(double density) async {
    final data = await _postJson('/api/user/density', {'density': density})
        as Map<String, dynamic>;
    return DensityStatus.fromJson(data);
  }

  void dispose() => _http.close();
}
