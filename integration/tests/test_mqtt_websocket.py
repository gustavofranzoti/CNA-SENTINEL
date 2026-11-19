"""Teste local dos dois executáveis contra um broker MQTT via WS ou WSS."""

import asyncio
from contextlib import ExitStack
import json
import os
from pathlib import Path
from queue import SimpleQueue
import socket
import subprocess
import sys

import paho.mqtt.client as mqtt
import pytest

PHASES = ["DECOLANDO", "EM_ROTA", "NA_ZONA", "INSPECIONANDO", "RETORNANDO", "CONCLUIDO"]
ROOT = Path(__file__).resolve().parents[2]
WS_PATH = "/sentinel-test"


async def wait_for(condition, description):
    for _ in range(200):
        if condition():
            return
        await asyncio.sleep(0.05)
    pytest.fail(f"tempo esgotado aguardando {description}")


@pytest.mark.parametrize("transport", ["ws", "wss"])
def test_websocket_roundtrip_and_reconnect(tmp_path, transport):
    Broker = pytest.importorskip("amqtt.broker").Broker
    listener = {"type": "ws"}
    ca_file = ""
    if transport == "wss":
        trustme = pytest.importorskip("trustme")
        ca = trustme.CA()
        ca_file = str(tmp_path / "ca.pem")
        ca.cert_pem.write_to_path(ca_file)
        certificate = ca.issue_cert("127.0.0.1")
        certificate.cert_chain_pems[0].write_to_path(tmp_path / "server.pem")
        certificate.private_key_pem.write_to_path(tmp_path / "server.key")
        listener.update(ssl=True, certfile=tmp_path / "server.pem", keyfile=tmp_path / "server.key")

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    listener["bind"] = f"127.0.0.1:{port}"
    broker_config = {
        "listeners": {"default": listener},
        "plugins": {"amqtt.plugins.authentication.AnonymousAuthPlugin": {"allow_anonymous": True}},
    }
    env = {
        **os.environ, "MQTT_HOST": "127.0.0.1", "MQTT_PORT": str(port),
        "MQTT_TRANSPORT": transport, "MQTT_WS_PATH": WS_PATH, "MQTT_CA_CERT": ca_file,
        "MQTT_USERNAME": "", "MQTT_PASSWORD": "", "MQTT_CLIENT_CERT": "", "MQTT_CLIENT_KEY": "",
        "MQTT_BRIDGE_CLIENT_ID": "cna-sentinel-bridge", "MQTT_DRONE_CLIENT_ID": "cna-sentinel-drone",
        "UBIDOTS_TOKEN": "", "UBIDOTS_DEVICE": "", "PYTHONIOENCODING": "utf-8",
    }
    bridge_log, drone_log = (tmp_path / name for name in ("bridge.log", "drone.log"))

    def logs(path):
        return path.read_text(encoding="utf-8")

    async def run():
        ready = SimpleQueue()
        incoming = SimpleQueue()
        observer = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "sentinel-test", transport="websockets")
        observer.ws_set_options(path=WS_PATH)
        if ca_file:
            observer.tls_set(ca_certs=ca_file)
        observer.on_connect = lambda client, *_: client.subscribe("cna/#", qos=1)
        observer.on_subscribe = lambda _client, _userdata, _mid, reasons, _props: ready.put(reasons)
        observer.on_message = lambda _client, _userdata, msg: incoming.put((msg.topic, msg.payload.decode()))
        received = []

        def messages(topic):
            while not incoming.empty():
                received.append(incoming.get_nowait())
            return [payload for name, payload in received if name == topic]

        def publish(topic, payload):
            assert observer.publish(topic, payload, qos=1).rc == mqtt.MQTT_ERR_SUCCESS

        async def roundtrip(zone, event):
            prefix = f"cna/zona/{zone}"
            publish(f"{prefix}/temperatura", "25.5")
            publish(f"{prefix}/estado", "NORMAL")
            publish(f"{prefix}/comando", "ACK")
            publish(f"{prefix}/comando", "INVALIDO")
            publish("cna/drone/missao", "invalid JSON")
            publish(f"{prefix}/evento", json.dumps({"evento": event}))
            await wait_for(lambda: len(messages("cna/drone/status")) == len(PHASES), f"status de {zone}")
            mission, = [json.loads(payload) for payload in messages("cna/drone/missao") if payload.startswith("{")]
            statuses = [json.loads(payload) for payload in messages("cna/drone/status")]
            assert (mission["zone_id"], mission["event_type"], mission["command"]) == (zone, event, "INSPECIONAR")
            assert [status["status"] for status in statuses] == PHASES
            assert all(status["mission_id"] == mission["mission_id"] and status["zone_id"] == zone
                       for status in statuses)
            assert statuses[-1]["inspection_result"] == "ANOMALIA_CONFIRMADA"
            assert f"'{zone.lower()}_temperatura': 25.5" in logs(bridge_log)
            assert f"'{zone.lower()}_estado': {{'value': 0, 'context': {{'label': 'NORMAL'}}}}" in logs(bridge_log)
            await wait_for(
                lambda: any("'label': 'CONCLUIDO'" in line and f"'label': '{zone}'" in line
                            for line in logs(bridge_log).splitlines()),
                f"status de {zone} recebido pela Bridge",
            )
            publish("cna/drone/missao", json.dumps(mission))
            await wait_for(lambda: f"missão duplicada: {mission['mission_id']}" in logs(drone_log), "rejeição duplicada")
            await wait_for(lambda: f"falha ao processar {prefix}/comando" in logs(bridge_log), "comando inválido")
            assert len(messages("cna/drone/status")) == len(PHASES)
            assert messages(f"{prefix}/comando") == ["ACK", "INVALIDO"]
            received.clear()

        with ExitStack() as stack:
            for path, args in (
                (bridge_log, ["-m", "integration.main"]),
                (drone_log, ["drone/main.py", "--mqtt", "--result", "ANOMALIA_CONFIRMADA"]),
            ):
                output = stack.enter_context(path.open("wb"))
                proc = subprocess.Popen([sys.executable, *args], cwd=ROOT, env=env, stdout=output, stderr=output)
                stack.callback(proc.wait, timeout=5)
                stack.callback(proc.terminate)
            await wait_for(lambda: "falha ao conectar" in logs(bridge_log) and "falha ao conectar" in logs(drone_log),
                           "falha inicial da Bridge e do drone")
            observer.connect_async("127.0.0.1", port)
            observer.loop_start()
            try:
                for attempt, (zone, event) in enumerate((("Z1", "ALERTA"), ("Z2", "CRITICO")), 1):
                    broker = Broker(broker_config)
                    await broker.start()
                    try:
                        await wait_for(lambda: not ready.empty(), "assinatura cna/#")
                        assert not any(reason.is_failure for reason in ready.get_nowait())
                        await wait_for(lambda: logs(bridge_log).count("assinaturas confirmadas") == attempt and
                                       logs(drone_log).count("assinatura de missões confirmada") == attempt,
                                       "assinaturas da Bridge e do drone")
                        await roundtrip(zone, event)
                    finally:
                        await broker.shutdown()
                    await wait_for(lambda: "Bridge desconectada" in logs(bridge_log) and
                                   "drone desconectado" in logs(drone_log), "detecção de perda de conexão")
            finally:
                observer.disconnect()
                observer.loop_stop()

    asyncio.run(run())
