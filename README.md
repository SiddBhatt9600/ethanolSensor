# Ethanol Sensor Data Acquisition Framework

An Arduino UNO Q based sensor acquisition framework for monitoring fuel quality and system health using the Arduino Router/Bridge RPC framework.

The project demonstrates communication between the Qualcomm QRB2210 MPU (Debian Linux) and the STM32U585 MCU through the Arduino Bridge API. The MCU exposes sensor APIs over RPC while the Linux application periodically polls the data, stores it as JSON and prepares it for higher-level processing.

---

## Architecture

```
                        +-------------------------+
                        |      Mobile / Cloud     |
                        +------------+------------+
                                     |
                                     |
                          Future BLE / MQTT / REST
                                     |
                                     |
                    +----------------v----------------+
                    |      Debian Linux (MPU)         |
                    |---------------------------------|
                    | Python Application              |
                    |                                 |
                    | HbManager                       |
                    | SensorManager                   |
                    | AiManager (fuel quality MLP +   |
                    |            drift detection)     |
                    | JSON Logger                     |
                    | Web Dashboard + REST APIs       |
                    +----------------+----------------+
                                     |
                           Arduino Router / Bridge
                                     |
                           MessagePack RPC
                                     |
                    +----------------v----------------+
                    |        STM32U585 (MCU)          |
                    |---------------------------------|
                    | Bridge.provide_safe() APIs      |
                    |                                 |
                    | Heartbeat                       |
                    | Fuel Temperature                |
                    | Ethanol Percentage              |
                    | Water In Fuel                   |
                    | Turbidity                       |
                    | Density                         |
                    +---------------------------------+
```

---

## Current Features

- Heartbeat monitoring
- Fuel temperature acquisition
- Ethanol percentage acquisition
- Water-In-Fuel (WIF) acquisition
- Turbidity acquisition
- Density acquisition
- Background polling using Python threads
- JSON based persistent logging
- Sliding window logging (1000 records)
- **AI fuel quality classification** (GOOD / SUSPECT / ADULTERATED)
  with confidence, probabilities and plain-language explanations
- **Physics-based feature engineering**: density is temperature
  corrected to 15 °C and compared against the density physics
  predicts for the measured ethanol % — the residual exposes
  kerosene / solvent dilution that no single raw sensor shows
- **Refuel-drift anomaly detection** (rolling z-score over the
  last 30 readings per parameter)
- Web dashboard with live AI verdict card, verdict history and
  on-demand analysis of button captures

---

## Repository Structure

```
.
├── python
│   ├── main.py              app entry: managers + REST APIs
│   ├── hbManager.py         heartbeat monitor
│   ├── sensorManager.py     sensor polling + button capture
│   ├── aiManager.py         AI worker thread + drift detection
│   ├── fuelQualityModel.py  numpy MLP inference + explanations
│   ├── features.py          shared feature engineering (train==serve)
│   ├── model_weights.json   trained model (6-16-16-3, 435 params)
│   ├── fuel_simulator.py    physics data generator (training)
│   ├── train_model.py       training + JSON export (dev machine)
│   ├── metrics.txt          accuracy + confusion matrix
│   ├── test_ai.py           AI test suite (numpy only)
│   └── local_demo.py        full-stack demo without the board
│
├── assets
│   ├── index.html           web dashboard
│   ├── app.js
│   └── style.css
│
├── sketch
│   ├── sketch.ino
│   └── sketch.yaml
│
├── AI_PLAN.md               AI layer plan & status
├── INTEGRATION.md           AI integration notes
├── hb_history.json
├── sensor_history.json
├── app.yaml
└── README.md
```

---

## Components

### Arduino Sketch

The MCU exposes RPC endpoints using the Arduino Bridge library.

Current RPC methods:

| Function | Description |
|----------|-------------|
| getHbState | Returns heartbeat counter |
| getFuelTemp | Returns fuel temperature |
| getethanolPercentage | Returns ethanol percentage |
| getwif | Returns Water-In-Fuel value |
| getturbidity | Returns turbidity value |
| getdensity | Returns fuel density |

Currently these APIs return simulated values for software development and integration.

---

### HbManager

Responsibilities:

- Periodically requests heartbeat from MCU
- Detects missed heartbeats
- Logs heartbeat history
- Maintains last known heartbeat
- Stores latest 1000 records

Output:

```
hb_history.json
```

Example:

```json
{
    "timestamp": "...",
    "heartbeat": 123,
    "missed_hb": 0
}
```

---

### SensorManager

Responsibilities:

- Reads all available fuel sensor values
- Maintains in-memory sensor cache
- Logs sensor data periodically
- Stores latest 1000 samples

Sensors:

- Fuel Temperature
- Ethanol Percentage
- Water-In-Fuel
- Turbidity
- Density

Output:

```
sensor_history.json
```

---

## Current Communication Flow

```
STM32

Bridge.provide_safe()

↓

Arduino Router

↓

Python Bridge.call()

↓

HbManager / SensorManager

↓

JSON Logger
```

---

### AiManager (AI Layer)

Responsibilities:

- Scores every continuous reading with a 435-parameter MLP
  (GOOD / SUSPECT / ADULTERATED) in <1 ms, numpy only
- Physics feature: density temperature-corrected to 15 °C compared
  against the density expected for the measured ethanol % — the
  residual exposes kerosene/solvent dilution
- Refuel-drift anomaly detection (rolling z-score, 30-reading window)
- Plain-language explanations for the dashboard / app UI
- On-demand scoring of button captures

REST endpoints (exposed via the WebUI brick):

| Endpoint | Description |
|----------|-------------|
| /api/ai/current | Latest verdict (status card) |
| /api/ai/verdicts | Last 10 verdicts |
| /api/ai/capture_verdict | Scores the latest button capture |

Output:

```
ai_history.json
```

Model: trained on a physics-grounded simulator
(`fuel_simulator.py`), 94.2% test accuracy (`metrics.txt`).
Retraining on real calibration data takes seconds:
`python3 train_model.py` regenerates `model_weights.json`.

---

## Testing

Offline AI test suite (needs only numpy):

```
cd python
python3 test_ai.py
```

Full-stack demo without the UNO Q (real SensorManager + AiManager
against a mock bridge, real dashboard at http://localhost:8000):

```
cd python
python3 local_demo.py
```

---

## Technologies Used

- Arduino UNO Q
- Arduino Router / Bridge
- Python 3
- MessagePack RPC
- Debian Linux
- JSON
- Multithreading

---

## Current Status

Implemented

- Heartbeat monitoring
- RPC communication
- Sensor polling
- Background worker threads
- JSON logging
- Rolling log buffer

Work In Progress

- Actual sensor integration
- IMU support
- BLE interface
- Mobile application
- Health monitoring
- Recovery mechanism
- Diagnostics

---

## Future Improvements

- Replace polling with event-driven architecture
- Introduce central Event Queue
- Sensor abstraction layer
- Cloud synchronization
- Sensor calibration
- Automatic recovery on MCU timeout
- Web dashboard
- Data visualization
- Historical analytics

---

## License

MIT License
