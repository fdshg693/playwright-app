---
paths:
  - "resources/custom_pages/**"
  - "scripts/stories/custom-pages-demo.yaml"
---

## 自作テストページ（resources/custom_pages）の規約

- ページ追加時は`pages/`配下にHTMLを置き、role-basedロケータで一意に拾える要素（visibleなラベル/aria-label付き）のみを使う。SPA化・ビルドツール導入はしない。
- 検索・一覧系のページは固定の静的レスポンスとし、入力に応じた動的な絞り込みロジックは実装しない。
- ローカル起動は `npm run serve:pages`（system nginxを`resources/custom_pages/nginx/nginx.conf`で起動、ポート8080固定）。フォアグラウンド起動のみで、停止はCtrl+C。
- GCPデプロイ（Terraform）は未実装。追加する場合は`resources/custom_pages/`直下にインフラ用ディレクトリを新設し、`pages/`側には手を入れない。
