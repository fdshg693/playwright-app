# AI に画面テストを効率よくさせるためのツール作成

人間が自然言語で書いたテストストーリーを、AIがブラウザを操作しながら実行し、再実行可能なPlaywrightテストコード（`.spec.ts`）として生成するツール。`big_plans/`のStep1〜8（縦の一本通し〜最低限の安全策）まで実装済み。

## ドキュメント

| ドキュメント | 内容 |
|---|---|
| [MERMAID.md](MERMAID.md) | 全体の流れ・構成を図解 |
| [QUICKSTART.md](QUICKSTART.md) | セットアップから実行までの最短手順、Makefileコマンド一覧 |
| [FEATURES.md](FEATURES.md) | 現状実装済みの機能一覧 |
| [NEXT.md](NEXT.md) | あると良いがまだ無い機能・部分対応の機能 |
| [big_plans/](big_plans/) | 実装ロードマップ（何を・どの順で作るか） |
| [.claude/plan/main/](.claude/plan/main/) | 実装詳細プラン（どう実装するか） |
| [.claude/rules/](.claude/rules/) | サブシステムごとの実装詳細・規約 |

## はじめかた

```bash
make setup && make env
```

以降は [QUICKSTART.md](QUICKSTART.md) を参照。
