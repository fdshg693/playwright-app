# FEATURES

現状（`big_plans/` Step1〜8すべて実装済み）で実際に使える機能の一覧。図解は [MERMAID.md](MERMAID.md)、動かし方は [QUICKSTART.md](QUICKSTART.md)。未対応・部分対応は [NEXT.md](NEXT.md)。

## コアループ（Step1: vertical slice）

- 自然言語のテストストーリーをYAML（`scripts/stories/*.yaml`: `name`/`intent`/`seed_url`/`steps[].instruction`）で表現し、`python -m scripts.vertical_slice.main --story <yaml>`（`make slice`）で人間の介入なしに最初から最後まで実行できる
- 1ステップ＝1フレッシュなAIコンテキスト。ステップ間で会話履歴を引き継がない。ステップ内は「操作→結果確認→次の操作」のマルチターンで、`finish_step` が単独で呼ばれるまで続く（`MAX_TURNS_PER_STEP=8`が安全弁）
- AIが呼べる操作: `navigate`/`click`/`fill`（`submit`オプション付き）/`press`/`select`/`check`/`uncheck`/`hover`、確認専用の`add_expectation`（`toBeVisible`/`toHaveText`）
- `playwright-cli` はコマンド成功時 exit code 0 だが失敗時も0を返すため、`### Error` 文字列で成否を判定する（`CliExecutor`）

## サーバー骨組み・セッション管理（Step2）

- FastAPIサーバー（`scripts/server/`）が `session_id -> CliExecutor` を管理し、1テスト実行につきPlaywright CLIセッションを1本、最初から最後まで維持する
- `POST /sessions`（開始・target_url自動navigation）／`GET /sessions/{id}/snapshot`／`POST /sessions/{id}/command`（1コマンドを人間が直接叩く）／`DELETE /sessions/{id}`

## タスクオーケストレーションの自動化（Step3）

- `POST /sessions/{id}/run` で、ストーリー全体をAI主導・人間の介入なしに最初から最後まで自動実行する
- サーバー経由でも「1タスク＝1フレッシュコンテキスト」が保たれる（`runner.run_steps()`/`step_runner.run_step()`をCLI版と共有）

## 生成コードの組み立て（Step4）

- 各ステップの生成コードをステップ境界つき（`// {id}. {instruction}` コメント）で1本の `.spec.ts` に組み立てる（`runner.write_spec_file`）
- `POST /sessions` 時点のnavigationコードもseedとして先頭に含めるため、生成された `.spec.ts` はこのツールを介さず単体で `npx playwright test` 実行・再現できる
- 期待値確認は `add_expectation` 経由で安定ロケータ・期待テキストを取得し `await expect(...)` として組み込む（AIにセレクタ文字列やevalスクリプトを直接書かせない）
- 生成後 `npx playwright test` を自動実行して確認する

## 記録と途中再開・分岐（Step5）

- 実行ごとに `{stem}.history/{run_id}__{stem}.steps.jsonl`（AIターン単位の生ログ）・`{stem}.history/{run_id}__{stem}.tasks.jsonl`（タスク単位: 実行前後のsnapshot/screenshot・生成コード・成否）・`{stem}.recordings/*.png`（ステップ前後のスクリーンショット）を、`run_id`（秒精度・時刻順ソート可能）で実行ごとに新規ファイルとして残す（過去実行を上書きしない）
- `POST /sessions/resume`（サーバー）／`--resume-tasks-log`+`--resume-before-step`（CLI）で、記録済みの操作コード列を `playwright-cli run-code` により先頭から早送り再生し、途中のステップから再開できる
- 再開先に別のストーリーYAMLを渡すことで「タスクNまでは記録から復元し、それ以降は別パターンで実行する」分岐実行ができる（`search-demo-branch.yaml`/`wizard-demo-branch.yaml`が実例）

## 失敗時のふるまい（Step6）

- タスク失敗時は自動リトライ（`MAX_STEP_ATTEMPTS=3`: 初回+2回）。人間による代理操作はしない
- 最終試行も失敗した場合のみ `console`/`requests`/失敗直前の`snapshot`/スクリーンショットを追加取得し、`<out>.failure-notes.json` に `reason`/`hint`/`attempt`/`max_attempts`/`diagnostics` として記録して停止する
- 「仕様が古いのか回帰バグか」の判断は行わず、人間に判断材料（診断情報）だけを渡す

## 人間による確認・介入（Step7）

- `POST /sessions/{id}/stop` で実行中のセッションを外部から強制停止できる（`threading.Event`による非同期シグナル）。反映はステップ境界・リトライ試行境界の2箇所
- 停止・完了いずれも、記録ファイル（`.steps.jsonl`/`.tasks.jsonl`/スクリーンショット/`.failure-notes.json`）だけから後追いで「何が起きたか」を確認できる
- 停止済みセッションからの再開は常に `POST /sessions/resume`（新しい`session_id`）で行う

## 安全性ガードレール（Step8）

- `ALLOWED_DOMAINS`（カンマ区切り、`*.example.com`ワイルドカード対応）で遷移先ドメインを許可リスト化。`goto`・間接的なクリック遷移・`run-code`リプレイ・`/command`のすべてが同じ関門（`CliExecutor.execute()`）を通る。範囲外への遷移はHTTP 400（`DisallowedNavigationError`）
- `MAX_CONCURRENT_SESSIONS`（デフォルト5）を超える `POST /sessions` はHTTP 429で拒否
- `IDLE_SESSION_TIMEOUT_SECONDS`（デフォルト1800秒）を超えて操作の無いセッションは、バックグラウンドの sweep スレッドが自動的に `close()` する

## 補助機能

- **コスト集計** (`scripts/internal/cost_summary.py`, `make cost`/`make cost-html`): `.steps.jsonl` のトークン使用量からモデル別単価で概算コストを算出。単一ファイルはステップ内訳、複数ファイル/ディレクトリはrun-history表（時刻昇順＋累計）。`--start`/`--end`で時間範囲絞り込み、`--html`で自己完結の静的HTMLダッシュボード（インラインSVG棒グラフ）を生成
- **自作テストページ** (`resources/custom_pages/`): 認証不要・静的な検証用ページ（検索・フォーム・複数ページに渡るウィザード・意図的な失敗フィクスチャ`edge-cases.html`）を `npm run serve:pages`（nginx, ポート8080固定）でローカル配信
- **デモ・エッジケース用ストーリー一式** (`scripts/stories/*.yaml`): 正常系（`search-demo`/`custom-pages-demo`/`wizard-demo`等）に加え、`navigate`直接呼び出し・`fill`の`submit`・ラジオボタン/テキストエリア・3ページ連続のウィザード＋resume・意図的に失敗/blockedになるエッジケース（無効化ボタン・非対応input・ロケータ非一意・未対応操作/ドラッグ）を一通りカバー
