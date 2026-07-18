# Step 4: 生成コードの組み立て

## 目的

タスクの実行中に `playwright-cli` が都度出力する生成コード片を回収し、1本のPlaywrightテストファイルへ組み立てる。

## やること

- `playwright-cli` の generate フロー（[test-generation.md](../.claude/skills/playwright-cli/references/test-generation.md) 2章）に沿って、各タスクで発行したコマンドの生成コードを蓄積する
- ステップごとに `// N. <ステップの説明>` コメントを付与する（generate フローの規約に合わせる）
- ストーリー中の期待値（「〜が表示されることを確認する」等）を `expect` アサーションへ変換する
  - `generate-locator` や `eval` を使って、アサーション用のロケータ・期待値を取得する処理を組み込む
- 完成したコードを `tests/<group>/<scenario>.spec.ts` に書き出す
- 書き出したテストを実際に `npx playwright test` で1回実行し、成功することを確認する

## 完了条件

- Step 3で自動実行したシナリオから、人手を介さずにPlaywrightテストファイルが生成される
- 生成されたテストが `getByRole` 等の安定したロケータを使っている（脆いCSSセレクタ・座標指定になっていない）
- 生成されたテストが単体で（このツールを介さず）`npx playwright test` で実行・再現できる
