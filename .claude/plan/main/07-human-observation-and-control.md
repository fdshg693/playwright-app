# Step 7 詳細版: 人間による確認・介入

> [big_plans/07-human-observation-and-control.md](../../../big_plans/07-human-observation-and-control.md) の詳細版。[00-overview.md](00-overview.md)参照。

## やること

- サーバーAPI（`scripts/server/`）に `POST /sessions/{session_id}/stop` を追加し、実行中の `/run`・`/sessions/resume` を外部から強制停止できるようにする。停止は`SessionManager`が`session_id`ごとに持つ`threading.Event`をセットするだけの非同期シグナルで、`/stop`自体は即座に返る（`/run`/`/sessions/resume`の完了を待たない）。
- 停止の反映粒度は「ステップ境界」と「同一ステップ内のリトライ試行境界」の2箇所のみとし、`step_runner.run_step()`のターン制御ループには一切手を入れない（Step4〜6の既存方針を踏襲）。`runner.run_steps()`は次のステップに着手する直前に、`runner.run_task_logged_step()`は失敗したリトライ試行の直後に、それぞれ停止フラグを確認する。
- 停止によって「これから着手するはずだったステップが未着手のまま終わった」場合は、既存の`failure_notes`パイプラインに新しい`reason: "stopped"`を1件積むだけで表現し、`run_steps`/`write_and_test`/4つのエントリポイント（`run_vertical_slice`/`resume_vertical_slice`/`orchestrator.run_story`/`resume_story`）の戻り値の型は一切変更しない。既存の「`failure_notes`があれば`npx playwright test`をスキップする」という`write_and_test`の分岐をそのまま利用する。
- 停止時点までに完了済みのタスクは通常どおり`<out>.tasks.jsonl`に記録済みなので、Step5の`POST /sessions/resume`（`tasks_log`・`resume_before_step`・`story`）にそのまま渡せば続きから再開できる。`resume_before_step`に使う値は、`failure_notes`中の`reason: "stopped"`エントリが持つ`step`（＝未着手だった最初のステップのid）。新しいレスポンススキーマは追加しない（`RunResponse`/`ResumeResponse`の既存の`run_id`・`spec_path`・`failure_notes`だけで、次の`/sessions/resume`呼び出しに必要な情報は揃う）。
- ログ閲覧については、Step5/6で既に`{stem}.history/{run_id}__{stem}.steps.jsonl`・`.tasks.jsonl`が「1実行1ファイル、時系列に`run_id`でソート可能」という形で存在しており、big_plansの「最初はファイルを時系列に並べるだけでもよい」を実質的に満たしている。今回は新しいHTTP読み取りエンドポイントやビューアを追加しない（過剰実装をスコープ外とする明示的判断。詳細は決定事項参照）。`playwright-cli show --annotate`は調査の結果、ライブセッション中に人間が要素を指差すための対話コマンドであり、過去ログの閲覧用途には転用できないことを確認した。
- CLI（`scripts/vertical_slice/main.py`）には停止機構を追加しない。big_plans原文が停止インターフェースを「Step2のサーバーAPI」に明示的に限定していることに加え、CLIは1プロセス1実行なのでCtrl+C（SIGINT）によるプロセスkillで十分に代替できる（サーバーは複数セッションが1プロセス内に同居し得るため、プロセスkillでは他セッションも巻き添えになるという非対称性がある）。
- 動作確認は新規story YAMLを作らず、既存の複数ステップシナリオ（`scripts/stories/wizard-demo.yaml`、Step5のresume検証に既に使われている多段ページ遷移シナリオ）を使い、`/run`をバックグラウンドスレッドで叩きながら途中で`/stop`を呼ぶ確認用スクリプトを`scripts/temp/`に追加する。実AI APIコールを伴うため、このプラン段階では実行せず、確認観点のみ明記する。

## 読むべきファイル・実行推奨Grep

