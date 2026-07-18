# Step 1: 実行ごとに残るログファイルへの変更

> [00-overview.md](00-overview.md)の続き。

## やること

`<out>.steps.jsonl`/`<out>.tasks.jsonl`を、実行のたびに`unlink()`で消してから同じパスに追記する現行方式をやめ、実行ごとに一意な`run_id`を発行してファイル名に埋め込む方式に変える。CLI（`main.py`）・サーバー（`app.py`/`orchestrator.py`）の両方の呼び出し経路を直す。

## 読むべきファイル・実行推奨Grep

**現行のログパス生成・上書き箇所を正確に把握するため（優先度: 高）**
- 読む: `scripts/vertical_slice/step_log.py` — `step_log_path()`/`append_step_log()`。パス生成ロジックの現在の実体
- 読む: `scripts/vertical_slice/task_log.py` — `task_log_path()`/`append_task_log()`/`recordings_dir()`。screenshotディレクトリの命名規則（`{stem}.recordings/`）が今回`history_dir()`を作るときの前例になる
- Grep: `unlink(missing_ok=True)` — `runner.py`・`orchestrator.py`に計4箇所。全て削除対象

**`run_id`を通す必要がある呼び出し経路を洗うため（優先度: 高）**
- 読む: `scripts/vertical_slice/runner.py` — `run_vertical_slice`/`resume_vertical_slice`/`run_steps`/`run_task_logged_step`/`log_seed_task`。`out_path`を受け渡している箇所と同じ経路で`run_id`も通す
- 読む: `scripts/vertical_slice/step_runner.py` — `run_step()`。`append_step_log`呼び出し箇所に`run_id`を渡す
- 読む: `scripts/server/orchestrator.py` — `run_story`/`resume_story`。`runner.py`と同じ`unlink`パターンを持つ独立した呼び出し元
- 読む: `scripts/server/schemas.py` — `RunResponse`/`ResumeResponse`。呼び出し元がログファイルの実パスを後から特定できるよう、レスポンスに`run_id`を足す必要がある
- 読む: `scripts/vertical_slice/main.py` — CLI側は`run_id`をレスポンスとして返す先が無いので、`logging`で標準出力に出すだけで足りる

**再開機能（Step5）への影響を確認するため（優先度: 中）**
- 読む: `.claude/rules/vertical-slice-runner.md` の「記録と途中再開・分岐」節 — `resume_vertical_slice`が`tasks_log_path`（＝再開元）を読んだ**後**に自分の新規ログを`unlink`している現行の順序に依存していないか確認（`run_id`化で新規ログは別ファイルになるため、この順序制約自体が不要になる。単純化であって新たなリスクではないことの確認）

## 触るファイル

### 新規
- `scripts/vertical_slice/run_id.py` — `new_run_id() -> str`（ソート可能なローカル時刻文字列、例`20260719T153012`）と、ファイル名先頭の`run_id`プレフィックスを読み取って`datetime`に戻す`parse_run_id_prefix(name: str) -> datetime | None`を持つ。命名フォーマットの単一の権威とし、Step2の`cost_log_discovery.py`もここを import する

### 変更
- `scripts/vertical_slice/step_log.py` — `step_log_path(out_path, run_id)`に変更。`history_dir(out_path)`（`task_log.recordings_dir`と対になる、`{parent}/{stem}.history/`）配下に`{run_id}__{stem}.steps.jsonl`を書くようにする
- `scripts/vertical_slice/task_log.py` — 同様に`task_log_path(out_path, run_id)`へ変更し、`{run_id}__{stem}.tasks.jsonl`を`history_dir(out_path)`配下に書く。`history_dir()`はここに新設し`step_log.py`から import する（`recordings_dir`と同じファイルにある方が対称性が高い）
- `scripts/vertical_slice/step_runner.py` — `run_step(..., out_path, run_id)`に引数追加し、`append_step_log(entry, out_path, run_id)`へ渡す
- `scripts/vertical_slice/runner.py` — `run_vertical_slice`/`resume_vertical_slice`の先頭で`run_id = new_run_id()`を発行し、戻り値に含める（呼び出し元がログの場所を特定できるように、`bool`単体ではなく`(passed, run_id)`を返すようにシグネチャ変更）。`run_steps`/`run_task_logged_step`/`log_seed_task`にも`run_id`を引き回す。4箇所の`unlink()`呼び出しは削除
- `scripts/vertical_slice/main.py` — `run_vertical_slice`/`resume_vertical_slice`の戻り値変更に追従し、`run_id`を`logger.info`で出力する
- `scripts/server/orchestrator.py` — `run_story`/`resume_story`で同様に`run_id`を発行・引き回し・返却する
- `scripts/server/schemas.py` — `RunResponse`/`ResumeResponse`に`run_id: str`を追加
- `scripts/server/app.py` — `orchestrator.run_story`/`resume_story`の戻り値変更（`run_id`追加）に追従してレスポンス組み立てを直す

