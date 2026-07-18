# Step 2: APIクライアント実装 + フォーム組み込み（サンプル）

> [01-research-step-example.md](01-research-step-example.md) の続き。「読むべきファイル・推奨Grep」の書き方、および新規ルールファイル作成時のフロントマターの書き方のサンプルです。実装対象ではありません。

## やること

Step1の調査結果をもとに、会員登録フォームの郵便番号欄に「住所自動入力」を追加する。

## 読むべきファイル・実行推奨Grep

**類似実装を確認するため（優先度: 高）**
- 読む: `ArticleShare/Services/ArticleService.cs` — 本アプリのService層の書き方の基準（DIの受け方、非同期メソッドの命名規則）
- Grep: `IHttpClientFactory` — 他に外部APIを呼んでいる箇所が本当に無いか最終確認（Step1でHaikuサブエージェントに委任した調査結果の裏取り）

**影響範囲を確認するため（優先度: 中）**
- 読む: `ArticleShare/Controllers/AccountController.cs` — 登録フォームの既存アクション・バリデーション構造
- 読む: `ArticleShare/Views/Account/Register.cshtml` — 郵便番号入力欄のフォーム構造と、JSファイルの読み込み方

**規約・落とし穴を確認するため（優先度: 低。時間があれば）**
- 読む: `.claude/rules/external-api.md` — この時点ではまだ存在しない（このステップで新規作成する側）ので存在確認だけして無ければスキップする

## 触るファイル

### 新規
- `ArticleShare/Services/ExternalApi/IPostalCodeApiClient.cs` / `PostalCodeApiClient.cs` — zipcloud APIを呼び出すクライアント
- `ArticleShare/wwwroot/js/postal-code-autofill.js` — 郵便番号入力時にAPIを叩いて住所欄へ反映するJS
- `.claude/rules/external-api.md` — 外部API呼び出しの規約（新規ルールファイル）

### 変更
- `ArticleShare/Controllers/AccountController.cs` — `PostalCodeApiClient` をDI登録し、住所検索用の軽量エンドポイント（`GET /account/postal-code/{code}`）を追加
- `ArticleShare/Views/Account/Register.cshtml` — 郵便番号欄に`postal-code-autofill.js`を読み込ませる

## 決定事項・注意点／落とし穴

| 決定 | 理由 |
|---|---|
| 外部API呼び出しは `PostalCodeApiClient` に閉じ込め、Controllerから`HttpClient`を直接叩かない | 外部APIの仕様変更やテスト時のモック差し替えの影響範囲をService層に限定するため |
| `results: null`（該当なし）はエラーではなく「該当住所なし」として扱い、204相当を返す | Step1の調査どおり zipcloud APIは該当なしでもHTTP 200を返すため、ステータスコードだけで成否判定すると誤判定になる — [01-research-step-example.md](01-research-step-example.md) 参照 |
| レート制限は自前実装しない（都度呼び出しのみ） | Step1の調査で明確な制限値が確認できなかった。無いリスクに対する事前の作り込みはYAGNI。問題が顕在化したらキャッシュ導入を検討する |

## `.claude/rules` 更新ポイント

新規ルールファイル `.claude/rules/external-api.md` を作成する（既存ルールに外部API呼び出しの規約がまだ無いため）。フロントマターで対象パスを列挙する:

```markdown
---
paths:
  - "ArticleShare/Services/ExternalApi/**/*.cs"
---

## 外部API呼び出し規約

- 外部APIクライアントは `Services/ExternalApi/` 配下に集約し、Controllerから直接`HttpClient`を叩かない。
- レスポンスがHTTP 200でも「該当なし」を返すAPIがある（zipcloud等）。ステータスコードだけで成否判定しない。
```

---

## 書き方のポイント

- **「読むべきファイル・推奨Grep」はファイルパスを並べるだけにしない。** 「何を確認するために読むのか」という観点でグルーピングし、優先度（高／中／低）を明示する。実装者が読む順番に迷わないようにするための節であり、「触るファイル」（変更対象）とは別物。
- Grepは新規の調査だけでなく、「Step1でHaikuサブエージェントに委任した調査結果の裏取り」のように、既に得た情報を実装直前に軽く再確認する用途にも使ってよい。
- **新規ルールファイルを作る場合はフロントマターまでプランに書く。** 対象パス（`paths:`）を決めるのは設計判断そのものであり、実装時の思いつきに任せると粒度がぶれる。本文（規約の中身）は既存サンプル同様、要点のみでよい（[writing-rulesスキル](../../skills/writing-rules/writing.md)のフォーマットに従う）。
- 既存ルールファイルに1行追記するだけの場合（[03-single-file-example.md](03-single-file-example.md) 参照）は、対象パスに変化が無ければフロントマターの変更は不要。新規作成のときだけフロントマターの設計が必要になる。
- 決定事項の理由には、Step1の調査結果を根拠として引用してよい。調査結果の全文はコピーせず、リンクで参照する。
