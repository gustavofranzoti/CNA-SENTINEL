#pragma once

#include <stdint.h>

namespace Config {
#if defined(CNA_ZONE_Z1) == defined(CNA_ZONE_Z2)
#error "Defina exatamente uma macro de zona: CNA_ZONE_Z1 ou CNA_ZONE_Z2"
#endif

#if defined(CNA_ZONE_Z1)
constexpr char ZONE_ID[] = "Z1";
#else
constexpr char ZONE_ID[] = "Z2";
#endif
constexpr unsigned long SERIAL_BAUD_RATE = 115200;

namespace Pins {
constexpr uint8_t PIR = 27;
constexpr uint8_t ACCESS = 26;
constexpr uint8_t TAMPER = 25;
constexpr uint8_t DHT = 4;
constexpr uint8_t RGB_RED = 16;
constexpr uint8_t RGB_GREEN = 17;
constexpr uint8_t RGB_BLUE = 18;
constexpr uint8_t BUZZER = 19;
constexpr uint8_t LCD_RS = 13;
constexpr uint8_t LCD_E = 14;
constexpr uint8_t LCD_D4 = 21;
constexpr uint8_t LCD_D5 = 22;
constexpr uint8_t LCD_D6 = 23;
constexpr uint8_t LCD_D7 = 32;
}  // namespace Pins

constexpr uint32_t DEBOUNCE_MS = 30;
constexpr uint32_t SERIAL_INTERVAL_MS = 1000;
constexpr uint32_t DHT_INTERVAL_MS = 2500;
constexpr float ATTENTION_TEMPERATURE_C = 35.0f;
constexpr float CRITICAL_TEMPERATURE_C = 45.0f;
constexpr uint32_t ALERT_COMBINATION_WINDOW_MS = 10000;
constexpr uint32_t BUZZER_DURATION_MS = 300;
constexpr uint32_t BUZZER_FREQUENCY_HZ = 2000;
constexpr uint32_t ALARM_BEEP_ON_MS = 250;
constexpr uint32_t ALARM_BEEP_OFF_MS = 750;
constexpr uint8_t BUZZER_CHANNEL = 0;
}  // namespace Config
