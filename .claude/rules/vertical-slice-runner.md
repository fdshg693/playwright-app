---
paths:
  - "scripts/vertical_slice/**"
  - "scripts/stories/**"
  - "tests/generated/**"
---

## vertical_slice ランナー

SPEC.md の Step1（縦の一本通し）実装。`python -m scripts.vertical_slice.main --story <yaml>` で、人間の介入なしにストーリー1本を最初から最後まで実行し、`tests/generated/*.spec.ts` を生成する。責務は `.claude/plan/main/01-vertical-slice.md` に詳しい。

- `story.py` — `scripts/stories/*.yaml`（`seed_url` + `steps[].instruction`）を `Story`/`Step` にロードするだけ。
- `cli_executor.py` の `CliExecutor` が SPEC.md でいう「サーバー」役。ネットワークサーバーではなく、1つの名前付き playwright-cli セッション（`-s=<session>`）を最初から最後まで維持するプロセス境界。**playwright-cli はコマンド失敗時も exit code 0 のまま stdout に `### Error` を返す**ため、成功判定は exit code ではなく毎回 stdout をこの文字列でチェックしている（`CliExecutor.execute`）。
- `prompts.py` の `build_input()` が「1ステップ＝1フレッシュコンテキスト」の起点。呼び出しごとに `previous_response_id` は使わず、developer prompt + 残りステップ + 現在のsnapshot からゼロで組み立てる。ステップ内の複数ターンは `main.run_step()` がこの `input_items` リストにローカルで追記して繋ぐ（＝ステップを跨いだ記憶は持たないが、ステップ内はチェーンする）。
- `tools.py` の `TOOL_SCHEMAS` が OpenAI Responses API に渡すツール定義一式。`finish_step` はCLIコマンドではなくループ制御用の合図で、**他の操作系ツールと同じターンで一緒に呼んではいけない**契約（呼ばれた場合 `main.run_step()` は同時に来た操作呼び出しを無視してログに warning を出す）。操作系ツールは `ref`（snapshotに載っているものだけ）でしか要素を指定できない。

### ステップ内ループの終了条件（`main.run_step`）

`MAX_TURNS_PER_STEP = 8` の間、`finish_step` が呼ばれるまでターンを重ねる。以下のいずれかで即停止し `failure_notes` に理由が積まれる：`finish_step(status="blocked")` / モデルがツールを1つも呼ばない / CLI呼び出しが `CliError` を投げる / `MAX_TURNS_PER_STEP` 到達。これは**リトライ機構ではない**（リトライは Step6 の未実装スコープ、SPEC.md 6章）— 1ステップの応答時間に対する安全弁のみ。

### 生成物

- `<out>.spec.ts` — 集めた `generated_code` を1つの `test()` に組み立てて書き出し（`write_spec_file`)。書き出し後 `npx playwright test` を自動実行する。
- `<out>.failure-notes.json` — 失敗があった場合のみ（`write_failure_notes`)。
- `<out>.steps.jsonl` — 全ターンの生ログ（プロンプト・モデル出力・ツール結果）。停止理由を後から読み返すためのもので、`main.py` 冒頭のモジュールdocstringに全体フローの説明がある。
