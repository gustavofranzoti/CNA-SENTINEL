"""Configuração do simulador; valores sensíveis vêm do ambiente."""

from dataclasses import dataclass, field
import os

DRONE_CLIENT_ID = "cna-sentinel-drone"

@dataclass(frozen=True)
class MqttConfig:
    host: str = field(default_factory=lambda: os.getenv("MQTT_HOST", ""))
    port: int = field(default_factory=lambda: int(os.getenv("MQTT_PORT") or 0))
    username: str | None = field(default_factory=lambda: os.getenv("MQTT_USERNAME") or None)
    password: str | None = field(default_factory=lambda: os.getenv("MQTT_PASSWORD") or None)
    ca_cert: str | None = field(default_factory=lambda: os.getenv("MQTT_CA_CERT") or None)
    client_cert: str | None = field(default_factory=lambda: os.getenv("MQTT_CLIENT_CERT") or None)
    client_key: str | None = field(default_factory=lambda: os.getenv("MQTT_CLIENT_KEY") or None)
    transport: str = field(default_factory=lambda: os.getenv("MQTT_TRANSPORT", "").lower())
    ws_path: str = field(default_factory=lambda: os.getenv("MQTT_WS_PATH", ""))
    client_id: str = field(default_factory=lambda: os.getenv("MQTT_DRONE_CLIENT_ID", DRONE_CLIENT_ID))

    def __post_init__(self):
        if not self.host or not 1 <= self.port <= 65535:
            raise ValueError("informe MQTT_HOST e MQTT_PORT (1 a 65535)")
        if self.transport not in {"ws", "wss", "mqtts", "mqtt"}:
            raise ValueError("MQTT_TRANSPORT deve ser ws, wss, mqtts ou mqtt")
        if self.transport in {"ws", "wss"} and not self.ws_path.startswith("/"):
            raise ValueError("informe MQTT_WS_PATH começando com /")
        if self.client_id != DRONE_CLIENT_ID:
            raise ValueError(f"MQTT_DRONE_CLIENT_ID deve ser {DRONE_CLIENT_ID}")
        if bool(self.client_cert) != bool(self.client_key):
            raise ValueError("informe MQTT_CLIENT_CERT e MQTT_CLIENT_KEY juntos")


MISSION_TOPIC = "cna/drone/missao"
STATUS_TOPIC = "cna/drone/status"
