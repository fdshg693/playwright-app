"""Entry point: run one story end-to-end with no human mediation.

    python -m scripts.vertical_slice.main --story scripts/stories/search-demo.yaml

Parses CLI args and wires together the story loader, playwright-cli session,
and OpenAI client, then delegates the actual run to
`runner.run_vertical_slice()` (see that module, and `step_runner.run_step`,
for the story/step-level flow; `step_log` for the `<out>.steps.jsonl` format).
"""

from __future__ import annotations

import argparse
import logging

from dotenv import load_dotenv
from openai import OpenAI

from . import config
from .cli_executor import CliExecutor
from .runner import run_vertical_slice
from .story import load_story


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", required=True, help="path to a story YAML file")
    parser.add_argument("--session", default="vertical-slice", help="playwright-cli session name")
    parser.add_argument("--model", default=None, help="overrides the AI_MODEL env var / default")
    parser.add_argument(
        "--out",
        default="tests/generated/search-demo.spec.ts",
        help="path to write the generated .spec.ts file",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    story = load_story(args.story)
    model = args.model or config.get_model()
    client = OpenAI(api_key=config.get_api_key(), base_url=config.get_base_url())
    cli = CliExecutor(session=args.session)

    try:
        passed = run_vertical_slice(story, cli, client, model, args.out)
    finally:
        cli.close()

    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
