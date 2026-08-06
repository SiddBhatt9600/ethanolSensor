import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/app_state.dart';
import '../theme.dart';
import '../widgets/verdict_card.dart';

/// Mirrors the sensor-history table and #aiTable in the web dashboard.
class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> with SingleTickerProviderStateMixin {
  late final TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) context.read<AppState>().refreshAiHistory();
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();

    return Column(
      children: [
        TabBar(
          controller: _tabController,
          labelColor: AppColors.accent,
          unselectedLabelColor: AppColors.textMuted,
          tabs: const [Tab(text: 'Sensor History'), Tab(text: 'AI Verdicts')],
        ),
        Expanded(
          child: TabBarView(
            controller: _tabController,
            children: [
              _sensorHistoryTable(appState),
              _verdictHistoryList(appState),
            ],
          ),
        ),
      ],
    );
  }

  Widget _sensorHistoryTable(AppState appState) {
    final rows = appState.sensorHistory.reversed.toList();
    if (rows.isEmpty) {
      return const Center(child: Text('No sensor readings yet.', style: TextStyle(color: AppColors.textMuted)));
    }
    return SingleChildScrollView(
      padding: const EdgeInsets.all(12),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: DataTable(
          columns: const [
            DataColumn(label: Text('Time')),
            DataColumn(label: Text('Temp')),
            DataColumn(label: Text('Ethanol')),
            DataColumn(label: Text('Density')),
            DataColumn(label: Text('WIF')),
            DataColumn(label: Text('Turbidity')),
          ],
          rows: [
            for (final r in rows)
              DataRow(cells: [
                DataCell(Text(r.timestamp ?? '--')),
                DataCell(Text('${r.temp ?? "--"}')),
                DataCell(Text('${r.ethanol ?? "--"}')),
                DataCell(Text('${r.density ?? "--"}')),
                DataCell(Text('${r.wif ?? "--"}')),
                DataCell(Text('${r.turbidity ?? "--"}')),
              ]),
          ],
        ),
      ),
    );
  }

  Widget _verdictHistoryList(AppState appState) {
    final rows = appState.verdictHistory.reversed.toList();
    if (rows.isEmpty) {
      return RefreshIndicator(
        onRefresh: appState.refreshAiHistory,
        child: ListView(
          children: const [
            SizedBox(height: 120),
            Center(child: Text('No AI verdicts yet.', style: TextStyle(color: AppColors.textMuted))),
          ],
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: appState.refreshAiHistory,
      child: ListView.separated(
        padding: const EdgeInsets.all(12),
        itemCount: rows.length,
        separatorBuilder: (_, __) => const SizedBox(height: 12),
        itemBuilder: (context, index) {
          final v = rows[index];
          final anomalies = v.anomalies.isNotEmpty ? v.anomalies.map((a) => a.parameter).join(', ') : '—';
          return Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.card,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        v.verdict,
                        style: TextStyle(color: verdictColor(v.verdict), fontWeight: FontWeight.bold),
                      ),
                    ),
                    Text('${(v.confidence * 100).toStringAsFixed(1)} %', style: const TextStyle(color: AppColors.textPrimary)),
                  ],
                ),
                const SizedBox(height: 4),
                Text(v.timestamp ?? '--', style: const TextStyle(color: AppColors.textMuted, fontSize: 12)),
                if (v.explain != null) ...[
                  const SizedBox(height: 6),
                  Text(
                    'Density @15°C ${v.explain!.density15} · expected ${v.explain!.expectedDensity15} · residual ${v.explain!.rhoResidual}',
                    style: const TextStyle(color: AppColors.textMuted, fontSize: 11),
                  ),
                ],
                const SizedBox(height: 4),
                Text('Anomalies: $anomalies', style: const TextStyle(color: AppColors.textMuted, fontSize: 11)),
              ],
            ),
          );
        },
      ),
    );
  }
}
