# 進め方 概要

[SPEC.md](../SPEC.md) を段階的に実装するためのステップ分割。各ステップは前段の成果物の上に積み上げる想定で、MVPをまず縦に1本通してから機能を足していく順序にしている。

1. [01-vertical-slice.md](01-vertical-slice.md) — サーバーなしで、コアループ（ストーリー断片＋snapshot→AI判断→playwright-cli実行→コード生成）が成立するかを手動で検証する
2. [02-server-skeleton.md](02-server-skeleton.md) — Playwright CLIセッションを永続させ、外部からリクエストを受けられるサーバーの骨組みを作る
3. [03-task-orchestration.md](03-task-orchestration.md) — 1タスク＝1フレッシュコンテキストでAIを呼び出すオーケストレーションを自動化する
4. [04-code-generation-assembly.md](04-code-generation-assembly.md) — タスクごとに生成されたコードをテストファイルへ組み立てる（plan/generateフローへの接続）
5. [05-recording-and-resume.md](05-recording-and-resume.md) — 操作ログ・スクリーンショットの記録と、そこからの途中再開を実装する
6. [06-failure-handling.md](06-failure-handling.md) — リトライと、失敗時の診断情報つき停止（healフローへの接続）を実装する
7. [07-human-observation-and-control.md](07-human-observation-and-control.md) — 人間が進捗確認・強制停止できる手段を用意する
8. [08-safety-guardrails.md](08-safety-guardrails.md) — 対象URLの固定など、最低限の安全策を入れる

各ステップの完了条件は、そのステップのファイル内に記載する。実装を進める中でSPEC.mdの内容と矛盾が出た場合は、SPEC.md側を更新すること。
