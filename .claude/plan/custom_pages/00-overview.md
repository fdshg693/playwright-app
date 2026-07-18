# 自作テストページ（resources/custom_pages） 実装プラン - 概要

> [.claude/rules/architecture.md](../../rules/architecture.md) 記載の通り、現状 `big_plans` Step1（[main/01-vertical-slice.md](../main/01-vertical-slice.md)）のみ実装済み。本プランはStep2以降の実装そのものではなく、Step2以降で使うテスト対象を自作ページに差し替えるための準備作業。[.claude/rules/plans.md](../../rules/plans.md) が定める `big_plans`⇔`.claude/plan/main` の1対1対応の外側にあるサブプランで、対応する`big_plans/0N-*.md`は無い。

## 要件

- 現状のvertical slice（[main/01-vertical-slice.md](../main/01-vertical-slice.md)）は `playwright.dev` という外部サイトを対象にしている。外部サイトはDOM構造やコンテンツがこちらの都合で変わらず、snapshotのサイズ・内容も制御できない。
- `resources/custom_pages/` 配下に、テストしやすく・snapshotが小さく安定した自作の簡易Webアプリを作り、ローカルでホスティングする。
- 技術選定はNGINX＋素のHTML（ユーザー指定）。SPAフレームワーク・ビルドツールは使わない。
- 将来的なGCPデプロイ（Terraform）は視野に入れるが、**今回のスコープには含めない**（決定事項参照）。

## 実装ステップ

1. [01-page-design.md](01-page-design.md) — テスト対象ページの設計・作成（vertical sliceのtool群を一通り使える操作パターンを揃える）
2. [02-local-hosting.md](02-local-hosting.md) — NGINXによるローカルホスティング設定と、既存stories/vertical sliceからの参照切り替え

## 主要な決定事項

| 決定 | 理由 |
|---|---|
| SPAフレームワークやビルドツールは使わず素のHTML/CSS/最小限のJSのみ | snapshot（アクセシビリティツリー）を小さく・予測可能に保つことが目的で、フレームワークのDOM複雑化は目的に反する |
| ローカルホスティングはWSL環境に既に入っているsystem nginx（`/usr/sbin/nginx`）をそのまま使い、Dockerは使わない | 追加の抽象化（コンテナ化）を今回の目的（ローカルでの軽量ホスティング）に対して持ち込む必要が無い |
| Terraform/GCPデプロイは今回実装しない。ただし`resources/custom_pages/`配下はページ本体（`pages/`）とホスティング設定（`nginx/`）を分けたディレクトリ構成にしておく | 未確定のインフラ要件をYAGNIで作り込まない一方、後で`infra/terraform`等を足す際にページ本体へ手を入れずに済むよう、構成分離だけは先に決めておく |

## 変更/新規ファイル一覧

（各ファイルの役割・読むべき既存ファイルは各ステップを参照）

### 新規
- `resources/custom_pages/pages/*.html`（複数、Step1で確定）
- `resources/custom_pages/nginx/nginx.conf`
- `resources/custom_pages/serve.sh`
- `scripts/stories/custom-pages-demo.yaml`
- `.claude/rules/custom-pages.md`

### 変更
- `package.json`（ローカル起動用npm scriptを追加）

## `.claude/rules` 更新ポイント

- `custom-pages.md`（Step2, 新規作成・フロントマター付き）: 自作テストページの配置規約・起動方法・GCPデプロイ未実装である旨
