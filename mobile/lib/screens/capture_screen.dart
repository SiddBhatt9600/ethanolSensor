import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/button_capture.dart';
import '../state/app_state.dart';
import '../theme.dart';
import '../widgets/section_card.dart';
import '../widgets/verdict_card.dart';

/// Mirrors the "Button Capture" panel + "Analyze" flow in
/// assets/app.js (loadButtonCapture / analyzeCapture).
class CaptureScreen extends StatelessWidget {
  const CaptureScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final capture = appState.buttonCapture;
    final hasSamples = capture != null && capture.samples.isNotEmpty;

    return RefreshIndicator(
      onRefresh: appState.refreshNow,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          SectionCard(
            title: 'Latest Button Capture',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'Press the physical button on the device, or tap '
                  '"Capture Now" below, to record the average of the '
                  'next five readings.',
                  style: TextStyle(color: AppColors.textMuted),
                ),
                const SizedBox(height: 12),
                ElevatedButton(
                  onPressed: appState.triggeringCapture ? null : () => appState.triggerCapture(),
                  child: Text(appState.triggeringCapture ? 'Capturing…' : 'Capture Now'),
                ),
                if (appState.captureTriggerMessage != null) ...[
                  const SizedBox(height: 8),
                  Text(appState.captureTriggerMessage!, style: const TextStyle(color: AppColors.textMuted, fontSize: 12)),
                ],
                if (hasSamples) ...[
                  const SizedBox(height: 12),
                  _captureTable(capture),
                ],
              ],
            ),
          ),
          if (hasSamples) SectionCard(title: 'Average', child: _averageBlock(capture)),
          SectionCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ElevatedButton(
                  onPressed: appState.analyzingCapture ? null : () => appState.analyzeCapture(),
                  child: Text(appState.analyzingCapture ? 'Analyzing…' : 'Analyze Latest Capture'),
                ),
                const SizedBox(height: 12),
                if (appState.captureVerdictError != null)
                  Text(appState.captureVerdictError!, style: const TextStyle(color: AppColors.bad))
                else if (appState.captureVerdict != null)
                  VerdictCard(verdict: appState.captureVerdict),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _captureTable(ButtonCapture capture) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: DataTable(
        columns: const [
          DataColumn(label: Text('#')),
          DataColumn(label: Text('Temp')),
          DataColumn(label: Text('Ethanol')),
          DataColumn(label: Text('Density')),
          DataColumn(label: Text('WIF')),
          DataColumn(label: Text('Turbidity')),
        ],
        rows: [
          for (var i = 0; i < capture.samples.length; i++)
            DataRow(cells: [
              DataCell(Text('${i + 1}')),
              DataCell(Text('${capture.samples[i].temp ?? "--"}')),
              DataCell(Text('${capture.samples[i].ethanol ?? "--"}')),
              DataCell(Text('${capture.samples[i].density ?? "--"}')),
              DataCell(Text('${capture.samples[i].wif ?? "--"}')),
              DataCell(Text('${capture.samples[i].turbidity ?? "--"}')),
            ]),
        ],
      ),
    );
  }

  Widget _averageBlock(ButtonCapture capture) {
    final a = capture.average;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Temperature: ${a.temp ?? "--"} °C'),
        Text('Ethanol: ${a.ethanol ?? "--"} %'),
        Text('Density: ${a.density ?? "--"}'),
        Text('Water: ${a.wif ?? "--"}'),
        Text('Turbidity: ${a.turbidity ?? "--"}'),
      ],
    );
  }
}
