#include <Arduino.h>

// ELEGOO ESP-32 USB-Cの基板上LED。
constexpr uint8_t kLedPin = 2;

void setup() {
    pinMode(kLedPin, OUTPUT);
}

void loop() {
    digitalWrite(kLedPin, HIGH);
    delay(500);
    digitalWrite(kLedPin, LOW);
    delay(500);
}
