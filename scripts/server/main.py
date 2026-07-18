"""Entry point: run the session server.

    python -m scripts.server.main --host 127.0.0.1 --port 8000

Loads `.env` (so `/run`'s OpenAI client can pick up OPENAI_API_KEY), parses
CLI args, and starts uvicorn against `app.app`. No wiring beyond that --
request handling lives in `app.py`, session lifecycle in
`session_manager.py`, AI orchestration in `orchestrator.py`.
"""

from __future__ import annotations

import argparse

import uvicorn
from dotenv import load_dotenv


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    uvicorn.run("scripts.server.app:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
