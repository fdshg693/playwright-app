# MERMAID

実装の詳細は `.claude/rules/*.md` を参照。

## 1. 全体の流れ

人間が書いたストーリーから、再実行可能な `.spec.ts` ができるまで。

```mermaid
flowchart TD
    A["人間: 自然言語のテストストーリー"] --> B["Story YAML化\nscripts/stories/*.yaml"]
    B --> C["セッション開始\nPOST /sessions もしくは\nscripts.vertical_slice.main"]
    C --> D["playwright-cli セッション起動\n(ブラウザ, 実行の最初から最後まで永続)"]
    D --> E["snapshot取得"]
    E --> F["AI呼び出し\n(1ステップ=1フレッシュコンテキスト)"]
    F --> G["playwright-cli コマンド実行"]
    G --> D
    G --> H{"finish_step?"}
    H -- blocked --> J["停止 + 診断情報を人間に提示"]
    H -- done --> I{"次のステップがある?"}
    I -- yes --> E
    I -- no --> K[".spec.ts 組み立て\nnpx playwright test 自動実行"]
```

## 2. コンポーネント構成

```mermaid
flowchart LR
  subgraph Client["呼び出し方"]
    CLIENTRY["scripts.vertical_slice.main\n(単発CLI実行)"]
    HTTP["HTTPクライアント (curl等)"]
  end

  subgraph Server["scripts/server (FastAPI)"]
    APP["app.py\n6+1本のHTTPエンドポイント"]
    SM["SessionManager\nsession_id -> CliExecutor"]
    ORCH["orchestrator.py\nrun_story / resume_story"]
  end

  subgraph Core["scripts/vertical_slice"]
    RUNNER["runner.py\nrun_steps / write_and_test"]
    STEPR["step_runner.py\n1ステップ=マルチターンループ"]
    TOOLS["tools.py\nTOOL_SCHEMAS"]
    CE["cli_executor.py\nCliExecutor"]
  end

  subgraph External["外部"]
    PWCLI["playwright-cli (子プロセス)"]
    BROWSER["ブラウザ"]
    OPENAI["OpenAI Responses API"]
  end

  subgraph Storage["tests/generated/"]
    SPECTS["*.spec.ts"]
    HIST["{stem}.history/\n*.steps.jsonl, *.tasks.jsonl"]
    REC["{stem}.recordings/\n*.png"]
    FAIL["*.failure-notes.json"]
  end

  CLIENTRY --> RUNNER
  HTTP --> APP
  APP --> SM
  APP --> ORCH
  ORCH --> RUNNER
  RUNNER --> STEPR
  STEPR --> TOOLS
  STEPR --> OPENAI
  TOOLS --> CE
  CE --> PWCLI
  PWCLI --> BROWSER
  RUNNER --> SPECTS
  RUNNER --> HIST
  RUNNER --> REC
  RUNNER --> FAIL
```

## 3. 1ステップ実行のシーケンス

「1タスク＝1ステップ＝1フレッシュコンテキスト」がどう動くか。

```mermaid
sequenceDiagram
  participant Runner as runner.py / orchestrator.py
  participant CLI as CliExecutor
  participant PW as playwright-cli
  participant AI as OpenAI Responses API

  Runner->>CLI: snapshot_text()
  CLI->>PW: snapshot --json
  PW-->>CLI: snapshot
  CLI-->>Runner: snapshot

  loop 1ステップ内 (最大 MAX_TURNS_PER_STEP=8 ターン)
    Runner->>AI: build_input(残りステップ + snapshot)\n※ previous_response_id は使わず毎回ゼロから
    AI-->>Runner: tool call
    alt 操作系ツール (navigate/click/fill/...)
      Runner->>CLI: execute_tool(...)
      CLI->>PW: 対応コマンド実行
      PW-->>CLI: 生成コード + 結果
      CLI-->>Runner: ActionResult
      Runner->>CLI: snapshot_text() (次ターン用)
    else finish_step(status=done|blocked)
      Runner-->>Runner: ステップ終了
    end
  end
```

## 4. リトライ・失敗時のフロー（Step6）

```mermaid
flowchart TD
  S["ステップ実行 attempt=1"] -->|"finish_step(done)"| Done["tasks.jsonlへ記録"]
  S -->|"失敗 (cli_error / blocked / max_turns_exceeded)"| Chk1{"attempt < MAX_STEP_ATTEMPTS=3?"}
  Chk1 -- yes --> Retry["再試行 attempt+=1\n(ブラウザ状態はロールバックしない)"]
  Retry --> Chk2{"成功?"}
  Chk2 -- yes --> Done
  Chk2 -- no --> Chk1
  Chk1 -- "no (最終試行も失敗)" --> Diag["console / requests / snapshot / screenshot を追加取得"]
  Diag --> Stop["failure-notes.json に診断情報付きで記録し停止\n(仕様/回帰バグの判断は人間に委ねる)"]
  S -->|"reason=disallowed_url"| StopNow["残り試行を消費せず即座に打ち切り"]
```

## 5. セッションのライフサイクル（Step2/7/8）

```mermaid
stateDiagram-v2
  [*] --> Created: "POST /sessions\n(max_sessions未満なら作成)"
  Created --> Running: "GET /snapshot, POST /command, POST /run"
  Running --> Running: "アクティビティ更新\n(get() / is_stop_requested())"
  Running --> Stopping: "POST /sessions/{id}/stop\n(threading.Event をセット、即座に返る)"
  Stopping --> Closed: "ステップ境界 or リトライ試行境界で検知し\n実行中の /run が停止して終了"
  Running --> Closed: "DELETE /sessions/{id}"
  Running --> Closed: "idle_timeout_seconds 超過\n(バックグラウンドの sweep スレッドが自動close)"
  Closed --> [*]
  Closed --> Created: "POST /sessions/resume\n(新しい session_id, tasks_log から早送り)"
```
