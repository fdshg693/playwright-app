# Step 3: 未カバーのフォーム要素（ラジオボタン・テキストエリア）

> [02-coverage-gap-fills.md](02-coverage-gap-fills.md) の続き。

## やること

- 既存ページ（`index.html` / `search.html` / `form.html`）ではまだ使われていない2種類のフォーム要素、ラジオボタンとテキストエリアを追加する。新規ページは作らず、既に「フォーム操作一式を1画面に集約する」という同じ役割を持つ既存の`form.html`にフィールドを追加する形で行う。
- 対応するシナリオ`advanced-form-demo.yaml`を追加し、ラジオボタン選択→テキストエリア入力→送信→完了確認、を一通り実行させる。

## 読むべきファイル・実行推奨Grep

**既存フォームページの構造・パターンを踏襲するため（優先度: 高）**
- 読む: `resources/custom_pages/pages/form.html` — チェックボックス・セレクト・ツールチップ（CSS hover）・送信ボタン（inline JSでの固定メッセージ表示）の既存実装パターン。追加するラジオボタン・テキストエリアもこの構成に合わせる
- 読む: `scripts/stories/custom-pages-demo.yaml` — `form.html`を対象にした既存シナリオ。今回追加するフィールドをこのシナリオの指示文言が一切参照しないこと（＝既存stepでは新フィールドに触れない）を確認し、フィールド追加が既存シナリオの実行結果に影響しないことを裏取りする

**ラジオボタン/テキストエリアのrole-based解決を確認するため（優先度: 中）**
- 読む: `.claude/skills/playwright-cli/references/test-generation.md` — role-basedロケータ優先方針（`getByRole('radio', ...)` / `getByRole('textbox', ...)`がテキストエリアにも使われる想定か確認）
- 読む: `scripts/vertical_slice/tools.py` の `check`/`uncheck`ツール説明文（「チェックボックス/ラジオボタン」と明記されている点。既存toolのままラジオボタンを扱える前提の裏取り）

## 触るファイル

### 新規
- `scripts/stories/advanced-form-demo.yaml` — `intent`に「ラジオボタン・複数行テキストエリアという既存stories未使用の要素種別を踏ませる」ことを書く。seed_urlを`http://localhost:8080/form.html`に直接指定し（`index.html`経由の遷移は`custom-pages-demo.yaml`側で既に検証済みのため重複させない）、ラジオボタンのいずれかを選択→テキストエリアに改行を含む複数行テキストを入力→送信→完了メッセージ確認、のステップ列にする

### 変更
- `resources/custom_pages/pages/form.html` — お問い合わせ種別（ラジオボタン3択程度、例:「一般」「不具合」「要望」、それぞれ独立した`<label>`付き`<input type="radio" name="...">`）と、お問い合わせ内容（複数行`<textarea>`、`<label>`付き）を既存フォームに追記する

## 決定事項・注意点／落とし穴

| 決定 | 理由 |
|---|---|
| 新規ページ`advanced-form.html`は作らず、既存`form.html`を拡張する（当初案からの変更） | `form.html`は既に「フォーム操作一式を1画面に集約する」という同じ役割を持っており、新規ページを立てると内容が重複するだけの近縁ファイルが増える。既存ファイルを優先的に育てる方針（[[00-overview]]決定事項）に従う |
| `index.html`のナビゲーション変更は不要 | `form.html`は既に`index.html`からリンクされている。新規ページを作らないため、リンク追加も発生しない |
| ラジオボタンは同一`name`属性でグループ化した3つの`<input type="radio">`とし、それぞれに個別の`<label for=...>`を付ける | 単一の`aria-label`で3つをまとめず、`getByRole('radio', { name: ... })`で個々を一意に拾えるようにするため。[[custom-pages]]の「role-basedロケータで一意に拾える要素のみを使う」規約に従う |
| テキストエリアへの入力値には改行を含む複数行文字列を使うシナリオ文言にする | 既存シナリオの`fill`はいずれも1行の値しか渡しておらず、複数行値の`fill`はまだ踏まれていないため |
| 完了確認は既存の「送信ボタン→inline JSでの固定メッセージ表示」パターンをそのまま使い、新しいJS挙動（バリデーション等）は増やさない | [[custom-pages]]の「SPA化・ビルドツール導入はしない」方針を維持しつつ、既存パターンの再利用でレビューコストを下げるため |
| `custom-pages-demo.yaml`の既存ステップ列（id 8〜15）は変更しない | 既存stepの指示文言はいずれも新規フィールド（ラジオボタン・テキストエリア）に言及しないため、AIはそれらに触れずシナリオを完走できる。既存の回帰シナリオを壊さずに済む |

## `.claude/rules` 更新ポイント

なし（`paths`はStep2で`scripts/stories/*.yaml`へ拡張済み。規約からの逸脱も無いため本文追記は不要）
