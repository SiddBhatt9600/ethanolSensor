import 'dart:async';

import 'package:flutter/foundation.dart';

import '../models/ai_verdict.dart';
import '../models/button_capture.dart';
import '../models/density_status.dart';
import '../models/heartbeat_status.dart';
import '../models/imu_sample.dart';
import '../models/imu_statistics.dart';
import '../models/sensor_reading.dart';
import '../services/api_client.dart';
import '../services/device_connection.dart';

/// App-wide state: polls the configured device on a fixed cadence and
/// exposes the latest readings to every screen. Mirrors the polling
/// loop in assets/app.js (refreshDashboard / loadImu), adapted to a
/// single shared client instead of independent DOM updates.
class AppState extends ChangeNotifier {
  final DeviceConnection connection;
  ApiClient? _client;

  Timer? _pollTimer;
  Timer? _imuTimer;

  bool connected = false;
  String? lastError;

  List<SensorReading> sensorHistory = [];
  ButtonCapture? buttonCapture;
  AiVerdict? currentVerdict;
  List<AiVerdict> verdictHistory = [];
  HeartbeatStatus? heartbeat;

  List<ImuSample> imuSamples = [];
  ImuStatistics? imuStatistics;

  AiVerdict? captureVerdict;
  String? captureVerdictError;
  bool analyzingCapture = false;

  DensityStatus? densityStatus;
  bool submittingDensity = false;
  String? densitySubmitError;
  String? densitySubmitSuccess;

  AppState(this.connection) {
    connection.addListener(_onConnectionChanged);
    _onConnectionChanged();
  }

  void _onConnectionChanged() {
    _client?.dispose();
    final url = connection.baseUrl;
    _client = url == null ? null : ApiClient(url);
    connected = false;
    lastError = null;
    _restartPolling();
    notifyListeners();
  }

  void _restartPolling() {
    _pollTimer?.cancel();
    if (_client == null) return;
    _poll();
    _pollTimer = Timer.periodic(const Duration(seconds: 1), (_) => _poll());
  }

  /// Public alias used for pull-to-refresh on the dashboard.
  Future<void> refreshNow() => _poll();

  Future<void> _poll() async {
    final client = _client;
    if (client == null) return;
    try {
      final results = await Future.wait([
        client.getSensors(),
        client.getHeartbeat(),
        client.getAiCurrent(),
        client.getButtonCapture(),
        client.getUserDensity(),
      ]);
      sensorHistory = results[0] as List<SensorReading>;
      heartbeat = results[1] as HeartbeatStatus;
      currentVerdict = results[2] as AiVerdict;
      buttonCapture = results[3] as ButtonCapture;
      densityStatus = results[4] as DensityStatus;
      connected = true;
      lastError = null;
    } catch (e) {
      connected = false;
      lastError = e.toString();
    }
    notifyListeners();
  }

  Future<void> refreshAiHistory() async {
    final client = _client;
    if (client == null) return;
    try {
      verdictHistory = await client.getAiVerdicts();
      notifyListeners();
    } catch (_) {
      // Sensor/AI polling already surfaces connectivity errors;
      // a failed history refresh just leaves the last-known list.
    }
  }

  void startImuPolling() {
    _imuTimer?.cancel();
    if (_client == null) return;
    _pollImu();
    _imuTimer = Timer.periodic(const Duration(milliseconds: 250), (_) => _pollImu());
  }

  void stopImuPolling() {
    _imuTimer?.cancel();
    _imuTimer = null;
  }

  Future<void> _pollImu() async {
    final client = _client;
    if (client == null) return;
    try {
      final samples = await client.getImuCapture();
      final stats = await client.getImuStatistics();
      imuSamples = samples;
      imuStatistics = stats;
      notifyListeners();
    } catch (_) {
      // IMU is a secondary stream; the dashboard's main poll already
      // reports connectivity loss, so stay quiet here to avoid churn.
    }
  }

  Future<void> analyzeCapture() async {
    final client = _client;
    if (client == null) return;
    analyzingCapture = true;
    captureVerdictError = null;
    notifyListeners();
    try {
      captureVerdict = await client.getCaptureVerdict();
    } on ApiCaptureError catch (e) {
      captureVerdict = null;
      captureVerdictError = e.message;
    } catch (e) {
      captureVerdict = null;
      captureVerdictError = 'Analysis failed: $e';
    }
    analyzingCapture = false;
    notifyListeners();
  }

  void setDensitySubmitError(String message) {
    densitySubmitError = message;
    densitySubmitSuccess = null;
    notifyListeners();
  }

  Future<void> submitDensity(double density) async {
    final client = _client;
    if (client == null) return;
    submittingDensity = true;
    densitySubmitError = null;
    densitySubmitSuccess = null;
    notifyListeners();
    try {
      densityStatus = await client.submitDensity(density);
      densitySubmitSuccess =
          'Density set to ${densityStatus!.density} kg/m³.';
    } catch (e) {
      densitySubmitError = 'Failed: $e';
    }
    submittingDensity = false;
    notifyListeners();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _imuTimer?.cancel();
    connection.removeListener(_onConnectionChanged);
    _client?.dispose();
    super.dispose();
  }
}
