import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'screens/root_shell.dart';
import 'services/device_connection.dart';
import 'state/app_state.dart';
import 'theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final prefs = await SharedPreferences.getInstance();
  final connection = DeviceConnection(prefs);
  runApp(FuelQualityApp(connection: connection));
}

class FuelQualityApp extends StatelessWidget {
  final DeviceConnection connection;

  const FuelQualityApp({super.key, required this.connection});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider<DeviceConnection>.value(value: connection),
        ChangeNotifierProvider<AppState>(create: (_) => AppState(connection)),
      ],
      child: MaterialApp(
        title: 'Fuel Quality Monitor',
        debugShowCheckedModeBanner: false,
        theme: buildAppTheme(),
        home: const RootShell(),
      ),
    );
  }
}
