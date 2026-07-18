# 郵便番号からの住所自動入力機能 実装プラン - 概要（サンプル）

> これは `.claude/plans/references/` 配下のサンプルです。架空の機能を題材に、複数ステップに分割するプランの書き方を示しています。実装対象ではありません。

## 要件

- 会員登録フォームの郵便番号欄に、外部API（zipcloud）を使った住所自動入力を追加する。
- 該当住所が無い場合はエラーにせず、住所欄を空のまま残す。

## 実装ステップ

1. [01-research-step-example.md](01-research-step-example.md) — 外部API仕様の事前調査（Web調査 + 既存コード調査をHaikuサブエージェントへ委任）
2. [02-implementation-step-example.md](02-implementation-step-example.md) — APIクライアント実装 + フォーム組み込み

## 主要な決定事項

| 決定 | 理由 |
|---|---|
| DBスキーマは変更しない（住所は取得のたびにフォームへ表示するだけで永続化しない） | 保存が要件に含まれておらず、永続化は過剰設計 |
| 外部APIクライアントは新規レイヤー `Services/ExternalApi/` として独立させる | Article本体のドメインロジックとは無関係な横断的関心事であり、既存の `ArticleService` 等とは責務が異なる |

## 変更/新規ファイル一覧

（各ファイルの役割・読むべき既存ファイルは各ステップを参照）

### 新規
- `ArticleShare/Services/ExternalApi/IPostalCodeApiClient.cs` / `PostalCodeApiClient.cs`
- `ArticleShare/wwwroot/js/postal-code-autofill.js`
- `.claude/rules/external-api.md`

### 変更
- `ArticleShare/Controllers/AccountController.cs`
- `ArticleShare/Views/Account/Register.cshtml`

## `.claude/rules` 更新ポイント

- `external-api.md`（Step2, 新規作成・フロントマター付き）: 外部APIクライアントの配置規約とレスポンス成否判定の注意点

---

## 書き方のポイント

- **要件は2〜4行の箇条書きで十分。** 背景の説明やユースケースの動機は書かない。
- **外部API・外部ライブラリなど、実装前にWeb上の仕様を確認しないと決定事項が固まらない機能は、調査を独立したステップ（Step1）として先に置く。** 実装ステップ（Step2）はその結果を前提に書けるので、調査時に読んだページの全文を実装ステップ側に持ち込まずに済む。詳細は[README.md](../README.md)の「外部知識が必要な場合」節を参照。
- **実装ステップの数は機能の複雑さなりに。** 小さい機能は調査ステップも不要で、1ファイルに収める（[03-single-file-example.md](03-single-file-example.md) 参照）。無理に `00-overview.md` + 複数ステップの型に当てはめない。
- **決定事項は「決定」と「理由」を1行ずつ。** 判断の根拠となる規約は `[[リンク]]` で指すだけにする。理由の全文はリンク先の `.claude/rules` に書かれているべきもので、プラン側で重複させない。
- **ファイル一覧は「新規」「変更」の2分類のみ。** 「読むべきファイル・推奨Grep」のような、実装者向けの詳細な手引きは各ステップファイル側に書き、概要ファイルには持ち込まない。
