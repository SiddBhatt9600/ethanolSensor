import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Persists the Arduino UNO Q's local network address (e.g.
/// "http://192.168.1.50:8000") across app launches. The device serves
/// REST APIs directly on the local Wi-Fi network — there is no cloud
/// backend, so the app just needs to know where to point requests.
class DeviceConnection extends ChangeNotifier {
  static const _prefsKey = 'device_base_url';

  final SharedPreferences _prefs;
  String? baseUrl;

  DeviceConnection(this._prefs) : baseUrl = _prefs.getString(_prefsKey);

  Future<void> setBaseUrl(String input) async {
    final normalized = _normalize(input);
    baseUrl = normalized.isEmpty ? null : normalized;
    if (baseUrl == null) {
      await _prefs.remove(_prefsKey);
    } else {
      await _prefs.setString(_prefsKey, baseUrl!);
    }
    notifyListeners();
  }

  static String _normalize(String input) {
    var url = input.trim();
    if (url.isEmpty) return url;
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      url = 'http://$url';
    }
    while (url.endsWith('/')) {
      url = url.substring(0, url.length - 1);
    }
    return url;
  }
}