**停止シグナルをどこで受けてどこまで伝播させるかを確認するため（優先度: 高）**
- 読む: `scripts/vertical_slice/runner.py` の `run_steps()` / `run_task_logged_step()` — 4エントリポイント全部が経由する共有ループの現在地。`run_steps()`のfor文直前、`run_task_logged_step()`のリトライfor文内の2箇所が今回のチェックポイント。`run_task_logged_step()`は現状`run_steps()`からしか呼ばれていないことを確認し、シグネチャ変更の影響範囲を`run_steps()`1箇所に限定できることを裏取りする
- 読む: `scripts/vertical_slice/runner.py` の `MAX_STEP_ATTEMPTS` / `FAILURE_REASON_HINTS`（Step6で追加済み） — 新しい`reason: "stopped"`を辞書に足す場所、および`step_failures`への追記パターン（`{"step": step.id, "reason": ..., ...}`）の既存の形
- 読む: `scripts/vertical_slice/runner.py` の `write_and_test()` — 「`failure_notes`が非空なら`npx playwright test`をスキップする」既存分岐（`stopped`もこの1本の分岐にそのまま乗る想定であることの裏取り）
- 読む: `scripts/vertical_slice/step_runner.py` 冒頭のモジュールdocstringと`run_step()`のfor文（`MAX_TURNS_PER_STEP`） — 「リトライ機構ではない、ターン単位の安全弁のみ」という既存コメントの通り、この関数には一切手を入れないことの再確認（Step6が既に同じ制約下で実装済み）
- Grep: `run_task_logged_step\(` と `run_steps\(` で呼び出し元を全て洗い出し、シグネチャに`should_stop`パラメータを追加した際の影響範囲（CLI側の`run_vertical_slice`/`resume_vertical_slice`は`should_stop`を渡さずデフォルト`None`のままで良いことの確認）に漏れがないか確認する

**サーバー側の配線・排他制御に関する既存決定を確認するため（優先度: 高）**
- 読む: `scripts/server/session_manager.py` の `SessionManager`（`create`/`get`/`close`）とモジュールdocstring — 「並行アクセスの安全性は未対応（ロックなし）」という既存の明示的な割り切り。新設する`_stop_flags: dict[str, threading.Event]`もこの割り切りの範囲内に収める（`threading.Event`自体はスレッドセーフだが、辞書へのキー追加/削除自体は無ロックのままにする）
- 読む: `scripts/server/app.py` の `run_session`（`/run`）・`resume_session`（`/sessions/resume`）・`_get_cli` — 新設する`/stop`エンドポイントの位置づけと、既存の404返却パターン（`SessionNotFoundError`→`HTTPException(404)`）の踏襲
- 読む: `scripts/server/orchestrator.py` の `run_story()` / `resume_story()` — いずれも`runner.run_steps()`をそのまま呼んでいるだけの薄いラッパーであることの再確認。`should_stop`をここでも素通しできることの裏取り
- 読む: `.claude/rules/session-server.md` の「`/run`はHTTPリクエスト内で同期的に最後まで実行する。進捗のストリーミング配信や途中中断のAPIは無い（Step7スコープ）」という記述 — 今回のStep7でここを更新する対象箇所そのもの
- 読む: `big_plans/02-server-skeleton.md`（決定事項テーブル該当部）・`big_plans/08-safety-guardrails.md` — Step8（未実装）が将来追加予定の「最大同時セッション数」「アイドルタイムアウト」は今回のstopとは別トリガー（人間の明示リクエスト vs 放置検知）であり、Step7のスコープに含めないことの根拠

