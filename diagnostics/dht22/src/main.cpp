#include <Arduino.h>
#include <DHTesp.h>
#include <math.h>

namespace {
constexpr uint8_t DHT_PIN = 4;
constexpr uint32_t READ_INTERVAL_MS = 2500;

DHTesp dht;
uint32_t nextReadAt = 0;

void readAndReport() {
    const TempAndHumidity reading = dht.getTempAndHumidity();
    const DHTesp::DHT_ERROR_t status = dht.getStatus();

    if (status == DHTesp::ERROR_NONE && isfinite(reading.temperature) &&
        isfinite(reading.humidity)) {
        Serial.printf("DHT22 OK | Temperatura: %.1f C | Umidade: %.1f %%\n",
                      reading.temperature, reading.humidity);
        return;
    }

    Serial.printf("DHT22 ERRO | codigo: %d | descricao: %s\n", status,
                  dht.getStatusString());
}
}  // namespace

void setup() {
    Serial.begin(115200);
    delay(100);

    dht.setup(DHT_PIN, DHTesp::DHT22);
    nextReadAt = millis() + READ_INTERVAL_MS;

    Serial.println("DHT22 DIAGNOSTICO INICIADO");
    Serial.println("GPIO: 4 | intervalo: 2500 ms");
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
