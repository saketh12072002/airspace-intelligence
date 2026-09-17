"""Standalone in-process Redis TCP server for local development without Docker."""

from __future__ import annotations

import signal
import sys
import fakeredis


def main() -> None:
    print("Starting in-memory Redis TCP server on 127.0.0.1:6379...", flush=True)
    server = fakeredis.TcpFakeServer(("127.0.0.1", 6379))

    def _sig_handler(sig: int, frame: object) -> None:
        print("\nShutting down Redis TCP server...", flush=True)
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _sig_handler(signal.SIGINT, None)


if __name__ == "__main__":
    main()
