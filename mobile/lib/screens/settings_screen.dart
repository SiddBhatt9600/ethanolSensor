import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/api_client.dart';
import '../services/device_connection.dart';
import '../theme.dart';
import '../widgets/section_card.dart';

/// Lets the user point the app at the Arduino UNO Q's local IP
/// address (there is no cloud backend — the device serves its REST
/// APIs directly on the local Wi-Fi network, see README.md).
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _controller;
  String? _testResult;
  bool _testing = false;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: context.read<DeviceConnection>().baseUrl ?? '');
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _saveAndTest() async {
    final connection = context.read<DeviceConnection>();
    setState(() {
      _testing = true;
      _testResult = null;
    });

    await connection.setBaseUrl(_controller.text);

    final url = connection.baseUrl;
    if (url == null) {
      setState(() {
        _testing = false;
        _testResult = 'Enter a device address first.';
      });
      return;
    }

    final client = ApiClient(url);
    try {
      final hb = await client.getHeartbeat();
      setState(() => _testResult = 'Connected — heartbeat ${hb.heartbeat}');
    } catch (e) {
      setState(() => _testResult = 'Could not reach device: $e');
    } finally {
      client.dispose();
      if (mounted) setState(() => _testing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final connection = context.watch<DeviceConnection>();
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        SectionCard(
          title: 'Device Address',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                "Enter the Arduino UNO Q's IP address and port on your local Wi-Fi network, "
                'e.g. 192.168.1.50:8000',
                style: TextStyle(color: AppColors.textMuted, fontSize: 12),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _controller,
                keyboardType: TextInputType.url,
                decoration: const InputDecoration(
                  labelText: 'Host:port',
                  hintText: '192.168.1.50:8000',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
              ElevatedButton(
                onPressed: _testing ? null : _saveAndTest,
                child: Text(_testing ? 'Testing…' : 'Save & Test Connection'),
              ),
              if (_testResult != null) ...[
                const SizedBox(height: 12),
                Text(
                  _testResult!,
                  style: TextStyle(color: _testResult!.startsWith('Connected') ? AppColors.good : AppColors.bad),
                ),
              ],
              if (connection.baseUrl != null) ...[
                const SizedBox(height: 12),
                Text('Currently saved: ${connection.baseUrl}', style: const TextStyle(color: AppColors.textMuted, fontSize: 12)),
              ],
            ],
          ),
        ),
      ],
    );
  }
}
