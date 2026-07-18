---
paths:
  - "resources/custom_pages/**"
  - "scripts/stories/*.yaml"
---

## 自作テストページ（resources/custom_pages）の規約

- ページ追加時は`pages/`配下にHTMLを置き、role-basedロケータで一意に拾える要素（visibleなラベル/aria-label付き）のみを使う。SPA化・ビルドツール導入はしない。
- 検索・一覧系のページは固定の静的レスポンスとし、入力に応じた動的な絞り込みロジックは実装しない。
- ローカル起動は `npm run serve:pages`（system nginxを`resources/custom_pages/nginx/nginx.conf`で起動、ポート8080固定）。フォアグラウンド起動のみで、停止はCtrl+C。
- GCPデプロイ（Terraform）は未実装。追加する場合は`resources/custom_pages/`直下にインフラ用ディレクトリを新設し、`pages/`側には手を入れない。
- `edge-cases.html`は意図的な失敗・非対応操作の検証用フィクスチャであり、role-basedロケータの一意性規約の対象外とする（同一アクセシブルネームを持つ複数ボタンを意図的に配置している）。`index.html`からもリンクしない。詳細は[.claude/plan/scenarios/05-failure-and-blocked-cases.md](../plan/scenarios/05-failure-and-blocked-cases.md)を参照。
