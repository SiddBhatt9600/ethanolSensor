import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/app_state.dart';
import '../widgets/connection_banner.dart';
import '../widgets/density_input_card.dart';
import '../widgets/section_card.dart';
import '../widgets/sensor_grid.dart';
import '../widgets/verdict_card.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final latest = appState.currentVerdict?.reading;

    return RefreshIndicator(
      onRefresh: appState.refreshNow,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const ConnectionBanner(),
          const SectionCard(
            title: 'Measured Fuel Density',
            child: DensityInputCard(),
          ),
          SensorGrid(latest: latest),
          const SizedBox(height: 16),
          SectionCard(
            title: 'AI Fuel Quality Verdict',
            child: VerdictCard(verdict: appState.currentVerdict),
          ),
        ],
      ),
    );
  }
}
