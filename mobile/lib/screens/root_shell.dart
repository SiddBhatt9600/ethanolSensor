import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/app_state.dart';
import 'capture_screen.dart';
import 'dashboard_screen.dart';
import 'history_screen.dart';
import 'imu_screen.dart';
import 'settings_screen.dart';

class RootShell extends StatefulWidget {
  const RootShell({super.key});

  @override
  State<RootShell> createState() => _RootShellState();
}

class _RootShellState extends State<RootShell> {
  int _index = 0;

  static const _titles = ['Dashboard', 'Button Capture', 'History', 'IMU', 'Settings'];
  static const _imuTabIndex = 3;

  void _onTap(int index) {
    final appState = context.read<AppState>();
    if (index == _imuTabIndex) {
      appState.startImuPolling();
    } else if (_index == _imuTabIndex) {
      appState.stopImuPolling();
    }
    setState(() => _index = index);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(_titles[_index])),
      body: IndexedStack(
        index: _index,
        children: const [
          DashboardScreen(),
          CaptureScreen(),
          HistoryScreen(),
          ImuScreen(),
          SettingsScreen(),
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        type: BottomNavigationBarType.fixed,
        currentIndex: _index,
        onTap: _onTap,
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.dashboard_outlined), label: 'Dashboard'),
          BottomNavigationBarItem(icon: Icon(Icons.touch_app_outlined), label: 'Capture'),
          BottomNavigationBarItem(icon: Icon(Icons.history), label: 'History'),
          BottomNavigationBarItem(icon: Icon(Icons.speed), label: 'IMU'),
          BottomNavigationBarItem(icon: Icon(Icons.settings_outlined), label: 'Settings'),
        ],
      ),
    );
  }
}
