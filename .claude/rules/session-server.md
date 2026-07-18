---
paths:
  - "scripts/server/**"
---

## セッションサーバー（scripts/server）

SPEC.mdの「ブラウザセッションは永続、AIコンテキストはステップごとに初期化」を担うFastAPIサーバー。Step2（骨組み・人間駆動のsnapshot/command）とStep3（`/run`によるAI駆動の全自動実行）の実装が同居する。責務は[.claude/plan/main/02-server-skeleton.md](../plan/main/02-server-skeleton.md)・[.claude/plan/main/03-task-orchestration.md](../plan/main/03-task-orchestration.md)に詳しい。

- `session_manager.py` の `SessionManager` が `session_id -> CliExecutor` のin-memoryレジストリ。`session_id` はplaywright-cliの `-s=` セッション名そのもの。`POST /sessions`で受け取る`story`は**ストーリーYAMLファイルへのパス**として`create()`内で即座に`story.load_story()`によりパースされ、`Story | None`として保持される（`StartSessionRequest.story: str`という外部契約自体は生文字列のまま）。並行アクセスの安全性は未対応（ロックなし）。
- `app.py` が4+1本のHTTPエンドポイントを持つ。`/snapshot`・`/command`はStep2由来で人間が直接叩く想定、`/run`はStep3で追加した自動実行エンドポイント。OpenAIクライアントは`_get_client()`でモジュール内シングルトンとして遅延初期化する（`config.get_api_key()`が`OPENAI_API_KEY`未設定で例外を投げるため、トップレベル生成するとAI不要な既存エンドポイントまで起動不能になる）。
- `orchestrator.py` の `run_story(cli, client, model, story, out_path)` が`/run`の実体。**新しいAIループは書いていない** — `scripts/vertical_slice/step_runner.run_step`をステップごとに呼び、`scripts/vertical_slice/runner.write_spec_file`/`write_failure_notes`/`run_playwright_test`をそのまま再利用している。`runner.run_vertical_slice()`自体は使わない（`story.seed_url`へ毎回navigationする前提のため。サーバーでは`POST /sessions`の`target_url`で既にnavigation済みなので二重navigationを避けている）。タスク（＝ステップ）の完了判定もStep1の`finish_step`宣言方式をそのまま踏襲し、サーバー側で独自のチェックポイント判定は行わない。
- `/run`はHTTPリクエスト内で同期的に最後まで実行する。進捗のストリーミング配信や途中中断のAPIは無い（Step7スコープ）。生成物の出力パスは`story.name`ベース（`tests/generated/{story.name}.spec.ts`）で、`session_id`は使わない。同じストーリーを複数セッションで並行実行すると出力ファイルが競合するが、これも未対応。
- `main.py`は起動時に`load_dotenv()`を呼ぶ（`.env`の`OPENAI_API_KEY`を`/run`のOpenAIクライアントが読めるようにするため）。
- `/run`は実AI APIへの課金コールを伴う。人間が直接叩く分には確認不要だが、動作確認としてこのエンドポイントをスクリプトから叩く場合は[[vertical-slice-runner]]や`vertical-slice-ai-test`スキルと同様「実行前にユーザーへ確認」の方針を踏襲する（[architecture.md](architecture.md)参照）。
