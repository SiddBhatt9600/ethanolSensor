#include <Arduino_RouterBridge.h>
#include <Wire.h>

#define BMI323_ADDR 0x68

#define BMI323_CHIP_ID_REG  0x00
#define BMI323_ACC_X_REG    0x03
#define BMI323_GYR_X_REG    0x06
#define BMI323_ACC_CONF_REG 0x20
#define BMI323_GYR_CONF_REG 0x21

static int hbCounter = 0;
bool lastState = LOW;
constexpr int buttonPin = 2;

// 16-bit register write, little-endian
void writeReg16(uint8_t reg, uint16_t value) {
  Wire.beginTransmission(BMI323_ADDR);
  Wire.write(reg);
  Wire.write(value & 0xFF);        // LSB
  Wire.write((value >> 8) & 0xFF); // MSB
  byte err = Wire.endTransmission();

  if (err != 0) {
    Monitor.print("Write failed reg 0x");
    Monitor.print(reg, HEX);
    Monitor.print(" err=");
    Monitor.println(err);
  }
}

// BMI323 I2C read: first 2 bytes are dummy, then actual data
uint16_t readReg16(uint8_t reg) {
  Wire.beginTransmission(BMI323_ADDR);
  Wire.write(reg);
  byte err = Wire.endTransmission();

  if (err != 0) {
    Monitor.print("Reg addr write failed 0x");
    Monitor.print(reg, HEX);
    Monitor.print(" err=");
    Monitor.println(err);
    return 0xFFFF;
  }

  delayMicroseconds(500);

  int n = Wire.requestFrom(BMI323_ADDR, 4);
  if (n != 4) {
    Monitor.print("Read failed reg 0x");
    Monitor.print(reg, HEX);
    Monitor.print(" bytes=");
    Monitor.println(n);
    return 0xFFFF;
  }

  Wire.read(); // dummy LSB
  Wire.read(); // dummy MSB

  uint8_t lsb = Wire.read();
  uint8_t msb = Wire.read();

  return ((uint16_t)msb << 8) | lsb;
}

int16_t readSigned16(uint8_t reg) {
  return (int16_t)readReg16(reg);
}

void setupBMI323() {
  // ACC_CONF:
  // ODR = 100 Hz, range = ±8g, bandwidth ODR/2, averaging default-ish, mode continuous
  // Based on BMI323 config bit layout: ODR bits 3:0, range bits 6:4, BW bit 7, mode bits 14:12.
  uint16_t accConf = 0;
  accConf |= 0x08;        // ODR index for 100 Hz
  accConf |= (0x02 << 4); // ±8g range index
  accConf |= (0x04 << 12);// continuous mode
  writeReg16(BMI323_ACC_CONF_REG, accConf);

  delay(10);

  // GYR_CONF:
  // ODR = 100 Hz, range = ±500 dps, bandwidth ODR/2, mode continuous
  uint16_t gyrConf = 0;
  gyrConf |= 0x08;        // ODR index for 100 Hz
  gyrConf |= (0x02 << 4); // ±500 dps range index
  gyrConf |= (0x04 << 12);// continuous mode
  writeReg16(BMI323_GYR_CONF_REG, gyrConf);

  delay(50);
}

// ==================================================================
// Simulated fuel scenario (until real sensors arrive)
//
// The Python AI layer fuses all five values, so they must be
// physically coherent, not independent randoms. One scenario is
// picked and all five values are derived from it, mirroring the
// physics in python/fuel_simulator.py:
//
//   rho15   = (1-e-k-w)*petrol + e*789.4 + k*805 + w*998
//   density = rho15 - 0.85 * (temp - 15)
//
// The scenario rotates GOOD -> SUSPECT -> ADULTERATED every 90 s
// so the dashboard demo shows every verdict and the refuel-drift
// anomaly detector fires on each transition.
// ==================================================================

enum FuelScenario { FUEL_GOOD, FUEL_SUSPECT, FUEL_ADULTERATED };

constexpr unsigned long SCENARIO_MS = 90000;   // scenario rotation
constexpr unsigned long READING_MS  = 2000;    // reading refresh

FuelScenario scenario = FUEL_GOOD;
unsigned long lastScenarioMs = 0;
unsigned long lastReadingMs  = 0;

int   simTemp      = 30;
int   simEthanol   = 10;
int   simWif       = 2;
int   simTurbidity = 3;
float simDensity   = 745.0;

float frand(float lo, float hi) {
  return lo + (hi - lo) * (random(0, 10001) / 10000.0);
}

