#include <Adafruit_Sensor.h>
#include <Arduino.h>
#include <DHT.h>
#include <math.h>

namespace {
constexpr uint8_t DHT_PIN = 4;
constexpr uint8_t DHT_TYPE = DHT22;
constexpr uint32_t READ_INTERVAL_MS = 2500;

DHT dht(DHT_PIN, DHT_TYPE);
uint32_t nextReadAt = 0;
uint32_t readCount = 0;

void readAndReport() {
    ++readCount;
    const float humidity = dht.readHumidity();
    const float temperature = dht.readTemperature();

    if (isnan(humidity) || isnan(temperature)) {
        Serial.printf("DHT22 ERRO | leitura: %lu | Adafruit retornou NaN\n",
                      static_cast<unsigned long>(readCount));
        return;
    }

    Serial.printf("DHT22 OK | leitura: %lu | Temperatura: %.1f C | Umidade: %.1f %%\n",
                  static_cast<unsigned long>(readCount), temperature, humidity);
}
}  // namespace

void setup() {
    Serial.begin(115200);
    delay(100);

    dht.begin();
    nextReadAt = millis() + READ_INTERVAL_MS;

    Serial.println("DHT22 DIAGNOSTICO ALTERNATIVO INICIADO");
    Serial.println("Biblioteca: Adafruit DHT sensor library 1.4.6");
    Serial.println("GPIO: 4 | tipo: DHT22 | intervalo: 2500 ms");
    Serial.println("Primeira leitura aguardara 2500 ms.");
}

void loop() {
    const uint32_t now = millis();
    if (static_cast<int32_t>(now - nextReadAt) >= 0) {
        readAndReport();
        nextReadAt += READ_INTERVAL_MS;
    }

    delay(1);
}
