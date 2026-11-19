import json
from threading import Event
from time import monotonic
from unittest.mock import Mock

import pytest
import requests

from integration.bridge import IntegrationBridge
from integration.config import IntegrationConfig
from integration.ubidots_client import UbidotsClient


def response(status_code, body=""):
    result = requests.Response()
    result.status_code = status_code
    result._content = body.encode("utf-8")
    return result


def drone_status(status, result):
    return json.dumps({
        "drone_id": "DRONE-01", "mission_id": "m1", "zone_id": "Z1",
        "status": status, "inspection_result": result, "timestamp": "2026-11-17T00:00:00Z",
    })


def test_posts_numeric_values_with_text_context():
    session = Mock()
    session.post.return_value = response(200)
    ubidots = UbidotsClient("test-token", "cna-sentinel", session, min_interval=0.01)
    bridge = IntegrationBridge(ubidots)

    bridge.handle_zone_message("cna/zona/Z1/temperatura", "25.5")
    bridge.handle_zone_message("cna/zona/Z1/estado", "OFFLINE")
    bridge.handle_zone_message("cna/zona/Z2/evento", b'{"evento":"CRITICO"}')
    bridge.handle_drone_status(drone_status("DECOLANDO", None))
    bridge.handle_drone_status(drone_status("CONCLUIDO", "NADA_ENCONTRADO"))
    ubidots.close()

    payloads = [call.kwargs["json"] for call in session.post.call_args_list]
    assert payloads == [
        {"z1_temperatura": 25.5},
        {"z1_estado": {"value": 5, "context": {"label": "OFFLINE"}}},
        {"z2_ultimo_evento": {"value": 3, "context": {"label": "CRITICO"}}},
        {
            "estado_drone": {"value": 1, "context": {"label": "DECOLANDO"}},
            "zona_inspecionada": {"value": 1, "context": {"label": "Z1"}},
            "resultado_inspecao": {"value": 0, "context": {"label": "SEM_RESULTADO"}},
        },
        {
            "estado_drone": {"value": 6, "context": {"label": "CONCLUIDO"}},
            "zona_inspecionada": {"value": 1, "context": {"label": "Z1"}},
            "resultado_inspecao": {"value": 1, "context": {"label": "NADA_ENCONTRADO"}},
        },
    ]
    assert ubidots.published == payloads
    assert session.post.call_args.args == ("https://industrial.api.ubidots.com/api/v1.6/devices/cna-sentinel",)
    assert session.post.call_args.kwargs["headers"]["X-Auth-Token"] == "test-token"


def test_http_failure_preserves_mqtt_mission_and_drone_status(caplog):
    session = Mock()
    token = "temporary-test-secret"
    session.post.side_effect = [
        response(400, f'{{"code":400001,"detail":"erro de teste","secret":"{token}"}}'),
        response(503),
        response(200),
        response(200),
    ]
    ubidots = UbidotsClient(token, "cna-sentinel", session, min_interval=0.01)
    mqtt_publish = Mock()
    bridge = IntegrationBridge(ubidots, publish=mqtt_publish)

    mission = bridge.handle_zone_message("cna/zona/Z1/evento", "ALERTA")
    mqtt_publish.assert_called_once_with("cna/drone/missao", json.dumps(mission))
    assert bridge.missions[mission["mission_id"]] == mission
    status = drone_status("CONCLUIDO", "ANOMALIA_CONFIRMADA")
    assert bridge.handle_drone_status(status) == json.loads(status)
    assert bridge.drone_status["m1"] == json.loads(status)
    bridge.handle_zone_message("cna/zona/Z2/temperatura", "25")
    ubidots.close()

    payloads = [call.kwargs["json"] for call in session.post.call_args_list]
    assert payloads[1] == payloads[2]
    assert ubidots.published == [payloads[2], {"z2_temperatura": 25}]
    assert all(message in caplog.text for message in ("HTTP 400", "400001", "HTTP 503", "[redigido]"))
    assert token not in caplog.text


