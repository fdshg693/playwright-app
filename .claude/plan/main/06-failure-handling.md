# Step 6 詳細版: 失敗時のふるまい

> [big_plans/06-failure-handling.md](../../../big_plans/06-failure-handling.md) の詳細版。[00-overview.md](00-overview.md)参照。

## やること

- タスク（＝ステップ）が失敗した場合、`step_runner.run_step()` をもう一度フレッシュな呼び出しとして呼び直す形でリトライする。ターン制御ループ（`MAX_TURNS_PER_STEP`）自体には手を入れない（Step4/5の決定を踏襲。ヘッダコメント「MAX_TURNS_PER_STEPはリトライ機構ではない」の通り、リトライは本ステップで初めて実装する別レイヤー）。
- リトライ回数の上限を `MAX_STEP_ATTEMPTS = 3`（初回1回＋リトライ2回）という小さい固定値で導入する（SPEC.md 9章のOpen Question。big_plans記載の「まずは小さい値から始める」方針通り、CLI引数・環境変数化はせず`MAX_TURNS_PER_STEP`と同じ「モジュール定数」の扱いに揃える。運用しながら調整する前提を保つ）。
- リトライは`runner.run_task_logged_step()`の内部に閉じ込める。同じステップに対する複数回の試行があっても、`<out>.tasks.jsonl`には**1ステップ＝1エントリ**という既存の不変条件（Step5）を保ったまま、`code`フィールドに全試行分の生成コードを試行順に連結して持たせる（各試行の操作は実際に同じブラウザセッションに対して行われているため）。これにより`task_log.build_replay_source`/`runner.build_resume_state`（`step_id`でエントリを1件引き当てる前提）は無改造で動く。
- 最終（`MAX_STEP_ATTEMPTS`回目）の試行も失敗した場合にだけ、`playwright-cli console`/`requests`を1回ずつ追加で叩き、その時点のsnapshot/screenshot（task_log用に元々取得している`after_snapshot`/`after_screenshot`と同じ値を再利用、CLI呼び出しの追加なし）とあわせて`failure_notes`のエントリに`diagnostics`として埋め込む。リトライの途中（1〜2回目の失敗）ではconsole/requestsは取得しない。
- 「失敗の推定原因」は新たにAIへ判断させず、既存の`failure_notes`の`reason`（`cli_error`/`blocked`/`no_tool_call`/`max_turns_exceeded`）を機械的な説明文にマッピングした`hint`をサーバー側で付与するだけに留める。「仕様が古いのかアプリ側の回帰バグか」という判断はしない（heal.md 3.4節・SPEC.md 6章の思想通り、事実の整理のみ）。
- 動作確認は新規YAMLを作らず、既存の`scripts/stories/edge-*-demo.yaml`（5本、いずれも「Step6着手前のベースライン記録として」用意済み）を使う。実AI APIコールが必要なため、このプラン段階では実行せず、確認観点のみ明記する（後述）。

## 読むべきファイル・実行推奨Grep

**リトライを差し込む既存ループを確認するため（優先度: 高）**
- 読む: `scripts/vertical_slice/runner.py` の `run_task_logged_step()` / `run_steps()` / `StepBlock` — 現状「`run_step`を1回呼ぶ→`task_log.append_task_log`を1回呼ぶ」という1:1の対応になっている箇所。ここにリトライループを差し込む。`run_steps()`は`step_failures`が非空なら即break する既存ロジックを変えない（＝リトライ後もなお失敗した場合だけ`step_failures`を非空で返す、という契約を守る必要がある）
- 読む: `scripts/vertical_slice/step_runner.py` の `run_step()` と冒頭のモジュールdocstring・`MAX_TURNS_PER_STEP`のコメント — 「リトライはStep6スコープ」と明記されている箇所。ターン制御ループ本体（`for turn in range(...)`）には触れず、ログ用に`attempt`番号を1パラメータとして通すだけに留める
- 読む: `scripts/vertical_slice/task_log.py` の `append_task_log()` / `load_task_log()` / `build_replay_source()` — 「1エントリ=1タスク(=1ステップ)」という前提がどこで使われているか（`build_replay_source`が`step_id`だけを見て連結している点、`runner.build_resume_state`が`step_id`でエントリをフィルタしている点）。この前提を崩さないことが今回最大の制約

