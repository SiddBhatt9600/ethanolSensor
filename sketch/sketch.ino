#include <Arduino_RouterBridge.h>
#if 0     // enable when Accelerometer is present
#include <Arduino_Modulino.h>
#endif

// ModulinoMovement movement;
static int hbCounter = 0;
bool lastState = LOW;
constexpr int buttonPin = 2;
float x_accel, y_accel, z_accel; // Accelerometer values in g

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
  randomSeed(analogRead(A0));
  Bridge.provide_safe("getHbState", getHbState);
  Bridge.provide_safe("getFuelTemp", getFuelTemp);
  Bridge.provide_safe("getethanolPercentage", getethanolPercentage);
  Bridge.provide_safe("getwif", getwif);
  Bridge.provide_safe("getturbidity", getturbidity);
  Bridge.provide_safe("getdensity", getdensity);

  refreshReading();

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

// Only for IMU, accleration measurement and button press
void loop() {
  bool currentState = digitalRead(buttonPin);
  if (currentState == HIGH && lastState == LOW) {
    Serial.println("Button Pressed, recording sensor values");

    Bridge.notify("record_sensor_values");
  }
  lastState = currentState;

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

  // float randomFloat = random(0, 1000001) / 1000000.0;
  // // has_movement = movement.update();
  //   if(1) {
  //     // Get acceleration values

  //     // Change the values later
  //     x_accel = randomFloat;
  //     y_accel = randomFloat;
  //     z_accel = randomFloat;

  //     Bridge.notify("record_sensor_movement", x_accel, y_accel, z_accel);
  //   }
  //   delay(100);
}
