"""Start: uv run python -m weerwolven [--port 8000]"""
from __future__ import annotations

import argparse
import logging

import uvicorn

from .server import Hub, create_app, lan_ip


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="0.0.0.0")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    hub = Hub(port=args.port)
    app = create_app(hub)
    ip = lan_ip()
    print("\n" + "=" * 60)
    print("  WEERWOLVEN VAN WAKKERDAM")
    print(f"  Spelers (GSM):   http://{ip}:{args.port}/")
    print(f"  Hoofdscherm:     http://localhost:{args.port}/screen")
    print(f"  Host-paneel:     http://{ip}:{args.port}/host?key={hub.game.host_key}")
    print("=" * 60 + "\n")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
