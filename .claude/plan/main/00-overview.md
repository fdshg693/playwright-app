# SPEC.md実装 詳細プラン - 概要

[big_plans/00-overview.md](../../../big_plans/00-overview.md) の各ステップを、実装に踏み込んだ詳細プランとして展開したもの。書き方は[README.md](../README.md)の方針・[references/](../references/)のサンプルに従う。

## 要件

- [SPEC.md](../../../SPEC.md) に定義されたAI駆動E2Eテスト生成の仕組みを、MVPをまず縦に1本通してから機能を足していく順序で実装する。
- 各ステップの目的・完了条件は big_plans 側の概要ファイル（各ステップ冒頭からリンク）に従う。この詳細プラン側は「どう実装するか」の決定事項に絞る。

## 実装ステップ

1. [01-vertical-slice.md](01-vertical-slice.md) — サーバーなしでコアループが成立するかをPython自動スクリプトで検証する（実装・実行済み）
2. [02-server-skeleton.md](02-server-skeleton.md) — Playwright CLIセッションを永続させるサーバーの骨組み
3. [03-task-orchestration.md](03-task-orchestration.md) — 1タスク＝1フレッシュコンテキストのAI呼び出しオーケストレーション自動化
4. [04-code-generation-assembly.md](04-code-generation-assembly.md) — 生成コードのテストファイルへの組み立て（`// N.`ステップコメント付与 + `add_expectation`ツールによる`expect`アサーション生成）
5. [05-recording-and-resume.md](05-recording-and-resume.md) — 操作ログ・スクリーンショットの記録と途中再開（詳細は後に記載）
6. [06-failure-handling.md](06-failure-handling.md) — リトライと失敗時の診断情報つき停止（詳細は後に記載）
7. [07-human-observation-and-control.md](07-human-observation-and-control.md) — 人間による進捗確認・強制停止（詳細は後に記載）
8. [08-safety-guardrails.md](08-safety-guardrails.md) — 対象URL固定などの最低限の安全策（詳細は後に記載）

## 主要な決定事項

| 決定 | 理由 |
|---|---|
| Step1はネットワークサーバー化せず、`CliExecutor`というコード上のモジュール境界だけを用意する | Step2でこの境界をそのままネットワークサーバーへ切り出す想定のため。詳細は[[01-vertical-slice]] |
| AI呼び出しは`previous_response_id`を使わず、タスクごとに`input`をゼロから組み立てる | SPEC.md 2章「1タスク＝1フレッシュコンテキスト」を隠れた状態に依存せず保証するため |
| Step2でStep1の`CliExecutor`境界をFastAPIによるネットワークサーバーへ切り出す（`session_id`はplaywright-cliの`-s=`セッション名と1:1対応） | Step1の決定表どおり「Step2でこの境界をそのままネットワークサーバーへ切り出す想定」を実行するため。詳細は[[02-server-skeleton]] |
| Step3では新しいAIループを書かず、Step1の`step_runner.run_step`（`finish_step`宣言によるステップ完了判定）をサーバーから再利用する。`POST /sessions/{id}/run`はHTTPリクエスト内で同期的に最後まで実行し、進捗ストリーミングは作らない | Step1で動作確認済みの設計に乗ることでStep3のリスクを増やさないため。進捗可視化・強制停止はStep7のスコープ。詳細は[[03-task-orchestration]] |
| Step4は新しいAIループを追加せず、`add_expectation`という新規ツールをStep1の操作系ツール群に1つ追加するだけに留める。`finish_step`の単独ターン制御など`step_runner.run_step`のループ制御ロジックには手を入れない | 既存のターン制御を変えずに`tools.py`/`prompts.py`側の追加だけで`expect`アサーション生成を実現できるため。詳細は[[04-code-generation-assembly]] |

Step5以降の決定事項は、各ステップの詳細が固まり次第この表に追記する。

## 変更/新規ファイル一覧

（各ファイルの役割・読むべき既存ファイルは各ステップを参照）

### 新規（Step1で実装・実行済み）
- `scripts/vertical_slice/`（`main.py` / `cli_executor.py` / `tools.py` / `prompts.py` / `story.py` / `config.py`）
- `scripts/stories/search-demo.yaml`
- `tests/generated/search-demo.spec.ts`

### 新規（Step2）
- `scripts/server/`（`app.py` / `session_manager.py` / `schemas.py` / `main.py`）

### 変更（Step2）
- `pyproject.toml` — `fastapi`・`uvicorn`を依存に追加

### 今後（Step3以降）
後に記載。

## `.claude/rules` 更新ポイント

- 現時点でルール新設・更新は無し。Step2以降で`scripts/`配下の構成（サーバー化後のモジュール分割）が固まった時点で検討する。
