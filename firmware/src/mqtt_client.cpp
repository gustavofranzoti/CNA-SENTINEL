#include "cna_mqtt_client.h"
#include <WiFi.h>
#include <mqtt_client.h>
#include <atomic>
#include <cstring>
#include <time.h>

#if __has_include("mqtt_config.h")
#include "mqtt_config.h"
#else
#include "mqtt_config.h.example"
#endif

namespace {
#if defined(CNA_ZONE_Z1)
constexpr char CLIENT_ID[] = "cna-sentinel-z1";
#else
constexpr char CLIENT_ID[] = "cna-sentinel-z2";
#endif
#ifndef CNA_MQTT_CLIENT_ID
#define CNA_MQTT_CLIENT_ID CLIENT_ID
#endif
// Cabeçalhos locais antigos usavam MQTT diretamente sobre TLS.
#ifndef CNA_MQTT_TRANSPORT
#define CNA_MQTT_TRANSPORT "mqtts"
#endif
#ifndef CNA_MQTT_WS_PATH
#define CNA_MQTT_WS_PATH ""
#endif

constexpr uint32_t RETRY_MS = 10000;
constexpr size_t PAYLOAD_SIZE = 192;

struct Publication {
    const char* topic;
    char payload[PAYLOAD_SIZE];
    bool retain;
};

#if defined(CNA_ZONE_Z1)
#define CNA_ZONE_TOPIC "cna/zona/Z1/"
#else
#define CNA_ZONE_TOPIC "cna/zona/Z2/"
#endif
constexpr char TEMPERATURE_TOPIC[] = CNA_ZONE_TOPIC "temperatura";
constexpr char TELEMETRY_TOPIC[] = CNA_ZONE_TOPIC "telemetria";
constexpr char STATE_TOPIC[] = CNA_ZONE_TOPIC "estado";
constexpr char EVENT_TOPIC[] = CNA_ZONE_TOPIC "evento";
constexpr char COMMAND_TOPIC[] = CNA_ZONE_TOPIC "comando";

QueueHandle_t telemetryQueue = nullptr;
QueueHandle_t eventQueue = nullptr;
QueueHandle_t commandQueue = nullptr;
std::atomic<bool> connected{false};
bool networkReady = false;

void receiveCommand(const esp_mqtt_event_t& event) {
    if (event.topic_len != sizeof(COMMAND_TOPIC) - 1 ||
        memcmp(event.topic, COMMAND_TOPIC, sizeof(COMMAND_TOPIC) - 1) != 0 ||
        event.current_data_offset != 0 || event.data_len != event.total_data_len) {
        return;
    }

    String command;
    for (int i = 0; i < event.data_len; ++i) command += event.data[i];
    command.trim();
    command.toUpperCase();
    char serialCommand;
    if (command == "ARM") serialCommand = 'A';
    else if (command == "DISARM") serialCommand = 'D';
    else if (command == "ACK") serialCommand = 'K';
    else if (command == "RESET") serialCommand = 'X';
    else {
        Serial.println("MQTT comando rejeitado");
        return;
    }
    Serial.printf("MQTT comando recebido: %s\n", command.c_str());
    xQueueOverwrite(commandQueue, &serialCommand);
}

void mqttEvent(void*, esp_event_base_t, int32_t id, void* data) {
    const auto& event = *static_cast<esp_mqtt_event_t*>(data);
    switch (id) {
        case MQTT_EVENT_CONNECTED:
            esp_mqtt_client_subscribe(event.client, COMMAND_TOPIC, 1);
            esp_mqtt_client_publish(event.client, STATE_TOPIC, "ONLINE", 0, 0, true);
            connected.store(true);
            Serial.printf("MQTT conectado; telemetria pendente=%u\n",
                          static_cast<unsigned>(uxQueueMessagesWaiting(telemetryQueue)));
            break;
        case MQTT_EVENT_DISCONNECTED:
            connected.store(false);
            Serial.println("MQTT desconectado; haverá nova tentativa");
            break;
        case MQTT_EVENT_DATA:
            receiveCommand(event);
            break;
        case MQTT_EVENT_ERROR:
            if (event.error_handle) {
                Serial.printf("MQTT falha (%d), TLS=0x%x, CONNACK=%d\n",
                              event.error_handle->error_type,
                              event.error_handle->esp_tls_last_esp_err,
                              event.error_handle->connect_return_code);
                Serial.printf("TLS stack=0x%x, cert_flags=0x%x, socket_errno=%d\n",
                              event.error_handle->esp_tls_stack_err,
                              event.error_handle->esp_tls_cert_verify_flags,
                              event.error_handle->esp_transport_sock_errno);
            }
            break;
        default:
            break;
    }
}

void networkTask(void* parameter) {
    auto& config = *static_cast<esp_mqtt_client_config_t*>(parameter);
    esp_mqtt_client_handle_t client = nullptr;
    bool wifiAttempted = false;
    bool ntpStarted = false;
    uint32_t lastWifiAttempt = 0;
    uint32_t lastMqttAttempt = 0;
    bool mqttAttempted = false;

    for (;;) {
        const uint32_t now = millis();
        if (WiFi.status() != WL_CONNECTED) {
            if (!wifiAttempted || now - lastWifiAttempt >= RETRY_MS) {
                wifiAttempted = true;
                lastWifiAttempt = now;
                WiFi.mode(WIFI_STA);
                WiFi.begin(CNA_WIFI_SSID, CNA_WIFI_PASSWORD);
            }
        } else if (!client && (!mqttAttempted || now - lastMqttAttempt >= RETRY_MS)) {
            if (config.cert_pem && !ntpStarted) {
                configTime(0, 0, "pool.ntp.org", "time.nist.gov");
                ntpStarted = true;
            }
            if (!config.cert_pem || time(nullptr) >= 1700000000) {
    mqttAttempted = true;
    lastMqttAttempt = now;

esp_log_level_set("*", ESP_LOG_VERBOSE);

Serial.printf(
    "Heap livre antes do MQTT: %u bytes\n",
    static_cast<unsigned>(ESP.getFreeHeap())
);

client = esp_mqtt_client_init(&config);

if (!client) {
    Serial.println("ERRO: esp_mqtt_client_init falhou");
    Serial.printf("URI MQTT: %s\n", config.uri ? config.uri : "(null)");
    Serial.printf("HOST MQTT: %s\n", config.host ? config.host : "(null)");
    Serial.printf("TRANSPORTE MQTT: %d\n", static_cast<int>(config.transport));
    Serial.printf("CERTIFICADO: %s\n", config.cert_pem ? "PRESENTE" : "AUSENTE");
    } else {
        esp_err_t eventResult =
            esp_mqtt_client_register_event(
                client, MQTT_EVENT_ANY, mqttEvent, nullptr
            );

        if (eventResult != ESP_OK) {
            Serial.printf("ERRO: register_event = %d\n", eventResult);
            esp_mqtt_client_destroy(client);
            client = nullptr;
        } else {
            esp_err_t startResult = esp_mqtt_client_start(client);

            if (startResult != ESP_OK) {
                Serial.printf("ERRO: mqtt_client_start = %d\n", startResult);
                esp_mqtt_client_destroy(client);
                client = nullptr;
            } else {
                Serial.println("Cliente MQTT iniciado; aguardando conexao...");
            }
                }
            }
        }
        }

        Publication message;
        if (connected.load()) {
            if (xQueuePeek(eventQueue, &message, 0) == pdTRUE &&
                esp_mqtt_client_publish(client, message.topic, message.payload, 0, 0, message.retain) >= 0) {
                Serial.printf("MQTT evento enviado: topico=%s tamanho=%u\n",
                              message.topic, static_cast<unsigned>(strlen(message.payload)));
                xQueueReceive(eventQueue, &message, 0);
            }
            if (xQueuePeek(telemetryQueue, &message, 0) == pdTRUE) {
                const int messageId = esp_mqtt_client_publish(
                    client, message.topic, message.payload, 0, 0, message.retain);
                Serial.printf("MQTT fila consumida: topico=%s tamanho=%u retorno=%d\n",
                              message.topic, static_cast<unsigned>(strlen(message.payload)), messageId);
                if (messageId >= 0) {
                    xQueueReceive(telemetryQueue, &message, 0);
                }
            }
        } else {
            const unsigned pending = static_cast<unsigned>(uxQueueMessagesWaiting(telemetryQueue));
            if (pending > 0) {
                Serial.printf("MQTT offline; fila preservada: itens=%u\n", pending);
            }
        }
        vTaskDelay(pdMS_TO_TICKS(20));
    }
}

void queueTelemetry(const char* topic, const char* payload, bool retain) {
    if (!networkReady) {
        Serial.printf("MQTT telemetria descartada: fila indisponivel topico=%s\n", topic);
        return;
    }
    Publication message{topic, {}, retain};
    snprintf(message.payload, sizeof(message.payload), "%s", payload);
    BaseType_t queued = xQueueSend(telemetryQueue, &message, 0);
    if (queued != pdTRUE) {
        Publication dropped;
        if (xQueueReceive(telemetryQueue, &dropped, 0) == pdTRUE) {
            Serial.printf("MQTT fila cheia; descartando mais antiga: topico=%s\n", dropped.topic);
            queued = xQueueSend(telemetryQueue, &message, 0);
        }
    }
    Serial.printf("MQTT fila envio: topico=%s tamanho=%u resultado=%s\n",
                  topic, static_cast<unsigned>(strlen(message.payload)),
                  queued == pdTRUE ? "OK" : "CHEIA" );
}
}

