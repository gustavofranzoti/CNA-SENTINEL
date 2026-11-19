"""Modelos e serialização das mensagens do drone."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any


VALID_ZONES = {"Z1", "Z2"}
VALID_EVENTS = {"ALERTA", "CRITICO"}
VALID_COMMANDS = {"INSPECIONAR"}
VALID_RESULTS = {"NADA_ENCONTRADO", "ANOMALIA_CONFIRMADA"}


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Mission:
    mission_id: str
    zone_id: str
    event_type: str
    command: str
    timestamp: str

    def __post_init__(self) -> None:
        if not self.mission_id:
            raise ValueError("mission_id não pode ser vazio")
        if self.zone_id not in VALID_ZONES:
            raise ValueError("zone_id deve ser Z1 ou Z2")
        if self.event_type not in VALID_EVENTS:
            raise ValueError("event_type deve ser ALERTA ou CRITICO")
        if self.command not in VALID_COMMANDS:
            raise ValueError("command deve ser INSPECIONAR")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Mission":
        required = {"mission_id", "zone_id", "event_type", "command", "timestamp"}
        missing = required - payload.keys()
        if missing:
            raise ValueError(f"campos ausentes: {', '.join(sorted(missing))}")
        values = {key: str(payload[key]) for key in required}
        return cls(**values)

    @classmethod
    def from_json(cls, message: str) -> "Mission":
        try:
            payload = json.loads(message)
        except json.JSONDecodeError as exc:
            raise ValueError("JSON inválido") from exc
        if not isinstance(payload, dict):
            raise ValueError("payload deve ser um objeto JSON")
        return cls.from_dict(payload)


@dataclass(frozen=True)
class Status:
    drone_id: str
    mission_id: str
    zone_id: str
    status: str
    inspection_result: str | None
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "drone_id": self.drone_id,
            "mission_id": self.mission_id,
            "zone_id": self.zone_id,
            "status": self.status,
            "inspection_result": self.inspection_result,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))
