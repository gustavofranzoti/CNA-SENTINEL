import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from drone_simulator import DroneSimulator, DroneState
from models import Mission


def mission(zone="Z1", mission_id="m1"):
    return Mission(mission_id, zone, "ALERTA", "INSPECIONAR", "2026-11-17T00:00:00Z")


def test_initial_state_and_full_sequence():
    drone = DroneSimulator()
    assert drone.state == DroneState.DISPONIVEL
    drone.accept_mission(mission())
    statuses = drone.run_mission("NADA_ENCONTRADO")
    assert [s.status for s in statuses] == [s.value for s in DroneState][1:]
    assert statuses[-1].inspection_result == "NADA_ENCONTRADO"
    assert drone.state == DroneState.DISPONIVEL


@pytest.mark.parametrize("zone", ["Z1", "Z2"])
def test_zones(zone):
    drone = DroneSimulator()
    drone.accept_mission(mission(zone))
    assert drone.active_mission.zone_id == zone


def test_confirmed_anomaly():
    drone = DroneSimulator()
    drone.accept_mission(mission())
    assert drone.run_mission("ANOMALIA_CONFIRMADA")[-1].inspection_result == "ANOMALIA_CONFIRMADA"


def test_invalid_and_concurrent_or_duplicate_missions():
    drone = DroneSimulator()
    with pytest.raises(ValueError):
        drone.accept_mission(Mission("m", "Z3", "ALERTA", "INSPECIONAR", "t"))
    drone.accept_mission(mission())
    with pytest.raises(RuntimeError):
        drone.accept_mission(mission("Z2", "m2"))
    drone.run_mission("NADA_ENCONTRADO")
    with pytest.raises(ValueError):
        drone.accept_mission(mission())
