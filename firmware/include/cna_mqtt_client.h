#pragma once
#include <Arduino.h>

void mqttBegin();
void mqttPublishTemperature(float value);
void mqttPublishTelemetry(float temperature, float humidity, bool motion,
                          bool accessOpen, bool tamperActive, const char* state);
void mqttPublishState(const char* state);
void mqttPublishEvent(const char* eventName);
char mqttTakeCommand();
