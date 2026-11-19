from __future__ import annotations
import argparse, logging
import sys
from pathlib import Path
from threading import Event
from .bridge import IntegrationBridge
from .ubidots_client import UbidotsClient
from .config import IntegrationConfig

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--demo", action="store_true"); args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.demo:
        out = []
        bridge = IntegrationBridge(UbidotsClient(), publish=lambda topic, payload: out.append((topic, payload)))
        for zone in ("Z1", "Z2"):
            bridge.handle_zone_message(f"cna/zona/{zone}/temperatura", "24.0")
            mission = bridge.handle_zone_message(f"cna/zona/{zone}/evento", "CRITICO")
            print(zone, mission["mission_id"])
            sys.path.insert(0, str(Path(__file__).parents[1] / "drone"))
            from drone_simulator import DroneSimulator
            from models import Mission
            parsed = Mission.from_dict(mission)
            drone = DroneSimulator(on_status=lambda status: bridge.handle_drone_status(status.to_json()))
            drone.accept_mission(parsed)
            drone.run_mission("NADA_ENCONTRADO")
        print("comandos:", [bridge.handle_command("cna/zona/Z1/comando", c) for c in ("ARM", "DISARM", "ACK", "RESET")])
        print("publicações locais:", len(out))
        return

    from dotenv import load_dotenv
    from .mqtt_client import MqttBridgeTransport

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    try:
        config = IntegrationConfig()
        ubidots = UbidotsClient(
            config.ubidots_token, config.ubidots_device, min_interval=config.ubidots_min_interval,
        )
        bridge = IntegrationBridge(ubidots)
        transport = MqttBridgeTransport(config, bridge)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    try:
        transport.connect()
        Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            transport.close()
        finally:
            ubidots.close()
if __name__ == "__main__": main()
