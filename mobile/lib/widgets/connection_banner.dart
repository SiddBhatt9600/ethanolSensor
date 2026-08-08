import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/device_connection.dart';
import '../state/app_state.dart';
import '../theme.dart';
import 'section_card.dart';

/// Mirrors #connectionBar / #connectionStatus in the web dashboard.
class ConnectionBanner extends StatelessWidget {
  const ConnectionBanner({super.key});

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final connection = context.watch<DeviceConnection>();
    final connected = appState.connected;
    final hasTarget = connection.baseUrl != null;

    final label = !hasTarget
        ? 'No device configured — set the IP in Settings'
        : connected
            ? 'Connected · ${connection.baseUrl}'
            : 'Disconnected · ${connection.baseUrl}';

    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.circle, size: 12, color: connected ? AppColors.good : AppColors.bad),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  label,
                  style: TextStyle(
                    color: connected ? AppColors.good : AppColors.textMuted,
                    fontWeight: FontWeight.bold,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (appState.heartbeat != null)
                Text('HB ${appState.heartbeat!.heartbeat}', style: const TextStyle(color: AppColors.textMuted)),
            ],
          ),
          if (!connected && hasTarget && appState.lastError != null) ...[
            const SizedBox(height: 6),
            Text(
              appState.lastError!,
              style: const TextStyle(color: AppColors.bad, fontSize: 11),
            ),
          ],
        ],
      ),
    );
  }
}
