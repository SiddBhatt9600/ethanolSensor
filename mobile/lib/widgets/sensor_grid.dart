import 'package:flutter/material.dart';

import '../models/sensor_reading.dart';
import '../theme.dart';

/// Mirrors the .cardContainer fuel-quality cards in the web dashboard
/// (ethanol / temperature / density / water / turbidity).
class SensorGrid extends StatelessWidget {
  final SensorReading? latest;

  const SensorGrid({super.key, required this.latest});

  String _fmt(double? v, [String unit = '']) => v == null ? '--' : '$v$unit';

  String _waterStatus(double? wif) {
    if (wif == null) return '--';
    if (wif < 30) return '🟢 Normal';
    if (wif < 70) return '🟡 Warning';
    return '🔴 Critical';
  }

  @override
  Widget build(BuildContext context) {
    final tiles = <(String, String)>[
      ('Ethanol', _fmt(latest?.ethanol, ' %')),
      ('Temperature', _fmt(latest?.temp, ' °C')),
      ('Density', _fmt(latest?.density)),
      ('Water in Fuel', _waterStatus(latest?.wif)),
      ('Turbidity', _fmt(latest?.turbidity)),
    ];

    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisSpacing: 12,
      mainAxisSpacing: 12,
      childAspectRatio: 1.5,
      children: [for (final t in tiles) _tile(t.$1, t.$2)],
    );
  }

  Widget _tile(String label, String value) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: AppColors.textMuted, fontSize: 13)),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(
              value,
              style: const TextStyle(color: AppColors.accent, fontSize: 22, fontWeight: FontWeight.bold),
            ),
          ),
        ],
      ),
    );
  }
}
