"""Transporte MQTT opcional; o simulador local não depende deste módulo."""

from __future__ import annotations

import json
import logging
import ssl
from typing import Callable

from config import MISSION_TOPIC, STATUS_TOPIC, MqttConfig
from models import Mission, Status

try:
    import paho.mqtt.client as mqtt
except ImportError:  # permite usar o modo local sem instalar Paho
    mqtt = None


class MqttTransport:
    def __init__(self, config: MqttConfig, on_mission: Callable[[Mission], None], logger=None):
        if mqtt is None:
            raise RuntimeError("instale as dependências de requirements.txt para usar MQTT")
        self.config = config
        self.on_mission = on_mission
        self.logger = logger or logging.getLogger(__name__)
        websocket = config.transport in {"ws", "wss"}
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=config.client_id,
            transport="websockets" if websocket else "tcp",
        )
        if websocket:
            self.client.ws_set_options(path=config.ws_path)
        if config.username:
            self.client.username_pw_set(config.username, config.password)
        if config.transport in {"wss", "mqtts"}:
            context = ssl.create_default_context(cafile=config.ca_cert)
            if config.client_cert and config.client_key:
                context.load_cert_chain(config.client_cert, config.client_key)
            self.client.tls_set_context(context)
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.on_connect = self._on_connect
        self.client.on_connect_fail = self._on_connect_fail
        self.client.on_disconnect = self._on_disconnect
        self.client.on_subscribe = self._on_subscribe
        self.client.on_message = self._on_message

    def _on_connect(self, client, _userdata, _flags, reason, _properties):
        if reason.is_failure:
            self.logger.warning("broker recusou o drone: %s", reason)
            return
        result, _ = client.subscribe(MISSION_TOPIC)
        if result != mqtt.MQTT_ERR_SUCCESS:
            self.logger.warning("falha ao solicitar assinatura de missões: %s", result)

    def _on_subscribe(self, _client, _userdata, _mid, reasons, _properties):
        if any(reason.is_failure for reason in reasons):
            self.logger.warning("broker recusou a assinatura de missões: %s", reasons)
        else:
            self.logger.info("Drone conectado e assinatura de missões confirmada")

    def _on_connect_fail(self, _client, _userdata):
        self.logger.warning("falha ao conectar o drone a %s:%s via %s; haverá nova tentativa",
                            self.config.host, self.config.port, self.config.transport)

    def _on_disconnect(self, _client, _userdata, _flags, reason, _properties):
        if reason.is_failure:
            self.logger.warning("drone desconectado: %s; haverá nova tentativa", reason)

    def _on_message(self, _client, _userdata, message):
        try:
            self.on_mission(Mission.from_json(message.payload.decode("utf-8")))
        except (ValueError, RuntimeError) as exc:
            self.logger.warning("missão MQTT rejeitada: %s", exc)

    def connect(self):
        self.client.connect_async(self.config.host, self.config.port, keepalive=60)
        self.client.loop_start()

    def publish_status(self, status: Status):
        result = self.client.publish(STATUS_TOPIC, json.dumps(status.to_dict(), ensure_ascii=False), qos=1)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            self.logger.warning("status sem envio imediato: %s", mqtt.error_string(result.rc))

    def close(self):
        self.client.disconnect()
        self.client.loop_stop()
