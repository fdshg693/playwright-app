# Step 1: 縦の一本通し（サーバーなし）

> 実装の詳細（Python + OpenAI Responses APIを使った最小スクリプトでの自動化計画）は [plan/detail/01-vertical-slice.md](detail/01-vertical-slice.md) を参照。

## 目的

サーバーやオーケストレーションを作る前に、コアループそのものが成立するかを手動で確認する。

コアループ:

```
テストストーリー（次ステップ含む）＋現在の画面snapshot
  → AIが判断
  → playwright-cli コマンド発行
  → 生成されたPlaywrightコードを回収
```

## やること

- 簡単なテストストーリーを1つ用意する（例: 「トップページを開き、検索欄に"playwright"と入力してEnterを押し、検索結果が表示されることを確認する」）
- 対象は認証不要の適当なWebサイト（[08-safety-guardrails.md](08-safety-guardrails.md) の前提に合わせる）
- 人間（自分）がストーリーをステップに分割し、各ステップを新しい会話（＝フレッシュなコンテキストを模したもの）としてAIに渡す
  - 各ステップの入力は「残りのストーリー」と「直前の `playwright-cli snapshot` の出力」のみ。会話履歴は意図的に渡さない
- `playwright-cli` を使って実際に操作を行い、生成されたコードを手元でファイルに書き出す
- 最終的に1本のPlaywrightテストファイル（`.spec.ts`）が完成し、`npx playwright test` で通ることを確認する

## 完了条件

- 「現在の画面情報だけで次のタスクが判断できる」という前提（SPEC.md 2章）が、少なくとも1つのシナリオで実際に成立することを確認できている
- 成立しないケースに遭遇した場合、それがどういう性質のシナリオだったかをメモしておく（スコープ外の境界線を知るための材料になる）

## 実行結果メモ

- 2026-07-18、`search-demo.yaml` のステップ1（「検索欄をクリックしてフォーカスする」）で、モデルが `click(ref="e218")` は呼んだが、同じレスポンス内で `finish_step` を呼ばなかった。`tool_choice="required"` かつプロンプトで「最後に必ずfinish_stepを呼ぶ」と明示していても、1レスポンスに複数tool callを確実に含めさせることはできなかった
  - スクリプトは設計通り（[main.py](../scripts/vertical_slice/main.py)）`finish_step_missing` として failure note に記録し、その場で停止した（`tests/generated/search-demo.spec.failure-notes.json`）
  - [detail/01-vertical-slice.md](detail/01-vertical-slice.md) のOpen Question「1レスポンス内で複数tool callを許可した場合…『1レスポンス=1操作』まで粒度を落とすべきかを判断する」が、まさにこのケースで顕在化した
  - 対応済み: (a)を採用。ステップ内を「モデル呼び出し→tool call実行→結果と最新snapshotを返す→再度モデル呼び出し」の多ターンループに変更し（`main.py`の`run_step`）、`finish_step`が単独で返るまで繰り返すようにした（上限`MAX_TURNS_PER_STEP=8`、超えたら`max_turns_exceeded`としてfailure note）。プロンプト（`prompts.py`）も「finish_stepは他の操作系ツールと同時に呼ばず、結果を確認してから単独で呼ぶ」よう明記
  - 再実行（2026-07-18）: ステップ1〜3は`click`→結果確認→`finish_step`のように2ターンで正常完了。ステップ4（「検索結果が表示されていることを確認する」）は`blocked`で停止 — Enter押下後、検索モーダルが一覧を出さずトップの候補ページへ直接遷移したため、モデルが「現在のsnapshotだけでは検索結果表示を確認できない」と正しく判断した。これはツール呼び出しの設計問題ではなく、シナリオ（`search-demo.yaml`）の想定と実際のサイト挙動のズレによるもの
