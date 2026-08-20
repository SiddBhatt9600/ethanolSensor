# AI Layer — Plan & Status
### Fuel Quality Monitor · Arduino UNO Q (QRB2210 + STM32U585)
Owner: Sulagna · Updated: 11 Jul 2026 · Deadline: 31 Jul 2026

---

## What the AI does

1. **Fuel quality classification** (DONE, v1): fuses ethanol %, WIF,
   turbidity, density, temperature into GOOD / SUSPECT / ADULTERATED
   with confidence + plain-language reasons. MLP 6-16-16-3,
   435 parameters, 94.2% test accuracy, <1 ms inference on the A53.
   The physics feature is the differentiator: density is
   temperature-corrected to 15 °C and compared against the density
   physics predicts for the measured ethanol % — the residual exposes
   kerosene/solvent dilution that no single raw sensor shows.

2. **Anomaly / refuel-drift detection** (DONE, v1): rolling z-score
   over the last 30 readings per parameter. Catches quality *shifts*
   after refuelling — including moderate kerosene cuts whose absolute
   density still looks plausible (documented limitation of any
   snapshot method; this is our mitigation).

3. **Driver behavior scoring from BMI323** (NEXT): windows of
   accel+gyro → smooth / harsh brake / harsh accel / rash cornering.
   Blocked on IMU data reaching the MPU (Turjasu/Siddhartha).

## Status

| Item | State |
|---|---|
| Physics-based data simulator | Done (`fuel_simulator.py`) |
| Feature engineering (shared train/serve) | Done (`features.py`) |
| Classifier trained + evaluated | Done (94.2%, `metrics.txt`) |
| Portable weights (numpy-only, no TFLite needed) | Done (`model_weights.json`) |
| On-device inference module | Done (`fuelQualityModel.py`) |
| AiManager thread + JSON logging + REST | Done (`aiManager.py`) |
| main.py integration | Done (12 Jul, endpoints live) |
| Web dashboard AI panel | Done (verdict card, history, spot check) |
| Scenario-coherent MCU simulation | Done (sketch rotates GOOD/SUSPECT/ADULTERATED) |
| Offline test suite | Done (`test_ai.py`, 34 checks) |
| Board-free full-stack demo | Done (`local_demo.py`) |
| Board validation | Pending (needs UNO Q, ~30 min) |
| Real-fuel calibration + retrain | Pending (needs sensors + petrol) |
| BLE + mobile app | Next week |
| Driver behavior model | Next week (blocked on IMU) |

## Why numpy instead of TFLite

The QRB2210 has no NPU; inference runs on the A53 CPUs either way.
A 435-parameter MLP runs in microseconds in plain numpy, ships as a
readable JSON file, needs zero runtime installation, and retrains in
seconds when calibration data arrives. TFLite adds install friction
for no benefit at this model size. (If the driver-behavior CNN grows,
that one can go to TFLite — decision deferred until it exists.)

## Known limitations (be upfront in submission — judges reward this)

* Trained on physics-simulated data until real calibration samples
  exist. The simulator encodes real fuel physics (BIS density bands,
  ethanol-water phase behavior, kerosene density), but sensor-specific
  response curves need real measurements. Plan: collect labelled
  captures via the button-capture flow, retrain (seconds), reship JSON.
* Low-dose kerosene (<~15%) into mid-band petrol is inside the clean
  density envelope — undetectable from a snapshot by ANY method with
  these sensors. Mitigated by refuel-drift anomaly detection.
* Ethanol sensor is the anchor input; its calibration quality bounds
  overall accuracy.

## Timeline to deadline (Jul 31)

**Week of Jul 13 (integration week)**
- [ ] Merge AI layer into repo, run on the UNO Q, measure real
      inference latency + CPU/RAM (30 min once board is available)
- [ ] Fix MCU sketch simulated values to be scenario-coherent
      (see INTEGRATION.md note) so demos make sense pre-sensors
- [ ] Start BLE GATT server (BlueZ) exposing /api/ai/current data
- [ ] IMU data path agreed with Siddhartha (window size, rate)

**Week of Jul 20 (real data week)**
- [ ] Sensors arrive → calibration protocol: known-good petrol
      baseline, then measured water spikes, measured particulates,
      E10/E20 references. Log every sample via button capture.
- [ ] Retrain on real captures mixed with simulator data; publish
      new metrics
- [ ] Driver behavior classifier v1 (UAH-DriveSet pretrain +
      board-in-hand shake/drive calibration)
- [ ] Mobile app: React PWA + Web Bluetooth (fastest polished path)

**Week of Jul 27 (submission week)**
- [ ] 24 h soak test — uptime, memory, thermal (endurance claim)
- [ ] Demo video: live water-drip test flipping the verdict on
      camera + drive test flipping driver score
- [ ] Write-up: architecture, physics features, metrics, honest
      limitations, drift mitigation story

## File map

```
python/
├── features.py          shared feature engineering (train == serve)
├── fuel_simulator.py    physics data generator (training only)
├── train_model.py       training + eval + JSON export (dev machine)
├── model_weights.json   the model (ship to board)
├── fuelQualityModel.py  numpy inference + explanations
├── aiManager.py         worker thread, anomaly detect, REST, logging
├── metrics.txt          accuracy + confusion matrix
└── INTEGRATION.md       10-line main.py patch
```
