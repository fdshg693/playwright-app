---
paths:
  - "scripts/vertical_slice/**"
  - "scripts/stories/**"
  - "tests/generated/**"
---

## vertical_slice ランナー

SPEC.md の Step1（縦の一本通し）実装。`python -m scripts.vertical_slice.main --story <yaml>` で、人間の介入なしにストーリー1本を最初から最後まで実行し、`tests/generated/*.spec.ts` を生成する。責務は `.claude/plan/main/01-vertical-slice.md` に詳しい。

- `story.py` — `scripts/stories/*.yaml`（`seed_url` + `steps[].instruction` + `intent`）を `Story`/`Step` にロードするだけ。`intent`はこのシナリオが何を検証したい・できるかを書く必須の自由記述フィールドで、実行時のロジックには一切使われない（生成される`.spec.ts`にも反映しない）人間・AI読者向けドキュメンテーション専用。欠けていると`load_story`が`KeyError`で落ちる。
- `cli_executor.py` の `CliExecutor` が SPEC.md でいう「サーバー」役。ネットワークサーバーではなく、1つの名前付き playwright-cli セッション（`-s=<session>`）を最初から最後まで維持するプロセス境界。**playwright-cli はコマンド失敗時も exit code 0 のまま stdout に `### Error` を返す**ため、成功判定は exit code ではなく毎回 stdout をこの文字列でチェックしている（`CliExecutor.execute`）。
- `prompts.py` の `build_input()` が「1ステップ＝1フレッシュコンテキスト」の起点。呼び出しごとに `previous_response_id` は使わず、developer prompt + 残りステップ + 現在のsnapshot からゼロで組み立てる。ステップ内の複数ターンは `step_runner.run_step()` がこの `input_items` リストにローカルで追記して繋ぐ（＝ステップを跨いだ記憶は持たないが、ステップ内はチェーンする）。
- `tools.py` の `TOOL_SCHEMAS` が OpenAI Responses API に渡すツール定義一式。`finish_step` はCLIコマンドではなくループ制御用の合図で、**他の操作系ツールと同じターンで一緒に呼んではいけない**契約（呼ばれた場合 `step_runner.run_step()` は同時に来た操作呼び出しを無視してログに warning を出す）。操作系ツールは `ref`（snapshotに載っているものだけ）でしか要素を指定できない。`add_expectation`（`ref`/`matcher`(`toBeVisible`|`toHaveText`)/`description`）も他の操作系ツールと同じ扱いの読み取り専用ツールで、確認のみのステップで使う。AIには`eval`スクリプトやロケータ文字列そのものを書かせず、`cli_executor.generate_locator`/`eval_raw`（`--raw`付きのCLI呼び出し）でこちら側が安定ロケータ・期待テキストを取得し、`await expect(page.<locator>).<matcher>(...)` 相当のTypeScript文を組み立てて返す（`tools._add_expectation`）。
- `step_runner.py` の `run_step()` が1ステップ分のマルチターン tool-calling ループ本体（前段落2つの実体）。ターンごとに `step_log.append_step_log()` を呼んで生ログを`<out>.steps.jsonl` に追記する。
- `runner.py` の `run_vertical_slice()` がストーリー全体のオーケストレーション（seed_url を開く → 各ステップで `step_runner.run_step()` を呼ぶ → 生成物を書き出す）と、生成物の書き出し（`write_spec_file` / `write_failure_notes`）・`npx playwright test` の実行（`run_playwright_test`）を担う。`run_steps()`（ストーリーのステップ列を先頭から実行して`StepBlock`/`failure_notes`を積む）・`run_task_logged_step()`（1ステップ分を`step_runner.run_step()`に委ねつつ前後のタスクログを取る）・`write_and_test()`（`.spec.ts`書き出し〜`npx playwright test`実行）は`run_vertical_slice`/`resume_vertical_slice`（後述）双方、および`scripts/server/orchestrator.py`の`run_story`/`resume_story`からも共有で呼ばれる（[[session-server]]参照）。
- `step_log.py` が `<out>.steps.jsonl` の直列化・追記ロジック（`serialize_output_item` / `truncate` / `append_step_log`）を持つ。診断ログのフォーマットに関する責務はここに閉じる。`step_runner.run_step()`がターンごとに書き込む`model`フィールドは（Step5で）リクエスト文字列ではなくAPIレスポンスが実際にエコーバックした`response.model`に変更した。リクエスト時に指定した文字列は`requested_model`として別途残る（`cost_summary.py`のpricing lookupは`model`優先のまま変更不要）。
- `task_log.py` が `<out>.tasks.jsonl`（タスク＝ステップ単位の記録）の直列化・読み込み・リプレイ用コード列の組み立てを持つ。`step_log.py`との責務分担: `.steps.jsonl`はAIターン単位の生ログ、`.tasks.jsonl`はタスク単位で完結した「実行前後のsnapshot/screenshot・そのタスクで生成されたコード列・成否」のみを持つ（`task_log_path` / `append_task_log` / `load_task_log` / `build_replay_source` / `recordings_dir`）。screenshotの保存先は`recordings_dir(out_path)`（`{stem}.recordings/`、例: `tests/generated/search-demo.recordings/3-before.png`）。
- `main.py` は argparse と各コンポーネントの配線（`CliExecutor` / `OpenAI` client / `load_story`）だけを行うCLIエントリポイント。実行ロジックは持たない。`--resume-tasks-log`/`--resume-before-step`を指定すると`run_vertical_slice`の代わりに`runner.resume_vertical_slice`を呼ぶ。

