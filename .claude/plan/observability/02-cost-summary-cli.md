# Step 2: cost_summary.py の複数ファイル/ディレクトリ/時間範囲対応

> [01-run-scoped-logs.md](01-run-scoped-logs.md)の続き。Step1で`{run_id}__{stem}.steps.jsonl`が`{stem}.history/`配下に複数残るようになった前提で、それらを跨いだ集計をできるようにする。

## やること

`scripts/internal/cost_summary.py`を、①複数ファイル指定、②ディレクトリ指定（配下の`*.steps.jsonl`のみ再帰取得、`*.tasks.jsonl`は対象外）、③開始/終了時刻によるファイル絞り込み、に対応させる。既存の1ファイル単位の集計ロジックはほぼそのまま再利用しつつ、責務ごとに`scripts/internal/`配下の複数モジュールへ分割する。

## 読むべきファイル・実行推奨Grep

**既存ロジックを正確に流用するため（優先度: 高）**
- 読む: `scripts/internal/cost_summary.py` — 現行の全ロジック（`load_usages`/`_extract`/`aggregate`/`resolve_model`/`load_pricing_table`/`get_pricing`/`estimate_cost`/`format_report`）。分割後もこれらの関数シグネチャ・挙動は極力変えず、置き場所だけを移す
- 読む: `scripts/internal/model_pricing.csv` — 価格表の形（`model,input_price_per_1m,output_price_per_1m,cached_input_price_per_1m`、`default`行必須）。分割後も参照元は変わらない

**Step1で新設したファイル名規約を再利用するため（優先度: 高）**
- 読む: [01-run-scoped-logs.md](01-run-scoped-logs.md) の `run_id.py` の決定事項 — `parse_run_id_prefix()`をそのままディレクトリスキャン時の時刻抽出に使う（命名フォーマットの解釈ロジックを2箇所に重複させない）

**既存の呼び出しコンテキストを確認するため（優先度: 中）**
- Grep: `cost_summary` — `.claude/skills/vertical-slice-ai-test/SKILL.md`等、既存の呼び出し例が引数を1ファイル固定で書いていないか確認し、あれば使い方の記述を更新する

## 触るファイル

### 新規
- `scripts/internal/cost_log_discovery.py` — ファイル/ディレクトリ引数の解決・時間範囲フィルタ
  - `discover_log_files(inputs: list[str]) -> list[Path]`: 各要素がディレクトリなら`**/*.steps.jsonl`を再帰glob、ファイルならそのまま採用。結果を重複排除しソートして返す
  - `resolve_run_time(path: Path) -> datetime`: `run_id.parse_run_id_prefix(path.name)`が取れればそれを、取れなければ`path.stat().st_mtime`を使う（旧形式ログのフォールバック）
  - `filter_by_time_range(paths, start: datetime | None, end: datetime | None) -> list[Path]`: `resolve_run_time`基準で`[start, end]`（各`None`は無制限）に収まるものだけ残す
- `scripts/internal/cost_aggregate.py` — 現行`cost_summary.py`の`load_usages`/`_extract`/`aggregate`/`resolve_model`/`load_pricing_table`/`get_pricing`/`estimate_cost`をそのまま移設
- `scripts/internal/cost_report.py` — 出力整形
  - `format_single_file_report(...)`: 現行の`format_report`相当（ステップ内訳＋overall＋見積コスト）。単一ファイル指定時のみ使う
  - `format_run_history_report(rows: list[RunCostRow], ...)`: 複数ファイル時のデフォルト出力。`RunCostRow`＝ファイルパス・実行時刻(`resolve_run_time`)・モデル・overall totals・その回のコスト、を時刻昇順で1行ずつ表示した後、末尾に累計コストを出す
- `.claude/rules/cost-summary.md` — 下記フロントマター付きで新規作成

### 変更
- `scripts/internal/cost_summary.py` — CLIエントリポイントのみに縮小。`argparse`で`paths: list[str]`（`nargs="+"`、ファイル/ディレクトリ混在可）・`--start`/`--end`（ISO8601、`datetime.fromisoformat`でパース、ローカルナイーブ時刻として扱う）・`--model`（既存の挙動を維持）を受け、`cost_log_discovery`→（ファイルごとに）`cost_aggregate`→`cost_report`の順に呼ぶだけの薄い配線にする

## 決定事項・注意点／落とし穴

