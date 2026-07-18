# Step 2 詳細版: サーバーの骨組み

> [big_plans/02-server-skeleton.md](../../../big_plans/02-server-skeleton.md) の詳細版。[00-overview.md](00-overview.md)参照。

## やること

- Step1の`CliExecutor`（[[vertical-slice-runner]]）が担っていた「1本のplaywright-cliセッションを維持し、コマンド実行結果を返す」役割を、ネットワークサーバー（FastAPI）として切り出す。00-overview.mdの決定事項どおり、Step1で意図的に作らなかった「ネットワークサーバー」をここで実体化する。
- 最低限のHTTP API（big_plans記載の4操作）を用意する。
  - `POST /sessions` — テスト実行を開始する（`target_url`を受け取り、playwright-cliセッションを1本起動して`target_url`へ遷移する）
  - `GET /sessions/{session_id}/snapshot` — 現在の画面snapshotを取得する
  - `POST /sessions/{session_id}/command` — playwright-cliコマンドを1つ実行する（生の`command`/`args`を受け取る）
  - `DELETE /sessions/{session_id}` — テスト実行を終了する（セッションを閉じる）
- AIオーケストレーション（Step3）はまだ作らない。人間がこれらのエンドポイントを都度呼び出すことで、Step1と同じシナリオ（`search-demo.yaml`の手順）を実行できることを確認する。
- SPEC.md 2章の「セッションの永続性（サーバー側）」と「AIコンテキストの非永続性（Step3で足す）」の分離を、プロセス境界としても明確にする。このサーバープロセスはセッション管理にのみ責務を持つ。

## 読むべきファイル・実行推奨Grep

**再利用する既存実装を確認するため（優先度: 高）**
- 読む: `scripts/vertical_slice/cli_executor.py` の`CliExecutor` — そのまま流用する（コピーしない）。`open`/`snapshot_text`/`execute`/`close`がAPIの4操作にほぼ1:1対応する
- 読む: `.claude/rules/vertical-slice-runner.md` — `CliExecutor.execute`が exit code ではなく stdout の`### Error`文字列で成否判定している点（サーバー側のエラーハンドリングでも同じ前提を踏襲する）

**規約・依存関係を確認するため（優先度: 中）**
- 読む: `pyproject.toml` — 現状Web frameworkの依存が無いことの確認（FastAPI/uvicornを新規追加する）
- 読む: `scripts/vertical_slice/main.py` — 既存の「argparse+配線のみ」エントリポイントの書き方。`scripts/server/main.py`もこれに倣う

**次ステップへの引き継ぎを確認するため（優先度: 低）**
- 読む: `big_plans/03-task-orchestration.md` — Step3が「サーバーが1タスク＝1フレッシュコンテキストのループを回す」設計であること。このサーバープロセスに後からループを足す想定であり、別プロセスから叩かれる薄いRPCの想定ではない
- 読む: `scripts/vertical_slice/tools.py` — Step3のAI向けtool定義とは責務が別であることの確認（`/command`は生のCLIコマンドを受け取るだけで、tool schemaの解釈はしない）

## 触るファイル

### 新規
- `scripts/server/__init__.py`
- `scripts/server/app.py` — FastAPIアプリ定義とルーティング（4エンドポイント）
- `scripts/server/session_manager.py` — `session_id → CliExecutor`のインメモリレジストリ（作成／取得／破棄）
- `scripts/server/schemas.py` — リクエスト/レスポンスのPydanticモデル（`StartSessionRequest`/`CommandRequest`等）
- `scripts/server/main.py` — CLIエントリポイント（argparseでhost/portを受け、uvicornを起動する配線のみ）

### 変更
- `pyproject.toml` — `fastapi`・`uvicorn`を依存に追加

## 決定事項・注意点／落とし穴

| 決定 | 理由 |
|---|---|
| `CliExecutor`は`scripts/vertical_slice/`から移動せず、`scripts/server/`からそのままimportする | 現時点で利用者はvertical_sliceとserverの2箇所のみ。共通モジュールへの抽出は3箇所目が出てから検討する（早すぎる抽象化を避ける） |
| `session_id`はplaywright-cliの`-s=`セッション名と1:1対応させ、別の「run」概念を導入しない | SPEC.mdの「ブラウザセッション」という用語をAPI層でもそのまま使い、概念のズレを増やさない |
| `POST /sessions`は`story`フィールドを任意で受け取るが、この段階では保存するだけで解釈しない | big_plansの「テストストーリーを受け取る」という記載どおりAPI形状は先に決めるが、消費ロジック（AI呼び出し）はStep3の責務。Step3でこのエンドポイントの契約を壊さずに済む |
| `POST /sessions/{id}/command`はrole-basedのtool schema（`tools.py`）を経由せず、`command`/`args`の生文字列をそのまま`CliExecutor.execute`へ渡す | Step2はAIが呼ぶインターフェースではなく人間が手で叩く骨組みのため。tool schemaの解釈はStep3で追加する |
| 複数セッションの同時実行に対する排他制御（ロック等）はこの段階では入れない | Step2の完了条件はシナリオ1本の逐次実行の確認のみ。並行アクセスの安全性が必要になった時点で追加する |
| 人間による強制停止・進捗確認のUIは作らない（`DELETE /sessions/{id}`のみで代替） | SPEC.md 8章・big_plans Step7のスコープであり、ここでは骨組みのセッション終了エンドポイントで足りる |

## `.claude/rules` 更新ポイント

- 現時点では新規ルールファイルは作成しない。`scripts/server/`の構成は本ステップの実装結果を見てから、`.claude/rules/vertical-slice-runner.md`と並ぶ形で新設を検討する（Step3でAIループを足した後の方が構成が安定する）。
