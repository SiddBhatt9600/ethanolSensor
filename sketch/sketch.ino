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
