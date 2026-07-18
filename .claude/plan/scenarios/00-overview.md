# テストシナリオ拡充 実装プラン - 概要

> [.claude/rules/architecture.md](../../rules/architecture.md) 記載の通り、現状 `big_plans` Step1〜5（[main/00-overview.md](../main/00-overview.md)）まで実装済み。本プランはStep6（[main/06-failure-handling.md](../main/06-failure-handling.md)、現時点では詳細未記載）に着手する前に、Step1〜5で実装した機能（vertical slice / server / task orchestration / `add_expectation` / 記録・再開）をより広いパターンで踏ませておくための準備作業。[.claude/plan/custom_pages/00-overview.md](../custom_pages/00-overview.md)と同様、`big_plans`⇔`.claude/plan/main`の1対1対応の外側にあるサブプランで、対応する`big_plans/0N-*.md`は無い。

## 要件

- 現状のシナリオ（`scripts/stories/search-demo.yaml` / `search-demo-branch.yaml` / `custom-pages-demo.yaml`）は正常系中心で、`navigate`ツールの直接呼び出し・`fill`の`submit`引数・ラジオボタン/テキストエリア・3ページ以上連続するフルページロードのresumeなど、未踏の経路が残っている。
- [big_plans/06-failure-handling.md](../../../big_plans/06-failure-handling.md)の完了条件は「意図的に失敗するタスクを用意し、リトライ→停止→診断情報つき提示の流れを確認する」こと。Step6の実装に着手する前に、意図的に失敗・`blocked`になるシナリオ（無効化要素・非対応input type・ロケータ非一意・未対応操作）を先に用意し、現状（Step6未実装）のベースライン挙動を記録しておく。
- 各story YAMLに、その検証意図（何をテストしたいか・何ができることを確認したいか）を書ける`intent`フィールドを持たせる。
- 新規ファイルは目的が既存ファイルで代替できない場合にのみ追加する。既存ファイル（story YAML・自作ページ・ドキュメント）に不要・冗長な記述があれば積極的に削除・編集する。
- `intent`フィールド追加（Story側データモデルへの1フィールド追加）を除き、新しいPythonロジックは追加しない。既存の`Story`/`Step`データモデル、`scripts/vertical_slice/main.py`、`scripts/server/`のstory受け渡しをそのまま使い、YAML（および必要な自作HTMLページ）の追加・編集だけで完結させる。

## 実装ステップ

1. [01-story-intent-field.md](01-story-intent-field.md) — Story YAMLに検証意図を書く`intent`必須フィールドを追加（実装・実行済み）。既存3ファイルへの追記・冗長コメントの整理を含む
2. [02-coverage-gap-fills.md](02-coverage-gap-fills.md) — 既存stories未使用の`navigate`ツール直接呼び出し・`fill`の`submit`引数・`toHaveText`のバリエーションを踏ませる軽量な追加
3. [03-advanced-form-elements.md](03-advanced-form-elements.md) — ラジオボタン・テキストエリアなど既存ページ未使用のフォーム要素を、既存`form.html`を拡張する形でカバー
4. [04-multi-page-wizard-and-resume.md](04-multi-page-wizard-and-resume.md) — 3ページ連続フルページロードのウィザード形式ページを追加し、Step5のresume（[[05-recording-and-resume]]）をより長い連鎖で検証
5. [05-failure-and-blocked-cases.md](05-failure-and-blocked-cases.md) — Step6着手前の意図的失敗フィクスチャ（無効化ボタン・非対応input type・ロケータ非一意・未対応操作）

## 主要な決定事項

| 決定 | 理由 |
|---|---|
| 既存ファイル（story YAML・自作ページ・ドキュメント）に不要・冗長な記述が見つかった場合は、新規ファイルを積み増すのではなく既存ファイルの削除・編集で解消することを各ステップで優先的に検討する（例: [[01-story-intent-field]]での`search-demo-branch.yaml`コメント整理、[[03-advanced-form-elements]]での新規ページ追加をやめ既存`form.html`拡張に変更） | 純粋な追加だけを繰り返すとシナリオ・ページ数が線形に増え続け、後から見て「どれが今の正解か」が分かりにくくなる。既存資産を優先的に育てる方が保守コストが低い |
| Story YAMLには検証意図を書く`intent`必須フィールドを持たせる（[[01-story-intent-field]]） | シナリオ数が増えるほど「このYAMLは何を確認したくて作られたか」が読み手にとって非自明になる。ファイル名・ステップ列だけでなく、意図を構造化データとして残す |
| 新規ページは既存の`resources/custom_pages/pages/`規約（[[custom-pages]]: role-basedロケータ、SPA化しない、検索/一覧は固定レスポンス）に従う。ただし`edge-cases.html`のみ意図的に規約（一意ロケータ）を破る | Step6の完了条件（「意図的に失敗するタスク」）を満たすフィクスチャを事前に用意するため。規約の欠陥ではなく専用の負のテスト対象として明示的に例外扱いする。詳細は[[05-failure-and-blocked-cases]] |
| シナリオ追加のために新しいPythonロジックは書かない（`intent`フィールドの追加を除く）。YAML（`scripts/stories/`）とHTML（`resources/custom_pages/pages/`）の追加・編集のみで完結させる | Step1〜5で確立済みの「story YAMLを流し込むだけ」という使い方の範囲内に留め、実装フェーズを増やさないため。`intent`はデータモデルへの1フィールド追加のみで、AIループ等の挙動には影響しないため例外として許容する |
| wizardページ（Step4）は各ページ間を`<form method="get" action="...">`によるフルページ遷移で繋ぎ、SPA的なJS遷移は使わない | 既存`search.html`の確立済みパターンを踏襲しつつ、Step5のresumeが複数の連続したフルページロードを正しくreplayできるかを検証する意図的なテスト対象にするため |
| 各ページの入力内容はページをまたいで反映されない（フォームはstateless）ことを前提にシナリオ・アサーションを書く | 静的HTML縛り（バックエンド無し）である以上、動的反映は実装コストに見合わない。[[custom_pages/01-page-design]]の「検索結果は固定」という既存の割り切りと同じ考え方。反する前提のシナリオを書くとAIが達成不可能な確認を求められて`blocked`になる |
| `edge-cases.html`由来の失敗シナリオは、現時点（Step6未実装）では「正常に失敗する（blockedまたはCLIエラーで止まる）」こと自体が期待結果であり、CI等の自動実行対象には含めない | Step6着手前の現状把握・フィクスチャ整備が目的であり、"pass"を目指すシナリオではないため |