**診断情報コマンドの実装作法を確認するため（優先度: 高）**
- 読む: `scripts/vertical_slice/cli_executor.py` の `CliExecutor.execute()` / `generate_locator()` / `eval_raw()` — `--raw`付きコマンドをどう薄くラップするかの既存パターン
- 実行確認: `playwright-cli console --help` / `playwright-cli requests --help` / `playwright-cli --help`（Global options節）。実機で`playwright-cli -s=<session> console --raw`・`playwright-cli -s=<session> requests --raw`を試した結果、両コマンドとも`--raw`は`### Result`ヘッダを取り除くだけで、本文（`Total messages: ...`やメッセージ一覧、リクエスト一覧）は`execute()`の既存ロジック（`### Error`検知→`_CODE_BLOCK_RE`で該当なしなら`generated_code=None`）にそのまま乗る。`generate-locator`/`eval`のような専用の生文字列パース（`eval_raw`相当）は不要で、`execute("console", ["--raw"]).raw_output.strip()`で足りることを確認済み
- 読む: [test-generation.md](../../skills/playwright-cli/references/test-generation.md) 3.2節（診断コマンド例: `snapshot`/`console`/`requests`）・3.4節（「仕様が古いか回帰バグかは判断せず人間に確認する」思想）— 今回の`hint`が「判断」ではなく「reasonの説明」に留まるべき根拠

**既存4エントリポイントへの影響範囲を確認するため（優先度: 中）**
- 読む: `scripts/server/orchestrator.py` の `run_story()` / `resume_story()` — いずれも`runner.run_steps()`を素通しで呼んでいるだけなので、リトライを`runner.run_task_logged_step()`内に閉じ込めれば`orchestrator.py`は無変更で済むことの裏取り
- 読む: `scripts/server/schemas.py` の `RunResponse.failure_notes: list[dict]` / `ResumeResponse.failure_notes: list[dict]` — 型が緩い`list[dict]`のため、`failure_notes`の各dictに`attempt`/`max_attempts`/`hint`/`diagnostics`キーを増やしてもpydanticスキーマの変更が不要なことの裏取り
- 読む: `scripts/server/app.py` の `/run`・`/sessions/resume` ハンドラ — 上記の裏取りが正しければ、このステップで`scripts/server/`配下は一切変更しない

**動作確認に使う既存fixtureの対応関係を確認するため（優先度: 中）**
- 読む: `scripts/stories/edge-disabled-button-demo.yaml`（想定reason: `cli_error`か`blocked`）/ `edge-range-input-demo.yaml`（想定reason: `cli_error`、`intent`に「"Malformed value"でCliErrorになることを確認する」と明記済み）/ `edge-unsupported-action-demo.yaml` / `edge-unsupported-drag-demo.yaml`（想定reason: いずれも`blocked`、tools.py未対応操作）/ `edge-ambiguous-locator-demo.yaml`（想定reason: `blocked`想定だが「誤ってどちらかを選ぶ」可能性も`intent`に記載されている）
- 読む: `.claude/skills/vertical-slice-ai-test/SKILL.md` — 実AI API実行前にユーザー確認が必要という既存方針。今回の確認作業（後述）もこの方針に従う

## 触るファイル

### 変更（新規ファイルはなし）

- `scripts/vertical_slice/step_runner.py` — `run_step()`に`attempt: int = 1`引数を追加し、`append_step_log`に渡すdictへ`"attempt": attempt`を1フィールド追加するだけ。ターン制御ループ本体（`MAX_TURNS_PER_STEP`まわり）は無変更
- `scripts/vertical_slice/runner.py`
  - `MAX_STEP_ATTEMPTS = 3`（`step_runner.MAX_TURNS_PER_STEP`と対になる新定数）と`FAILURE_REASON_HINTS: dict[str, str]`（`cli_error`/`blocked`/`no_tool_call`/`max_turns_exceeded`の4キー、reasonの機械的な説明文）を追加
  - `run_task_logged_step()` を「`run_step()`を`MAX_STEP_ATTEMPTS`回まで試行するループ」に変更する。before側のsnapshot/screenshot取得は初回試行前に1回だけ、after側は最終試行後に1回だけ（Step5と同じ回数のまま）。各試行の`step_code`は`all_code`へ順に連結。ある試行が失敗し、かつそれが最後の試行だった場合のみ、`cli.console()`/`cli.requests()`（`CliError`は握って`{"error": str(exc)}`として記録し、診断取得自体の失敗で処理全体を止めない）を呼び、その試行の`failure_notes`エントリへ`diagnostics`（`console`/`requests`/`snapshot`＝取得済みの`after_snapshot`/`screenshot_path`＝取得済みの`after_screenshot`）と`hint`（`FAILURE_REASON_HINTS[reason]`）、`attempt`/`max_attempts`を追加する。それ以外（最終試行より前の失敗）はリトライして次の試行へ進む。`task_log.append_task_log()`の呼び出しは変わらず1回だけで、渡すdictに`"attempts": <実際に行った試行数>`を追加する
