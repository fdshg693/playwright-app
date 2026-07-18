from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Step:
    id: int
    instruction: str


@dataclass(frozen=True)
class Story:
    seed_url: str
    steps: list[Step]
    name: str
    intent: str


def load_story(path: str) -> Story:
    story_path = Path(path)
    with story_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    steps = [Step(id=s["id"], instruction=s["instruction"]) for s in data["steps"]]
    name = data.get("name", story_path.stem)
    return Story(seed_url=data["seed_url"], steps=steps, name=name, intent=data["intent"])
