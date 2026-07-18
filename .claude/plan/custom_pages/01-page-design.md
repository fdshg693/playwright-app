# Step 1: テスト対象ページの設計・作成

> [00-overview.md](00-overview.md) の続き。

## やること

- `resources/custom_pages/pages/` 配下に、vertical slice（および今後のStep2以降）が使う操作パターン（`navigate`/`click`/`fill`/`press`/`select`/`check`/`uncheck`/`hover` + 結果確認）を一通り再現できる、複数の簡易HTMLページを作る。
- 既存の `search-demo.yaml`（`playwright.dev`対象）と同等の「検索→結果確認」フローを自作ページで再現しつつ、フォーム入力・チェックボックス・セレクトなど他のtoolも1シナリオでカバーできるようにする。
- 見た目の作り込みはしない。role・label・aria属性を明示し、role-basedロケータで安定して要素を拾えることを優先する。
- ホスティング設定（nginx等）・stories側の切り替えは対象外（[02-local-hosting.md](02-local-hosting.md)で行う）。このステップではページのファイル一式のみを作る。

## 読むべきファイル・実行推奨Grep

**既存tool群の引数形状を確認するため（優先度: 高）**
- 読む: `scripts/vertical_slice/tools.py` — `navigate`/`click`/`fill`/`press`/`select`/`check`/`uncheck`/`hover`の引数（どんな要素をページ側に用意すればこれらを全部使えるか判断する材料）
- 読む: `scripts/stories/search-demo.yaml` — 既存デモシナリオのステップ分割の粒度・書き方の基準

**規約・snapshot形式を確認するため（優先度: 中）**
- 読む: `.claude/skills/playwright-cli/references/test-generation.md` — role-basedロケータ優先方針、生成コードの作法
- 読む: `.claude/skills/playwright-cli/SKILL.md` — snapshot出力の形式（どの属性がsnapshotに乗るか）

## 触るファイル

### 新規
- `resources/custom_pages/pages/index.html` — トップページ。他ページへの導線（`<a href>`によるフルロード遷移の起点）
- `resources/custom_pages/pages/search.html` — 検索フォーム→結果一覧（既存search-demoと同等の検証パターンをカバー）
- `resources/custom_pages/pages/form.html` — テキスト入力・チェックボックス・セレクト・ボタン一式を1画面に集約したフォーム確認用ページ
- `scripts/stories/custom-pages-demo.yaml` — 上記ページを対象にした新シナリオ定義（`seed_url`は[02-local-hosting.md](02-local-hosting.md)でローカルURLに設定するため、このステップでは仮値のままでよい）

## 決定事項・注意点／落とし穴

| 決定 | 理由 |
|---|---|
| 検索結果は固定の静的HTML（入力文字列によるJSでの絞り込みはしない。どんな検索語でも同じ結果セットを表示する） | 動的な絞り込みロジックを自作するとそれ自体が壊れる要因になる。目的はplaywright-cli操作の練習台を用意することであり、検索機能の正しさ検証ではないためYAGNI |
| 各操作対象要素には必ずvisibleなテキストラベルまたは`aria-label`を付与し、`getByRole`等のrole-basedロケータで一意に拾えることを確認する | [[test-generation]]のrole-based優先方針。ラベル無しの要素があるとhealステップでのセレクタ解決が不安定になる |
| ページ間遷移は通常の`<a href>`によるフルロードのみとし、SPA的なhistory API操作はしない | snapshot取得タイミングを単純化するため。SPA化するとnavigate完了判定が複雑になり、このステップのスコープを超える |

## `.claude/rules` 更新ポイント

このステップ単独では追記しない。ページ本体とホスティング設定の両方が揃った時点で、[02-local-hosting.md](02-local-hosting.md)でまとめて新規ルールファイルを作成する。
