#include <Arduino.h>
#include <DHT.h>
#include <LiquidCrystal.h>
#include <math.h>

#include "config.h"
#include "cna_mqtt_client.h"

namespace {
using namespace Config;

enum class LocalState { NORMAL, ATENCAO, ALERTA, CRITICO };

struct StateContext {
    LocalState current = LocalState::NORMAL;
    bool armed = true;
    bool alertLatched = false;
    bool criticalLatched = false;
    bool alertAcknowledged = false;
    bool criticalAcknowledged = false;
    bool alarmOutputOn = false;
    uint32_t lastPirEvent = 0;
    uint32_t lastAccessOpenEvent = 0;
    uint32_t lastAlarmPhaseChange = 0;
    bool previousCriticalCondition = false;
};

DHT dht(Pins::DHT, DHT22);
LiquidCrystal lcd(Pins::LCD_RS, Pins::LCD_E, Pins::LCD_D4, Pins::LCD_D5,
                  Pins::LCD_D6, Pins::LCD_D7);

// Armazena somente niveis eletricos para filtrar o contato mecanico.
struct DebouncedInput {
    uint8_t pin;
    bool stable = HIGH;
    bool candidate = HIGH;
    uint32_t changedAt = 0;

    explicit DebouncedInput(uint8_t inputPin) : pin(inputPin) {}

    void begin() {
        pinMode(pin, INPUT_PULLUP);
        stable = candidate = digitalRead(pin);
    }

