from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .server import SamadminServer
from .client import SamadminClient


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="samadmin")
    parser.add_argument("command", choices=("serve", "pending", "approve", "reject"))
    parser.add_argument("--root", default="runtime/samadmin")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8765")
    parser.add_argument("--request-id")
    parser.add_argument("--operator", default="Samadmin")
    args = parser.parse_args(argv)
    if args.command == "serve":
        token = os.environ.get("SAMADMIN_ADMIN_TOKEN", "")
        if not token:
            parser.error("Define SAMADMIN_ADMIN_TOKEN antes de iniciar Samadmin")
        server = SamadminServer(Path(args.root), admin_token=token, port=args.port)
        print("SAMADMIN_URL=" + server.url, flush=True)
        try:
            server.httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[Samadmin] Interrupción por el usuario. Apagando servidor...", flush=True)
        finally:
            server.close()
        return 0
    client = SamadminClient(args.endpoint)
    if args.command == "pending":
        print(json.dumps(client.pending(), ensure_ascii=False, indent=2))
        return 0
    if not args.request_id:
        parser.error("approve/reject requiere --request-id")
    token = os.environ.get("SAMADMIN_ADMIN_TOKEN", "")
    if not token:
        parser.error("Define SAMADMIN_ADMIN_TOKEN para decidir una solicitud")
    result = client.decide(
        args.request_id, approved=args.command == "approve",
        operator=args.operator, admin_token=token)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())