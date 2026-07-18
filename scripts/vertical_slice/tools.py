"""Tool (function calling) definitions handed to the OpenAI Responses API.

Only the subset of playwright-cli commands needed for the demo scenario is
exposed, plus `finish_step`, which is not a CLI command at all but the
loop-control signal the AI must emit at the end of every step (see
plan/detail/01-vertical-slice.md).
"""

from __future__ import annotations

from .cli_executor import ActionResult, CliExecutor

_REF_PROPERTY = {"type": "string", "description": "snapshot内の要素ref（例: e5）"}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "name": "navigate",
        "description": "指定したURLへ遷移する（playwright-cli goto に相当）。",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "遷移先のURL"}},
            "required": ["url"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "click",
        "description": "snapshot内のrefで指定した要素をクリックする。",
        "parameters": {
            "type": "object",
            "properties": {"ref": _REF_PROPERTY},
            "required": ["ref"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "fill",
        "description": "snapshot内のrefで指定した入力欄にテキストを入力する。",
        "parameters": {
            "type": "object",
            "properties": {
                "ref": _REF_PROPERTY,
                "text": {"type": "string", "description": "入力するテキスト"},
                "submit": {
                    "type": "boolean",
                    "description": "trueの場合、入力後にEnterキーを押す",
                },
            },
            "required": ["ref", "text", "submit"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "press",
        "description": "キーボードのキーを押す（例: Enter, ArrowDown）。",
        "parameters": {
            "type": "object",
            "properties": {"key": {"type": "string", "description": "押すキー名"}},
            "required": ["key"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "select",
        "description": "snapshot内のrefで指定したドロップダウンから値を選択する。",
        "parameters": {
            "type": "object",
            "properties": {
                "ref": _REF_PROPERTY,
                "value": {"type": "string", "description": "選択する値"},
            },
            "required": ["ref", "value"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "check",
        "description": "snapshot内のrefで指定したチェックボックス/ラジオボタンをチェックする。",
        "parameters": {
            "type": "object",
            "properties": {"ref": _REF_PROPERTY},
            "required": ["ref"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "uncheck",
        "description": "snapshot内のrefで指定したチェックボックスのチェックを外す。",
        "parameters": {
            "type": "object",
            "properties": {"ref": _REF_PROPERTY},
            "required": ["ref"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "hover",
        "description": "snapshot内のrefで指定した要素にマウスホバーする。",
        "parameters": {
            "type": "object",
            "properties": {"ref": _REF_PROPERTY},
            "required": ["ref"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "finish_step",
        "description": (
            "現在のステップの完了（またはブロック）を宣言する。"
            "他の操作系ツールとは同じレスポンス内で一緒に呼ばず、"
            "直前までの操作結果を確認したうえで単独で呼ぶこと。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["done", "blocked"],
                    "description": (
                        "done: このステップは正常に完了した。"
                        "blocked: 現在のsnapshotだけでは次に何をすべきか判断できない。"
                    ),
                },
                "observation": {
                    "type": "string",
                    "description": (
                        "確認のみのステップで、snapshotから読み取った根拠。"
                        "該当しない場合は空文字でよい。"
                    ),
                },
                "note": {
                    "type": "string",
                    "description": "補足情報。blockedの場合は理由を書く。該当しない場合は空文字でよい。",
                },
            },
            "required": ["status", "observation", "note"],
            "additionalProperties": False,
        },
    },
]

_SIMPLE_REF_COMMANDS = {"click", "check", "uncheck", "hover"}


def execute_tool(cli: CliExecutor, name: str, args: dict) -> ActionResult:
    """Dispatch one non-finish_step tool call to the CLI. Raises CliError on failure."""

    if name == "navigate":
        return cli.execute("goto", [args["url"]])

    if name in _SIMPLE_REF_COMMANDS:
        return cli.execute(name, [args["ref"]])

    if name == "fill":
        cli_args = [args["ref"], args["text"]]
        if args.get("submit"):
            cli_args.append("--submit")
        return cli.execute("fill", cli_args)

    if name == "press":
        return cli.execute("press", [args["key"]])

    if name == "select":
        return cli.execute("select", [args["ref"], args["value"]])

    raise ValueError(f"unknown tool: {name}")