    bool update(uint32_t now) {
        const bool reading = digitalRead(pin);
        if (reading != candidate) {
            candidate = reading;
            changedAt = now;
        }
        if (candidate != stable && now - changedAt >= DEBOUNCE_MS) {
            stable = candidate;
            return true;
        }
        return false;
    }
};

DebouncedInput accessInput{Pins::ACCESS};
DebouncedInput tamperInput{Pins::TAMPER};
bool motionDetected = false;
bool climateAttempted = false;
bool climateValid = false;
struct ClimateReading {
    float temperature = NAN;
    float humidity = NAN;
};
ClimateReading climate;
uint32_t lastClimateRead = 0;
uint32_t lastSerialReport = 0;
bool buzzerActive = false;
uint32_t buzzerStartedAt = 0;
StateContext stateContext;

void setRgb(bool red, bool green, bool blue) {
    // Catodo comum: HIGH acende cada canal, sem PWM.
    digitalWrite(Pins::RGB_RED, red);
    digitalWrite(Pins::RGB_GREEN, green);
    digitalWrite(Pins::RGB_BLUE, blue);
}

const char* stateName(LocalState state) {
    switch (state) {
        case LocalState::ATENCAO: return "ATENCAO";
        case LocalState::ALERTA: return "ALERTA";
        case LocalState::CRITICO: return "CRITICO";
        case LocalState::NORMAL:
        default: return "NORMAL";
    }
}

void applyStateLed(LocalState state) {
    switch (state) {
        case LocalState::ATENCAO: setRgb(true, true, false); break;
        case LocalState::ALERTA:
        case LocalState::CRITICO: setRgb(true, false, false); break;
        case LocalState::NORMAL:
        default: setRgb(false, true, false); break;
    }
}

void updateLcd() {
    char stateLine[17];
    char dataLine[17];
    snprintf(stateLine, sizeof(stateLine), "%s %s", ZONE_ID,
             stateName(stateContext.current));
    if (!climateAttempted) {
        snprintf(dataLine, sizeof(dataLine), "DHT: aguarde");
    } else if (!climateValid) {
        snprintf(dataLine, sizeof(dataLine), "DHT: ERRO");
    } else {
        snprintf(dataLine, sizeof(dataLine), "%4.1fC %3.0f%%",
                 climate.temperature, climate.humidity);
    }
    for (uint8_t row = 0; row < 2; ++row) {
        const char* line = row == 0 ? stateLine : dataLine;
        lcd.setCursor(0, row);
        const size_t length = strlen(line);
        for (size_t i = 0; i < 16; ++i) {
            lcd.write(i < length ? line[i] : ' ');
        }
    }
}

bool readClimate(uint32_t now) {
    if (now - lastClimateRead < DHT_INTERVAL_MS) {
        return false;
    }
    lastClimateRead = now;
    climateAttempted = true;
    const float humidity = dht.readHumidity();
    const float temperature = dht.readTemperature();
    if (isnan(humidity) || isnan(temperature)) {
        climateValid = false;
        updateLcd();
        return true;
    }

    climate.humidity = humidity;
    climate.temperature = temperature;
    climateValid = true;
    mqttPublishTemperature(climate.temperature);
    updateLcd();
    return true;
}

bool accessOpen() {
    return accessInput.stable == HIGH;
}

bool criticalCondition() {
    return tamperInput.stable == LOW ||
           (climateValid && climate.temperature >= CRITICAL_TEMPERATURE_C);
}

bool alertCondition(uint32_t now) {
    if (!stateContext.armed || stateContext.lastPirEvent == 0 ||
        stateContext.lastAccessOpenEvent == 0) {
        return false;
    }
    const uint32_t elapsed =
        stateContext.lastPirEvent > stateContext.lastAccessOpenEvent
            ? stateContext.lastPirEvent - stateContext.lastAccessOpenEvent
            : stateContext.lastAccessOpenEvent - stateContext.lastPirEvent;
    return elapsed <= ALERT_COMBINATION_WINDOW_MS &&
           now - min(stateContext.lastPirEvent, stateContext.lastAccessOpenEvent) <=
               ALERT_COMBINATION_WINDOW_MS;
}

bool attentionCondition() {
    return motionDetected || accessOpen() ||
           (climateValid && climate.temperature >= ATTENTION_TEMPERATURE_C);
}

void printStateEvent(const char* message) {
    Serial.printf("Estado: %s | %s\n", stateName(stateContext.current), message);
}

void classifyState(uint32_t now, bool motionChanged, bool accessChanged) {
    if (motionChanged && motionDetected) {
        stateContext.lastPirEvent = now;
        if (stateContext.alertLatched && stateContext.alertAcknowledged) {
            stateContext.alertAcknowledged = false;
        }
    }
    if (accessChanged && accessOpen()) {
        stateContext.lastAccessOpenEvent = now;
        if (stateContext.alertLatched && stateContext.alertAcknowledged) {
            stateContext.alertAcknowledged = false;
        }
    }

    const bool criticalNow = criticalCondition();
    const bool alertNow = alertCondition(now);
    if (criticalNow && !stateContext.previousCriticalCondition &&
        stateContext.criticalLatched) {
        stateContext.criticalAcknowledged = false;
    }
    if (criticalNow) {
        if (!stateContext.criticalLatched) {
            stateContext.criticalAcknowledged = false;
            printStateEvent("CRITICO latching ativado");
        }
        stateContext.criticalLatched = true;
        if (!stateContext.previousCriticalCondition) mqttPublishEvent("CRITICO");
    } else if (alertNow && !stateContext.alertLatched) {
        stateContext.alertAcknowledged = false;
        stateContext.alertLatched = true;
        mqttPublishEvent("ALERTA");
        printStateEvent("ALERTA latching ativado");
    }

    const LocalState previous = stateContext.current;
    if (stateContext.criticalLatched) {
        stateContext.current = LocalState::CRITICO;
    } else if (stateContext.alertLatched) {
        stateContext.current = LocalState::ALERTA;
    } else if (attentionCondition()) {
        stateContext.current = LocalState::ATENCAO;
    } else {
        stateContext.current = LocalState::NORMAL;
    }
    stateContext.previousCriticalCondition = criticalNow;

    if (stateContext.current != previous) {
        applyStateLed(stateContext.current);
        updateLcd();
        Serial.printf("Estado mudou: %s -> %s\n", stateName(previous),
                      stateName(stateContext.current));
        mqttPublishState(stateName(stateContext.current));
    }
}

void acknowledgeAlarms() {
    if (!stateContext.alertLatched && !stateContext.criticalLatched) {
        Serial.println("ACK rejeitado: nenhum alarme latching ativo");
        return;
    }
    stateContext.alertAcknowledged = stateContext.alertLatched;
    stateContext.criticalAcknowledged = stateContext.criticalLatched;
    stateContext.alarmOutputOn = false;
    ledcWrite(BUZZER_CHANNEL, 0);
    Serial.println("ACK aceito: alarme sonoro silenciado; estado preservado");
}

void resetAlarms() {
    const bool criticalNow = criticalCondition();
    const bool alertNow = alertCondition(millis());
    if (criticalNow || alertNow) {
        Serial.printf("RESET rejeitado: %s%s\n",
                      criticalNow ? "condicao critica ativa " : "",
                      alertNow ? "combinacao de alerta ativa" : "");
        return;
    }
    stateContext.alertLatched = false;
    stateContext.criticalLatched = false;
    stateContext.alertAcknowledged = false;
    stateContext.criticalAcknowledged = false;
    Serial.println("RESET aceito: estados persistentes limpos");
}

void updateAlarmBuzzer(uint32_t now) {
    const bool alarmLatched = stateContext.alertLatched || stateContext.criticalLatched;
    const bool acknowledged = stateContext.criticalLatched
                                  ? stateContext.criticalAcknowledged
                                  : stateContext.alertAcknowledged;
    if (!alarmLatched || acknowledged) {
        if (stateContext.alarmOutputOn) {
            ledcWrite(BUZZER_CHANNEL, 0);
            stateContext.alarmOutputOn = false;
        }
        return;
    }

    const uint32_t phase = now - stateContext.lastAlarmPhaseChange;
    const uint32_t limit = stateContext.alarmOutputOn ? ALARM_BEEP_ON_MS
                                                       : ALARM_BEEP_OFF_MS;
    if (phase >= limit) {
        stateContext.alarmOutputOn = !stateContext.alarmOutputOn;
        stateContext.lastAlarmPhaseChange = now;
        if (stateContext.alarmOutputOn) {
            ledcWriteTone(BUZZER_CHANNEL, BUZZER_FREQUENCY_HZ);
        } else {
            ledcWrite(BUZZER_CHANNEL, 0);
        }
    }
}

void printReadings() {
    Serial.printf("[%s] Movimento: %s | Acesso: %s | Tamper: %s | ",
                  ZONE_ID, motionDetected ? "DETECTADO" : "NAO DETECTADO",
                  accessInput.stable == HIGH ? "ABERTO" : "FECHADO",
                  tamperInput.stable == LOW ? "ACIONADO" : "NORMAL");
    if (!climateAttempted) {
        Serial.println("Temperatura/umidade: aguardando primeira leitura");
    } else if (!climateValid) {
        Serial.println("Temperatura/umidade: ERRO DHT22 (NaN)");
    } else {
        Serial.printf("Temperatura: %.1f C | Umidade: %.1f %%\n",
                      climate.temperature, climate.humidity);
    }
}

void printHelp() {
    Serial.println("TESTES: r=vermelho g=verde b=azul y=amarelo c=ciano");
    Serial.println("        m=magenta w=branco 0=RGB apagado s=som h=ajuda");
    Serial.println("ESTADO: A=armar D=desarmar K=ACK X=RESET");
    Serial.println("Envie uma letra pelo monitor serial. Som: 2000 Hz / 300 ms.");
}

void handleSerial() {
    // Limite por passagem para nao atrasar sensores se houver muitos comandos.
    char mqttCommand = mqttTakeCommand();
    for (uint8_t i = 0; i < 16 && (mqttCommand || Serial.available()); ++i) {
        char command = mqttCommand ? mqttCommand : Serial.read();
        mqttCommand = 0;
        switch (command) {
            case 'r': setRgb(true, false, false); break;
            case 'g': setRgb(false, true, false); break;
            case 'b': setRgb(false, false, true); break;
            case 'y': setRgb(true, true, false); break;
            case 'c': setRgb(false, true, true); break;
            case 'm': setRgb(true, false, true); break;
            case 'w': setRgb(true, true, true); break;
            case '0': setRgb(false, false, false); break;
            case 's':
                ledcWriteTone(BUZZER_CHANNEL, BUZZER_FREQUENCY_HZ);
                buzzerStartedAt = millis();
                buzzerActive = true;
                Serial.println("Buzzer: teste iniciado (300 ms)");
                continue;
            case 'h': printHelp(); continue;
            case 'A':
                stateContext.armed = true;
                Serial.println("Zona armada");
                continue;
            case 'D':
                stateContext.armed = false;
                Serial.println("Zona desarmada");
                continue;
            case 'K': acknowledgeAlarms(); continue;
            case 'X': resetAlarms(); continue;
            case '\r':
            case '\n':
            case ' ': continue;
            default:
                Serial.println("Comando desconhecido. Use h para ajuda.");
                continue;
        }
        Serial.printf("RGB: comando %c aplicado\n", command);
    }
}

void updateBuzzer(uint32_t now) {
    if (buzzerActive && now - buzzerStartedAt >= BUZZER_DURATION_MS) {
        ledcWrite(BUZZER_CHANNEL, 0);
        buzzerActive = false;
        Serial.println("Buzzer: teste encerrado");
    }
}
}  // namespace

