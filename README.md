# Fuel Quality Monitoring System

A modular fuel quality monitoring and vehicle telemetry framework built on the **Arduino UNO Q**, leveraging the dual-processor architecture of the Qualcomm Dragonwing QRB2210 MPU (Debian Linux) and the STM32U585 MCU (Zephyr/Arduino).

The project demonstrates a production-style architecture where the MCU performs real-time sensor acquisition while the Linux MPU handles data logging, visualization, analytics, and external communication through the Arduino Router/Bridge RPC framework.

---

# Features

## Fuel Quality Monitoring

- Fuel Temperature
- Ethanol Percentage
- Fuel Density
- Water-In-Fuel (WIF)
- Turbidity

## Vehicle Telemetry

- BMI323 6-DoF IMU
- 100 Hz Accelerometer Sampling
- 100 Hz Gyroscope Sampling
- Live IMU Dashboard
- Circular 30-minute IMU Buffer
- Background IMU Logging

## System Monitoring

- Heartbeat Monitoring
- Missed Heartbeat Detection
- Background Health Monitoring
- JSON Persistent Logging

## User Interface

- Responsive Web Dashboard
- Live Sensor Cards
- Live Accelerometer Graph
- Live Gyroscope Graph
- Historical Sensor Table
- Button Capture Panel
- Mobile Friendly

## Dashboard

![Dashboard](docs/dashboard.png)

---

# System Architecture

```
                    +-----------------------------------+
                    |         Mobile Browser            |
                    |     Live Dashboard (Chart.js)     |
                    +-----------------+-----------------+
                                      |
                                      |
                                 REST APIs
                               WebSocket (IMU)
                                      |
                                      |
                    +-----------------v-----------------+
                    |        Debian Linux (MPU)          |
                    |------------------------------------|
                    | main.py                            |
                    |                                    |
                    | HbManager                          |
                    | SensorManager                      |
                    | ImuManager                         |
                    | WebUI                              |
                    | JSON Logger                        |
                    +-----------------+------------------+
                                      |
                        Arduino Router / Bridge RPC
                           MessagePack over UART
                                      |
                    +-----------------v-----------------+
                    |         STM32U585 (MCU)           |
                    |-----------------------------------|
                    | Sensor Acquisition                |
                    | BMI323 IMU                        |
                    | Button Monitoring                 |
                    | Bridge.provide_safe() APIs        |
                    +-----------------------------------+
```

---

# Software Architecture

```
main.py

│

├── HbManager

├── SensorManager

├── ImuManager

├── WebUI

└── Arduino Bridge
```

Each manager is responsible for its own acquisition, buffering, logging and REST APIs.

---

# Repository Structure

```
.
├── python
│   ├── main.py
│   ├── hbManager.py
│   ├── sensorManager.py
│   └── imuManager.py
│
├── assets
│   ├── index.html
│   ├── app.js
│   └── style.css
│
├── sketch
│   ├── sketch.ino
│   └── sketch.yaml
│
├── sensor_history.json
├── sensor_history_button.json
├── hb_history.json
├── imu_history.json
│
├── app.yaml
└── README.md
```

---

# Managers

## HbManager

Responsibilities

- Heartbeat polling
- Heartbeat monitoring
- Missed heartbeat detection
- JSON logging
- Rolling heartbeat history

Output

```
hb_history.json
```

---

## SensorManager

Responsibilities

- Polls all fuel sensors every 10 seconds
- Stores latest readings
- Rolling sensor history
- Button-triggered sensor capture
- Calculates average of five samples
- Persistent JSON logging

Outputs

```
sensor_history.json

sensor_history_button.json
```

---

## ImuManager

Responsibilities

- Receives live BMI323 data over Bridge RPC
- Stores samples in a circular RAM buffer
- Maintains last 30 minutes of data
- Periodically flushes to JSON
- Live WebSocket streaming
- Statistics generation
- Historical retrieval

Output

```
imu_history.json
```

---

# Bridge RPC APIs

## MCU → Linux

| RPC Method | Description |
|------------|-------------|
| record_sensor_values | Trigger button capture |
| record_imu_values | Send IMU sample |

---

## Linux → MCU

| RPC Method | Description |
|------------|-------------|
| getHbState | Heartbeat |
| getFuelTemp | Fuel Temperature |
| getethanolPercentage | Ethanol Percentage |
| getwif | Water In Fuel |
| getturbidity | Turbidity |
| getdensity | Fuel Density |

---

# REST APIs

| Endpoint | Description |
|----------|-------------|
| /api/sensors | Last 10 fuel sensor readings |
| /api/button_capture | Latest button capture |
| /api/imu_capture | Latest IMU samples |
| /api/imu_history | Last 30 minutes of IMU data |
| /api/imu_statistics | IMU statistics |
| /api/heartbeat | Heartbeat status |

---

# Web Dashboard

The dashboard is served directly from the Arduino UNO Q and includes:

- Live connection status
- Heartbeat monitor
- Fuel quality cards
- Live accelerometer chart
- Live gyroscope chart
- Live sensor history
- Button capture history
- Averaged sensor values
- Event log

The dashboard is responsive and can be accessed from desktop and mobile devices connected to the same network.

---

# Current Status

## Implemented

- Arduino Router / Bridge RPC
- Modular manager architecture
- Heartbeat monitoring
- Fuel sensor acquisition
- BMI323 integration
- Circular IMU buffer
- JSON persistence
- Web Dashboard
- Chart.js visualization
- Mobile dashboard
- REST APIs
- Background workers
- Thread-safe acquisition

---

# Planned Features

- MQTT publishing
- BLE companion application
- OTA firmware updates
- Fuel quality anomaly detection
- Crash detection
- Vehicle tilt detection
- Harsh braking detection
- Road roughness estimation
- Sensor calibration
- Data export (CSV/JSON)
- Historical playback
- Cloud synchronization

---

# Technologies

- Arduino UNO Q
- Qualcomm Dragonwing QRB2210
- STM32U585
- Debian Linux
- Arduino Router / Bridge
- MessagePack RPC
- Python 3
- HTML5
- CSS3
- JavaScript
- Chart.js
- JSON
- Multithreading

---

# License

MIT License