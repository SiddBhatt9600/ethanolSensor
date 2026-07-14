#include <Arduino_RouterBridge.h>
#include <Wire.h>

#define BMI323_ADDR 0x68

#define BMI323_CHIP_ID_REG  0x00
#define BMI323_ACC_X_REG    0x03
#define BMI323_GYR_X_REG    0x06
#define BMI323_ACC_CONF_REG 0x20
#define BMI323_GYR_CONF_REG 0x21

#define TURBIDITY_PIN A0
#define DS18B20_PIN   7

#define ADC_REF_VOLTAGE 3.3f
#define ADC_MAX_COUNTS  4095.0f

static int hbCounter = 0;
bool lastState = LOW;
constexpr int buttonPin = 2;

// ---------------- OneWire low-level functions ----------------

void ow_drive_low() {
  pinMode(DS18B20_PIN, OUTPUT);
  digitalWrite(DS18B20_PIN, LOW);
}

void ow_release() {
  pinMode(DS18B20_PIN, INPUT_PULLUP);
}

bool ow_reset() {
  ow_drive_low();
  delayMicroseconds(480);

  ow_release();
  delayMicroseconds(70);

  bool presence = !digitalRead(DS18B20_PIN);

  delayMicroseconds(410);

  return presence;
}

void ow_write_bit(uint8_t bitVal) {
  if (bitVal) {
    ow_drive_low();
    delayMicroseconds(6);
    ow_release();
    delayMicroseconds(64);
  } else {
    ow_drive_low();
    delayMicroseconds(60);
    ow_release();
    delayMicroseconds(10);
  }
}

uint8_t ow_read_bit() {
  uint8_t bitVal;

  ow_drive_low();
  delayMicroseconds(6);
  ow_release();
  delayMicroseconds(9);

  bitVal = digitalRead(DS18B20_PIN);

  delayMicroseconds(55);

  return bitVal;
}

void ow_write_byte(uint8_t data) {
  for (int i = 0; i < 8; i++) {
    ow_write_bit(data & 0x01);
    data >>= 1;
  }
}

uint8_t ow_read_byte() {
  uint8_t data = 0;

  for (int i = 0; i < 8; i++) {
    if (ow_read_bit()) {
      data |= (1 << i);
    }
  }

  return data;
}

// 16-bit register write, little-endian
void writeReg16(uint8_t reg, uint16_t value) {
  Wire.beginTransmission(BMI323_ADDR);
  Wire.write(reg);
  Wire.write(value & 0xFF);        // LSB
  Wire.write((value >> 8) & 0xFF); // MSB
  byte err = Wire.endTransmission();

  if (err != 0) {
    Serial.print("Write failed reg 0x");
    Serial.print(reg, HEX);
    Serial.print(" err=");
    Serial.println(err);
  }
}

// BMI323 I2C read: first 2 bytes are dummy, then actual data
uint16_t readReg16(uint8_t reg) {
  Wire.beginTransmission(BMI323_ADDR);
  Wire.write(reg);
  byte err = Wire.endTransmission();

  if (err != 0) {
    Serial.print("Reg addr write failed 0x");
    Serial.print(reg, HEX);
    Serial.print(" err=");
    Serial.println(err);
    return 0xFFFF;
  }

  delayMicroseconds(500);

  int n = Wire.requestFrom(BMI323_ADDR, 4);
  if (n != 4) {
    Serial.print("Read failed reg 0x");
    Serial.print(reg, HEX);
    Serial.print(" bytes=");
    Serial.println(n);
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

// ---------------- DS18B20 read ----------------
// Why do we need to keep this one specifically before 
// setup? It makes no sense.......
// Others getValues works just fine being after setup
float readDS18B20TempC() {
  if (!ow_reset()) {
    return NAN;
  }

  ow_write_byte(0xCC); // Skip ROM, for single DS18B20 on bus
  ow_write_byte(0x44); // Convert T

  // 12-bit conversion needs up to 750 ms
  delay(750);

  if (!ow_reset()) {
    return NAN;
  }

  ow_write_byte(0xCC); // Skip ROM
  ow_write_byte(0xBE); // Read scratchpad

  uint8_t temp_lsb = ow_read_byte();
  uint8_t temp_msb = ow_read_byte();

  int16_t rawTemp = ((int16_t)temp_msb << 8) | temp_lsb;

  return rawTemp / 16.0f;
}

// I will keep this before setup as well
// JUST IN CASE
int readTurbidityRaw() {
  return analogRead(TURBIDITY_PIN);
}

float rawToVoltage(int raw) {
  return ((float)raw * ADC_REF_VOLTAGE) / ADC_MAX_COUNTS;
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
  analogReadResolution(12);
  pinMode(TURBIDITY_PIN, INPUT);
  pinMode(DS18B20_PIN, INPUT_PULLUP);

  uint16_t chip = readReg16(BMI323_CHIP_ID_REG);
  Serial.print("CHIP_ID = 0x");
  Serial.println(chip, HEX);

  setupBMI323();

  Serial.println("BMI323 configured");
  Serial.println("----------------------");

  randomSeed(analogRead(A0)); 
  Bridge.provide_safe("getHbState", getHbState);
  // Bridge.provide_safe("getFuelTemp", getFuelTemp);
  Bridge.provide_safe("readDS18B20TempC", readDS18B20TempC);
  Bridge.provide_safe("getethanolPercentage", getethanolPercentage);
  Bridge.provide_safe("getwif", getwif);
  // Bridge.provide_safe("getturbidity", getturbidity);
  Bridge.provide_safe("readTurbidityRaw", readTurbidityRaw);
  Bridge.provide_safe("getdensity", getdensity);

  Bridge.provide_safe("poll_sensors", poll_sensors);

  Serial.println("MCU ready: Turbidity + DS18B20 polling");
  Serial.println("MPU can call: poll_sensors");
}

// ---------------- Turbidity read ----------------

String poll_sensors() {
  uint32_t t_ms = millis();

  int turb_raw = readTurbidityRaw();
  float turb_v = rawToVoltage(turb_raw);

  float temp_c = readDS18B20TempC();

  String out = "";

  out += "t_ms,turb_raw,turb_v,temp_c\n";
  out += String(t_ms);
  out += ",";
  out += String(turb_raw);
  out += ",";
  out += String(turb_v, 3);
  out += ",";

  if (isnan(temp_c)) {
    out += "nan";
  } else {
    out += String(temp_c, 2);
  }

  out += "\n";

  return out;
}

int getHbState() {
  hbCounter++;
  return hbCounter;
}

int getFuelTemp() {
  int randomFloat = random(20, 70);
  int fuelTemp = randomFloat;
  return fuelTemp;
}

int getethanolPercentage() {
  int randomFloat = random(0, 100);
  int ehtPer = randomFloat;
  return ehtPer;
}

int getwif() {
  int randomFloat = random(0, 100);
  int wifVal = randomFloat;
  return wifVal;
}

int getturbidity() {
  int randomFloat = random(0, 100);
  int turbidityVal = randomFloat;
  return turbidityVal;
}

float getdensity() {
  float randomFloat = random(700000, 800000) / 1000.0;
  float densityVal = randomFloat;
  return densityVal;
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
    delay(100);
}
