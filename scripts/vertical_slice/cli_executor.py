"""Thin subprocess wrapper around playwright-cli.

This module plays the role SPEC.md assigns to "the server": it keeps one
named browser session alive for the whole run and turns each AI tool call
into a `playwright-cli` invocation, returning the generated Playwright
TypeScript for that action. No network server is involved -- this is a
plain in-process function call boundary (see plan/detail/01-vertical-slice.md).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass


class CliError(RuntimeError):
    """Raised when playwright-cli reports a failed action."""


@dataclass
class ActionResult:
    generated_code: str | None
    raw_output: str


_CODE_BLOCK_RE = re.compile(r"### Ran Playwright code\n```(?:js)?\n(.*?)\n```", re.DOTALL)


def _resolve_base_command() -> list[str]:
    if shutil.which("playwright-cli"):
        return ["playwright-cli"]
    return ["npx", "--no-install", "playwright", "cli"]


class CliExecutor:
    """Drives a single named playwright-cli browser session.

    playwright-cli reports command failures as `### Error` text in stdout
    (exit code stays 0), so success can't be determined from the return
    code alone -- every call's stdout is inspected for that marker.
    """

    def __init__(self, session: str, base_command: list[str] | None = None):
        self.session = session
        self.base_command = base_command or _resolve_base_command()

    def _run(self, args: list[str]) -> str:
        cmd = [*self.base_command, f"-s={self.session}", *args]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise CliError(
                f"playwright-cli exited {proc.returncode}: {(proc.stderr or proc.stdout).strip()}"
            )
        return proc.stdout

    def execute(self, command: str, args: list[str]) -> ActionResult:
        out = self._run([command, *args])
        if "### Error" in out:
            raise CliError(out.split("### Error", 1)[1].strip())
        match = _CODE_BLOCK_RE.search(out)
        code = match.group(1).strip() if match else None
        return ActionResult(generated_code=code, raw_output=out)

    def open(self, url: str) -> ActionResult:
        return self.execute("open", [url])

    def snapshot_text(self) -> str:
        # snapshot --json is the one command whose --json output inlines the
        # snapshot text directly, instead of only a saved-file path.
        out = self._run(["snapshot", "--json"])
        return json.loads(out)["snapshot"]

    def close(self) -> None:
        try:
            self._run(["close"])
        except CliError:
            pass
