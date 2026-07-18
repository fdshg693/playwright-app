---
paths:
  - "big_plans/**"
  - ".claude/plan/**"
---

## プランの二層構造

`big_plans/` と `.claude/plan/main/` はステップ名・ステップ数が1対1対応する別ファイル群で、役割が違う。

- `big_plans/` — 「何を・どの順で作るか」(SPEC.mdをどうMVPから積み上げるか)。完了条件はここに書く。実装を進めてSPEC.mdと矛盾したらSPEC.md側を更新する。
- `.claude/plan/main/` — 「どう実装するか」の詳細プラン。書式・粒度の方針は [.claude/plan/README.md](README.md) を参照（実装詳細のコードスニペットは書かない、5点構成、`references/` にサンプルあり）。

**現状 `01-vertical-slice.md`（実装・実行済み）と `02-server-skeleton.md`（詳細プランのみ、未実装）が詳細まで埋まっており、`03`〜`08` はプレースホルダ（「詳細は後に記載」)。** 新しいステップに着手する際はまず対応する `big_plans/0N-*.md` を読んで完了条件を掴んでから、`.claude/plan/main/0N-*.md` を詳細プランで埋める。

`.claude/plan/README.md` は `.claude/rules/roles.md` に従うことを前提にしている記述があるが、そのファイルは本リポジトリにまだ存在しない（テンプレート由来の未解決参照）。ルールファイルを更新する際の運用ルールは当面このリポジトリでは [writing-rules スキル](../skills/writing-rules/writing.md) の方針に従うこと。