**実装作法・既存パターンの流用を確認するため（優先度: 中）**
- 読む: `scripts/temp/test_server_ai_run.py` — サーバーのAI駆動エンドポイントを実APIに対して検証する既存スクリプトの型（起動待ち・`urllib`ベースのHTTPクライアント・`finally`でのセッションclose）。新設する停止確認用スクリプトはこの構造をそのまま流用し、`/run`をバックグラウンドスレッドで叩く点だけが差分になる
- 読む: `scripts/vertical_slice/task_log.py` の `history_dir()` / `task_log_path()` — クライアント側（`ResumeRequest.tasks_log`を組み立てる側）が`run_id`と`spec_path`から`tasks_log`のパスをどう機械的に再構成できるかの命名規則（`{spec_path.parent}/{spec_path.stem}.history/{run_id}__{spec_path.stem}.tasks.jsonl`）。Step5時点で既に同じ再構成が`/sessions/resume`利用者に要求されており、Step7で新たに追加する負担ではないことの確認
- 実行確認: `grep -rn "threading" scripts/` で現状スレッド関連の実装が皆無であることを確認済み（`threading.Event`が本リポジトリ初のスレッド同期プリミティブ導入になる）
- 読む: [SKILL.md](../../skills/playwright-cli/SKILL.md)の`show --annotate`節 — ライブセッション中の要素指差し用コマンドであり、過去ログ閲覧には使えないことの実機確認済みの根拠（やること節で前述）

## 触るファイル

### 新規
- `scripts/temp/test_server_stop_resume.py` — `test_server_ai_run.py`と同型の実AI疎通確認スクリプト。`wizard-demo.yaml`で`/sessions`→バックグラウンドスレッドで`/run`→数秒待ってから`/stop`→`/run`スレッドの完了を待ち`passed is False`かつ`failure_notes`に`reason: "stopped"`が1件あることを確認→そのstep idを`resume_before_step`、`run_id`+`spec_path`から組み立てた`tasks_log`パスを使って`/sessions/resume`を叩き、最終的に`passed is True`になることを確認する

### 変更
- `scripts/server/session_manager.py` — `SessionManager.__init__`に`self._stop_flags: dict[str, threading.Event] = {}`を追加。`create()`で新規`threading.Event()`を発行して登録、`close()`で該当エントリを削除。新規メソッド`request_stop(session_id) -> None`（未知の`session_id`なら`SessionNotFoundError`、既知なら`self._stop_flags[session_id].set()`）と`is_stop_requested(session_id) -> bool`（`self._stop_flags[session_id].is_set()`）を追加
- `scripts/server/app.py` — `POST /sessions/{session_id}/stop`エンドポイントを追加（`_get_cli(session_id)`で存在確認後`sessions.request_stop(session_id)`、`StopResponse(session_id=session_id)`を返す）。`run_session`（`/run`）・`resume_session`（`/sessions/resume`）内の`orchestrator.run_story(...)`/`orchestrator.resume_story(...)`呼び出しに`should_stop=lambda: sessions.is_stop_requested(session_id)`を追加で渡す
- `scripts/server/schemas.py` — `StopResponse(session_id: str, stop_requested: bool = True)`を追加
- `scripts/server/orchestrator.py` — `run_story()`/`resume_story()`のシグネチャに`should_stop: Callable[[], bool] | None = None`引数を追加し、`runner.run_steps(...)`呼び出しへそのまま渡すだけ（`SessionManager`型そのものは知らない、呼び出し可能オブジェクトを受け取るだけの薄いパススルーに留める）
- `scripts/vertical_slice/runner.py`
  - `FAILURE_REASON_HINTS`に`"stopped": "The run was stopped via an external stop request before this step started."`を追加
  - `run_steps()`のシグネチャに`should_stop: Callable[[], bool] | None = None`を追加。for文の各反復の先頭で`should_stop`が非Noneかつ`should_stop()`が真なら、`failure_notes.append({"step": step.id, "reason": "stopped", "hint": FAILURE_REASON_HINTS["stopped"]})`を積んでbreak（この場合`run_task_logged_step()`は一切呼ばれず、`<out>.tasks.jsonl`にも当該ステップのエントリは作られない）
  - `run_task_logged_step()`のシグネチャにも同じ`should_stop`を追加し、`run_steps()`から素通しで渡す。リトライfor文の直前で`stopped_mid_retry = False`を初期化し、`if not step_failures: break`の直後の`elif`として`elif should_stop and should_stop(): stopped_mid_retry = True; break`を追加（＝この試行が失敗し、かつ外部から停止要求が来ていれば、残りのリトライ回数を消費せず打ち切る）。打ち切られたことが分かるよう、直後の`for note in step_failures:`ループで各noteに`note["stopped"] = stopped_mid_retry`を1フィールド追加する（`attempt`と`MAX_STEP_ATTEMPTS`の比較から間接的に推測させない。将来break条件が増えても壊れない明示的なフラグにする）。診断情報（`console`/`requests`）取得・`hint`付与のロジック自体は既存のまま変更しない

