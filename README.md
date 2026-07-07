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
                    | JSON Logger                     |
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

---

## Repository Structure

```
.
├── python
│   ├── main.py
│   ├── hbManager.py
│   └── sensorManager.py
│
├── sketch
│   ├── sketch.ino
│   └── sketch.yaml
│
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
