import json
import re

import pytest

from integration.bridge import IntegrationBridge
from integration.ubidots_client import UbidotsClient

def setup():
    sent=[]; ub=UbidotsClient(); b=IntegrationBridge(ub, lambda t,p: sent.append((t,p))); return b,sent,ub
def test_telemetry_and_mission_z1():
    b,s,_=setup(); b.handle_zone_message("cna/zona/Z1/temperatura", "25.5"); m=b.handle_zone_message("cna/zona/Z1/evento", "ALERTA"); assert m["zone_id"]=="Z1" and json.loads(s[0][1])["event_type"]=="ALERTA"
def test_duplicate_and_invalid_command():
    b,s,_=setup(); b.handle_zone_message("cna/zona/Z2/evento", "CRITICO"); assert b.handle_zone_message("cna/zona/Z2/evento", "CRITICO") is None
    try: b.handle_command("cna/zona/Z2/comando", "BOGUS"); assert False
    except ValueError: pass
def test_drone_status_and_local_without_credentials():
    b,_,ub=setup(); data=b.handle_drone_status('{"drone_id":"DRONE-01","mission_id":"m","zone_id":"Z2","status":"CONCLUIDO","inspection_result":"ANOMALIA_CONFIRMADA","timestamp":"t"}'); assert data["zone_id"]=="Z2" and ub.published

def test_rejects_invalid_telemetry_payloads():
    bridge, _, _ = setup()
    with pytest.raises(ValueError, match="temperatura deve ser numérica"):
        bridge.handle_zone_message("cna/zona/Z1/temperatura", "quente")


def test_json_events_publish_missions_and_deduplicate_by_zone_and_type():
    bridge, sent, ubidots = setup()
    z1 = "cna/zona/Z1/evento"
    z2 = "cna/zona/Z2/evento"

    first = bridge.handle_zone_message(z1, b'{"evento":"ALERTA","timestamp":"t1"}')
    assert bridge.handle_zone_message(z1, b'{"timestamp":"t2","event_type":"ALERTA"}') is None
    assert bridge.handle_zone_message(z1, b'ALERTA') is None
    second = bridge.handle_zone_message(z2, b'{"event_type":"ALERTA"}')
    third = bridge.handle_zone_message(z1, b'"CRITICO"')

    missions = [first, second, third]
    assert [(m["zone_id"], m["event_type"]) for m in missions] == [
        ("Z1", "ALERTA"), ("Z2", "ALERTA"), ("Z1", "CRITICO"),
    ]
    assert len(bridge.missions) == len(sent) == 3
    for mission, (topic, payload) in zip(missions, sent, strict=True):
        assert re.fullmatch(r"MISSION-[0-9A-F]{10}", mission["mission_id"])
        assert mission["command"] == "INSPECIONAR"
        assert topic == "cna/drone/missao"
        assert json.loads(payload) == mission
    assert ubidots.published[0] == {"z1_ultimo_evento": {"value": 2, "context": {"label": "ALERTA"}}}


@pytest.mark.parametrize("payload", [
    b'NORMAL', b'{}', b'["ALERTA"]', b'{"evento":{"tipo":"ALERTA"}}',
    b'{"event_type":["CRITICO"]}', b'{"evento":"NORMAL"}', b'{"evento":null}',
])
def test_invalid_event_json_is_rejected_before_side_effects(payload):
    bridge, sent, ubidots = setup()
    with pytest.raises(ValueError, match="evento inválido"):
        bridge.handle_zone_message("cna/zona/Z1/evento", payload)
    assert not (bridge.telemetry or bridge.missions or bridge.processed_events or sent or ubidots.published)


def test_telemetry_json_preserves_all_sensor_values_and_publishes_numeric_ubidots_fields():
    bridge, _, ubidots = setup()
    payload = '{"temperatura":24.0,"umidade":40.0,"movimento":true,"acesso":"ABERTO","tamper":"NORMAL","estado":"ATENCAO"}'

    message = bridge.handle_zone_message("cna/zona/Z1/telemetria", payload)

    assert message is None
    assert bridge.telemetry[("Z1", "telemetria")] == json.loads(payload)
    assert ubidots.published == [{
        "z1_temperatura": 24.0,
        "z1_umidade": 40.0,
        "z1_movimento": 1,
        "z1_acesso": 1,
        "z1_tamper": 0,
        "z1_estado": {"value": 1, "context": {"label": "ATENCAO"}},
    }]


def test_telemetry_requires_the_complete_sensor_contract():
    bridge, _, _ = setup()
    with pytest.raises(ValueError, match="telemetria incompleta"):
        bridge.handle_zone_message("cna/zona/Z1/telemetria", '{"temperatura":24}')
