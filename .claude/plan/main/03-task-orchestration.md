# Step 3 詳細版: タスクオーケストレーションの自動化

> [big_plans/03-task-orchestration.md](../../../big_plans/03-task-orchestration.md) の詳細版。[00-overview.md](00-overview.md)参照。

## やること

- Step2（[02-server-skeleton.md](02-server-skeleton.md)）のセッションサーバーに、Step1（[01-vertical-slice.md](01-vertical-slice.md)）で実装済みの「1ステップ＝1フレッシュコンテキスト」AIループをそのまま載せる。新しいループ実装は書かない — `scripts/vertical_slice/step_runner.py`の`run_step()`、`runner.py`の`write_spec_file`/`write_failure_notes`/`run_playwright_test`、`prompts.py`/`tools.py`/`story.py`/`config.py`を`scripts/server/`からimportして再利用する。
- `POST /sessions/{session_id}/run` を新設する。呼ばれると、そのセッションに紐づく（`POST /sessions`時に受け取った）ストーリーの全ステップを、人間の介入なしに最初から最後まで自動実行し、完了後に生成物（`.spec.ts`等）を書き出して`npx playwright test`まで走らせ、結果を返す。
- タスク（＝ステップ）の完了判定は新設せず、Step1の`finish_step`設計（AI自身がステップ完了/blockedを宣言し、`step_runner.run_step`がそれをループの停止条件として扱う）をそのまま踏襲する。「サーバー側でチェックポイントと突き合わせる」方式は採用しない。
- `POST /sessions`の`story`フィールド（Step2では「受け取って保存するだけで解釈しない」契約だった文字列）を、このステップで初めて解釈する。**ストーリーYAMLファイルへのパス**として扱い、`story.load_story()`にそのまま渡す（インラインYAMLテキストのような新しいフォーマットは発明しない）。
- ループ全体は`/run`のHTTPリクエスト内で同期的に（ブロッキングで）最後まで実行する。進捗のストリーミング配信や召来の中断は作らない（Step7のスコープ）。

## 読むべきファイル・実行推奨Grep

**再利用する既存実装を確認するため（優先度: 高）**
- 読む: `scripts/vertical_slice/step_runner.py`の`run_step()` — 1ステップ分のマルチターンループ本体。シグネチャは`(cli, client, model, step, remaining_steps, out_path)`で、`CliExecutor`を直接受け取る点に注意（HTTP越しではなく同一プロセス内呼び出し）
- 読む: `scripts/vertical_slice/runner.py`の`run_vertical_slice()` — **このステップでは`run_vertical_slice()`自体はimportしない**。冒頭で`cli.open(story.seed_url)`を呼んでおり、サーバー側では`POST /sessions`が既に`target_url`で`cli.open()`済みのため二重navigationになる。代わりに、同ファイル内の`write_spec_file`/`write_failure_notes`/`run_playwright_test`（`run_vertical_slice`から独立した関数）と、ステップをループして`run_step`を呼ぶ部分だけを新しいモジュールで組み立て直す
- 読む: `scripts/vertical_slice/story.py`の`load_story()` — YAMLファイルパスを受け取り`Story`/`Step`を返す。この関数のシグネチャ・挙動を変更せずそのまま使う
- 読む: `scripts/vertical_slice/config.py` — `get_api_key()`/`get_model()`/`get_base_url()`。サーバー側でも同じ関数をそのまま使い、設定の重複実装をしない

**Step2の現状を確認するため（優先度: 高）**
- 読む: `scripts/server/session_manager.py` — 現状`_stories: dict[str, str | None]`が生文字列を無解釈で保持しているだけ。ここを`Story | None`を保持するように変更する
- 読む: `scripts/server/app.py` — `start_session`が`body.story`を`sessions.create()`に渡している箇所、`_get_cli`のエラーハンドリングパターン（`SessionNotFoundError` → 404）をそのまま`/run`にも踏襲する
- 読む: `scripts/server/schemas.py` — 既存のRequest/Responseモデルの書き方（フィールド名・型ヒントの流儀）に合わせて`RunResponse`を追加する

**規約・落とし穴を確認するため（優先度: 中）**
- 読む: `.claude/rules/vertical-slice-runner.md` — `finish_step`の契約（他の操作系ツールと同じターンで呼んではいけない）、`MAX_TURNS_PER_STEP=8`が安全弁でありリトライ機構ではない点。サーバー化しても挙動は変えない
- 読む: `scripts/vertical_slice/main.py` — `load_dotenv()`を呼んでから`OPENAI_API_KEY`を読んでいる。`scripts/server/main.py`は現状これを呼んでいないため、`.env`経由のAPIキーがサーバー起動時に読まれない落とし穴がある
- 読む: `scripts/temp/test_server.py` — Step2の疎通確認スクリプト。`story`に`"custom search demo"`という自由文字列を渡している箇所があるが、これはStep2時点の暫定値であり、Step3以降は実在するYAMLファイルパスに書き換える必要がある（このステップの完了条件の一部としてこのスクリプトを更新するか、専用の確認スクリプトを別途置くかは実装時に判断してよい）

## 触るファイル

### 新規
- `scripts/server/orchestrator.py` — `run_story(cli, client, model, story, out_path)`のようなエントリポイントを持つ。`story.steps`を順にループして`step_runner.run_step()`を呼び、失敗があれば打ち切り、最後に`runner.write_spec_file`/`write_failure_notes`/`run_playwright_test`を呼ぶ（`runner.run_vertical_slice()`の「`cli.open()`を除いた後半部分」に相当する処理をここに書く）

