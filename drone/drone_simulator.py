"""Máquina de estados local do drone simulado."""

from __future__ import annotations

from enum import StrEnum
from typing import Callable

from models import Mission, Status, VALID_RESULTS, utc_timestamp


class DroneState(StrEnum):
    DISPONIVEL = "DISPONIVEL"
    DECOLANDO = "DECOLANDO"
    EM_ROTA = "EM_ROTA"
    NA_ZONA = "NA_ZONA"
    INSPECIONANDO = "INSPECIONANDO"
    RETORNANDO = "RETORNANDO"
    CONCLUIDO = "CONCLUIDO"


class DroneSimulator:
    def __init__(self, drone_id: str = "DRONE-01", on_status: Callable[[Status], None] | None = None):
        self.drone_id = drone_id
        self.state = DroneState.DISPONIVEL
        self.active_mission: Mission | None = None
        self.processed_missions: set[str] = set()
        self.last_result: str | None = None
        self.on_status = on_status

    @property
    def available(self) -> bool:
        return self.active_mission is None

    def _emit(self, state: DroneState, result: str | None = None) -> Status:
        if self.active_mission is None:
            raise RuntimeError("não há missão ativa")
        self.state = state
        status = Status(self.drone_id, self.active_mission.mission_id, self.active_mission.zone_id,
                        state.value, result, utc_timestamp())
        if self.on_status:
            self.on_status(status)
        return status

    def accept_mission(self, mission: Mission) -> list[Status]:
        if mission.mission_id in self.processed_missions:
            raise ValueError(f"missão duplicada: {mission.mission_id}")
        if not self.available:
            raise RuntimeError("drone ocupado com outra missão")
        self.active_mission = mission
        self.processed_missions.add(mission.mission_id)
        self.last_result = None
        return []

    def run_mission(self, result: str) -> list[Status]:
        if self.active_mission is None:
            raise RuntimeError("não há missão ativa")
        if result not in VALID_RESULTS:
            raise ValueError("resultado de inspeção inválido")
        statuses = [
            self._emit(DroneState.DECOLANDO),
            self._emit(DroneState.EM_ROTA),
            self._emit(DroneState.NA_ZONA),
            self._emit(DroneState.INSPECIONANDO),
            self._emit(DroneState.RETORNANDO, result),
            self._emit(DroneState.CONCLUIDO, result),
        ]
        self.last_result = result
        self.active_mission = None
        self.state = DroneState.DISPONIVEL
        return statuses
