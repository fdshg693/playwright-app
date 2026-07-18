# Step 3: 専用ダッシュボード化

> [02-cost-summary-cli.md](02-cost-summary-cli.md)の続き。Step1・2で作った`{stem}.history/`配下のrun-scopedログと`cost_summary.py`の集計・出力ロジックを再利用し、コマンド実行のたびに端末で読む代わりに、後から見返せる静的HTMLレポートとして残せるようにする。

## やること

`scripts/internal/cost_summary.py`に`--html [PATH]`オプションを追加し、指定すると`cost_report.py`のrun-history集計結果（`RunCostRow`のリスト）から自己完結HTMLファイルを生成する。集計・価格計算ロジック（`cost_log_discovery.py`/`cost_aggregate.py`/`cost_report.py`）は一切再実装せず、既存のrun-history経路（Step2で作った複数ファイル時の集計パス）にHTML出力という新しい「出し先」を1つ足すだけに留める。常駐サーバー化は行わない（理由は下記決定事項）。

## 読むべきファイル・実行推奨Grep

**既存の集計・出力ロジックをそのまま再利用するため（優先度: 高）**
- 読む: `scripts/internal/cost_report.py` — `RunCostRow`のフィールド構成と`format_run_history_report`の組み立て方。HTML版もこの同じ`RunCostRow`リストから作る（データの再取得・再計算はしない）
- 読む: `scripts/internal/cost_summary.py` — 現行の`single_file_mode`分岐と、複数ファイル時に`rows`を組み立てるループの位置。`--html`指定時にこのループへどう合流させるかがこのステップの主眼

**既存のCLI引数追加パターンを確認するため（優先度: 中）**
- Grep: `add_argument` in `cost_summary.py` — `--start`/`--end`/`--model`と揃えた足し方をする

**常駐サーバー化を採用しないという判断の裏取りのため（優先度: 中）**
- 読む: `.claude/rules/session-server.md` — 既存の唯一のFastAPI常駐サーバー（`scripts/server/`）が常駐している理由（ブラウザセッションという「生きた状態」の保持）を確認し、コスト集計には同じ必要性が無いことを確認する
- 読む: `.claude/plan/observability/00-overview.md` の主要な決定事項テーブル — 「スクリプト実行ベースを優先」「過剰な作り込みを避ける」という既存方針の確認

**視覚表現（グラフ）を作る際のガイドライン確認のため（優先度: 低、実装直前でよい）**
- `dataviz`スキル（組み込みスキル一覧） — 色・軸・凡例など可視化の一般指針。今回作る棒グラフはごく単純なので参照は軽くでよい

## 触るファイル

### 新規
- `scripts/internal/cost_html.py` — `render_html_report(rows: list[cost_report.RunCostRow]) -> str`。既存の`RunCostRow`リスト（`format_run_history_report`と同じ入力）から自己完結HTML文字列を生成する。内容は (1) ヘッダー（対象run数・時間範囲・累計コスト）、(2) run一覧テーブル（時刻・パス・モデル・トークン数・コスト・`matched`が`False`の場合の注記など、`format_run_history_report`と同じ情報をHTML化）、(3) run毎のコスト推移を示す最小限の棒グラフ（インラインSVG、rows数分`<rect>`を並べるだけの単純な実装。外部JS/CSSライブラリ・CDN依存は使わない）。ファイルパスやモデル名などrows由来の文字列は`html.escape`でエスケープする

### 変更
- `scripts/internal/cost_summary.py` — `--html`を追加する。`argparse`の`nargs="?"`＋`const="cost_dashboard.html"`（値を省略してフラグだけ指定した場合に使われる）＋`default=None`（フラグ自体が無い場合。この場合は従来通りHTML出力しない）という3値パターンにする。`args.html`が`None`でない場合は、ファイルが1件でも常に（`single_file_mode`の分岐を通らず）現行の複数ファイル時と同じ`rows`組み立てループを使い、`cost_html.render_html_report(rows)`の結果を`args.html`のパスへ書き込む。標準出力には書き込み先パスと概要1行のみ出し、従来のテキストレポートは印字しない。`--html`未指定時の既存の挙動（単一ファイル時のステップ内訳・複数ファイル時のテキストrun-history表）は変更しない
- `.claude/rules/cost-summary.md` — 既存ファイルへ追記。`--html`/`cost_html.py`の役割、`--html`指定時は常にrun-history経路のデータを使うこと、生成HTMLは外部依存の無い自己完結ファイルであることを記載する。frontmatterの`paths: scripts/internal/cost_*.py`は`cost_html.py`も自動的にカバーするため変更不要
- `.claude/skills/vertical-slice-ai-test/SKILL.md`（任意・低優先度） — 既存の`cost_summary.py`使用例セクション（58〜68行目付近、`--start`/`--end`の例がある箇所）に`--html`の呼び出し例を1行追記し、使い方の説明を最新化する
- `.claude/plan/observability/00-overview.md`（ドキュメント整合性のための軽微な更新） — 「実装ステップ」一覧の3番目を「専用ダッシュボード化（未着手、プレースホルダ）」から実際の内容（`cost_summary.py`への`--html`追加）を反映した一行に更新し、「変更/新規ファイル一覧」の新規に`scripts/internal/cost_html.py`を追加する

