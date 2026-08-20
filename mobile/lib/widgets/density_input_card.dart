import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/density_status.dart';
import '../state/app_state.dart';
import '../theme.dart';

/// There is no board density sensor — density is measured by the
/// user (e.g. with a hydrometer) and submitted here, applying to
/// every reading (continuous + button capture) until updated again.
/// Mirrors the "Measured Fuel Density" section in assets/index.html.
class DensityInputCard extends StatefulWidget {
  const DensityInputCard({super.key});

  @override
  State<DensityInputCard> createState() => _DensityInputCardState();
}

class _DensityInputCardState extends State<DensityInputCard> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final status = appState.densityStatus;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _statusBox(status),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: TextField(
                controller: _controller,
                keyboardType:
                    const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(
                  hintText: 'e.g. 751.2 (kg/m³, standard 725-775)',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
              ),
            ),
            const SizedBox(width: 10),
            ElevatedButton(
              onPressed: appState.submittingDensity ? null : _submit,
              child: Text(appState.submittingDensity ? '…' : 'Submit'),
            ),
          ],
        ),
        if (appState.densitySubmitError != null) ...[
          const SizedBox(height: 8),
          Text(appState.densitySubmitError!,
              style: const TextStyle(color: AppColors.bad, fontSize: 12)),
        ] else if (appState.densitySubmitSuccess != null) ...[
          const SizedBox(height: 8),
          Text(appState.densitySubmitSuccess!,
              style: const TextStyle(color: AppColors.good, fontSize: 12)),
        ],
      ],
    );
  }

  void _submit() {
    final value = double.tryParse(_controller.text);
    if (value == null) {
      context
          .read<AppState>()
          .setDensitySubmitError('Enter a numeric density value first.');
      return;
    }
    context.read<AppState>().submitDensity(value);
  }

  Widget _statusBox(DensityStatus? status) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.bg,
        borderRadius: BorderRadius.circular(8),
        border: const Border(left: BorderSide(color: AppColors.accent, width: 4)),
      ),
      child: Text(
        status != null && status.isSet
            ? 'Current density in use: ${status.density} kg/m³ (set ${status.timestamp})'
            : 'No density entered yet — enter a hydrometer/measured reading '
                'below. The AI verdict will not appear until this is set '
                '(there is no density sensor on the board).',
        style: const TextStyle(color: AppColors.textPrimary, fontSize: 13),
      ),
    );
  }
}
