import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/imu_sample.dart';
import '../models/imu_statistics.dart';
import '../state/app_state.dart';
import '../theme.dart';
import '../widgets/section_card.dart';

/// Mirrors the IMU accelerometer/gyroscope charts in assets/app.js.
/// Polls /api/imu_capture + /api/imu_statistics only while this
/// screen is visible (see AppState.startImuPolling/stopImuPolling).
class ImuScreen extends StatefulWidget {
  const ImuScreen({super.key});

  @override
  State<ImuScreen> createState() => _ImuScreenState();
}

class _ImuScreenState extends State<ImuScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) context.read<AppState>().startImuPolling();
    });
  }

  @override
  void dispose() {
    context.read<AppState>().stopImuPolling();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final samples = appState.imuSamples;
    final stats = appState.imuStatistics;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        SectionCard(
          title: 'Accelerometer',
          child: SizedBox(
            height: 220,
            child: _chart(samples, (s) => s.ax.toDouble(), (s) => s.ay.toDouble(), (s) => s.az.toDouble()),
          ),
        ),
        SectionCard(
          title: 'Gyroscope',
          child: SizedBox(
            height: 220,
            child: _chart(samples, (s) => s.gx.toDouble(), (s) => s.gy.toDouble(), (s) => s.gz.toDouble()),
          ),
        ),
        if (stats != null && stats.sampleCount > 0)
          SectionCard(
            title: 'Statistics (last 30 min, ${stats.sampleCount} samples)',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (stats.accelerometer != null) _statRow('Accel', stats.accelerometer!),
                if (stats.gyroscope != null) _statRow('Gyro', stats.gyroscope!),
              ],
            ),
          ),
      ],
    );
  }

  Widget _chart(
    List<ImuSample> samples,
    double Function(ImuSample) x,
    double Function(ImuSample) y,
    double Function(ImuSample) z,
  ) {
    if (samples.isEmpty) {
      return const Center(child: Text('Waiting for IMU data…', style: TextStyle(color: AppColors.textMuted)));
    }

    List<FlSpot> spots(double Function(ImuSample) sel) =>
        [for (var i = 0; i < samples.length; i++) FlSpot(i.toDouble(), sel(samples[i]))];

    return LineChart(
      LineChartData(
        gridData: const FlGridData(show: false),
        titlesData: const FlTitlesData(show: false),
        borderData: FlBorderData(show: false),
        lineTouchData: const LineTouchData(enabled: false),
        lineBarsData: [
          LineChartBarData(spots: spots(x), color: AppColors.bad, dotData: const FlDotData(show: false), barWidth: 1.5),
          LineChartBarData(spots: spots(y), color: AppColors.good, dotData: const FlDotData(show: false), barWidth: 1.5),
          LineChartBarData(spots: spots(z), color: AppColors.accent, dotData: const FlDotData(show: false), barWidth: 1.5),
        ],
      ),
    );
  }

  Widget _statRow(String label, AxisGroup group) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        '$label  X: avg ${group.x.avg} rms ${group.x.rms}  ·  '
        'Y: avg ${group.y.avg} rms ${group.y.rms}  ·  '
        'Z: avg ${group.z.avg} rms ${group.z.rms}',
        style: const TextStyle(color: AppColors.textMuted, fontSize: 12),
      ),
    );
  }
}
