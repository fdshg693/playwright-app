# Step 4 詳細版: 生成コードの組み立て

> [big_plans/04-code-generation-assembly.md](../../../big_plans/04-code-generation-assembly.md) の詳細版。[00-overview.md](00-overview.md)参照。

## やること

- AIが呼べるツールに `add_expectation` を1つ追加する。確認のみのステップ（「〜が表示されることを確認する」等）で `finish_step(status="done")` を呼ぶ前に、現在のsnapshotのrefと期待する検証方法（`toBeVisible` / `toHaveText`）を指定して呼び出す。実行すると `playwright-cli generate-locator <ref> --raw` で安定ロケータを、`toHaveText` の場合はさらに `playwright-cli eval "el => el.textContent" <ref> --raw` で期待テキストを取得し、`await expect(page.<locator>).<matcher>(...)` 相当のTypeScript文を組み立てて返す。これはStep1で「Step4のスコープとして意図的に外した」`expect`アサーション生成そのものにあたる（[01-vertical-slice.md](01-vertical-slice.md) 決定事項参照）。
- `add_expectation` は他の操作系ツール（`click`/`fill`等）と同じ「アクション系」として扱う。`finish_step`のように単独ターンを強制する特別扱いはしない（ロジックはtools.py/prompts.pyの追加だけで完結させ、`step_runner.run_step`のターン制御には手を入れない）。
- `runner.write_spec_file`（Step1実装）を、ステップ境界を保持した入力を受け取るように変更し、各ステップのコードの先頭に `// {step.id}. {step.instruction}` コメントを付与する（[test-generation.md](../../skills/playwright-cli/references/test-generation.md) 2.2節の規約）。現状は全ステップの生成コードをフラットな `list[str]` にextendして1つのtest内に流し込んでいるだけで、ステップ区切りが失われている。
- `npx playwright test` による自動実行確認（`runner.run_playwright_test`）はStep1で既に実装済みのため変更しない。

## 読むべきファイル・実行推奨Grep

**再利用・変更する既存実装を確認するため（優先度: 高）**
- 読む: `scripts/vertical_slice/tools.py` の `TOOL_SCHEMAS` / `execute_tool` / `_SIMPLE_REF_COMMANDS` — 既存ツールの定義・dispatchパターン。`add_expectation`もこの形式に合わせて追加する
- 読む: `scripts/vertical_slice/cli_executor.py` の `CliExecutor` — `execute`/`snapshot_text`が使っている `_CODE_BLOCK_RE`（`### Ran Playwright code`ブロックの抽出）は`--raw`出力には使えない点に注意。`--raw`は該当セクションを削って結果値のみを返すため、新設するメソッドは単純に stdout を `.strip()` するだけでよい
- 読む: `scripts/vertical_slice/runner.py` の `write_spec_file` / `run_vertical_slice` — 現状 `generated_code: list[str]` をstepループの中で`.extend()`しているだけで、ステップ境界の情報を`write_spec_file`に渡していない。ここを変更する
- 読む: `scripts/server/orchestrator.py` の `run_story` — `runner.write_spec_file`を`runner.py`と全く同じパターン（`generated_code.extend(step_code)` → 1回だけ`write_spec_file`呼び出し）で使っている。`write_spec_file`のシグネチャ変更はこちらの呼び出し側も同時に直す必要がある
- 読む: `scripts/vertical_slice/prompts.py` の `DEVELOPER_PROMPT` — 「確認のみのステップでは操作系ツールを呼ばず、finish_stepのobservationに根拠を書く」という現行指示を、「`add_expectation`を呼んでから`finish_step`を呼ぶ」指示に書き換える

**アサーション生成の作法を確認するため（優先度: 高）**
- 読む: [test-generation.md](../../skills/playwright-cli/references/test-generation.md) の「0. How generation works」節 — `generate-locator --raw` / `eval "el => el.textContent" --raw` の使い分けと、推奨マッチャー一覧（`toBeVisible`/`toHaveText`/`toHaveValue`/`toBeChecked`/`toMatchAriaSnapshot`）
- 読む: 同ファイル「2.2 Generate one scenario」の `Rules:` — `// N. <step text>` コメントの付与規約
- 読む: `.claude/skills/playwright-cli/references/element-attributes.md` — `eval`の一般的な使い方（`add_expectation`が内部で組み立てる`eval`スクリプトの参考）

**次ステップへの引き継ぎ・影響範囲を確認するため（優先度: 中）**
- 読む: `scripts/stories/search-demo.yaml` のステップ4（「検索結果が表示されていることを確認する（画面操作は不要、確認のみ）」）— このステップで実際に`add_expectation`が呼ばれることを動作確認の基準にする。YAML自体（`Step`に`instruction`のみ）は変更不要
- 読む: `.claude/rules/vertical-slice-runner.md` / `.claude/rules/session-server.md` — 更新対象の現行記述（下記「`.claude/rules`更新ポイント」参照）

## 触るファイル

### 変更
- `scripts/vertical_slice/cli_executor.py` — `CliExecutor`に`generate_locator(ref)`（`generate-locator <ref> --raw`）と`eval_raw(script, ref=None)`（`eval <script> [ref] --raw`）を追加
- `scripts/vertical_slice/tools.py` — `TOOL_SCHEMAS`に`add_expectation`（`ref`/`matcher`(`toBeVisible`|`toHaveText`)/`description`）を追加し、`execute_tool`にdispatchを追加。`generate_locator`/`eval_raw`の結果からTypeScript文を組み立てて`ActionResult(generated_code=...)`として返す
- `scripts/vertical_slice/prompts.py` — `DEVELOPER_PROMPT`の確認のみステップに関する記述を`add_expectation`呼び出し前提に書き換え
- `scripts/vertical_slice/runner.py` — `write_spec_file`の入力をステップ境界つきの構造に変更し、`// {step.id}. {step.instruction}`コメントを挿入。`run_vertical_slice`側もステップ境界を保持したまま`write_spec_file`に渡すよう変更
- `scripts/server/orchestrator.py` — `write_spec_file`のシグネチャ変更に合わせて`run_story`の呼び出し箇所を追随

