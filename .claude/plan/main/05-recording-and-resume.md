# Step 5 詳細版: 記録と途中再開

> [big_plans/05-recording-and-resume.md](../../../big_plans/05-recording-and-resume.md) の詳細版。[00-overview.md](00-overview.md)参照。

## やること

- 各タスク（＝ステップ、architecture.md「1タスク＝1ステップ」）の実行境界ごとに、新規の`<out>.tasks.jsonl`へ1行1タスクの記録を追記する。記録内容は実行前後のsnapshot・screenshot・そのタスクで生成されたコード列・成否。既存の`<out>.steps.jsonl`（ターン単位のAI生ログ、Step1実装済み）とは責務を分離し、リプレイに必要な情報だけを別ファイルに持つ。
- 記録からの復元は「`state-save`/`state-load`によるcookie/localStorage復元」ではなく、「記録済みの操作コード列を先頭から`playwright-cli run-code`で再実行する」方式を採る（理由は下記決定事項）。新しいCliExecutorセッション（＝新しいブラウザ）に対し、`<out>.tasks.jsonl`のうち指定タスク番号より前の分の`code`を連結して1回の`run-code`で流し込み、ブラウザ状態をそのタスク開始時点まで早送りしてから、以降のタスクを通常のAIループで実行する。
- 「途中のタスクから再実行する」「別パターンのテストへ分岐する」（README概要の要件）を実際に試す。分岐先は別のStory YAMLとして用意し、`--story`（CLI）/`story`（サーバー）にそのYAMLを渡すことで「タスク3までは記録から復元し、タスク4以降を別の入力で実行する」を再現する。
- CLI（`scripts/vertical_slice/main.py`）とサーバー（`scripts/server/app.py`）の両方に復元エントリを生やす。実体のロジック（リプレイ用コード列の組み立て、`prior_blocks`を先頭に積んだ`write_spec_file`呼び出し）は`runner.py`に1箇所実装し、`orchestrator.py`はStep3〜4と同じパターンでそのまま再利用する。

## 読むべきファイル・実行推奨Grep

**記録を追加する既存のステップループを確認するため（優先度: 高）**
- 読む: `scripts/vertical_slice/runner.py` の `run_vertical_slice` / `StepBlock` / `write_spec_file` — タスク記録・screenshot取得を挿入するステップループの現在の形。`StepBlock`は`step`と`code`しか持たないため、リプレイに使う`prior_blocks`をここにどう積むかが実装の中心になる
- 読む: `scripts/server/orchestrator.py` の `run_story` — `runner.py`と全く同じステップループ構造（`generated_code`ではなく`blocks`へ`StepBlock`を積む形はStep4で既に統一済み）。記録追加・resume分の変更を同じ形で追随させる
- 読む: `scripts/vertical_slice/step_runner.py` の `run_step` — **このループのターン制御ロジックには手を入れない**（Step4の決定を踏襲）。before/after のsnapshot・screenshotは`run_step`の外側（呼び出し元のステップループ）で追加のCLI呼び出しとして取得する
- 読む: `scripts/vertical_slice/step_log.py` — `<out>.steps.jsonl`の書き込みパターン（`append_step_log`/`truncate`/パスの決め方）。新設する`task_log.py`はこのファイルの構造をほぼそのまま`.tasks.jsonl`向けに複製できる

**CliExecutorへの追加メソッドの実装作法を確認するため（優先度: 高）**
- 読む: `scripts/vertical_slice/cli_executor.py` の `CliExecutor.execute` / `generate_locator` / `eval_raw` — 新設する`screenshot`/`run_code`もこの薄いラッパーの作法（`_run`を呼び、`execute`経由なら`### Error`検知はタダで付いてくる）に合わせる
- 読む: [SKILL.md](../../skills/playwright-cli/SKILL.md) の「Save as」節（`screenshot --filename=`） — 相対パスの解決先（呼び出し元CWD基準かplaywright-cliデーモン基準か）が明記されていないため、実装時に`playwright-cli screenshot --help`と実際の保存先を確認すること（Step4の`--raw`位置確認と同じ要領）
- 読む: [running-code.md](../../skills/playwright-cli/references/running-code.md) — `run-code`は`async page => { ... }`という関数式を丸ごと1つの引数として渡す（import/export不可、`page`のみが注入される）。渡す文字列に`expect`は存在しない点に注意
- 読む: [storage-state.md](../../skills/playwright-cli/references/storage-state.md) — `state-save`/`state-load`が保存するのはcookie・localStorage・sessionStorageのみで、ナビゲーション履歴やDOM状態は含まれないことの裏取り（下記決定事項の根拠）

