import logging
import ssl

import paho.mqtt.client as mqtt

from .config import TOPICS, COMMAND_TOPICS, DRONE_STATUS_TOPIC

log = logging.getLogger(__name__)


class MqttBridgeTransport:
    def __init__(self, config, bridge):
        self.bridge, self.config = bridge, config
        websocket = config.mqtt_transport in {"ws", "wss"}
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=config.mqtt_client_id,
            transport="websockets" if websocket else "tcp",
        )
        if websocket:
            self.client.ws_set_options(path=config.mqtt_ws_path)
        if config.mqtt_username:
            self.client.username_pw_set(config.mqtt_username, config.mqtt_password)
        if config.mqtt_transport in {"wss", "mqtts"}:
            self.client.tls_set_context(ssl.create_default_context(cafile=config.mqtt_ca_cert))
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.on_connect = self._on_connect
        self.client.on_connect_fail = self._on_connect_fail
        self.client.on_disconnect = self._on_disconnect
        self.client.on_subscribe = self._on_subscribe
        self.client.on_message = self._message
        bridge.publish = self.publish

    def _on_connect(self, client, _userdata, _flags, reason, _properties):
        if reason.is_failure:
            log.warning("broker recusou a Bridge: %s", reason)
            return
        result, _ = client.subscribe([(topic, 1) for topic in [*TOPICS, *COMMAND_TOPICS, DRONE_STATUS_TOPIC]])
        if result != mqtt.MQTT_ERR_SUCCESS:
            log.warning("falha ao solicitar assinaturas da Bridge: %s", result)

    def _on_subscribe(self, _client, _userdata, _mid, reasons, _properties):
        if any(reason.is_failure for reason in reasons):
            log.warning("broker recusou assinaturas da Bridge: %s", reasons)
        else:
            log.info("Bridge conectada e assinaturas confirmadas")

    def _on_connect_fail(self, _client, _userdata):
        log.warning("falha ao conectar a Bridge a %s:%s via %s; haverá nova tentativa",
                    self.config.mqtt_host, self.config.mqtt_port, self.config.mqtt_transport)

    def _on_disconnect(self, _client, _userdata, _flags, reason, _properties):
        if reason.is_failure:
            log.warning("Bridge desconectada: %s; haverá nova tentativa", reason)

    def _message(self, _client, _userdata, message):
        try:
            if message.topic in TOPICS:
                self.bridge.handle_zone_message(message.topic, message.payload)
            elif message.topic in COMMAND_TOPICS:
                # O broker já distribui o comando aos nós inscritos.
                self.bridge.handle_command(message.topic, message.payload, publish=False)
            elif message.topic == DRONE_STATUS_TOPIC:
                self.bridge.handle_drone_status(message.payload)
        except Exception as exc:
            log.error("falha ao processar %s: %s", message.topic, exc)

    def connect(self):
        self.client.connect_async(self.config.mqtt_host, self.config.mqtt_port, keepalive=60)
        self.client.loop_start()

    def publish(self, topic, payload):
        result = self.client.publish(topic, payload, qos=1)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            log.warning("publicação sem envio imediato em %s: %s", topic, mqtt.error_string(result.rc))
        return result

    def close(self):
        self.client.disconnect()
        self.client.loop_stop()
