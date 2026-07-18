# Step 5: Step6着手前の意図的失敗フィクスチャ

> [04-multi-page-wizard-and-resume.md](04-multi-page-wizard-and-resume.md) の続き。

## やること

- [big_plans/06-failure-handling.md](../../../big_plans/06-failure-handling.md)の完了条件「意図的に失敗するタスク（例: 存在しない要素をクリックさせる）を用意し、リトライ→停止→診断情報つき提示、の流れが動作することを確認する」に向けて、big_plans Step6着手前の現状（リトライも診断整形も無い）でのベースライン挙動を先に記録しておくための、意図的に失敗・`blocked`になるフィクスチャ群を用意する。
- 4系統の失敗パターンをカバーする1枚のページ`edge-cases.html`を追加する。
  1. 無効化(`disabled`)されたボタンのクリック試行
  2. `<input type="range">`への`fill`試行（Playwrightの`fill()`はrange未対応の入力タイプ）
  3. 同一アクセシブルネームを持つ複数ボタン（role-basedロケータが一意に定まらない）
  4. ファイルアップロード欄・ドラッグ操作対象のリスト（現状の`tools.py`にアップロード/ドラッグ用ツールが存在しないため、AIが`finish_step(status="blocked")`を返さざるを得ない状況）
- 上記4パターンそれぞれに対応する独立したシナリオYAMLを追加する。1つのシナリオに混ぜると、どの機能欠如が原因で失敗したのか切り分けられなくなるため分離する。各YAMLの`intent`には、どの失敗パターンをどんな理由で検証したいか（「Step6着手前のベースライン記録」である旨）を明記する（[[01-story-intent-field]]で追加した必須フィールド）。

## 読むべきファイル・実行推奨Grep

**現状の失敗時挙動のフォーマットを確認するため（優先度: 高）**
- 読む: `tests/generated/search-demo.spec.failure-notes.json` / `search-demo-branch.spec.failure-notes.json` — 既存の`blocked`時の記録フォーマット（`step`/`reason`/`note`）。今回追加する4パターンも同じ形式で出力される想定
- 読む: `scripts/vertical_slice/step_runner.py` の `run_step` — `blocked`判定・エラー捕捉の現在のロジック。Step6着手前の「今の挙動」を正確に理解するために読むだけで、ロジック自体は変更しない

**tools.pyの制約を裏取りするため（優先度: 高）**
- 読む: `scripts/vertical_slice/tools.py` の `TOOL_SCHEMAS` — アップロード・ドラッグ用のツールが存在しないことの確認（存在しないことが(4)のシナリオの前提）
- 読む: `scripts/vertical_slice/cli_executor.py` の `CliExecutor.execute` — `### Error`検知で`CliError`になる現状の仕組み（(1)(2)がCLIコマンド自体のエラーとして落ちるのか、AIの`blocked`判断として落ちるのかを実装時に切り分けるための前提知識）

## 触るファイル

### 新規
- `resources/custom_pages/pages/edge-cases.html` — 前述4パターンの要素を1画面にまとめたページ。無効化ボタン、`<input type="range">`、同一アクセシブルネームの複数ボタン（例: 商品カード2件それぞれに「詳細」ボタン）、`<input type="file">`とドラッグ対象の`<li draggable="true">`リストを配置する
- `scripts/stories/edge-disabled-button-demo.yaml` — 無効化ボタンをクリックさせる指示のみの短いシナリオ
- `scripts/stories/edge-range-input-demo.yaml` — range inputへ特定の値を入力させる指示のみの短いシナリオ
- `scripts/stories/edge-ambiguous-locator-demo.yaml` — 「詳細ボタンをクリックする」のように、どちらの「詳細」ボタンか特定できない曖昧な指示のみの短いシナリオ
- `scripts/stories/edge-unsupported-action-demo.yaml`（ファイルをアップロードする指示） / `scripts/stories/edge-unsupported-drag-demo.yaml`（リスト項目をドラッグして並び替える指示）— どちらも現状tool無しのみの短いシナリオ。直下の決定事項（(4)は別々のYAMLに分ける）通り2ファイルに分離

### 変更
- `.claude/rules/custom-pages.md` — `edge-cases.html`の規約例外を追記

## 決定事項・注意点／落とし穴