- `scripts/vertical_slice/cli_executor.py` — `CliExecutor`に`console() -> str`（`execute("console", ["--raw"]).raw_output.strip()`）と`requests() -> str`（`execute("requests", ["--raw"]).raw_output.strip()`）を追加。**実AI呼び出しテストで判明した追加修正**: `snapshot_text()`が`snapshot --json`の`isError: true`形状（`### Error`テキストマーカーとは別の異常応答）を無条件で`["snapshot"]`アクセスしており、`edge-unsupported-action-demo.yaml`（ファイルアップロード欄クリック→file-chooserモーダル）で未捕捉の`KeyError`によりプロセスがクラッシュしていた（`.claude/plan/scenarios/05-failure-and-blocked-cases.md`のベースライン記録で既知）。`isError`時は`CliError`を投げるように変更し、他のCLIラッパーメソッドと同じ例外系に揃えた
- `scripts/vertical_slice/step_runner.py` — 上記`snapshot_text()`の`CliError`化に伴い、`run_step()`内の2箇所（ループ開始前の初回snapshot、各ターンのアクション実行後snapshot）を`try/except CliError`で囲み、他のCLIエラーと同じ`reason: "cli_error"`（`tool: "snapshot"`）として`failure_notes`に積んで`stop`する。ターン制御ループの条件分岐自体（`for turn in range(...)`、`finish_step`/`no_tool_call`判定）は変更しない
- `scripts/vertical_slice/runner.py`
  - `step_log.py`から`truncate`を追加importし、`diagnostics`へ埋め込む`console`/`requests`の文字列にも（`snapshot`と同様に）適用する（下記決定事項参照）
  - `run_task_logged_step()`内の`before_snapshot`/`before_screenshot`/`after_snapshot`/`after_screenshot`取得を、新設のプレースホルダ変換ヘルパー（`CliError`時に例外を伝播させず`"<... unavailable: ...>"`文字列へ差し替える）経由にする。`run_step()`側で`CliError`を`failure_notes`化しても、ブラウザ自体が壊れた状態（モーダルが開いたまま等）から自然に回復するわけではなく、`run_task_logged_step()`側の`after_snapshot`取得がそのままクラッシュしうるため
- `scripts/vertical_slice/task_log.py` — 直列化ロジック自体（`append_task_log`/`load_task_log`）は素朴なdictの読み書きなので変更不要。モジュールdocstring/コメントに、新設される`"attempts"`フィールドの意味（1なら初回成功、2以上ならリトライが発生したことを示す）を1〜2行追記する

`scripts/server/orchestrator.py` / `app.py` / `schemas.py` / `main.py` はいずれも無変更（決定事項参照）。

## 決定事項・注意点／落とし穴