void mqttBegin() {
    if (!CNA_WIFI_SSID[0] || !CNA_MQTT_HOST[0]) return;

    static esp_mqtt_client_config_t config{};
    const bool ws = strcmp(CNA_MQTT_TRANSPORT, "ws") == 0;
    const bool wss = strcmp(CNA_MQTT_TRANSPORT, "wss") == 0;
    const bool mqtts = strcmp(CNA_MQTT_TRANSPORT, "mqtts") == 0;
    if ((!ws && !wss && !mqtts) || CNA_MQTT_PORT < 1 || CNA_MQTT_PORT > 65535 ||
        ((ws || wss) && CNA_MQTT_WS_PATH[0] != '/') ||
        ((wss || mqtts) && !CNA_MQTT_CA_CERT[0]) ||
        strcmp(CNA_MQTT_CLIENT_ID, CLIENT_ID) != 0) {
        Serial.println("MQTT configuração inválida; operação local ativa");
        return;
    }

    static char mqttUri[160];

if (wss) {
    snprintf(mqttUri, sizeof(mqttUri), "wss://%s:%u%s",
             CNA_MQTT_HOST,
             static_cast<unsigned>(CNA_MQTT_PORT),
             CNA_MQTT_WS_PATH);
    config.uri = mqttUri;
    config.host = nullptr;
    config.port = 0;
    config.path = nullptr;
    // A complete URI is authoritative. Do not provide a second transport
    // selector to the IDF 4.4 client during its initial configuration.
    config.transport = MQTT_TRANSPORT_UNKNOWN;
} else {
    config.host = CNA_MQTT_HOST;
    config.port = CNA_MQTT_PORT;
    config.path = (ws) ? CNA_MQTT_WS_PATH : nullptr;
}

if (!wss) {
    config.transport = ws ? MQTT_TRANSPORT_OVER_WS : MQTT_TRANSPORT_OVER_SSL;
}
config.cert_pem = (wss || mqtts) ? CNA_MQTT_CA_CERT : nullptr;
    config.client_id = CNA_MQTT_CLIENT_ID;
    config.username = CNA_MQTT_USERNAME[0] ? CNA_MQTT_USERNAME : nullptr;
    config.password = config.username && CNA_MQTT_PASSWORD[0] ? CNA_MQTT_PASSWORD : nullptr;
    config.lwt_topic = STATE_TOPIC;
    config.lwt_msg = "OFFLINE";
    config.lwt_qos = 1;
    config.lwt_retain = true;
    config.keepalive = 15;
    config.protocol_ver = MQTT_PROTOCOL_V_3_1_1;
    config.reconnect_timeout_ms = RETRY_MS;

    telemetryQueue = xQueueCreate(16, sizeof(Publication));
    eventQueue = xQueueCreate(4, sizeof(Publication));
    commandQueue = xQueueCreate(1, sizeof(char));
    if (telemetryQueue && eventQueue && commandQueue &&
        xTaskCreate(networkTask, "cna-network", 4096, &config, tskIDLE_PRIORITY + 1, nullptr) == pdPASS) {
        networkReady = true;
        return;
    }
    if (telemetryQueue) vQueueDelete(telemetryQueue);
    if (eventQueue) vQueueDelete(eventQueue);
    if (commandQueue) vQueueDelete(commandQueue);
    Serial.println("MQTT recursos insuficientes; operação local ativa");
}

