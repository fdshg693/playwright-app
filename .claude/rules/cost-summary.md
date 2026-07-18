---
paths:
  - "scripts/internal/cost_*.py"
---

## コスト集計サブシステム（scripts/internal/）

- `cost_summary.py`はCLIエントリポイントのみ（argparse配線）。実処理は3モジュールに分割されている: `cost_log_discovery.py`（ファイル/ディレクトリ引数の解決・時間範囲フィルタ）、`cost_aggregate.py`（`<out>.steps.jsonl`のusage集計・価格計算）、`cost_report.py`（出力整形）。
- 引数を1ファイルだけ渡すとそのファイルのステップ内訳（`format_single_file_report`）を出す。複数ファイル/ディレクトリを渡すと実行ごとの行（時刻昇順）＋末尾に累計コストの「run history」表（`format_run_history_report`）に切り替わる。
- 複数ファイルの累計コストは、トークンを合算してから1回課金するのではなく、ファイルごとに自分のモデルで価格計算した金額（ドル）を合算する（ファイルによってモデルが異なりうるため）。
- ディレクトリを渡すと配下の`*.steps.jsonl`のみ再帰的に対象にする（`*.tasks.jsonl`は`usage`フィールドを持たないため対象外）。
- 実行時刻は`scripts/vertical_slice/run_id.py`の`parse_run_id_prefix`でファイル名プレフィックス（`{run_id}__{stem}`）から復元し、無ければファイルの`mtime`にフォールバックする（run history表に`(mtime fallback)`と注記される）。
- 壊れた/空のJSON行はファイル単位でスキップし警告を`stderr`に出す（`cost_aggregate.load_usages`）。usageが1件も無いファイルやモデルが一意に決まらないファイルは、複数ファイルモードでは警告を出してそのファイルだけスキップし、他ファイルの集計は継続する（単一ファイルモードでは従来どおりエラー終了する）。
- 該当ファイルが0件（ディレクトリにマッチ無し／時間範囲で全滅／全ファイルがusage無しでスキップ）の場合はエラーにせず「0件でした」という旨のメッセージを出して正常終了する。
- `--html [PATH]`（`nargs="?"`＋`const="cost_dashboard.html"`）を指定すると、run-history集計結果（`RunCostRow`のリスト）を`cost_html.py`の`render_html_report`でHTML化し、指定パス（省略時は`cost_dashboard.html`）へ書き込む。標準出力には書き込み先パスと概要1行のみ出す。`--html`指定時はファイルが1件しかなくても常にrun-history経路（`rows`のリスト）を使い、単一ファイル用のステップ内訳（`format_single_file_report`）は使わない。生成されるHTMLは外部JS/CSSライブラリ・CDN参照の無い自己完結ファイル（インラインCSS、インラインSVGの棒グラフ）で、rows由来の文字列（パス・モデル名）は`html.escape`でエスケープ済み。`--html`未指定時の既存の出力（単一ファイルのステップ内訳・複数ファイルのrun-historyテキスト表）は変更されない。