void refreshReading() {
  float temp     = frand(24, 42);
  float petrol15 = frand(735, 762);   // base petrol density (BIS band)
  float ethanol, wif, turbidity;
  float kerosene = 0.0, water = 0.0;

  switch (scenario) {

    case FUEL_GOOD:
      // clean E10 / E20 pump blend
      ethanol   = (random(0, 2) == 0) ? frand(9, 11) : frand(18, 22);
      wif       = frand(0, 4);
      turbidity = frand(0, 6);
      break;

    case FUEL_SUSPECT:
      // dissolved water near phase separation, slight haze
      ethanol   = frand(10, 22);
      water     = frand(0.004, 0.009);
      wif       = frand(9, 20);
      turbidity = frand(5, 14);
      break;

    default:  // FUEL_ADULTERATED
      if (random(0, 2) == 0) {
        // kerosene cut: density rises, everything else looks clean
        ethanol   = frand(0, 12);
        kerosene  = frand(0.15, 0.32);
        wif       = frand(0, 6);
        turbidity = frand(0, 10);
      } else {
        // free water / phase separation
        ethanol   = frand(8, 22);
        water     = frand(0.02, 0.05);
        wif       = frand(35, 90);
        turbidity = frand(25, 65);
      }
      break;
  }

  float e     = ethanol / 100.0;
  float rho15 = (1.0 - e - kerosene - water) * petrol15
              + e * 789.4
              + kerosene * 805.0
              + water * 998.0;

  simTemp      = (int)(temp + 0.5);
  simEthanol   = (int)(ethanol + 0.5);
  simWif       = (int)(wif + 0.5);
  simTurbidity = (int)(turbidity + 0.5);
  simDensity   = rho15 - 0.85 * (temp - 15.0);
}

void setup() {
  // put your setup code here, to run once:
  pinMode(buttonPin, INPUT);
  Serial.begin(9600);
  Bridge.begin();

  delay(2000);

  Wire.begin();
  Wire.setClock(100000);
  Serial.println("BMI323 accel/gyro read test");

  uint16_t chip = readReg16(BMI323_CHIP_ID_REG);
  Serial.print("CHIP_ID = 0x");
  Serial.println(chip, HEX);

  setupBMI323();

  Serial.println("BMI323 configured");
  Serial.println("----------------------");

  randomSeed(analogRead(A0));
  Bridge.provide_safe("getHbState", getHbState);
  Bridge.provide_safe("getFuelTemp", getFuelTemp);
  Bridge.provide_safe("getethanolPercentage", getethanolPercentage);
  Bridge.provide_safe("getwif", getwif);
  Bridge.provide_safe("getturbidity", getturbidity);
  Bridge.provide_safe("getdensity", getdensity);

  refreshReading();
}

int getHbState() {
  hbCounter++;
  return hbCounter;
}

int getFuelTemp() {
  return simTemp;
}

int getethanolPercentage() {
  return simEthanol;
}

int getwif() {
  return simWif;
}

int getturbidity() {
  return simTurbidity;
}

float getdensity() {
  // small per-call jitter so button-capture averaging is visible
  return simDensity + frand(-0.5, 0.5);
}


void loop() {
    int16_t ax = readSigned16(BMI323_ACC_X_REG);
    int16_t ay = readSigned16(BMI323_ACC_X_REG + 1);
    int16_t az = readSigned16(BMI323_ACC_X_REG + 2);

    int16_t gx = readSigned16(BMI323_GYR_X_REG);
    int16_t gy = readSigned16(BMI323_GYR_X_REG + 1);
    int16_t gz = readSigned16(BMI323_GYR_X_REG + 2);

    Bridge.notify("record_imu_values", ax, ay, az, gx, gy, gz);

    bool currentState = digitalRead(buttonPin);
    if (currentState == HIGH && lastState == LOW) {
        Serial.println("Button Pressed, recording sensor values");
        Bridge.notify("record_sensor_values");
    }
    lastState = currentState;

    // Rotate the simulated fuel scenario and refresh the reading
    unsigned long now = millis();

    if (now - lastScenarioMs >= SCENARIO_MS) {
        lastScenarioMs = now;
        scenario = (FuelScenario)(((int)scenario + 1) % 3);
        Serial.print("Fuel scenario -> ");
        Serial.println(scenario == FUEL_GOOD ? "GOOD"
                       : scenario == FUEL_SUSPECT ? "SUSPECT"
                       : "ADULTERATED");
    }

    if (now - lastReadingMs >= READING_MS) {
        lastReadingMs = now;
        refreshReading();
    }

    delay(100);
}