void mqttPublishTemperature(float value) {
    char payload[PAYLOAD_SIZE];
    snprintf(payload, sizeof(payload), "%.1f", value);
    queueTelemetry(TEMPERATURE_TOPIC, payload, false);
}

void mqttPublishTelemetry(float temperature, float humidity, bool motion,
                          bool accessOpen, bool tamperActive, const char* state) {
    if (!networkReady) {
        Serial.printf("MQTT telemetria descartada: fila indisponivel topico=%s\n",
                      TELEMETRY_TOPIC);
        return;
    }
    char payload[PAYLOAD_SIZE];
    snprintf(payload, sizeof(payload),
             "{\"temperatura\":%.1f,\"umidade\":%.1f,\"movimento\":%s,"
             "\"acesso\":\"%s\",\"tamper\":\"%s\",\"estado\":\"%s\"}",
             temperature, humidity, motion ? "true" : "false",
             accessOpen ? "ABERTO" : "FECHADO",
             tamperActive ? "ACIONADO" : "NORMAL", state);
    Publication message{TELEMETRY_TOPIC, {}, false};
    snprintf(message.payload, sizeof(message.payload), "%s", payload);
    BaseType_t queued = xQueueSend(telemetryQueue, &message, 0);
    if (queued != pdTRUE) {
        Publication dropped;
        if (xQueueReceive(telemetryQueue, &dropped, 0) == pdTRUE) {
            Serial.printf("MQTT fila cheia; descartando mais antiga: topico=%s\n", dropped.topic);
            queued = xQueueSend(telemetryQueue, &message, 0);
        }
    }
    Serial.printf("MQTT telemetria fila: topico=%s tamanho=%u resultado=%s payload=%s\n",
                  TELEMETRY_TOPIC, static_cast<unsigned>(strlen(message.payload)),
                  queued == pdTRUE ? "OK" : "CHEIA", message.payload);
}

void mqttPublishState(const char* state) {
    queueTelemetry(STATE_TOPIC, state, true);
}

void mqttPublishEvent(const char* eventName) {
    if (!networkReady) return;
    Publication message{EVENT_TOPIC, {}, false};
    snprintf(message.payload, sizeof(message.payload), "%s", eventName);
    xQueueSend(eventQueue, &message, 0);
}

char mqttTakeCommand() {
    char command = 0;
    if (networkReady) xQueueReceive(commandQueue, &command, 0);
    return command;
}