**サーバー側の配線を確認するため（優先度: 中）**
- 読む: `scripts/server/app.py` の `start_session` / `run_session` / `_get_cli` — 新設する`resume`エンドポイントの位置づけ（`POST /sessions`と`POST /sessions/{id}/run`を1本化した形に近い）
- 読む: `scripts/server/session_manager.py` の `SessionManager.create` — `story`だけ渡して`cli.open()`を呼ばない使い方が既にできる（`create()`自体はnavigationしない。navigationは`app.py`の`start_session`が別途呼んでいる）ため、resume用に新しいメソッドを増やす必要はない
- 読む: `scripts/server/schemas.py` — 既存リクエスト/レスポンスのpydanticモデルの書き方
- 読む: `.gitignore` の`tests/generated/*.spec.ts`等のパターン — 新設するtask log・screenshotディレクトリも同じ扱いで追加する

## 触るファイル

### 新規
- `scripts/vertical_slice/task_log.py` — `<out>.tasks.jsonl`のシリアライズ・読み込み・リプレイ用コード列の組み立てを担う。主な関数:
  - `append_task_log(entry, out_path)` / `task_log_path(out_path)` — `step_log.py`と同型
  - `load_task_log(path) -> list[dict]`
  - `build_replay_source(entries, before_step) -> str` — `step_id`が`None`（seedブロック）または`before_step`未満のエントリの`code`を連結し、`await expect(`で始まる行を除外したうえで`"async page => {\n...\n}"`形式の1文字列を組み立てる（`CliExecutor.run_code`にそのまま渡せる形）
- 動作確認用の分岐ストーリー（例: `scripts/stories/search-demo-branch.yaml`）— 完了条件の「タスク3まで復元、タスク4以降を別入力」を実際に試すためのサンプル。既存`search-demo.yaml`の後半ステップを差し替えたもの

### 変更
- `scripts/vertical_slice/cli_executor.py` — `CliExecutor`に`screenshot(path: str) -> str`（`execute("screenshot", [f"--filename={path}"])`を呼び、pathをそのまま返す）と`run_code(source: str) -> ActionResult`（`execute("run-code", [source])`）を追加
- `scripts/vertical_slice/runner.py`
  - `run_vertical_slice`のステップループに、`run_step`呼び出しの前後で`cli.snapshot_text()`/`cli.screenshot(...)`を取得し`task_log.append_task_log(...)`を呼ぶ処理を追加。seedブロック（`cli.open(story.seed_url)`直後）にも同様にタスクログエントリ（`step_id: null`）を1件追加する
  - 新規関数`resume_vertical_slice(story, cli, client, model, out_path, tasks_log_path, resume_before_step)`を追加。`task_log.load_task_log`→`build_replay_source`→`cli.run_code(...)`でブラウザ状態を早送りしたのち、リプレイ済みエントリをそのまま`prior_blocks: list[StepBlock]`（assertion込みの元の`code`）へ変換して`blocks`の先頭に積み、以降は`run_vertical_slice`と同じステップループ（`story.steps`を先頭から実行）に合流させる。`write_spec_file`は`prior_blocks + 新規blocks`をまとめて1回呼ぶ
- `scripts/server/orchestrator.py` — `run_story`に同様のtask log・screenshot記録を追加。新規`resume_story(cli, client, model, story, out_path, tasks_log_path, resume_before_step)`を追加し、`runner.resume_vertical_slice`のリプレイ部分（`task_log`まわり）を共有ロジックとして呼び出す
- `scripts/server/app.py` — `POST /sessions/resume`エンドポイントを追加。`sessions.create(session_id, story=body.story)`で（navigationなしの）新セッションを作り、`orchestrator.resume_story(...)`を呼んで結果を返す。`start_session`と`run_session`を1本化した形（Step3の`/run`が同期実行である方針をそのまま踏襲、進捗ストリーミングは追加しない）
- `scripts/server/schemas.py` — `ResumeRequest`（`tasks_log: str`, `resume_before_step: int`, `story: str`）/`ResumeResponse`（`session_id: str`, `passed: bool`, `spec_path: str`, `failure_notes: list[dict]`）を追加
- `scripts/vertical_slice/main.py` — `--resume-tasks-log`/`--resume-before-step`のoptional引数を追加し、指定時は`run_vertical_slice`ではなく`runner.resume_vertical_slice`を呼ぶよう分岐
- `.gitignore` — `tests/generated/*.tasks.jsonl`と`tests/generated/*.recordings/`を追加（既存の`*.spec.ts`/`*.steps.jsonl`パターンと同列の生成物）

## 決定事項・注意点／落とし穴

