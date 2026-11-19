from dataclasses import dataclass, field
import os

BRIDGE_CLIENT_ID = "cna-sentinel-bridge"
DEFAULT_UBIDOTS_INTERVAL_SECONDS = 1.2

@dataclass(frozen=True)
class IntegrationConfig:
    mqtt_host: str = field(default_factory=lambda: os.getenv("MQTT_HOST", ""))
    mqtt_port: int = field(default_factory=lambda: int(os.getenv("MQTT_PORT") or 0))
    mqtt_username: str | None = field(default_factory=lambda: os.getenv("MQTT_USERNAME") or None)
    mqtt_password: str | None = field(default_factory=lambda: os.getenv("MQTT_PASSWORD") or None)
    mqtt_ca_cert: str | None = field(default_factory=lambda: os.getenv("MQTT_CA_CERT") or None)
    ubidots_token: str | None = field(default_factory=lambda: os.getenv("UBIDOTS_TOKEN") or None)
    ubidots_device: str | None = field(default_factory=lambda: os.getenv("UBIDOTS_DEVICE") or None)
    mqtt_transport: str = field(default_factory=lambda: os.getenv("MQTT_TRANSPORT", "").lower())
    mqtt_ws_path: str = field(default_factory=lambda: os.getenv("MQTT_WS_PATH", ""))
    mqtt_client_id: str = field(default_factory=lambda: os.getenv("MQTT_BRIDGE_CLIENT_ID", BRIDGE_CLIENT_ID))
    ubidots_min_interval: float = field(default_factory=lambda: float(
        os.getenv("UBIDOTS_MIN_INTERVAL_SECONDS") or DEFAULT_UBIDOTS_INTERVAL_SECONDS
    ))

    def __post_init__(self):
        if not self.mqtt_host or not 1 <= self.mqtt_port <= 65535:
            raise ValueError("informe MQTT_HOST e MQTT_PORT (1 a 65535)")
        if self.mqtt_transport not in {"ws", "wss", "mqtts"}:
            raise ValueError("MQTT_TRANSPORT deve ser ws, wss ou mqtts")
        if self.mqtt_transport in {"ws", "wss"} and not self.mqtt_ws_path.startswith("/"):
            raise ValueError("informe MQTT_WS_PATH começando com /")
        if self.mqtt_client_id != BRIDGE_CLIENT_ID:
            raise ValueError(f"MQTT_BRIDGE_CLIENT_ID deve ser {BRIDGE_CLIENT_ID}")

TOPICS = {f"cna/zona/{zone}/{kind}": (zone, kind) for zone in ("Z1", "Z2") for kind in ("temperatura", "telemetria", "estado", "evento")}
COMMAND_TOPICS = {f"cna/zona/{zone}/comando": zone for zone in ("Z1", "Z2")}
DRONE_MISSION_TOPIC = "cna/drone/missao"
DRONE_STATUS_TOPIC = "cna/drone/status"