## 決定事項・注意点／落とし穴

| 決定 | 理由 |
|---|---|
| ログ本体は`history_dir(out_path)`という`out_path`の親配下の新規サブディレクトリ（`{stem}.history/`）に置き、`tests/generated/`直下には増やさない | `tests/generated/`直下は`.spec.ts`/`.failure-notes.json`/`{stem}.recordings/`という「現在の状態」だけを置く場所として保っておきたい。実行回数分増え続ける履歴ファイルを直下に混ぜると、エディタでの一覧性や将来の保守が悪化する |
| ファイル名は`{run_id}__{stem}`のように`run_id`を先頭に置き、`stem`（シナリオ名を含む）を含める。`history_dir()`によってシナリオごとにディレクトリが分かれていても、ファイル名だけで見てシナリオが分かるようにする | 将来ログをディレクトリ外にコピー・集約しても（Step2のディレクトリ再帰スキャン等）ファイル名だけからシナリオと実行時刻の両方が読み取れるようにするため |
| `run_id`は秒精度（`%Y%m%dT%H%M%S`）。衝突検知や連番付与などの追加ロジックは入れない | 1回のAI駆動実行は数十秒〜数分かかり、同一シナリオを同一秒内に2回起動する運用は現実的に無い。将来問題になったら初めて対処すればよいYAGNI |
| 既存の`tests/generated/*.steps.jsonl`/`*.tasks.jsonl`（`run_id`プレフィックスの無い旧形式）は移行しない。そのまま放置し、Step2の`cost_log_discovery.py`側でファイル`mtime`フォールバックとして扱う | 移行スクリプトを書くコストに対して得られる価値が薄い（旧ログは1実行分の最新状態のみで、そもそも履歴比較の役に立たない）。過去分は「参考程度」で十分 |
| `resume_vertical_slice`の「`tasks_log_path`を読んでから自分の新規ログを`unlink`する」という順序制約は、`run_id`化で新規ログが別ファイルになるため consequenceが無くなる。順序自体は変えなくてよい（`build_resume_state`呼び出し→`run_id`発行はどちらが先でも安全になる） | 単純化であり退行ではないことをここで明言し、実装時に「順序を保たなければ」という余計な配慮をしなくて済むようにする |
| `run_vertical_slice`/`resume_vertical_slice`の戻り値を`bool`から`(bool, str)`に変える破壊的変更を許容する | 呼び出し元は`main.py`と`orchestrator.py`の2箇所のみで、どちらも本プランで同時に直すため影響範囲が閉じている。`run_id`を呼び出し元に返さないと、実行後にどのログファイルを見ればいいか特定する手段が無くなり本末転倒 |

## `.claude/rules` 更新ポイント

- `vertical-slice-runner.md`: `step_log.py`/`task_log.py`の項を更新し、`history_dir()`・`run_id`ベースの命名・`unlink`廃止を反映する。「記録と途中再開・分岐（Step5）」節の`resume_vertical_slice`の説明から「読んだ後に自分のログをunlinkする」という現行の順序前提の記述を削る
- `session-server.md`: `run_story`/`resume_story`が`run_id`を発行・`RunResponse`/`ResumeResponse`で返却するようになったことを追記
