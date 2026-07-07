#include <Arduino_RouterBridge.h>

static int hbCounter = 0;

void setup() {
  // put your setup code here, to run once:
  Bridge.begin();
  Bridge.provide_safe("getHbState", getHbState);
}

int getHbState() {
  hbCounter++;
  return hbCounter;
}

void loop() {
  
}
