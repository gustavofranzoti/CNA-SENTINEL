from __future__ import annotations
import json, logging, uuid
from .config import TOPICS, COMMAND_TOPICS, DRONE_MISSION_TOPIC, DRONE_STATUS_TOPIC
from .models import ZoneMessage, COMMANDS

class IntegrationBridge:
    def __init__(self, ubidots=None, publish=None, logger=None):
        self.ubidots = ubidots
        self.publish = publish or (lambda topic, payload: None)
        self.log = logger or logging.getLogger(__name__)
        self.telemetry, self.processed_events, self.missions = {}, set(), {}
        self.drone_status = {}

    def handle_zone_message(self, topic, payload):
        if topic not in TOPICS:
            raise ValueError("tópico de zona inválido")
        zone, kind = TOPICS[topic]
        msg = ZoneMessage.from_payload(zone, kind, payload)
        self.telemetry[(zone, kind)] = msg.value
        mission = self._event(zone, msg.value) if kind == "evento" else None
        if self.ubidots and kind != "telemetria":
            key = {"temperatura": "temperatura", "estado": "estado", "evento": "ultimo_evento"}[kind]
            self.ubidots.publish({f"{zone.lower()}_{key}": msg.value})
        elif self.ubidots:
            self.ubidots.publish({
                f"{zone.lower()}_temperatura": msg.value["temperatura"],
                f"{zone.lower()}_umidade": msg.value["umidade"],
                f"{zone.lower()}_movimento": 1 if msg.value["movimento"] else 0,
                f"{zone.lower()}_acesso": 1 if msg.value["acesso"] == "ABERTO" else 0,
                f"{zone.lower()}_tamper": 1 if msg.value["tamper"] == "ACIONADO" else 0,
                f"{zone.lower()}_estado": msg.value["estado"],
            })
        return mission

    def _event(self, zone, event):
        identity = (zone, event)
        if identity in self.processed_events:
            return None
        self.processed_events.add(identity)
        mission_id = f"MISSION-{uuid.uuid4().hex[:10].upper()}"
        mission = {"mission_id": mission_id, "zone_id": zone, "event_type": event, "command": "INSPECIONAR", "timestamp": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat().replace('+00:00','Z')}
        self.missions[mission_id] = mission
        self.publish(DRONE_MISSION_TOPIC, json.dumps(mission))
        return mission

    def handle_command(self, topic, payload, *, publish=True):
        if topic not in COMMAND_TOPICS:
            raise ValueError("tópico de comando inválido")
        command = str(payload.decode() if isinstance(payload, bytes) else payload).strip().upper()
        if command not in COMMANDS:
            raise ValueError("comando inválido")
        if publish:
            self.publish(topic, command)
        return command

    def handle_drone_status(self, payload):
        data = json.loads(payload.decode() if isinstance(payload, bytes) else payload)
        for key in ("drone_id", "mission_id", "zone_id", "status", "timestamp"):
            if key not in data: raise ValueError("status do drone incompleto")
        self.drone_status[data["mission_id"]] = data
        if self.ubidots:
            self.ubidots.publish({
                "estado_drone": data["status"],
                "zona_inspecionada": data["zone_id"],
                "resultado_inspecao": data.get("inspection_result") or "SEM_RESULTADO",
            })
        return data