### 新規
なし（新規ドメイン・新規レイヤーの追加ではなく、既存ツール一式・既存組み立て関数の拡張のみ）

## 決定事項・注意点／落とし穴

| 決定 | 理由 |
|---|---|
| `add_expectation`は`ref`＋`matcher`のenum（`toBeVisible`/`toHaveText`のみ、まず2種）を受け取るだけで、AIに`eval`スクリプトやロケータ文字列そのものを書かせない。`matcher`ごとにこちら側の固定`eval`スクリプト（例: `toHaveText`なら`"el => el.textContent"`）を対応させる | 他の操作系ツールと同じく「snapshot内のrefを指すだけ」に留め、AIの自由記述サーフェスを増やさないため。フリーフォームのJS文字列をAIに書かせると、ロケータ/期待値のハルシネーションや壊れやすいコード生成のリスクが再発する |
| `matcher`は`toBeVisible`/`toHaveText`の2種類のみサポートし、`toHaveValue`/`toBeChecked`/`toBeUnchecked`/`toMatchAriaSnapshot`は現時点で追加しない | `search-demo.yaml`の確認ステップ（検索結果の表示確認）はこの2種で足りる。`toMatchAriaSnapshot`は複数行スナップショットのTS埋め込み（バッククォート・改行のエスケープ）が絡み複雑度が増すため、必要になったシナリオが出てから追加する（YAGNI。Step1の他の決定と同じ判断軸） |
| `add_expectation`は`finish_step`と違い、他の操作系ツールと同じターンで一緒に呼ばれてもよい（`step_runner.run_step`の「finish_stepは単独ターン」制御は変更しない） | ステップ内ループの制御ロジックに手を入れず、`tools.py`/`prompts.py`側の追加だけで機能を成立させるため。`add_expectation`は状態を変更しない読み取り専用の呼び出しなので、他アクションと同時に呼ばれても安全 |
| `eval --raw`が返す文字列はそのままTypeScript文字列リテラルとして埋め込む（`json.dumps`で二重にエスケープしない） | 実AI呼び出しテストで判明：`playwright-cli eval ... --raw`はJS側の戻り値をJSON文字列としてシリアライズ済みの状態（例: `"foo\nbar"`、クォート込み）で返す。ここに`json.dumps(text)`をさらに適用すると、クォート自体がエスケープされて二重エンコードになり生成コードが壊れる（`custom-pages-demo.yaml`実行時に`toHaveText("\"...\"")`という壊れたコードが生成される形で顕在化）。JSON文字列リテラルはTS/JSの文字列リテラルとしてもそのまま有効なので、追加のエスケープ処理は不要 |
| `write_spec_file`はステップ境界（`step.id`/`step.instruction`と、そのステップで集まった生成コード行）を保持した入力を受け取るよう変更し、ステップ間の境界情報が失われないようにする。`cli.open(story.seed_url)`分の初期コードにはステップ番号コメントを付けない | test-generation.md 2.2節の`// N. <step text>`規約に合わせるため。`open()`はストーリーの番号付きステップではないため、無理に番号を割り当てない |
| 出力先は`tests/generated/{story.name}.spec.ts`のままとし、big_plans記載の`tests/<group>/<scenario>.spec.ts`という命名には変更しない | `Story`に`group`という概念が存在せず、導入すると`story.py`・呼び出し元（`main.py`/`session_manager.py`）まで変更が波及する。Step1/Step3で既に確立した出力先の慣習を崩してまでこのステップで対応する理由がない |
| `npx playwright test`による実行確認（`runner.run_playwright_test`）はStep1のまま変更しない | big_plans記載の完了条件のうちこの部分は既に満たされており、Step4で新規に対応すべき差分はアサーション生成とステップコメントの2点のみ |
| `--raw`フラグの付与位置は`generate-locator e5 --raw`（SKILL.mdの例）のようにコマンド固有引数の末尾に付ける形で実装する | SKILL.mdには`playwright-cli --raw eval ...`（先頭）と`playwright-cli generate-locator e5 --raw`（末尾）の両方の例があり、`CliExecutor._run`が`[base_command, "-s=...", *args]`という構造のため、`args`の末尾に`--raw`を足す形が既存コードへの変更量が最小で済む。実装時に`playwright-cli --help`で最終確認すること |

## `.claude/rules` 更新ポイント

- `.claude/rules/vertical-slice-runner.md`（既存ファイルへの追記。対象パスに変更は無いのでフロントマター変更は不要）
  - 「生成物」節の`<out>.spec.ts`の説明に、`// N. <ステップの説明>`コメント付きで組み立てられる旨を追記
  - `tools.py`の説明部分に`add_expectation`ツールの役割（確認ステップで`generate-locator`/`eval`を使い`expect`文を組み立てる、他の操作系ツールと同じ扱い）を追記
- `.claude/rules/session-server.md`（既存ファイルへの追記。対象パスに変更は無い）
  - `orchestrator.py`の説明部分で「`write_spec_file`をStep1と全く同じ形で再利用している」という記述を、ステップ境界つきの新シグネチャに合わせて更新