| 決定 | 理由 |
|---|---|
| `edge-cases.html`は`index.html`からリンクしない。各シナリオYAMLの`seed_url`を`http://localhost:8080/edge-cases.html`に直接指定する | 意図的な負のテスト用フィクスチャであり、通常のアプリ導線（`index.html`のナビゲーション）に混ぜないため |
| `edge-cases.html`は「role-basedロケータで一意に拾える要素のみを使う」という既存規約（[[custom-pages]]）に(3)のケースで意図的に違反する | 規約の欠陥ではなく、規約を守れないケースで何が起きるかを確認する専用フィクスチャであるため。`custom-pages.md`にこのページを名指しした例外規定を追記して、規約違反が意図的であることを明示する |
| これら4シナリオは「正常に失敗する（`blocked`またはCLIエラーで止まる）」こと自体が期待結果であり、"pass"を目指さない。CI等の自動実行対象には含めない | Step6着手前の現状把握・フィクスチャ整備が目的であり、既存の`search-demo.yaml`実行時点で既に`blocked`で止まっている前例（`search-demo.spec.failure-notes.json`）と同じ扱いにする |
| (2)のrange inputは、`fill`失敗時にplaywright-cli側のコマンドが例外を返すのか`### Error`検知で`CliError`になるのかを実機で確認してから正確な期待結果を記載する。プラン段階では「非対応であることを確認する」までに留め断定しない | 未確認の外部挙動（playwright-cliの`fill`コマンド内部実装）に依存するため、[[custom_pages/02-local-hosting]]の`--raw`位置確認と同じ要領で実装時に実機確認が必要 |
| **実装時の実機確認の結果、(2)の当初想定は誤りだった。** `playwright-cli fill`は`<input type="range">`に対し、`min`〜`max`範囲内の数値であれば実際には成功する（`el.value`が更新される）。`### Error`（`Error: Malformed value`）になるのは範囲外の値（例: `max=100`に対し`150`）または非数値を渡した場合のみ。`edge-range-input-demo.yaml`はこの実機確認結果を反映し、範囲外の値（150）をfillさせる指示に変更した | 「非対応input type」という当初の前提が実際のPlaywright挙動と異なっていたため。断定を避け実機確認してから記載する、という本ファイルの決定（直上の行）通りの手順で発覚した |
| (4)は「ファイルをアップロードする」と「リストをドラッグして並び替える」を別々のYAMLに分ける | 1つのシナリオに混ぜると、どちらの機能欠如が原因で`blocked`になったか切り分けられなくなるため |

## 実行結果（Step6着手前のベースライン記録、実行日 2026-07-19）

`scripts.vertical_slice.main`に対しMiniMax-M3で実際に実行した結果。いずれも意図通り"pass"せずに停止した。

| story | 結果 | 実際の停止理由 |
|---|---|---|
| `edge-disabled-button-demo.yaml` | `blocked` | AIはsnapshot上の`[disabled]`表示を見てクリックを試みる前に`finish_step(status="blocked")`を返した。CLI呼び出し自体は発生しなかった |
| `edge-range-input-demo.yaml` | `cli_error` | `fill(ref, "150")`が`### Error: Error: Malformed value`でCliErrorになった（範囲外の値。前掲の実機確認結果通り） |
| `edge-ambiguous-locator-demo.yaml` | `blocked` | AIは「詳細」ボタンが2つ（商品A/商品B）存在し指示だけでは一意に特定できないと判断し、当て推量で片方をクリックせず`blocked`を返した |
| `edge-unsupported-action-demo.yaml`（アップロード） | **未捕捉のPython例外でクラッシュ（想定外）** | AIが`click`ツールで添付ファイル欄（file input）をクリックし、playwright-cliが`Modal state: [File chooser]`に遷移。直後の`snapshot --json`が`{"isError": true, "error": "...does not handle the modal state."}`という通常と異なるJSON形状を返し、`CliExecutor.snapshot_text()`の`json.loads(out)["snapshot"]`が`KeyError: 'snapshot'`で例外送出、プロセスがtracebackとともに異常終了した。`.spec.ts`・`.failure-notes.json`は生成されず、`.tasks.jsonl`にはseedブロックのみ残る |
| `edge-unsupported-drag-demo.yaml` | `cli_error` | AIはドラッグ用ツールが無いため`hover`を2回試みた後、画面が変わったと誤認し存在しない`file:///home/user/sortable.html`へ`navigate`しようとして`Error: Access to "file:" protocol is blocked`でCliErrorになった |

**Step6スコープへの示唆**: (4)アップロードのケースは当初想定していた「AIが素直にblockedを返す」よりも重大な発見で、`CliExecutor.snapshot_text()`がplaywright-cliの`isError`付きJSON（モーダル状態時など`### Error`マーカー方式と異なる応答形状）を想定しておらず、`CliError`として捕捉されない生のPython例外でパイプライン全体がクラッシュする。Step6のリトライ・診断情報提示ロジックは、`CliError`だけでなく`snapshot_text`/`generate_locator`等の他のCLI呼び出しが返しうる非`### Error`形式の異常応答（`isError`キー等）も捕捉対象にする必要がある。本ステップでは`新しいPythonロジックは追加しない`というスコープ制約に従い、挙動の記録のみに留め修正はしていない。

## `.claude/rules` 更新ポイント

- `custom-pages.md`（既存ファイルへの追記。`paths`はStep2で拡張済みのため変更不要）
  - 「自作テストページ（resources/custom_pages）の規約」の末尾に以下を追記:
    - `edge-cases.html`は意図的な失敗・非対応操作の検証用フィクスチャであり、role-basedロケータの一意性規約の対象外とする。詳細は`.claude/plan/scenarios/05-failure-and-blocked-cases.md`を参照。