| 決定 | 理由 |
|---|---|
| 複数ファイルの累計コストは「全ファイルのトークンを1つに合算してから1回課金単価を掛ける」のではなく「ファイルごとに自分のモデルで価格計算し、出てきた金額（ドル）を合算する」 | ファイルによってモデル・単価が異なりうる（古い実行は別モデルだったかもしれない）。トークンを先に合算すると単価差が握り潰されて金額が狂う。`aggregate`/`estimate_cost`は既存どおりファイル単位で呼び、`cost_report`側で金額だけ足し上げる |
| 複数ファイル指定時のデフォルト出力は「実行ごとの行（時刻昇順）＋末尾に累計コスト」とし、現行の「ステップ内訳」はデフォルトから外す（単一ファイル指定時のみステップ内訳を出す`format_single_file_report`を使う） | 要件の主眼は「結果の推移・累計コスト」であり、複数実行分のステップ内訳を全部並べると読みにくい。ステップ単位のデバッグは元々1ファイル向けの粒度なので、そちらは維持しつつ使い分ける |
| ディレクトリ指定時は`*.steps.jsonl`のみ拾い、`*.tasks.jsonl`は対象外にする | `tasks.jsonl`は`usage`フィールドを持たないスキーマ（[[vertical-slice-runner]]参照）で、コスト集計に使えるのは`steps.jsonl`側だけ。要件の「配下のspec.jsonlのみ取得」はこの`*.steps.jsonl`を指す |
| 時間範囲フィルタはエントリ単位ではなくファイル単位（`resolve_run_time`で決めた1つの実行時刻）で行う | 要件どおり「対象ファイルを絞ったうえで集計」であり、1ファイル＝1実行なのでエントリ単位の粒度は不要。Step1で`.steps.jsonl`にタイムスタンプ付きエントリを追加する変更をしなくて済む |
| `run_id`が読み取れない旧形式ファイルは`mtime`にフォールバックする。フォールバックした事実は結果に注記する（例: 各行に`(mtime fallback)`を付ける） | 移行スクリプトなしで旧ログを扱えるようにしつつ、`mtime`はファイルシステム操作（コピー等）で変わりうる不正確な代替指標であることを利用者に分からせるため |
| 壊れた/空のJSON行はファイル単位でスキップし警告を`stderr`に出す（クラッシュさせない） | 実行が異常終了した場合、`.steps.jsonl`の最終行が書きかけで壊れることがある。1ファイルの1行の破損で他の全履歴の集計が止まるのは安定運用上望ましくない |
| 該当ファイルが0件（ディレクトリにマッチ無し／時間範囲で全滅）の場合は空の集計結果として扱い、スタックトレースではなく「0件でした」という明示メッセージを出して正常終了（exit code 0）する | CI等からの定期実行を想定すると、0件が異常系ではなく「その期間は実行が無かった」という正常な結果であるケースの方が多い |
| `--model`は「モデルが一意に決まらないファイル」に対する上書きとしてのみ働き、複数ファイルそれぞれが自力でモデルを解決できる場合はそちらを優先する（無理に全ファイルへ同一モデルを強制しない） | 履歴を跨いだ集計という新しい用途では、各ファイルが実際に使ったモデルで正確に価格計算することの方が「揃える」ことより重要 |

## `.claude/rules` 更新ポイント

新規ルールファイル`.claude/rules/cost-summary.md`を作成する:

```markdown
---
paths:
  - "scripts/internal/cost_*.py"
---

## コスト集計サブシステム（scripts/internal/）

- `cost_summary.py`はCLIエントリポイントのみ（argparse配線）。実処理は3モジュールに分割されている: `cost_log_discovery.py`（ファイル/ディレクトリ引数の解決・時間範囲フィルタ）、`cost_aggregate.py`（`<out>.steps.jsonl`のusage集計・価格計算）、`cost_report.py`（出力整形）。
- 複数ファイルの累計コストは、トークンを合算してから1回課金するのではなく、ファイルごとに自分のモデルで価格計算した金額を合算する（ファイルによってモデルが異なりうるため）。
- ディレクトリを渡すと配下の`*.steps.jsonl`のみ再帰的に対象にする（`*.tasks.jsonl`は対象外）。
- 実行時刻は`scripts/vertical_slice/run_id.py`のファイル名プレフィックス（`{run_id}__{stem}`）から復元し、無ければファイルの`mtime`にフォールバックする。
```
