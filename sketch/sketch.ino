#include <Arduino_RouterBridge.h>
#if 0     // enable when Accelerometer is present
#include <Arduino_Modulino.h>
#endif

// ModulinoMovement movement;
static int hbCounter = 0;
float x_accel, y_accel, z_accel; // Accelerometer values in g

void setup() {
  // put your setup code here, to run once:
  Bridge.begin();
  randomSeed(analogRead(A0)); 
  Bridge.provide_safe("getHbState", getHbState);
  Bridge.provide_safe("getFuelTemp", getFuelTemp);
  Bridge.provide_safe("getethanolPercentage", getethanolPercentage);
  Bridge.provide_safe("getwif", getwif);
  Bridge.provide_safe("getturbidity", getturbidity);
  Bridge.provide_safe("getdensity", getdensity);

#if 0     // enable when Accelerometer is present
  // Initialize Modulino I2C communication
  Modulino.begin(Wire1);

  // Detect and connect to movement sensor module
  while (!movement.begin()) {
    delay(1000);
  }
#endif
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

// Only for IMU, accleration measurement
void loop() {
  float randomFloat = random(0, 1000001) / 1000000.0;
  // has_movement = movement.update();
    if(1) {
      // Get acceleration values

      // Change the values later
      x_accel = randomFloat;
      y_accel = randomFloat;
      z_accel = randomFloat;
    
      Bridge.notify("record_sensor_movement", x_accel, y_accel, z_accel);
    }
    delay(100);
}
