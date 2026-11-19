from dataclasses import dataclass
from typing import Any
import json

ZONES = {"Z1", "Z2"}
EVENTS = {"ALERTA", "CRITICO"}
COMMANDS = {"ARM", "DISARM", "ACK", "RESET"}

@dataclass(frozen=True)
class ZoneMessage:
    zone: str
    kind: str
    value: Any

    @classmethod
    def from_payload(cls, zone: str, kind: str, payload: str | bytes):
        if zone not in ZONES or kind not in {"temperatura", "telemetria", "estado", "evento"}:
            raise ValueError("zona ou tipo inválido")
        raw = payload.decode() if isinstance(payload, bytes) else str(payload)
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        if kind == "evento":
            if isinstance(value, dict):
                value = value.get("evento", value.get("event_type"))
            if not isinstance(value, str) or value not in EVENTS:
                raise ValueError("evento inválido")
        if kind == "temperatura":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("temperatura deve ser numérica")
        if kind == "estado" and not isinstance(value, str):
            raise ValueError("estado deve ser texto")
        if kind == "telemetria":
            if not isinstance(value, dict):
                raise ValueError("telemetria deve ser um objeto JSON")
            required = {"temperatura", "umidade", "movimento", "acesso", "tamper", "estado"}
            if set(value) != required:
                raise ValueError("telemetria incompleta")
            if (isinstance(value["temperatura"], bool) or not isinstance(value["temperatura"], (int, float)) or
                    isinstance(value["umidade"], bool) or not isinstance(value["umidade"], (int, float))):
                raise ValueError("telemetria climática inválida")
            if not isinstance(value["movimento"], bool) or value["acesso"] not in {"ABERTO", "FECHADO"} or value["tamper"] not in {"ACIONADO", "NORMAL"} or not isinstance(value["estado"], str):
                raise ValueError("telemetria de sensores inválida")
        return cls(zone, kind, value)
