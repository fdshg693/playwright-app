# オブザーバビリティ（コスト集計）強化 実装プラン - 概要

> [.claude/rules/plans.md](../../rules/plans.md) が定める `big_plans`⇔`.claude/plan/main` の1対1対応の外側にあるサブプラン（[custom_pages](../custom_pages/00-overview.md)・[scenarios](../scenarios/00-overview.md)と同種）。対応する`big_plans/0N-*.md`は無い。`.claude/plan/main`のStep5（記録・途中再開）まで実装済みの状態からの脇道で、SPEC.mdの実装ロードマップとは独立に進める。

## 要件

- vertical_slice / session-server は同じシナリオを再実行すると`<out>.steps.jsonl`/`<out>.tasks.jsonl`を毎回同じパスに上書きしており（`runner.py`/`orchestrator.py`の`unlink()`→追記）、過去実行の履歴が残らない。まずこれを解消し、実行のたびに時刻昇順かつシナリオが分かるファイル名で残す。
- `scripts/internal/cost_summary.py`を、複数ファイル指定・ディレクトリ指定（配下の`*.steps.jsonl`のみ対象）・開始/終了時刻によるファイル絞り込みに対応させ、「推移」と「累計コスト」が一目で分かるようにする。
- 上記に伴い安定運用上必要な最低限の頑健性（壊れた行のスキップ、該当ファイル0件時の扱い、ファイルごとに異なるモデルの正しい按分等）を足す。1ファイルに詰め込まず、責務ごとにファイル分割する。
- 専用ダッシュボードUIは今回のスコープに含めない（後続プランで着手、[03-dashboard.md](03-dashboard.md)に置き場だけ用意）。

## 実装ステップ

1. [01-run-scoped-logs.md](01-run-scoped-logs.md) — `<out>.steps.jsonl`/`<out>.tasks.jsonl`を実行ごとに残る run-scoped なパスへ変更し、`unlink()`による上書きを廃止する
2. [02-cost-summary-cli.md](02-cost-summary-cli.md) — `cost_summary.py`を複数ファイル/ディレクトリ/時間範囲対応にし、責務ごとのモジュールへ分割する
3. [03-dashboard.md](03-dashboard.md) — `cost_summary.py`に`--html`オプションを追加し、run-history集計結果を自己完結HTMLとして出力する（実装済み）

## 主要な決定事項

| 決定 | 理由 |
|---|---|
| ログの上書き防止は、既存の`unlink()`を消して呼び出し元ごとに新規発行する`run_id`をファイル名に埋め込む方式で行う。`state-save`的な複雑な差分管理は導入しない | 各実行が独立した新規ファイルに書くだけで済み、`unlink`していた4箇所（`runner.py`×2・`orchestrator.py`×2）を削除するだけで衝突が起きなくなる。詳細は[[01-run-scoped-logs]] |
| `run_id`はファイル名の先頭に置く（`{run_id}__{scenario}.steps.jsonl`）。シナリオ名を先頭にはしない | ディレクトリを素直にソートしただけで全シナリオ横断の時刻昇順になる。シナリオが先頭だとシナリオ単位でしか時刻順にならない |
| 複数ファイルを跨ぐ累計コスト計算は、全ファイルのトークンを合算してから1回だけ価格を掛けるのではなく、ファイルごとに自分のモデルで価格計算してから金額を合算する | ファイルごとにモデルが異なりうる（run_idが古いファイルは別モデルで実行された可能性がある）ため、トークンを先に合算すると価格差が握り潰されて金額を誤る。詳細は[[02-cost-summary-cli]] |
| 時間範囲の絞り込みは、ログ内の各エントリではなく「ファイル単位」で行う（`run_id`から復元した実行時刻、無ければファイルの`mtime`で代替） | 要件が「開始終了時刻によって対象ファイルを絞ったうえで集計」であり、エントリ単位のタイムスタンプ追加は不要。既存の過去ログ（`run_id`が付いていない）も`mtime`フォールバックで扱え、移行スクリプトが要らない |
| 専用ダッシュボードは今回のスコープ外とし、スクリプト実行ベースのCLI出力に留める | 要件どおり「ひとまずスクリプト実行ベース」を優先し、ダッシュボードは後続プランとして切り出す（過剰な作り込みを避ける） |

## 変更/新規ファイル一覧

（各ファイルの役割・読むべき既存ファイルは各ステップを参照）

### 新規
- `scripts/vertical_slice/run_id.py`
- `scripts/internal/cost_log_discovery.py`
- `scripts/internal/cost_aggregate.py`
- `scripts/internal/cost_report.py`
- `scripts/internal/cost_html.py`（Step3）
- `.claude/rules/cost-summary.md`

### 変更
- `scripts/vertical_slice/step_log.py` / `task_log.py`
- `scripts/vertical_slice/step_runner.py` / `runner.py`
- `scripts/server/orchestrator.py` / `schemas.py`
- `scripts/internal/cost_summary.py`
- `.claude/rules/vertical-slice-runner.md` / `session-server.md`

## `.claude/rules` 更新ポイント

- `vertical-slice-runner.md`（Step1）: `step_log.py`/`task_log.py`のパス生成が`run_id`ベースに変わったこと、`unlink`による上書きが無くなったことを反映
- `session-server.md`（Step1）: `run_story`/`resume_story`が`run_id`を発行・返却するようになったことを反映
- `cost-summary.md`（Step2, 新規作成・フロントマター付き）: `scripts/internal/`配下のコスト集計サブシステムの責務分割・使い方
- `cost-summary.md`（Step3, 既存ファイルへ追記・フロントマター変更不要）: `--html`オプション・`cost_html.py`の役割