## 決定事項・注意点／落とし穴

| 決定 | 理由 |
|---|---|
| 常駐サーバー（FastAPI/uvicorn）は使わず、静的HTMLファイル生成に留める | `pyproject.toml`には既にfastapi/uvicorn依存があるが、それは`scripts/server/`がブラウザセッションという「生きた状態」を保持する必要があるために常駐している（[[session-server]]参照）。コストログは各run終了時点で既にディスク上に確定したファイルであり、ライブ更新・双方向インタラクションの必要性が無い。サーバーを常駐させるとポート管理・起動/停止の手間が発生し、[00-overview.md](00-overview.md)が明記する「スクリプト実行ベースを優先」「過剰な作り込みを避ける」という既存方針に反する |
| 集計・価格計算ロジック（`cost_log_discovery.py`/`cost_aggregate.py`）は一切変更・再実装せず、`cost_report.py`が持つ`RunCostRow`をそのままHTML化する | [00-overview.md](00-overview.md)の大方針どおり、Step2で確立した「ファイルごとに自分のモデルで価格計算してから金額を合算する」等のロジックを二重管理しない。HTML生成は既存の集計結果の「見せ方」を増やすだけの変更に閉じる |
| `--html`指定時は、ファイルが1件しか無い場合でも常にrun-history経路（`rows`のリスト）を使い、単一ファイル用のステップ内訳をHTML化する別テンプレートは作らない | ダッシュボードの目的は「run間の推移を後から見返せること」であり、run数1件は長さ1の推移として扱えば十分。単一ファイル/複数ファイルでHTMLテンプレートを2種類持つと保守面が倍になる。ステップ単位の詳細を見たい場合は既存の`--html`無しのテキスト単一ファイルモードで足りる |
| 生成するHTMLは自己完結（インラインCSS、外部JS/CSSライブラリ・CDN参照なし）にする | `file://`で直接開ける・オフライン環境でも壊れない・単体で共有できる、という静的レポートとしての利点を最大化するため。ビルドステップ（bundler等）も導入しない |
| グラフはrows数分の`<rect>`を並べる最小限の棒グラフ1種類のみとし、ソート・フィルタ・ズームなどのインタラクティブなJSは今回のスコープに含めない | 時間範囲の絞り込みは既存の`--start`/`--end`でHTML生成前に既に行えるため、クライアント側フィルタは不要。「一目で分かる」という要件はrows一覧テーブル＋簡易グラフで満たせる。要望が出たら後続プランで拡張するYAGNI判断 |
| `--html`は`nargs="?"`＋`const`（フラグのみ指定時のデフォルトファイル名、例`cost_dashboard.html`）＋`default=None`（フラグ自体が無い場合）で実装する。専用の出力先ディレクトリ規約は新設しない | argparseの`nargs='?'`は「フラグ自体が無い」場合と「フラグはあるが値を省略」の場合を`default`/`const`で区別できる。前者は従来のテキスト出力のまま、後者は固定ファイル名でHTML出力、という2状態をこの1オプションで表現できるため新しいフラグを増やさずに済む。出力先ディレクトリはリポジトリに既存の「レポート格納ディレクトリ」規約が無く、今回のために新設するのは過剰。パスを変えたい場合は`--html <path>`で明示すればよい |
| HTMLへ埋め込むrows由来の文字列（ファイルパス・モデル名等）は`html.escape`でエスケープする | ファイルパスやモデル名に将来`&`/`<`等が含まれた場合でもHTMLが壊れないようにする |
| `--html`未指定時の既存の出力（単一ファイル時のステップ内訳テキスト・複数ファイル時のrun-historyテキスト表）は一切変更しない | 既存の`vertical-slice-ai-test`スキルや利用者のスクリプト連携（テキストのgrep等）を壊さない後方互換性を優先する |

## `.claude/rules` 更新ポイント

- `cost-summary.md`（既存ファイルへの追記。frontmatterの`paths: scripts/internal/cost_*.py`は変更不要 — `cost_html.py`も同じglobで自動的にカバーされる）: 追記内容は以下を想定
  - `cost_summary.py`に`--html [PATH]`オプションが追加され、指定するとrun-history集計結果（`RunCostRow`のリスト）を`cost_html.py`の`render_html_report`でHTML化して書き出すこと
  - `--html`指定時は常にrun-history経路のデータを使うこと（単一ファイルでもrows化する）
  - 生成HTMLは外部JS/CSSライブラリに依存しない自己完結ファイルであること、`--html`未指定時の既存のテキスト出力は変わらないこと
