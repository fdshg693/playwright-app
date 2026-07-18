---
paths:
  - "**"
---

## アーキテクチャ概要

このプロジェクトは「人間が自然言語で書いたテストストーリー → AIがブラウザを操作 → 再実行可能なPlaywrightテストコード」を自動生成する仕組み。全体設計は [SPEC.md](../../SPEC.md) が正、実装ロードマップは [big_plans/](../../big_plans/)（WHAT・順序）と [.claude/plan/main/](../plan/main/)（HOW・実装詳細、`.claude/plan/README.md` の書式に従う）に分かれている。**現状 big_plans の Step1〜7（縦の一本通し・サーバー骨組み・タスクオーケストレーション自動化・コード生成組み立て・記録/再開・失敗時リトライ・人間による確認/強制停止）まで実装済み**で、`scripts/vertical_slice/`（詳細は [[vertical-slice-runner]]）と `scripts/server/`（詳細は [[session-server]]）がそれに当たる。Step8（安全性ガードレール）のみ未実装。

### 崩してはいけない前提（SPEC.md 2章）

- **ブラウザセッションは永続、AIコンテキストはステップごとに初期化**という2つを混同しないこと。サーバー（またはそれに相当するコード）側がセッションを1本維持しつつ、AI呼び出しのたびに `snapshot` を取り直して渡すことで「フレッシュなコンテキストでも今の画面がわかる」状態を作る。
- **1タスク＝1ステップ**が粒度の単位。「1シナリオ＝1セッション」という playwright-cli の plan→generate→heal のセッション単位と、AIコンテキストを初期化する単位は別物として扱う。
- 各ステップへの入力は「残りのストーリー」と「現在の画面snapshot」だけに絞る。過去の操作履歴に依存しないと解けないシナリオはスコープ外という設計上の割り切り。

### Playwright CLI を選んだ理由

Playwright MCP ではなく playwright-cli を採用している。MCPは閉じたループの中で完結するには楽だが、その中間にタスク管理・記録・再開制御などの独自ロジックを挟もうとするとMCPの作法に合わせるアダプトコストが発生するため。CLIは薄いプロセス呼び出しなので独自ロジックを挟むコストが小さい（SPEC.md 4章）。詳細は `playwright-cli` スキル（[.claude/skills/playwright-cli/SKILL.md](../skills/playwright-cli/SKILL.md)）を読んで理解すること。

### スキルの利用方針

- ある程度複雑なWeb検索には `use-tavily` スキルを積極的に使う。
- Playwright CLI の操作については `playwright-cli` スキルを読んで理解してから使う。
- `scripts/vertical_slice/main.py` を実AI APIに対して完走確認したい場合は `vertical-slice-ai-test` スキル（[.claude/skills/vertical-slice-ai-test/SKILL.md](../skills/vertical-slice-ai-test/SKILL.md)）に従う。実課金APIコールになるため、実行前に必ずユーザーへ確認する。