`scripts/vertical_slice/step_runner.py`・`main.py`（CLI）・`scripts/server/main.py`はいずれも無変更。

## 決定事項・注意点／落とし穴

| 決定 | 理由 |
|---|---|
| 停止フラグは`SessionManager`が`session_id`ごとに持つ`threading.Event`とし、専用ロックは追加しない | `threading.Event.set()`/`.is_set()`自体はスレッドセーフで、辞書へのキー追加・削除（`create`/`close`）と`/stop`呼び出しの間に理論上の競合（`close`と`request_stop`が同時に来て`KeyError`になる等）は残るが、これはStep2の既存決定「複数セッションの同時実行に対する排他制御はこの段階では入れない」の範囲内の既知のリスクとして受け入れる。新しい排他制御機構を持ち込むと、Step2のスコープを勝手に広げてしまう |
| 停止の反映粒度は「`run_steps()`のステップ境界」と「`run_task_logged_step()`のリトライ試行境界」の2箇所のみ。`step_runner.run_step()`のターン制御ループ（`MAX_TURNS_PER_STEP`）は一切変更しない | Step4〜6が繰り返し明言してきた「`run_step`のターン制御ロジックには手を入れない」という制約をStep7でも踏襲する。ターン単位でチェックを入れるには`run_step`の内部（AI呼び出し・CLI呼び出しの合間）にコードを差し込む必要があり、安定した既存ループを壊すリスクが大きい。一方でステップ境界だけだと最大`MAX_STEP_ATTEMPTS × MAX_TURNS_PER_STEP`（3×8=24ターン相当）分の遅延が発生し得るため、`run_task_logged_step`のリトライ境界も追加のチェックポイントとする（最大1試行＝8ターン分の遅延に短縮できる）。いずれの粒度でも、進行中のOpenAI API呼び出し1回自体を割り込みで中断することはできない（既知の限界として受け入れる） |
| 停止によって未着手のまま終わったステップは、既存`failure_notes`に新しい`reason: "stopped"`エントリとして積み、`run_steps`/`write_and_test`/4エントリポイントの戻り値の型は変更しない | `failure_notes`は既に`cli_error`/`blocked`/`no_tool_call`/`max_turns_exceeded`の4種類の`reason`を同じ形（`step`/`reason`/...のdict）で運んでおり、`stopped`を5番目の`reason`として追加するのが最小の変更で済む。別の戻り値（例:`stopped: bool`をタプルに追加）にすると`run_steps`→`run_vertical_slice`/`resume_vertical_slice`/`orchestrator.run_story`/`resume_story`→`app.py`の4系統すべてのシグネチャ変更が必要になり、影響範囲が不必要に広がる |
| リトライ試行の途中で停止要求により打ち切られた場合、`failure_notes`の`reason`は打ち切られた最後の試行の実際の失敗理由（`cli_error`/`blocked`等）をそのまま使い、`stopped`という新reasonは使わない。代わりに各noteへ`"stopped": true`フィールドを追加する | この場合、そのステップは実際に実行されて（部分的に）失敗しており、「未着手のまま終わった」わけではない。`reason`を`stopped`に上書きすると、本来の失敗理由（診断に有用な情報）が失われてしまう。`run_steps()`側の「未着手」ケースとは性質が異なるため、同じ`reason`文字列を使い回さず、区別できる形にする |
| 停止済みステップは`<out>.tasks.jsonl`にエントリを作らない（`run_task_logged_step`自体が呼ばれないため） | `resume_before_step`にそのステップのidをそのまま渡せば、`task_log.build_replay_source`/`runner.build_resume_state`の既存フィルタ（`step_id < resume_before_step`）が自然に「未着手ステップは再開時にリプレイ対象から除外され、次回はそこから通常のAIループで再実行される」という挙動になる。Step5で確立した「1エントリ＝1完了タスク」という不変条件を壊さずに済む |
| ステップが成功して`run_task_logged_step`から正常に戻った直後（＝`<out>.tasks.jsonl`への記録が完了した直後）は、たとえその最中に停止要求が来ていても、その完了済みタスクを取り消したり`failure_notes`化したりしない。次のステップに着手する直前のチェックで初めて停止を反映する | 「1タスク＝1ステップは常に完全に実行されて記録されるか、まったく未着手か」という単純な二値の状態だけを持たせることで、`task_log`のリプレイ前提を複雑にしない。完了済みの成果を停止要求のタイミング次第で捨ててしまうのはユーザー体験としても不自然 |
| `POST /sessions/resume`（`ResumeRequest`/`ResumeResponse`）のスキーマは変更しない。停止後の再開に必要な情報（`run_id`・`spec_path`・停止した`step` id）は既存の`RunResponse`/`ResumeResponse`の`run_id`・`spec_path`・`failure_notes`だけで揃っている | `tasks_log`パスは`spec_path`と`run_id`から命名規則的に機械的に再構成できる（`task_log.history_dir`/`task_log_path`と同じ規則）。この再構成は Step5時点の`/sessions/resume`利用でも既に必要だった既存の負担であり、Step7で新規に追加する情報ではない。`resume_before_step`は`failure_notes`中の`reason: "stopped"`エントリの`step`をそのまま使えばよい |
| ログ閲覧について、新しいHTTP読み取りエンドポイント（例: `GET /sessions/{id}/tasks`）やビューアは追加しない。既存の`{stem}.history/{run_id}__{stem}.steps.jsonl`/`.tasks.jsonl`（run_idでソート可能なファイル名、Step5/6で実装済み）をそのまま「時系列に並んだ記録」として使う | big_plans原文が「最初は凝ったダッシュボード不要、ファイルを時系列に並べるだけでもよい」と明示しており、既存のファイル命名規則（`run_id`プレフィックス）自体が既にその要件を満たしている。本システムはローカル/CI実行が前提でファイルシステムへの直接アクセスが可能なため、リモートクライアント向けの読み取りAPIを今追加する必然性が無い（YAGNI）。将来必要になった時点でGETエンドポイントを追加する方針とする |
| `playwright-cli show --annotate`は今回のログ閲覧要件には転用しない | 調査の結果、これはライブセッション中に人間がブラウザ上の要素を指差して選択・強調表示させるための対話コマンドであり、終了済みセッションの過去ログ（`.tasks.jsonl`等）を可視化するものではない。big_plansが「検討する」としていた選択肢を検討した上で不採用にした、という判断の記録として残す |
| CLI（`scripts/vertical_slice/main.py`）には停止機構を追加しない | big_plans原文が「Step2のサーバーAPIにstopを足す」と明示的にサーバーへスコープを限定している。CLIは1プロセス=1実行であり、Ctrl+C（SIGINT）によるプロセスkillで「強制停止」の目的を代替できる。サーバーは複数セッションが1プロセスに同居し得るため、プロセスkillでは無関係な他セッションも巻き添えにしてしまう非対称性があり、そちらにだけHTTP経由の個別停止インターフェースを持たせる価値がある |
| 一度`/stop`された`session_id`に対して（`/sessions/resume`で新セッションを作らず）同じセッションへ`/run`を再度叩いても、`threading.Event`はセット済みのままなので即座に「未着手」扱いで失敗する。この状態をクリアする`/sessions/{id}/unstop`のようなAPIは追加しない | 想定される再開フローは常に`/sessions/resume`で新しい`session_id`を発行する形であり（`SessionManager.create()`は既に「navigationしない新セッション」を作れる）、停止済みセッションへの`/run`再実行は既存のどのフローにも登場しない。フラグをクリアする手段を足すと「同じセッションで停止→再開」という、Step5のリプレイ前提（新しいブラウザで早送り）と矛盾するもう1つの再開経路を生んでしまうため、あえて塞いだままにする |
| 動作確認は`scripts/temp/test_server_stop_resume.py`（新規、実AI課金コール）としてこのプラン段階では実行しない。既存の複数ステップシナリオ（`wizard-demo.yaml`）を流用し、新規story YAMLは作らない | `vertical-slice-ai-test`スキル・Step6プランの既存方針（実AI APIコール前にユーザー確認）を踏襲する。`wizard-demo.yaml`は複数ページ遷移で1ステップあたりの所要時間が読みやすく、Step5のresume検証にも既に使われている実績のあるシナリオである。実装後の確認手順は: (1) `bash resources/custom_pages/serve.sh`と`python -m scripts.server.main`を起動、(2) `POST /sessions`→バックグラウンドスレッドで`POST /run`を開始、(3) 数秒待ってから`POST /sessions/{id}/stop`を呼ぶ、(4) `/run`スレッドの戻り値で`passed is False`・`failure_notes`に`reason: "stopped"`が1件だけ含まれることを確認、(5) `{run_id}__{stem}.tasks.jsonl`に停止したステップのエントリが存在しない（＝直前の完了ステップまでしか記録が無い）ことを確認、(6) `resume_before_step`=停止ステップのid・`tasks_log`=手順4のパスで`POST /sessions/resume`を呼び、最終的に`passed is True`で完走することを確認する |