### 変更
- `scripts/server/schemas.py` — `RunResponse`（`passed: bool` / `spec_path: str` / `failure_notes: list[dict]`程度）を追加
- `scripts/server/app.py` — `POST /sessions/{session_id}/run`を追加。OpenAIクライアントは遅延初期化（後述の決定事項）にする
- `scripts/server/session_manager.py` — `story`を保存時に`load_story()`でパースし、`Story | None`として保持する（`StartSessionRequest.story: str`という外部契約自体は変えない）
- `scripts/server/main.py` — 先頭で`load_dotenv()`を呼ぶよう追加（`.env`の`OPENAI_API_KEY`をサーバー起動時に読めるようにする）

## 決定事項・注意点／落とし穴

| 決定 | 理由 |
|---|---|
| `run_vertical_slice()`をそのまま呼ばず、`orchestrator.py`に「`cli.open()`を含まない」バージョンを新規に組み立てる | `run_vertical_slice()`は`story.seed_url`へ毎回navigationする前提で書かれているが、サーバーでは`POST /sessions`の`target_url`で既にnavigation済み。二重に開くとStep2の`target_url`とStep3の`story.seed_url`のどちらが真の遷移先か曖昧になる。`run_step`・`write_spec_file`等の個別関数は変更せず再利用し、ループの組み立てだけをサーバー側に持つ |
| `story`フィールドはYAMLファイルパスとして解釈する（インラインYAML文字列は扱わない） | `story.load_story()`が既にファイルパスを引数に取る設計であり、新しいパース方式を発明せずそのまま使えるため。呼び出し側（人間・将来のクライアント）は`scripts/stories/*.yaml`のパスを渡す運用にする |
| `story.seed_url`（YAML内）はサーバー経由の実行では使わない（無視する） | `target_url`が既にnavigationを担っているため。`Story.seed_url`と`target_url`が食い違っていても検証はしない（このステップのスコープでは呼び出し側の責任とする） |
| `/run`はHTTPリクエスト内で同期的に最後まで実行し、進捗のポーリング/ストリーミング用エンドポイントは作らない | Step3の完了条件は「サーバー主導で最初から最後まで実行できる」ことのみ。進捗の可視化・強制停止はStep7（[07-human-observation-and-control.md](07-human-observation-and-control.md)）のスコープであり、ここで先取りしない |
| OpenAIクライアントは`app.py`のモジュールトップレベルでは生成せず、`/run`ハンドラ内（または遅延初期化されたシングルトン）で生成する | `config.get_api_key()`は`OPENAI_API_KEY`未設定だと例外を投げる。トップレベルで生成すると、AIを使わないStep2既存エンドポイント（`/snapshot`や`/command`）までAPIキー無しでは起動できなくなってしまう |
| `/run`は実AI APIへの課金コールを伴う。人間が直接叩く分には確認不要だが、動作確認としてこのエンドポイントをスクリプトから叩く場合は`vertical-slice-ai-test`スキルと同様「実行前にユーザーへ確認」の方針を踏襲する | [.claude/rules/architecture.md](../../rules/architecture.md)の既存方針（実課金APIコールは事前確認）と矛盾させないため |
| タスク完了判定はStep1の`finish_step`宣言方式をそのまま使い、サーバー側で独自のチェックポイント突き合わせロジックは作らない | big_plans/03-task-orchestration.mdが判断を委ねている論点だが、Step1で既に動作確認済みの設計を流用する方が、新規ロジックのリスクを増やさずStep3の完了条件（人間の介入なしの完走）を満たせるため |
| 生成物の出力パス（`out_path`）は`story.name`ベース（`tests/generated/{story.name}.spec.ts`）とし、`session_id`は使わない | vertical_sliceの既存命名慣習（`--out`のデフォルトが`search-demo.spec.ts`）に揃え、生成ファイル名を人間が読める状態に保つため。同じストーリーを複数セッションで並行実行すると出力ファイルが競合するが、Step2で既に「並行アクセスの安全性はこの段階では扱わない」と決めており、Step3もそれを踏襲する |

## `.claude/rules` 更新ポイント

- `.claude/rules/vertical-slice-runner.md`のフロントマター（`paths:`）は`scripts/vertical_slice/**`等に閉じており、`scripts/server/**`を含まない。このステップで`scripts/server/orchestrator.py`が`step_runner`/`runner`/`prompts`/`tools`/`story`/`config`を再利用する構成が固まった段階で、以下のいずれかを実装時に判断する。
  - (a) `.claude/rules/vertical-slice-runner.md`の`paths:`に`scripts/server/orchestrator.py`を追加し、本文に「サーバーからの再利用のされ方」を1〜2行追記する
  - (b) `scripts/server/`用の新規ルールファイル（`.claude/rules/session-server.md`、`paths: ["scripts/server/**"]`）を作り、Step2骨組み分＋Step3オーケストレーション分をまとめて記載する（Step2完了時点ではまだ新規ルールを作らないと決めていたが、Step3でサーバー側の構成要素が増えるため再検討のタイミングとして妥当）
  - 実装時の状況（サーバー側コードの増え方）を見て(a)/(b)いずれかを選び、`writing-rules`スキルのフォーマットに従って書く
