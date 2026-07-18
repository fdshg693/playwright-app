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
from pathlib import Path


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

    def open(self, url: str | None = None) -> ActionResult:
        # No url: opens a blank browser/page (used by resume, which
        # fast-forwards via run_code instead of navigating directly).
        return self.execute("open", [url] if url else [])

    def snapshot_text(self) -> str:
        # snapshot --json is the one command whose --json output inlines the
        # snapshot text directly, instead of only a saved-file path.
        out = self._run(["snapshot", "--json"])
        data = json.loads(out)
        if data.get("isError"):
            # Some states (e.g. an open file-chooser modal) make snapshot
            # return this JSON shape instead of the "### Error" text marker
            # execute() checks for. Surface it the same way (CliError) so
            # callers don't need a separate isError code path.
            raise CliError(data.get("error") or "snapshot reported isError with no message")
        return data["snapshot"]

    def generate_locator(self, ref: str) -> str:
        # --raw strips the "### Ran Playwright code" wrapper entirely and
        # returns just the locator expression, so no _CODE_BLOCK_RE parsing
        # is needed here -- a plain strip is enough.
        return self._run(["generate-locator", ref, "--raw"]).strip()

    def eval_raw(self, script: str, ref: str | None = None) -> str:
        args = ["eval", script]
        if ref:
            args.append(ref)
        args.append("--raw")
        return self._run(args).strip()

    def screenshot(self, path: str) -> str:
        # `--filename=` resolves relative to this process's cwd (confirmed by
        # hand: it's neither the playwright-cli daemon's cwd nor
        # session-specific), same as `out_path` elsewhere in this package --
        # but unlike a plain file write, playwright-cli does not create
        # missing parent directories itself and errors with ENOENT.
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.execute("screenshot", [f"--filename={path}"])
        return path

    def run_code(self, source: str) -> ActionResult:
        return self.execute("run-code", [source])

    def console(self) -> str:
        # --raw strips the "### Result" wrapper only; the body (message list)
        # still flows through execute()'s normal ### Error / code-block checks.
        return self.execute("console", ["--raw"]).raw_output.strip()

    def requests(self) -> str:
        return self.execute("requests", ["--raw"]).raw_output.strip()

    def close(self) -> None:
        try:
            self._run(["close"])
        except CliError:
            pass
