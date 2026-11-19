"""Entrada do simulador de drone em modo local ou MQTT."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from threading import Event

from drone_simulator import DroneSimulator
from models import Mission, VALID_RESULTS, utc_timestamp


def build_mission(zone: str, event: str, mission_id: str) -> Mission:
    return Mission(mission_id, zone, event, "INSPECIONAR", utc_timestamp())


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulador de drone CNA Sentinel")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--zone", choices=("Z1", "Z2"))
    mode.add_argument("--mqtt", action="store_true", help="aguarda missões publicadas no broker")
    parser.add_argument("--event", choices=("ALERTA", "CRITICO"), default="ALERTA")
    parser.add_argument("--result", choices=sorted(VALID_RESULTS), default="NADA_ENCONTRADO")
    parser.add_argument("--mission-id", default=None)
    args = parser.parse_args()
    if args.mqtt:
        from dotenv import load_dotenv
        from config import MqttConfig
        from mqtt_client import MqttTransport

        logging.basicConfig(level=logging.INFO)
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")

        def run_mission(mission):
            drone.accept_mission(mission)
            drone.run_mission(args.result)

        try:
            transport = MqttTransport(MqttConfig(), run_mission)
        except (OSError, ValueError, RuntimeError) as exc:
            parser.error(str(exc))
        drone = DroneSimulator(on_status=transport.publish_status)
        try:
            transport.connect()
            Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            transport.close()
        return 0

    mission_id = args.mission_id or f"LOCAL-{args.zone}-001"

    def show(status):
        print(f"[{status.timestamp}] {status.status} | zona={status.zone_id}"
              f" | resultado={status.inspection_result or '-'}")

    drone = DroneSimulator(on_status=show)
    mission = build_mission(args.zone, args.event, mission_id)
    print("Missão:", json.dumps(mission.__dict__, ensure_ascii=False))
    drone.accept_mission(mission)
    drone.run_mission(args.result)
    print(f"Missão concluída; drone em {drone.state.value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
