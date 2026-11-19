import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from drone_simulator import DroneSimulator
from models import Mission


def test_status_callback_receives_all_phases():
    received = []
    drone = DroneSimulator(on_status=received.append)
    drone.accept_mission(Mission("m2", "Z2", "CRITICO", "INSPECIONAR", "t"))
    drone.run_mission("ANOMALIA_CONFIRMADA")
    assert [s.status for s in received] == [
        "DECOLANDO", "EM_ROTA", "NA_ZONA", "INSPECIONANDO", "RETORNANDO", "CONCLUIDO"
    ]
