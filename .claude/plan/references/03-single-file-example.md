# タグ一覧の人気順ソート追加 実装プラン（サンプル・単一ファイル完結）

> 小さい変更を1ファイルで完結させるプランのサンプルです。実装対象ではありません。`00-overview.md` + ステップ分割との使い分けは末尾の「書き方のポイント」を参照。

## やること

管理画面のタグ一覧に「紐づく記事数が多い順」のソートオプションを追加する。既存の名前順ソートに選択肢を1つ加えるだけで、新規ドメイン・新規レイヤーは発生しない。外部知識の調査も不要。

## 読むべきファイル・実行推奨Grep

**既存のソート実装を確認するため（優先度: 高）**
- 読む: `ArticleShare/Repositories/TagRepository.cs` — 現在のソートオプション（名前順）の実装
- Grep: `SortOption` — ソート種別のenum/switch文が使われている箇所を洗い出す（追加箇所の漏れ防止）

**影響範囲を確認するため（優先度: 中）**
- 読む: `ArticleShare/Views/Admin/Tags/Index.cshtml` — ソートドロップダウンの既存マークアップ

## 触るファイル

- 変更: `ArticleShare/Repositories/TagRepository.cs` — ソートキーに `ArticleCount` を追加
- 変更: `ArticleShare/Services/TagService.cs` — ソートオプションの列挙に `PopularityDesc` 相当を追加
- 変更: `ArticleShare/Views/Admin/Tags/Index.cshtml` — ソートドロップダウンに選択肢を追加

## 決定事項

| 決定 | 理由 |
|---|---|
| 記事数の集計はDBクエリの `Count` で都度計算し、非正規化カラムは作らない | タグ一覧はページネーション付きの小規模データであり、都度集計のコストは無視できる。非正規化はキャッシュ無効化の複雑さを持ち込むだけで割に合わない |

## 注意点・落とし穴

- 記事数のカウントは「論理削除・非公開を除いた記事数」にすること。単純な `Tags.Count(Articles)` にすると削除済み記事も数えてしまう（[[article-domain]] の論理削除フィルタ規約を参照）。
- 既存のページネーション実装（インメモリ方式 — [[pagination]]）を崩さないよう、ソート処理はページング前に適用する。

## `.claude/rules` 更新ポイント

- `category-tag-domain.md`（既存ファイルへの追記）: ソートオプションの追加を1行追記。対象パスに変更は無いのでフロントマターは変更不要（新規ルールファイル作成時のフロントマターの書き方は[02-implementation-step-example.md](02-implementation-step-example.md)を参照）

---

## 書き方のポイント

- **単一ファイルで完結させる目安**: 触るファイルが3〜4個以内、かつ既存レイヤーをまたぐ新規追加（新しいEntity/Repository/Serviceの新設など）や、独立した調査ステップを要する外部知識の調査が無い場合。
- `00-overview.md` + ステップ分割（[00-overview-example.md](00-overview-example.md) / [01-research-step-example.md](01-research-step-example.md) / [02-implementation-step-example.md](02-implementation-step-example.md) 参照）は、新規ドメイン追加、複数レイヤーにまたがる機能、または外部API調査が必要な機能に限定する。小さい変更にステップ分割を適用すると、ファイルを開き直すコストの方が実装コストを上回る。
- **「読むべきファイル・推奨Grep」は小さい変更でも省略しない。** 量は少なくてよいが、観点（何を確認するためか）と優先度は分けて書く。フラットな箇条書きにしない。
- 構成要素（やること／読むべきファイル・推奨Grep／触るファイル／決定事項／注意点／`.claude/rules`更新）は複数ファイル版のプランと同じ。単に1ファイルに収めているだけで、書く粒度・書かない情報（コードそのもの、自明な手順）は変わらない。