| 決定 | 理由 |
|---|---|
| リトライは`step_runner.run_step()`のターン制御ループの外側、`runner.run_task_logged_step()`の中に実装する（`run_step`をもう一度フレッシュな呼び出しとして呼ぶだけ） | 「1タスク＝1フレッシュコンテキスト」（SPEC.md 2章）という粒度と、`MAX_TURNS_PER_STEP`は安全弁でリトライ機構ではないという既存コメントに整合する。`run_step`自体の複雑なターン制御ロジックに手を入れるリスクを避けられる |
| リトライ中はブラウザ状態を明示的にロールバックしない。前の試行が途中まで実際に行った操作の結果を引き継いだまま、次の試行のフレッシュなAIコンテキストへ渡す | `run_step`は毎ターン`cli.snapshot_text()`を取り直しており、AIは常に「現在の実際の画面」を見て判断する設計（SPEC.md 2章）。この既存動作の範囲内でリトライを実現すれば、状態復元のための新機構（Step5で明示的に不採用とした`state-save`/`state-load`と同種の仕組み）を持ち込まずに済む。半端な操作（例: 送信済みフォーム）はロールバックしても意味を持たない場合があり、Step5の判断（記録済みコードの再実行方式）とも整合する。前の試行が画面を壊れた状態にしてしまい次の試行でも回復できない、というリスクは受け入れる（既知の限界として明示するだけに留め、このステップでは対処しない） |
| `<out>.tasks.jsonl`は「1ステップ＝1エントリ」を保ったまま、`code`フィールドに全試行分の生成コードを試行順に連結して持たせ、新規フィールド`attempts`で試行回数を記録する | `task_log.build_replay_source`/`runner.build_resume_state`は`step_id`でエントリを1件引き当てる前提で書かれており、同じ`step_id`が複数エントリになるとリプレイが未定義動作になる（プロンプトで指摘された最大の落とし穴）。一方、各試行が実際にブラウザへ加えた操作は次の試行にも影響する実際の状態変化であり、1回目の生成コードを丸ごと捨てるのは実態に反する。「1エントリに集約し、コードは全試行分を連結する」がこの両立点になる |
| `console`/`requests`による診断情報の取得は、最終（`MAX_STEP_ATTEMPTS`回目）の試行が失敗した時だけ行う。1〜2回目の失敗では取得しない | リトライ中に毎回`console`/`requests`のCLI呼び出しを増やすと、失敗が続くほどCLI往復コストが線形に増える。診断情報は「これ以上リトライしても仕方ないので人間に見せる」タイミングでのみ必要という前提に立つ |
| 診断情報バンドルの`snapshot`/`screenshot_path`は、`task_log`用に既に取得している`after_snapshot`/`after_screenshot`の値をそのまま再利用する（新規のCLI呼び出しを追加しない） | Step5で追加済みの前後snapshot/screenshot取得は、リトライ導入後も「最終試行後に1回」のまま変わらない。同じ値を`failure_notes`側にも埋め込むことで、`.failure-notes.json`だけで人間が状況を把握できるようにし（`.tasks.jsonl`を別途開く必要をなくす）、CLI呼び出しの追加コストもゼロで済む |
| リトライは`reason`（`cli_error`/`blocked`/`no_tool_call`/`max_turns_exceeded`）を区別せず一律に適用する。「`blocked`は環境要因なのでリトライしても無駄」といった判断はサーバー側に持ち込まない | サーバー側が「どの失敗が再試行に値するか」を判断し始めると、SPEC.md 6章・heal.md 3.4節が明確に禁じている「サーバー側の判断」領域に踏み込んでしまう。`MAX_STEP_ATTEMPTS`が小さい値である以上、`blocked`のようなおそらく再現するケースに数回分のAI呼び出しコストを払うのは許容範囲とする |
| 「失敗の推定原因」は`FAILURE_REASON_HINTS`という固定の辞書（reason文字列→説明文）でサーバー側が機械的に付与するだけとし、追加のAI呼び出しで原因を推定させない | SPEC.md 6章・heal.md 3.4節の「仕様が古いのか、アプリ側の回帰バグなのか」を判断せず人間に委ねる思想を守るため。`hint`は既存の`reason`分類が何を意味するかの事実説明（例: `blocked`＝AI自身が実行不能と宣言した、等）に留め、原因の断定や次の対処の指示は書かない |
| `MAX_STEP_ATTEMPTS = 3`（初回1回＋リトライ2回）を`runner.py`のモジュール定数として固定し、CLI引数・環境変数での上書きは用意しない | SPEC.md 9章のOpen Questionに対しbig_plansが指示する「小さい値（2〜3回）から始めて運用しながら調整する」を素直に反映。`step_runner.MAX_TURNS_PER_STEP`も同様にハードコードされた定数であり、同じ流儀に揃える。将来値を変える必要が出た時点で初めて設定可能にする（YAGNI） |
| `console()`/`requests()`は`CliExecutor.execute()`をそのまま使い（`["--raw"]`を渡すだけ）、`generate_locator`/`eval_raw`のような専用の生文字列パースは追加しない | 実機確認の結果、`console --raw`/`requests --raw`は`### Result`ヘッダを取り除くだけで、`execute()`の既存の`### Error`検知・`_CODE_BLOCK_RE`（該当なしなら`generated_code=None`になるだけで無害）に問題なく乗ることを確認した。`eval_raw`が専用実装になっていたのは`eval`が任意JS文字列を扱うためで、`console`/`requests`には同じ複雑さがない |
| `console()`/`requests()`の呼び出し自体が`CliError`を投げた場合は、その旨（`{"error": str(exc)}`）を診断情報として記録し、例外を再raiseしない | 診断情報の取得はあくまで人間への提示を厚くするための付加機能であり、ここで例外を伝播させると`failure_notes`/`task_log`の記録自体が失敗し、リトライ機構の主目的（停止して人間に提示する）が果たせなくなる |
| `console()`/`requests()`はブラウザセッション開始からの全履歴を返す（`playwright-cli`側に「直前の操作以降だけ」に絞るオプションや履歴クリア用コマンドは存在しない）。この制約は解消せず、`diagnostics`へ埋め込む前に`step_log.truncate`（既存の`snapshot`ログ切り詰めと同じ関数）を適用してサイズだけ抑える | ストーリーが何ステップも進んだ後に失敗すると、`console`/`requests`の内容はそのステップの操作とは無関係な過去の分も含んだまま返ってくる。これ自体はStep6のスコープでは解消しない既知の限界として明示するだけに留めるが、`.failure-notes.json`が無制限に肥大化するのは`truncate`を適用するだけで安価に防げるため、そこだけは対応する |
| `scripts/server/orchestrator.py`・`app.py`・`schemas.py`・`main.py`は無変更 | リトライは`runner.run_task_logged_step()`に閉じ込め、`run_steps()`（4つのエントリポイント全てが経由する共有関数）のインターフェースは変えていない。`failure_notes`は元々`list[dict]`という緩い型でAPIスキーマに載っており、dict内に新規キーを追加してもpydanticモデルの変更は不要 |
| `CliExecutor.snapshot_text()`が返しうる`isError`形状の異常応答を`CliError`として扱い、`run_step()`/`run_task_logged_step()`双方でその`CliError`を捕捉して処理を継続する（プロセスをクラッシュさせない） | `.claude/plan/scenarios/05-failure-and-blocked-cases.md`が実行時に発見しStep6のスコープとして明示的に持ち越していた既知の不具合。「サーバー側でCLIエラーを捕捉して停止・提示する」というStep6の目的そのものが、この不具合が残っていると`CliError`以外の異常応答（`isError`）で素通りされ達成できない。今回の実AI呼び出しテストで実際に再現・修正した |
| 動作確認は新規YAMLを作らず、既存の`edge-*-demo.yaml`5本のうち代表2本（`edge-range-input-demo.yaml`＝`reason: cli_error`が確実、`edge-unsupported-drag-demo.yaml`または`edge-ambiguous-locator-demo.yaml`＝`reason: blocked`が確実）を優先的に使う。5本すべてを毎回実行する必要はない。このプラン段階では実行しない | 実AI APIコールは課金対象であり、`vertical-slice-ai-test`スキル・architecture.mdの既存方針（実行前にユーザー確認）に従う必要がある。5本のfixtureは元々reasonの切り分けを目的に用意されたものなので、`cli_error`系・`blocked`系それぞれ1本ずつ確認すれば「リトライ→停止→診断情報つき提示」の流れ自体は十分に検証できる。実装後の確認手順は: (1) `npm run serve:pages`でedge-cases.htmlを配信、(2) `python -m scripts.vertical_slice.main --story scripts/stories/edge-range-input-demo.yaml --out tests/generated/edge-range-input-demo.spec.ts -v`を実行、(3) 出力される`run_id`から`tests/generated/edge-range-input-demo.history/{run_id}__edge-range-input-demo.steps.jsonl`を見て同じ`step: 1`に対し`attempt: 1,2,3`の3試行分のエントリがあることを確認、(4) 同runの`.tasks.jsonl`に`step_id: 1`のエントリが1件だけ（複数エントリに増えていない）で`attempts: 3`・`code`に3試行分のコードが連結されていることを確認、(5) `tests/generated/edge-range-input-demo.failure-notes.json`に`hint`と`diagnostics`（`console`/`requests`/`snapshot`/`screenshot_path`）が入っていることを確認する。`blocked`系の1本でも同様に確認する |