### 記録と途中再開・分岐（Step5）

- 復元方式は「記録済みの操作コード列を先頭から`playwright-cli run-code`で再実行する」。`state-save`/`state-load`（cookie/localStorageのみ復元、ナビゲーション履歴・DOM状態は復元不可）は使わない。`cli_executor.CliExecutor`に`screenshot(path) -> str`（`--filename=`は**呼び出し元プロセスのcwd基準**で解決され、親ディレクトリが無いとENOENTになるため`screenshot()`側で`mkdir(parents=True)`する）と`run_code(source) -> ActionResult`（`execute("run-code", [source])`）を追加した。
- `run_code`は新しいセッションで`cli.open()`（URL無し、ブランクページを開くだけ）を呼んだ後でないと使えない（未openだと`playwright-cli`がエラーを返す）。`build_replay_source`が組み立てる`"async page => { ... }"`文字列には`await expect(...)`行を含めない（`run-code`のサンドボックスに`expect`は無い）。除外は早送り用の一時文字列のみに適用し、`.spec.ts`用の`prior_blocks`（`runner.build_resume_state`が組み立てる）にはassertion込みの元コードをそのまま使う。
- `runner.resume_vertical_slice(story, cli, client, model, out_path, tasks_log_path, resume_before_step)`が復元の実体。`build_resume_state()`で`tasks_log_path`から`replay_source`（早送り用）と`prior_blocks`（`.spec.ts`用、`step_id`が`None`または`resume_before_step`未満のタスクをそのまま`StepBlock`化したもの）を組み立て、`cli.open()` + `cli.run_code(replay_source)`で早送りしたのち、`story.steps`を（`resume_before_step`によるフィルタなしで）先頭から通常のAIループで実行する。**`story`は`tasks_log_path`を生成した元のストーリーと別のYAMLでもよい** — 「タスク3までは記録から復元し、タスク4以降を別の入力で実行する」という分岐実行は、分岐先のステップだけを持つ別YAML（`scripts/stories/search-demo-branch.yaml`が例。ステップIDは元ストーリーと不連続でもよい）を`story`に渡すことで実現する。`scripts/server/orchestrator.py`の`resume_story`も同じ`build_resume_state`を呼ぶだけの薄いラッパー（[[session-server]]参照）。

### ステップ内ループの終了条件（`step_runner.run_step`）

`MAX_TURNS_PER_STEP = 8` の間、`finish_step` が呼ばれるまでターンを重ねる。以下のいずれかで即停止し `failure_notes` に理由が積まれる：`finish_step(status="blocked")` / モデルがツールを1つも呼ばない / CLI呼び出しが `CliError` を投げる / `MAX_TURNS_PER_STEP` 到達。これは**リトライ機構ではない**（リトライは Step6 の未実装スコープ、SPEC.md 6章）— 1ステップの応答時間に対する安全弁のみ。

### 生成物

- `<out>.spec.ts` — ステップ境界を保持した `runner.StepBlock` のリスト（`open()`分＋各ステップの生成コード）を1つの `test()` に組み立てて書き出し（`runner.write_spec_file`）。各ステップのコードの先頭には `// {step.id}. {step.instruction}` コメントが付く（test-generation.md 2.2節の規約。`open()`分にはステップ番号が無いのでコメントは付けない）。書き出し後 `npx playwright test` を自動実行する（`runner.run_playwright_test`）。
- `<out>.failure-notes.json` — 失敗があった場合のみ（`runner.write_failure_notes`)。
- `<out>.steps.jsonl` — 全ターンの生ログ（プロンプト・モデル出力・ツール結果）。停止理由を後から読み返すためのもので、書式は `step_log.py` 冒頭のモジュールdocstringに説明がある。
- `<out>.tasks.jsonl` — タスク（＝ステップ）単位の記録。1行1タスクで、実行前後のsnapshot・screenshotパス・そのタスクで生成されたコード列・成否を持つ（`task_log.py`）。途中再開・分岐実行のリプレイ元になる。
- `{stem}.recordings/` — `<out>.tasks.jsonl`が参照するscreenshot（`{step_id}-before.png`/`{step_id}-after.png`、seedブロックは`seed-after.png`のみ）の保存先。