## `.claude/rules` 更新ポイント

- `.claude/rules/session-server.md`（既存ファイルへの追記。対象パスに変更は無いのでフロントマター変更は不要）
  - 「`/run`はHTTPリクエスト内で同期的に最後まで実行する。進捗のストリーミング配信や途中中断のAPIは無い（Step7スコープ）」という既存文を、「Step7で`POST /sessions/{id}/stop`による外部からの強制停止が可能になった」旨に更新する（進捗ストリーミング配信自体は引き続き無い、という点は残す）
  - `SessionManager`の説明に、`session_id`ごとの`threading.Event`（`_stop_flags`）と`request_stop`/`is_stop_requested`を追記。既存の「並行アクセスの安全性は未対応（ロックなし）」という記述と矛盾しないよう、この停止フラグもロック無しの範囲内であることを明記する
  - `POST /sessions/{session_id}/stop`エンドポイントの説明（何をセットするだけで、`/run`/`/sessions/resume`の完了を待たずに即座に返る非同期シグナルであること）を追記
  - `orchestrator.run_story`/`resume_story`の説明に、`should_stop`引数（`runner.run_steps`への素通し）を追記
- `.claude/rules/vertical-slice-runner.md`（既存ファイルへの追記。対象パスに変更は無い）
  - `runner.py`の説明に、`run_steps()`/`run_task_logged_step()`が受け取る`should_stop`引数と、停止の反映粒度（ステップ境界・リトライ試行境界の2箇所のみ、`step_runner.run_step`のターン制御には手を入れない）を追記
  - `FAILURE_REASON_HINTS`の説明に、新しい`"stopped"`理由（未着手のまま終わったステップ）と、リトライ試行途中で停止された場合に`failure_notes`の各エントリへ付く`"stopped": true`フィールド（`reason`自体は元の失敗理由のまま）の違いを追記
  - 「生成物」節に、停止によって未着手のまま終わったステップは`<out>.tasks.jsonl`にエントリが作られない旨、`resume_before_step`にそのステップのidをそのまま渡せば再開できる旨を追記