## 変更/新規ファイル一覧

（各ファイルの役割・読むべき既存ファイルは各ステップを参照）

### 新規
- `resources/custom_pages/pages/search-empty.html`（Step2）
- `resources/custom_pages/pages/wizard-step1.html` / `wizard-step2.html` / `wizard-confirm.html`（Step4）
- `resources/custom_pages/pages/edge-cases.html`（Step5）
- `scripts/stories/navigate-direct-demo.yaml` / `search-empty-demo.yaml`（Step2）
- `scripts/stories/advanced-form-demo.yaml`（Step3）
- `scripts/stories/wizard-demo.yaml` / `wizard-demo-branch.yaml`（Step4）
- `scripts/stories/edge-disabled-button-demo.yaml` / `edge-range-input-demo.yaml` / `edge-ambiguous-locator-demo.yaml` / `edge-unsupported-action-demo.yaml`（Step5）

### 変更
- `scripts/vertical_slice/story.py` — `intent`必須フィールド追加（Step1、実装・実行済み）
- `scripts/stories/search-demo.yaml` / `search-demo-branch.yaml` / `custom-pages-demo.yaml` — `intent`追記、`search-demo-branch.yaml`の冗長コメント整理（Step1、実装・実行済み）
- `resources/custom_pages/pages/form.html` — ラジオボタン・テキストエリアを追加（新規ページを作らず既存ページを拡張。Step3）
- `resources/custom_pages/pages/index.html` — `wizard-step1.html`へのリンク追加（Step4）
- `.claude/rules/vertical-slice-runner.md` — `intent`フィールドの説明追記（Step1、実装・実行済み）
- `.claude/rules/custom-pages.md` — `paths`フロントマターの拡張、`edge-cases.html`の規約例外の追記（Step2, 5）

## `.claude/rules` 更新ポイント

- `vertical-slice-runner.md`（既存ファイルへの追記、Step1で実施済み）: `story.py`の説明に`intent`フィールド（必須・ドキュメンテーション専用）を追記。
- `custom-pages.md`（既存ファイルへの追記＋frontmatter変更、Step2でまとめて実施）: `paths`の`scripts/stories/custom-pages-demo.yaml`単体列挙を`scripts/stories/*.yaml`へ拡張する。以降のStep3〜5で追加するstoryを個別列挙し続けるコストを避けるため。
- `custom-pages.md`（Step5で追記）: `edge-cases.html`が一意ロケータ規約の対象外である旨の例外規定。

## 完了条件

- 既存3本の追跡対象story YAML（`search-demo.yaml` / `search-demo-branch.yaml` / `custom-pages-demo.yaml`）に`intent`が入り、`load_story`がそのまま通る（実装・実行済み）。
- `npm run serve:pages` で新規ページ（`edge-cases.html`含む）・拡張後の`form.html`が全てブラウザで正しく表示される。
- `advanced-form-demo.yaml` / `wizard-demo.yaml` / `search-empty-demo.yaml` / `navigate-direct-demo.yaml` を対象に `scripts/vertical_slice/main.py` を実行し、全ステップが`done`で完走する（実AI APIコールを伴うため、実行前に`vertical-slice-ai-test`スキルの方針に従いユーザーへ確認する）。
- `wizard-demo-branch.yaml` が `wizard-demo.yaml` 実行で得た `.tasks.jsonl` から `resume` により正しく分岐実行できる。
- `edge-*.yaml` の4本はいずれも`blocked`または明示的なCLIエラーで停止し、その`failure-notes.json`・エラーメッセージがStep6着手時の参考資料として残る。
