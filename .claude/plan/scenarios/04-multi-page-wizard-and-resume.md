# Step 4: 3ページ連続ウィザードとresumeの負荷検証

> [03-advanced-form-elements.md](03-advanced-form-elements.md) の続き。

## やること

- 3ページ連続のフルページロード遷移（`wizard-step1.html` → `wizard-step2.html` → `wizard-confirm.html`）で構成される、後戻りなし・一方通行のウィザード形式ページ群を追加する。目的はbig_plans Step5の`resume`（[[05-recording-and-resume]]の`build_replay_source`によるコード列再生）が、既存の`search-demo-branch`（playwright.dev、フルページロード1回のみ）や`custom-pages-demo`（`index`⇄`search`⇄`form`の行き来）よりも多い・後戻りのないフルページロードの連鎖を正しくreplayできるかを確認すること。
- 通常実行用の`wizard-demo.yaml`（全ステップ通し）と、big_plans Step5の完了条件（「記録されたログだけを使って、途中のタスクからテストを再開できる」「別パターンへ分岐実行できる」）をこの新しいページ群でも再現する`wizard-demo-branch.yaml`（confirmページ到達後、別の入力で分岐する）を追加する。
- `index.html`のナビゲーションに`wizard-step1.html`へのリンクを追加する。
- 追加する2本のstoryの`intent`には、それぞれ「多段フルページロードでのresume/分岐実行の検証」であることを明記する（[[01-story-intent-field]]で追加した必須フィールド）。

## 読むべきファイル・実行推奨Grep

**既存resumeの動かし方を確認するため（優先度: 高）**
- 読む: [main/05-recording-and-resume.md](../main/05-recording-and-resume.md) — resumeの仕組み全体（`<out>.tasks.jsonl`の記録内容、`resume_before_step`の意味、`prior_blocks`の組み立て方）
- 読む: `scripts/stories/search-demo-branch.yaml` とファイル先頭のコメント — resumeでは`seed_url`が実質使われない理由（`cli.open()`を経由せず`run-code`での早送りになるため）、分岐先ストーリーの書き方の実例
- 読む: `scripts/vertical_slice/main.py` の`--resume-tasks-log`/`--resume-before-step`引数パース箇所 — resumeを実際にコマンドラインでどう起動するか

**既存ページのフルページ遷移パターンを踏襲するため（優先度: 中）**
- 読む: `resources/custom_pages/pages/search.html` — `<form method="get" action="...">`によるフルページ遷移の既存実装パターン。wizardページ間の遷移もこれをテンプレートにする

## 触るファイル

### 新規
- `resources/custom_pages/pages/wizard-step1.html` — 氏名・メールアドレスの2つのテキスト入力欄を持つ`<form method="get" action="wizard-step2.html">`
- `resources/custom_pages/pages/wizard-step2.html` — 郵便番号・住所の2つのテキスト入力欄を持つ`<form method="get" action="wizard-confirm.html">`
- `resources/custom_pages/pages/wizard-confirm.html` — 固定文言の確認見出し＋「送信する」ボタン（`form.html`と同じinline JSでの固定完了メッセージ表示パターン）
- `scripts/stories/wizard-demo.yaml` — `wizard-step1.html`から入力・提出を3ページ分繰り返し、最終確認メッセージを確認するまでの全ステップ
- `scripts/stories/wizard-demo-branch.yaml` — `wizard-demo.yaml`実行で得た`.tasks.jsonl`のうち、confirmページ到達直後までを`resume-before-step`に指定して復元し、以降を「送信せず入力内容を確認するだけ」という別の完了条件に分岐させるシナリオ（`search-demo-branch.yaml`と同じくファイル先頭に`seed_url`実質未使用の注記を書く）

### 変更
- `resources/custom_pages/pages/index.html` — `<nav>`のリストに`wizard-step1.html`へのリンクを追加

## 決定事項・注意点／落とし穴

| 決定 | 理由 |
|---|---|
| ページ間遷移は全て`<form method="get" action="次のページ.html">`による通常のフルページロードとし、SPA的なhistory API操作はしない | [[custom_pages/01-page-design]]の既存決定「ページ間遷移は通常の`<a href>`によるフルロードのみ」を踏襲し、snapshot取得タイミングを単純化するため |
| 各ページの入力値は次ページに一切引き継がれない（バックエンドが無い静的サイトのため）。`wizard-confirm.html`の確認文言は固定文字列にし、「step1/step2で入力した値がここに表示される」という前提のシナリオ・アサーションは書かない | [[custom_pages/01-page-design]]の「検索結果は固定の静的HTML」という既存の割り切りと同じ考え方。反する前提のシナリオを書くとAIが達成不可能な確認を求められて`blocked`になる |
| 完了確認は`form.html`と同じ「送信ボタン→inline JSで固定の完了メッセージ表示」を流用し、4ページ目（完了専用ページ）は作らない | 3フルページロード＋1inlineメッセージで十分にresumeへ負荷をかけられるため、ページ数を無理に増やして保守コストを上げる必要はない |
| `wizard-demo-branch.yaml`の分岐点はconfirmページ到達直後（`wizard-demo.yaml`のconfirm到達までのタスク番号を`resume-before-step`に指定）とする | big_plans Step5の完了条件「途中のタスクから別入力で分岐実行できる」を最終ステップ手前という一番検証しがいのあるポイントで再現するため |

## `.claude/rules` 更新ポイント

なし（`paths`はStep2で`scripts/stories/*.yaml`へ拡張済み。規約からの逸脱も無いため本文追記は不要）
