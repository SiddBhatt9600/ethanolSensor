# Fuel Quality Monitor — Mobile App

A native Flutter companion app for the [Fuel Quality Monitoring System](../README.md).
It talks directly to the REST APIs already exposed by the Arduino UNO Q
over the local Wi-Fi network — no cloud backend, no changes needed on
the device side.

Screens:

- **Dashboard** — connection status, heartbeat, live fuel-quality
  sensor cards, AI verdict (confidence, class probabilities, blend
  check, physics explanation, refuel-drift alerts, mileage estimate)
- **Capture** — latest button-capture samples/average, on-demand
  "Analyze" against the AI model
- **History** — sensor reading history + AI verdict history
- **IMU** — live accelerometer/gyroscope charts + rolling statistics
- **Settings** — configure the device's local IP address/port

## Why Flutter here

The Python backend (`arduino.app_bricks.web_ui`) serves a plain
REST + polling API (see the project README's "REST APIs" table), so
this app is a straightforward native client over `http`, not a
Bluetooth/BLE integration. BLE + true offline pairing is called out
as a future step in `AI_PLAN.md` and can be layered in later without
touching this app's screens.

## Prerequisites

This repo does not vendor the Flutter SDK. Install it once:

```
# macOS
brew install --cask flutter
flutter doctor
```

`flutter doctor` will tell you if you're missing Xcode (iOS) or
Android Studio / an Android SDK (Android) — you only need the
toolchain for the platform(s) you intend to run on.

## First-time setup

This folder ships `pubspec.yaml` and `lib/` but not the generated
native `android/`, `ios/`, `web/` platform folders (those are
machine/SDK-version specific and are `.gitignore`d here). Generate
them once:

```
cd mobile
flutter create --org com.ethanolsensor --project-name fuel_quality_monitor .
flutter pub get
```

`flutter create .` on a directory that already has a `pubspec.yaml`
and `lib/` only adds the missing platform folders — it will not
overwrite the app code in this directory.

## Running

```
cd mobile
flutter devices        # list attached simulators/phones
flutter run             # launch on the selected device
```

On first launch, go to **Settings** and enter the Arduino UNO Q's LAN
IP and port shown by the device (e.g. `192.168.1.50:8000`), then tap
**Save & Test Connection**. Your phone and the board must be on the
same Wi-Fi network.

## Project layout

```
mobile/
├── pubspec.yaml
└── lib/
    ├── main.dart               app entry, providers, theme
    ├── theme.dart              colors matching assets/style.css
    ├── models/                 typed mirrors of the REST JSON shapes
    ├── services/
    │   ├── api_client.dart     REST client for every /api/* endpoint
    │   └── device_connection.dart   persisted device IP (SharedPreferences)
    ├── state/
    │   └── app_state.dart      polling loop + shared app state (Provider)
    ├── screens/                one file per bottom-nav tab
    └── widgets/                shared UI (verdict card, sensor grid, ...)
```

## Known limitations

- Polls REST endpoints on a timer (1 s for sensors/AI/heartbeat, 250 ms
  for IMU while the IMU tab is open) rather than subscribing to the
  WebUI's live WebSocket stream — the WebUI brick's socket framing is
  internal to the Arduino app_bricks package and wasn't reverse-
  engineered for this client. REST polling is the same fallback path
  `assets/app.js` uses when `WebUI.onMessage` isn't available, so
  behavior matches the web dashboard's guaranteed-working path.
- No BLE support yet (see `AI_PLAN.md`'s "BLE + mobile app" line) —
  this app assumes the phone is on the same Wi-Fi network as the board.