def test_timeout_retries_without_logging_exception_details(caplog):
    session = Mock()
    session.post.side_effect = [requests.Timeout("temporary-test-secret"), response(200)]
    ubidots = UbidotsClient("temporary-test-secret", "cna-sentinel", session, min_interval=0.01)
    assert ubidots.publish({"z1_temperatura": 25.5}) is True
    ubidots.close()
    assert ubidots.published == [{"z1_temperatura": 25.5}]
    assert "Timeout" in caplog.text
    assert "temporary-test-secret" not in caplog.text


@pytest.mark.parametrize("invalid_value", [float("nan"), float("inf"), -(10**400), True, "25"])
def test_invalid_temperature_is_filtered_before_http(invalid_value):
    session = Mock()
    ubidots = UbidotsClient("test-token", "cna-sentinel", session)
    assert ubidots.publish({"z1_temperatura": invalid_value}) is False
    session.post.assert_not_called()


def test_http_interval_comes_from_environment(monkeypatch):
    args = {"mqtt_host": "localhost", "mqtt_port": 8884, "mqtt_transport": "wss", "mqtt_ws_path": "/mqtt"}
    monkeypatch.delenv("UBIDOTS_MIN_INTERVAL_SECONDS", raising=False)
    assert IntegrationConfig(**args).ubidots_min_interval == 1.2
    monkeypatch.setenv("UBIDOTS_MIN_INTERVAL_SECONDS", "2.5")
    assert IntegrationConfig(**args).ubidots_min_interval == 2.5


def test_burst_of_drone_states_is_sent_in_order_at_minimum_interval():
    interval = 0.04
    calls = []

    def post(_url, *, json, **_kwargs):
        calls.append((monotonic(), json["estado_drone"]["context"]["label"]))
        return response(200)

    client = UbidotsClient("test-token", "cna-sentinel", Mock(post=post), min_interval=interval)
    bridge = IntegrationBridge(client)
    phases = ["DECOLANDO", "EM_ROTA", "NA_ZONA", "INSPECIONANDO", "RETORNANDO", "CONCLUIDO"]
    for phase in phases:
        bridge.handle_drone_status(drone_status(phase, None))
    client.close()

    assert [phase for _, phase in calls] == phases
    for (previous, _), (current, _) in zip(calls, calls[1:]):
        assert current - previous >= interval - 0.002


def test_http_429_retries_head_with_backoff_and_retry_after(caplog):
    calls = []
    limited = response(429)
    with_header = response(429)
    with_header.headers["Retry-After"] = "0.16"
    replies = iter([limited, limited, with_header, response(200), response(200)])

    def post(_url, *, json, **_kwargs):
        calls.append((monotonic(), json["z1_temperatura"]))
        return next(replies)

    client = UbidotsClient("test-token", "cna-sentinel", Mock(post=post), min_interval=0.02)
    client.publish({"z1_temperatura": 20})
    client.publish({"z1_temperatura": 21})
    client.close()

    assert [value for _, value in calls] == [20, 20, 20, 20, 21]
    waits = [current[0] - previous[0] for previous, current in zip(calls, calls[1:])]
    assert all(actual >= minimum - 0.002 for actual, minimum in zip(waits, (0.02, 0.04, 0.16, 0.02), strict=True))
    assert caplog.text.count("HTTP 429") == 3


def test_slow_http_does_not_block_bridge_or_shutdown(caplog):
    started, release = Event(), Event()

    def post(*_args, **_kwargs):
        started.set()
        release.wait(timeout=3)
        return response(200)

    session = Mock(post=Mock(side_effect=post))
    client = UbidotsClient("test-token", "cna-sentinel", session)
    mqtt_publish = Mock()
    bridge = IntegrationBridge(client, publish=mqtt_publish)
    try:
        bridge.handle_zone_message("cna/zona/Z1/temperatura", "25")
        assert started.wait(timeout=1)
        mission = bridge.handle_zone_message("cna/zona/Z1/evento", "ALERTA")
        bridge.handle_drone_status(drone_status("DECOLANDO", None))
        mqtt_publish.assert_called_once_with("cna/drone/missao", json.dumps(mission))
        assert bridge.drone_status["m1"]["status"] == "DECOLANDO"
        before_close = monotonic()
        client.close(timeout=0.05)
        assert monotonic() - before_close < 1
        assert client.publish({"z1_temperatura": 24}) is False
    finally:
        release.set()
        client.close()
    session.post.assert_called_once()
    assert "Prazo de encerramento" in caplog.text
