import 'package:flutter/material.dart';

import '../models/ai_verdict.dart';
import '../theme.dart';

Color verdictColor(String verdict) {
  switch (verdict) {
    case 'GOOD':
      return AppColors.good;
    case 'SUSPECT':
      return AppColors.suspect;
    case 'ADULTERATED':
      return AppColors.bad;
    default:
      return AppColors.textMuted;
  }
}

/// Mirrors loadAiVerdict() in assets/app.js: verdict badge, confidence,
/// class probabilities, blend check, drift anomalies and the
/// mileage-impact estimate.
class VerdictCard extends StatelessWidget {
  final AiVerdict? verdict;
  final String waitingMessage;

  const VerdictCard({
    super.key,
    required this.verdict,
    this.waitingMessage = 'First verdict arrives within ~10 seconds.',
  });

  @override
  Widget build(BuildContext context) {
    final v = verdict;
    if (v == null || v.verdict == 'UNKNOWN') {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: AppColors.bg,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.border, width: 2),
        ),
        alignment: Alignment.center,
        child: Column(
          children: [
            const Text(
              'WAITING…',
              style: TextStyle(
                fontSize: 26,
                fontWeight: FontWeight.bold,
                letterSpacing: 2,
                color: AppColors.textMuted,
              ),
            ),
            const SizedBox(height: 8),
            Text(waitingMessage, style: const TextStyle(color: AppColors.textMuted), textAlign: TextAlign.center),
          ],
        ),
      );
    }

    final color = verdictColor(v.verdict);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: color.withOpacity(0.12),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: color, width: 2),
          ),
          child: Column(
            children: [
              Text(
                v.verdict,
                style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, letterSpacing: 2, color: color),
              ),
              const SizedBox(height: 6),
              Text(
                'Confidence : ${(v.confidence * 100).toStringAsFixed(1)} %',
                style: const TextStyle(color: AppColors.textPrimary),
              ),
              if (v.probs != null) ...[
                const SizedBox(height: 4),
                Text(
                  'GOOD ${(v.probs!.good * 100).toStringAsFixed(1)} % · '
                  'SUSPECT ${(v.probs!.suspect * 100).toStringAsFixed(1)} % · '
                  'ADULTERATED ${(v.probs!.adulterated * 100).toStringAsFixed(1)} %',
                  style: const TextStyle(color: AppColors.textMuted, fontSize: 12),
                  textAlign: TextAlign.center,
                ),
              ],
              if (v.blend != null) ...[
                const SizedBox(height: 10),
                Text(
                  v.blend!.inSpec
                      ? 'Blend check : ${v.blend!.nearest} — measured ${v.blend!.measured} % ethanol (within band) ✓'
                      : '⚠ Blend check : measured ${v.blend!.measured} % ethanol — OFF-SPEC (nearest ${v.blend!.nearest})',
                  style: TextStyle(color: v.blend!.inSpec ? AppColors.good : AppColors.bad, fontWeight: FontWeight.bold),
                  textAlign: TextAlign.center,
                ),
              ],
            ],
          ),
        ),
        if (v.mileage != null) ...[
          const SizedBox(height: 12),
          _mileageBox(v.mileage!),
        ],
        if (v.anomalies.isNotEmpty) ...[
          const SizedBox(height: 12),
          _anomalyBox(v.anomalies),
        ],
      ],
    );
  }

  Widget _mileageBox(MileageInfo m) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.bg,
        borderRadius: BorderRadius.circular(8),
        border: const Border(left: BorderSide(color: AppColors.accent, width: 4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '${m.estimatedKmpl} km/l estimated (baseline ${m.baselineKmpl} km/l, ${m.totalPenaltyPct}% impact)',
            style: const TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 6),
          Text(
            'Ethanol blend: -${m.breakdown.ethanolBlendPct}% · '
            'Fuel quality: -${m.breakdown.fuelQualityPct}% · '
            'Driving style: -${m.breakdown.drivingBehaviorPct}%',
            style: const TextStyle(color: AppColors.textMuted, fontSize: 12),
          ),
          if (m.notes.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(m.notes.join(' '), style: const TextStyle(color: AppColors.textMuted, fontSize: 11)),
          ],
          if (m.disclaimer.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              m.disclaimer,
              style: const TextStyle(color: AppColors.textMuted, fontSize: 11, fontStyle: FontStyle.italic),
            ),
          ],
        ],
      ),
    );
  }

  Widget _anomalyBox(List<AnomalyInfo> anomalies) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.bad.withOpacity(0.12),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.bad),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '⚠ Anomalies / quality flags:',
            style: TextStyle(color: AppColors.bad, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 6),
          for (final a in anomalies)
            Text(
              a.isQuality
                  ? (a.reason ?? '')
                  : 'drift — ${a.parameter}: ${a.value} vs baseline ${a.baselineMean} (z = ${a.zScore})',
              style: const TextStyle(color: AppColors.textPrimary, fontSize: 12),
            ),
        ],
      ),
    );
  }
}
