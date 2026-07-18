# Step 2: NGINXによるローカルホスティングと既存stories側の切り替え

> [01-page-design.md](01-page-design.md) の続き。

## やること

- `resources/custom_pages/pages/` 配下の静的ページを、system nginxでローカル配信できるようにする。起動・停止を1コマンドで行えるようにする。
- Step1で作った `scripts/stories/custom-pages-demo.yaml` の `seed_url` をローカルnginxのURLへ設定し、vertical slice（`scripts/vertical_slice/main.py`）から自作ページを対象に実行できることを確認する。
- GCP/Terraformデプロイはこのステップでも対象外（[00-overview.md](00-overview.md)の決定事項参照）。

## 読むべきファイル・実行推奨Grep

**既存の設定読み込み・story解釈を確認するため（優先度: 高）**
- 読む: `scripts/vertical_slice/config.py` — 環境変数の読み込み方（ポート番号やベースURLをどう設定に足すかの既存パターン）
- 読む: `scripts/vertical_slice/story.py` — `seed_url`がどう読み込まれ、どこで使われるか
- Grep: `seed_url` — `main.py`/`story.py`内の参照箇所を洗い出し、ローカルURLに差し替えても動くか確認

**既存のURL関連設定と重複が無いか確認するため（優先度: 中）**
- 読む: `playwright.config.ts` — 既存のPlaywright実行設定（`baseURL`等が既にあるか。あれば重複させず合わせる）
- 読む: `.env.example` — 既存の環境変数命名規則（値そのものは書き換えず、命名パターンだけ確認）

## 触るファイル

### 新規
- `resources/custom_pages/nginx/nginx.conf` — `listen`ポート・`root`（`resources/custom_pages/pages/`）・`index`の設定
- `resources/custom_pages/serve.sh` — system nginxを上記confで起動／停止するスクリプト（システムのデフォルトconfは変更しない）
- `.claude/rules/custom-pages.md` — 自作テストページの配置規約（新規ルールファイル）

### 変更
- `package.json` — `"serve:pages": "bash resources/custom_pages/serve.sh"` 相当のnpm scriptを追加
- `scripts/stories/custom-pages-demo.yaml`（Step1で作成） — `seed_url`をローカルnginxのURL（例: `http://localhost:8080`）に設定

## 決定事項・注意点／落とし穴

| 決定 | 理由 |
|---|---|
| ポート番号は8080固定（必要なら環境変数で上書き可能にするが、デフォルト値はハードコードでよい） | 個人ローカル用途であり、複数環境での競合は現時点で考慮不要 |
| system nginx（`/usr/sbin/nginx`）をそのまま使い、起動時に`-c`で本リポジトリ内のconfを明示指定する。システムのデフォルトconf（`/etc/nginx/nginx.conf`）は変更しない | システム設定を汚さず、リポジトリ内で完結させるため |
| `serve.sh`はフォアグラウンド起動（`daemon off;`相当）を基本とし、バックグラウンド常駐・自動再起動の仕組みは作らない | ローカル検証用途であり、常駐監視の仕組みは過剰設計。必要になった時点で見直す |

## `.claude/rules` 更新ポイント

新規ルールファイル `.claude/rules/custom-pages.md` を作成する。フロントマターで対象パスを列挙する:

```markdown
---
paths:
  - "resources/custom_pages/**"
  - "scripts/stories/custom-pages-demo.yaml"
---

## 自作テストページ（resources/custom_pages）の規約

- ページ追加時は`pages/`配下にHTMLを置き、role-basedロケータで一意に拾える要素（visibleなラベル/aria-label付き）のみを使う。SPA化・ビルドツール導入はしない。
- 検索・一覧系のページは固定の静的レスポンスとし、入力に応じた動的な絞り込みロジックは実装しない。
- ローカル起動は `npm run serve:pages`（system nginxを`resources/custom_pages/nginx/nginx.conf`で起動、ポート8080固定）。
- GCPデプロイ（Terraform）は未実装。追加する場合は`resources/custom_pages/`直下にインフラ用ディレクトリを新設し、`pages/`側には手を入れない。
```

---

## 完了条件

- `npm run serve:pages` でローカルにページが表示できる。
- `scripts/stories/custom-pages-demo.yaml` を対象に `scripts/vertical_slice/main.py` を実行し、全ステップが完走する（またはStep1の`search-demo.yaml`実行時と同様に、スコープ外の落とし穴のみが記録される）。
- 同一シナリオを`playwright.dev`版（`search-demo.yaml`）と比較し、1ステップあたりのsnapshotサイズ・トークン消費が減っていることを確認する。
