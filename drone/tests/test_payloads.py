import sys
from pathlib import Path
import json

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from models import Mission, Status


def test_mission_validation_and_json():
    raw = '{"mission_id":"m1","zone_id":"Z2","event_type":"CRITICO","command":"INSPECIONAR","timestamp":"t"}'
    assert Mission.from_json(raw).zone_id == "Z2"
    with pytest.raises(ValueError):
        Mission.from_json('{"zone_id":"Z1"}')
    with pytest.raises(ValueError):
        Mission.from_json('{"mission_id":"m","zone_id":"Z9","event_type":"ALERTA","command":"INSPECIONAR","timestamp":"t"}')


def test_status_serialization():
    status = Status("DRONE-01", "m1", "Z1", "CONCLUIDO", "NADA_ENCONTRADO", "t")
    payload = json.loads(status.to_json())
    assert payload["status"] == "CONCLUIDO"
    assert payload["inspection_result"] == "NADA_ENCONTRADO"