## 実行結果（実AI呼び出しテスト、実行日 2026-07-19、MiniMax-M3）

`scripts/stories/edge-*-demo.yaml` 5本すべてに対し`python -m scripts.vertical_slice.main`を実行。いずれもクラッシュせず、リトライ→（必要な場合のみ）停止→診断情報つき`.failure-notes.json`、の流れが動作した（合計コスト概算 $0.009）。

| story | 結果 | 補足 |
|---|---|---|
| `edge-range-input-demo.yaml` | `cli_error`（3試行すべて失敗、diagnostics/hint付き） | ベースライン記録（05-failure-and-blocked-cases.md）と同じ`reason` |
| `edge-disabled-button-demo.yaml` | `cli_error`（3試行すべて失敗） | ベースラインは`blocked`だったが、今回はAIがクリックを試み`TimeoutError`（`CliError`として捕捉）になった。モデルの非決定性による違いで、リトライ・診断ロジック自体は正しく動作 |
| `edge-ambiguous-locator-demo.yaml` | **成功**（1試行目で完了） | ベースラインは`blocked`だったが、今回はAIが2つの「詳細」ボタンのうち1つを選んでクリックし完了。`intent`に記載の「誤ってどちらかを選ぶ可能性」が実際に起きた例。失敗しない場合にリトライが誤発火しないことも確認できた |
| `edge-unsupported-action-demo.yaml`（アップロード） | `cli_error`（3試行すべて失敗、diagnostics付き） | **本ステップで修正したクラッシュ（`CliExecutor.snapshot_text`の`isError`未処理によるKeyError）が実際に再現し、修正が機能することを確認した最重要ケース**。1試行目: `click`でファイルチューザーモーダルが開き、直後の`snapshot`が`isError`形状で失敗（`CliError`化） → 2・3試行目: モーダルが開いたままのため`run_step`冒頭の初回`snapshot`も同じ理由で即失敗。`run_task_logged_step`の`after_snapshot`/`after_screenshot`取得も同じくモーダル状態で失敗したが、プレースホルダ文字列（`<snapshot unavailable: ...>`/`<screenshot unavailable: ...>`）に差し替わり、プロセスはクラッシュせず`.failure-notes.json`まで書き出せた |
| `edge-unsupported-drag-demo.yaml` | `blocked`（3試行すべて失敗） | ベースラインは`cli_error`（存在しないURLへの誤navigate）だったが、今回は1試行目`blocked`→2試行目は存在しない`drag`ツールを幻覚呼び出しして`no_tool_call`→3試行目`blocked`、という経過。reasonが試行ごとに異なっても`task_log`には1エントリに正しく集約された |

