# Step 2: 既存stories未踏の経路を埋める軽量シナリオ

> [01-story-intent-field.md](01-story-intent-field.md) の続き。

## やること

- 既存の3本（`search-demo.yaml` / `search-demo-branch.yaml` / `custom-pages-demo.yaml`）は、実行済みログ（`tests/generated/*.spec.ts`）を見る限りいずれも次の2経路を一度も踏んでいない。
  - `navigate`ツールの直接呼び出し。既存シナリオの遷移は全て`click`によるリンククリックか、`cli.open(story.seed_url)`によるseed URLのみで、AIが`navigate`ツールを自発的に呼ぶケースが無い。
  - `fill`ツールの`submit`引数。既存シナリオは全て「`fill`で入力→別ターンで`press`によるEnter」の2手順に分かれており、`submit: true`による1手順の提出が未検証。
  この2つを踏ませる軽量シナリオ`navigate-direct-demo.yaml`を追加する。
- 検索結果0件の静的ページ`search-empty.html`を追加し、`toHaveText`アサーションのバリエーションを増やす（既存の`custom pages demo`実行ログでは`toHaveText`はツールチップの1箇所のみで踏まれている。別要素・別文面で`toHaveText`を踏ませておく）。対応するシナリオ`search-empty-demo.yaml`を追加する。
- 本ステップで`.claude/rules/custom-pages.md`の`paths`フロントマターを拡張し、以降のStep3〜5で追加する`scripts/stories/*.yaml`にも同ルールが適用される状態にしておく。
- 新規追加する2本の`intent`には、それぞれ「何を踏ませたいか」（`navigate`ツール直接呼び出し／`fill(submit=true)`、`toHaveText`のバリエーション）をそのまま書く（[[01-story-intent-field]]で追加した必須フィールド）。

## 読むべきファイル・実行推奨Grep

**未踏の経路を裏取りするため（優先度: 高）**
- 読む: `tests/generated/search-demo.spec.ts` / `search-demo-branch.spec.ts` / `custom pages demo.spec.ts`（生成済みコード。`page.goto`が`await page.goto(story.seed_url)`の1回しか出ておらず`navigate`ツール経由の`goto`が無いこと、`fill`が全て単独行で`.check()`等と同様に「入力のみ」であること、`toHaveText`がツールチップ1箇所のみであることを確認する）
- 読む: `scripts/vertical_slice/tools.py` の `TOOL_SCHEMAS`（`navigate`/`fill`の引数定義。`fill`の`submit`は必須パラメータだがtrue/falseのどちらを選ぶかはAI任せである点を確認）

**search-empty.htmlのテンプレートにするため（優先度: 中）**
- 読む: `resources/custom_pages/pages/search.html`（結果一覧の構造。`search-empty.html`はこの構造を保ったまま結果リストだけ差し替える）

## 触るファイル

### 新規
- `resources/custom_pages/pages/search-empty.html` — `search.html`と同じ検索フォーム＋見出し構造を持ち、結果一覧の代わりに固定の1行メッセージ（例:「検索結果が見つかりませんでした」）を表示するページ
- `scripts/stories/navigate-direct-demo.yaml` — `intent`に「`navigate`ツールの直接呼び出しと`fill(submit=true)`の1手順提出を踏ませる」ことを書く。seed_urlを`index.html`とし、1ステップ目で「検索ページを経由せず`http://localhost:8080/search-empty.html`に直接アクセスする」ことを指示するシナリオ。以降のステップで検索キーワード入力→Enterでの検索実行（`fill(submit=true)`が選ばれやすい1文にまとめる）を行う
- `scripts/stories/search-empty-demo.yaml` — `intent`に「`toHaveText`アサーションを別要素・別文面で踏ませる」ことを書く。seed_urlを`http://localhost:8080/search-empty.html`とし、固定の空状態メッセージが指定テキストと一致することを確認する（`add_expectation`の`toHaveText`を狙う指示文言にする）

### 変更
- `.claude/rules/custom-pages.md` — `paths`フロントマターを`scripts/stories/custom-pages-demo.yaml`の単体列挙から`scripts/stories/*.yaml`に拡張

## 決定事項・注意点／落とし穴

| 決定 | 理由 |
|---|---|
| `index.html`にも`search.html`にも`search-empty.html`への`<a href>`を置かない | リンククリックでは到達不能にすることで、AIが`navigate`ツールを選ばざるを得ない状況を作るため。逆にリンクを置くと`click`で解決されてしまい検証にならない |
| `fill`の`submit`引数の使用を強制するツール選択ロジックの変更はしない。シナリオ文言を「検索キーワード欄に"empty"と入力してそのままEnterで検索する」のように1ステップにまとめる程度の緩い誘導に留める | ツール選択はAI任せというarchitecture.mdの設計思想（1タスク＝1ステップ、過去の操作履歴に依存しない）を崩さないため。強制できなくても「1手順にまとめた指示」自体が既存シナリオには無いパターンであり、それだけで価値がある |
| `search-empty.html`上のフォーム自体は残すが、この静的ページでの検索実行（GET送信）は同じ`search-empty.html`に戻ってくるだけで内容は変化しない | 動的な絞り込みロジックを実装しないという既存規約（[[custom-pages]]）をそのまま踏襲するため |

## `.claude/rules` 更新ポイント

- `custom-pages.md`（既存ファイルへの追記＋frontmatter変更）
  - `paths`を以下に変更:
    ```yaml
    paths:
      - "resources/custom_pages/**"
      - "scripts/stories/*.yaml"
    ```
  - 追記内容は無し（規約本文はStep5で`edge-cases.html`の例外を追記するまで変更しない）