void setup() {
    Serial.begin(Config::SERIAL_BAUD_RATE);
    pinMode(Pins::PIR, INPUT);
    accessInput.begin();
    tamperInput.begin();
    pinMode(Pins::RGB_RED, OUTPUT);
    pinMode(Pins::RGB_GREEN, OUTPUT);
    pinMode(Pins::RGB_BLUE, OUTPUT);
    setRgb(false, false, false);

    ledcSetup(BUZZER_CHANNEL, BUZZER_FREQUENCY_HZ, 8);
    ledcAttachPin(Pins::BUZZER, BUZZER_CHANNEL);
    ledcWrite(BUZZER_CHANNEL, 0);

    dht.begin();
    mqttBegin();
    lastClimateRead = millis();
    lcd.begin(16, 2);
    lcd.print("CNA SENTINEL");
    applyStateLed(stateContext.current);
    mqttPublishState("NORMAL");
    updateLcd();

    Serial.println("CNA SENTINEL INICIADO");
    Serial.printf("ZONA: %s\n", ZONE_ID);
    Serial.println("ARMAMENTO: ARMADA");
    printHelp();
    motionDetected = digitalRead(Pins::PIR) == HIGH;
    const uint32_t startupNow = millis();
    if (motionDetected) {
        stateContext.lastPirEvent = startupNow;
    }
    if (accessOpen()) {
        stateContext.lastAccessOpenEvent = startupNow;
    }
    printReadings();
    lastSerialReport = millis();
}

