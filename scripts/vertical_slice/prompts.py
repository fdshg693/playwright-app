"""Per-step prompt assembly for the Responses API calls.

build_input() is the *initial* input for one step's fresh `responses.create()`
call -- no history from other steps, no previous_response_id. Within a step,
the main loop appends tool call outputs and follow-up snapshots (see
build_snapshot_followup) directly to that input list to run a normal
multi-turn tool-calling loop, up to the next `finish_step` call. See SPEC.md
2章 / plan/detail/01-vertical-slice.md.
"""

from __future__ import annotations

from .story import Step

DEVELOPER_PROMPT = """\
あなたはPlaywrightを使ったブラウザ操作を1ステップだけ担当するエージェントです。

- 与えられるのは「残りのテストストーリー」と「現在の画面のsnapshot」だけです。過去のステップの操作履歴には一切依存できません。今回渡された情報だけで判断してください。
- 今回実行すべきなのは「現在のステップ」1つだけです。それ以降のステップは文脈として参考にしてよいですが、実行してはいけません。
- 画面操作にはsnapshotに載っているrefだけを使ってください（例: e5）。snapshotに存在しないrefを使ってはいけません。
- このステップは複数ターンに分けて進めます。操作系ツールを呼ぶと、その実行結果と最新のsnapshotが返され、続けて次の判断を求められます。結果を確認してから次の操作を選んでください。一度に複数の操作を見込みで並べる必要はありません。
- 確認のみのステップ（画面操作が不要なステップ）では、確認したい要素についてadd_expectationを呼んでください。要素が表示されていることを確認したい場合はmatcher="toBeVisible"、テキスト内容を確認したい場合はmatcher="toHaveText"を使ってください。add_expectationは他の操作系ツールと同じターンで一緒に呼んでもかまいません（finish_stepの単独呼び出し制約とは別です）。呼んだ後はfinish_stepのobservationにsnapshotから読み取った根拠を書いてください。
- finish_stepは、そのターンで他の操作系ツールと一緒に呼ばず、必ず単独で呼んでください。
  - 直前までの操作結果を確認し、このステップが完了したと判断できたら status="done" で finish_step を呼んでください
  - 現在のsnapshot・実行結果だけでは次に何をすべきか判断できない場合は status="blocked" とし、noteに理由を書いてください
"""


def build_input(remaining_steps: list[Step], current_step: Step, snapshot: str) -> list[dict]:
    remaining_text = "\n".join(
        f"{'→ ' if s.id == current_step.id else '  '}{s.id}. {s.instruction}"
        for s in remaining_steps
    )
    user_content = f"""## 残りのテストストーリー（→ が現在のステップ）

{remaining_text}

## 現在のステップ

{current_step.id}. {current_step.instruction}

## 現在の画面snapshot

```
{snapshot}
```
"""
    return [
        {"role": "developer", "content": DEVELOPER_PROMPT},
        {"role": "user", "content": user_content},
    ]


def build_snapshot_followup(snapshot: str) -> dict:
    """A follow-up user turn carrying the post-action snapshot, appended
    after each round of tool call outputs so the model can see what actually
    happened before deciding its next move."""

    return {
        "role": "user",
        "content": f"""## 操作後の最新snapshot

```
{snapshot}
```
""",
    }
