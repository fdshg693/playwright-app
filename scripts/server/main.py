"""Entry point: run the session server.

    python -m scripts.server.main --host 127.0.0.1 --port 8000

Parses CLI args and starts uvicorn against `app.app`. No wiring beyond
that -- request handling lives in `app.py`, session lifecycle in
`session_manager.py`.
"""

from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    uvicorn.run("scripts.server.app:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