void loop() {
    handleSerial();
    const uint32_t now = millis();
    updateBuzzer(now);

    const bool accessChanged = accessInput.update(now);
    const bool tamperChanged = tamperInput.update(now);
    const bool motion = digitalRead(Pins::PIR) == HIGH;
    const bool motionChanged = motion != motionDetected;
    motionDetected = motion;
    const bool climateUpdated = readClimate(now);
    classifyState(now, motionChanged, accessChanged);
    if (climateUpdated || motionChanged || accessChanged || tamperChanged) {
        if (climateValid) {
            Serial.printf("MQTT telemetria chamada: temp=%.1f umid=%.1f movimento=%d acesso=%d tamper=%d estado=%s\n",
                          climate.temperature, climate.humidity, motionDetected,
                          accessOpen(), tamperInput.stable == LOW,
                          stateName(stateContext.current));
            mqttPublishTelemetry(climate.temperature, climate.humidity,
                                 motionDetected, accessOpen(),
                                 tamperInput.stable == LOW,
                                 stateName(stateContext.current));
        } else {
            Serial.println("MQTT telemetria não chamada: DHT ainda inválido");
        }
    }
    updateAlarmBuzzer(now);

    if (accessChanged || tamperChanged || motionChanged || climateUpdated ||
        now - lastSerialReport >= SERIAL_INTERVAL_MS) {
        printReadings();
        lastSerialReport = now;
    }
    // Cede ao escalonador do ESP32, sem esperas longas entre as leituras.
    delay(1);
}