| 決定 | 理由 |
|---|---|
| 復元方式は「記録済みの操作コード列を先頭から`run-code`で再実行する」を採用し、`state-save`/`state-load`は使わない | `state-save`/`state-load`が復元できるのはcookie・localStorage・sessionStorageのみで、ナビゲーション履歴やDOM状態（複数ページを跨ぐシナリオの「今どのページにいるか」）は復元できない（storage-state.md参照）。一方、各タスクの生成コード（`StepBlock.code`）は既にStep1〜4で「操作の記録」として確立されており、そのまま`run-code`に流し込めば同じ操作を再実行できる。二重の記録機構を持たずに済む |
| タスク単位の記録は新規`<out>.tasks.jsonl`に分離し、既存の`<out>.steps.jsonl`とは別ファイルにする | `.steps.jsonl`はAIターン単位の生ログで、リプレイに必要な「タスク単位で完結したコード列」を再構成するには余計なパースが要る。責務を分けることで`step_log.py`の既存フォーマット（診断ログ）を変更せずに済む |
| リプレイ用の文字列を組み立てる際、`add_expectation`が生成した`await expect(...)`行を除外する。最終成果物（`.spec.ts`）の組み立て（`prior_blocks`）では元のコード（assertion込み）をそのまま使う | `run-code`は`async page => { ... }`という関数スコープのみで実行され、`page`しか注入されない（`expect`は未定義でReferenceErrorになる）。assertionはブラウザの状態を変えない読み取り専用の呼び出しなので、早送り目的のリプレイでは省いても状態に影響しない。除外はリプレイ用の一時文字列にのみ適用し、`.spec.ts`用の`prior_blocks`には影響させない |
| before/afterのsnapshot・screenshotは`run_step`の内部では取得せず、呼び出し側（`run_vertical_slice`/`run_story`のステップループ）で追加のCLI呼び出しとして取得する | Step4の決定「`step_runner.run_step`のターン制御ロジックには手を入れない」を踏襲し、記録機能の追加で安定した既存ループを壊すリスクを避ける。追加のCLI往復コスト（1タスクにつきsnapshot/screenshot各2回）は許容する |
| screenshotの保存先は`<out>`と同階層の`{stem}.recordings/`ディレクトリ（例: `tests/generated/search-demo.recordings/3-before.png`）とし、`.gitignore`に追加する | 既存の`.spec.ts`/`.steps.jsonl`と同様に生成物であり、バイナリをコミットする理由がない。命名規則も既存の`tests/generated/*.steps.jsonl`パターンに揃える |
| resumeは常に新しいCliExecutorセッション（新しいブラウザ）を作る前提とし、元セッションが生きていることを要求しない | big_plans完了条件「記録されたログだけを使って、途中のタスクからテストを再開できることを確認する」を文字通り満たすため。サーバー・CLIどちらもプロセス再起動後の復元がユースケースの中心であり、元ブラウザの生存を前提にすると要件を満たせない |
| 分岐先ステップ（別パターンへの分岐）は別のStory YAMLとして用意し、`resume`系エントリの`story`引数にそのまま渡す。ステップIDの連番が元のストーリーと重複・不連続でも構わない | `write_spec_file`は各`StepBlock`の`step.id`をそのままコメントに出すだけで、番号の連続性を前提にしたロジックは無い。分岐先ストーリーを独立したYAMLとして管理する方が、既存`Story`/`Step`データモデルに変更を加えずに済む |
| resumeの実体ロジック（リプレイ・`prior_blocks`組み立て）は`runner.py`に1箇所実装し、`orchestrator.py`はそれを再利用するだけに留める | Step1→Step3で確立した「新しいAIループを書かず、`runner.py`/`step_runner.py`をサーバー側がそのまま再利用する」というパターンをresumeでも踏襲するため |
| `screenshot`の相対パス解決先（呼び出し元CWD基準かplaywright-cliデーモン基準か）は未確認 | SKILL.mdに明記が無い。実装時に`playwright-cli screenshot --help`と実機確認が必要（Step4で`--raw`の位置を実機確認したのと同じ要領）。解決先次第では`CliExecutor.screenshot`が絶対パスへ変換する処理を挟む可能性がある |

## `.claude/rules` 更新ポイント

- `.claude/rules/vertical-slice-runner.md`（既存ファイルへの追記。対象パスに変更は無いのでフロントマター変更は不要）
  - 「生成物」節に`<out>.tasks.jsonl`（タスク単位の記録: snapshot/screenshot/生成コード/成否）と`{stem}.recordings/`（screenshot保存先）を追記
  - `task_log.py`の役割（`step_log.py`との責務分担）、`runner.resume_vertical_slice`によるリプレイ復元の仕組みを追記
- `.claude/rules/session-server.md`（既存ファイルへの追記。対象パスに変更は無い）
  - `POST /sessions/resume`エンドポイントの説明（`orchestrator.resume_story`を呼ぶ、navigationなしの新セッションを作る点）を追記