**確認できたこと**: リトライ（`MAX_STEP_ATTEMPTS=3`）・診断情報付与（`console`/`requests`/`snapshot`/`screenshot_path`/`hint`）・`task_log`の1ステップ1エントリ不変条件・クラッシュ修正（`isError`ハンドリング）のいずれも実機で意図通り動作した。モデルの非決定性により個々の`reason`はベースラインと一致しないケースがあったが、これはStep6の実装ではなくAIの判断のばらつきによるもので、リトライ・診断ロジック自体の問題ではない。

## `.claude/rules` 更新ポイント

- `.claude/rules/vertical-slice-runner.md`（既存ファイルへの追記。対象パスに変更は無いのでフロントマター変更は不要）
  - `step_runner.py`の説明部分に、`run_step()`が`attempt`引数を受け取り`.steps.jsonl`の各エントリに`"attempt"`フィールドが付く旨を1行追記
  - `runner.py`の説明部分に、`run_task_logged_step()`が`MAX_STEP_ATTEMPTS`（初回1回＋リトライ2回）までリトライする旨、リトライ中はブラウザ状態をロールバックしない旨、最終試行の失敗時のみ`console`/`requests`を取得し`failure_notes`に`diagnostics`/`hint`を付与する旨を追記
  - 「生成物」節の`<out>.tasks.jsonl`の説明に、新規`"attempts"`フィールド（1なら初回成功、2以上はリトライが発生）を追記
  - 「生成物」節の`<out>.failure-notes.json`の説明に、各エントリが`attempt`/`max_attempts`/`hint`/（最終試行のみ）`diagnostics`（`console`/`requests`/`snapshot`/`screenshot_path`）を持つように変わった旨を追記
  - `cli_executor.py`の説明部分に`console()`/`requests()`（`--raw`付き`execute()`呼び出しのみで専用パースは不要）を追記
