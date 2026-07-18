# Step 1 詳細版: 縦の一本通し（実装計画）

> [big_plans/01-vertical-slice.md](../../../big_plans/01-vertical-slice.md) の詳細版。[00-overview.md](00-overview.md)参照。

## やること

- big_plans Step1（人間が手動でAIとplaywright-cliを仲介し、コアループの前提が成立するかを確認する）を、実際に動く最小スクリプトで置き換える。人間による手動仲介はやめ、Python（+ 必要な範囲でのNode.js/npm呼び出し）でループそのものを自動化する。
- 対象範囲はbig_plans Step1と同じく、シナリオ1本のみ・ブラウザセッション1本のみに留める。複数タスクのオーケストレーション基盤（Step3）、記録・再開（Step5）、リトライ（Step6）、人間向け監視UI（Step7）、安全策（Step8）は作らない。
- ネットワークサーバー化はしない。「AIに渡すツール定義」と「playwright-cli実行」はコード上のモジュール境界（`CliExecutor`）としてのみ分離し、同一Pythonプロセス内で完結させる（Step2でこの境界をそのままネットワークサーバーへ切り出す想定）。
- ストーリーのステップ分割自体は人間が事前にYAMLで定義し、AIには分割済みステップだけを渡す（動的な分割・完了判定はStep3のスコープ）。
- 実装・実行済み（2026-07-18）。詳細は「実行結果」参照。

## 読むべきファイル・実行推奨Grep

**既存実装を確認するため（優先度: 高。実装済みにつき、変更・拡張時はまずここを読む）**
- 読む: `scripts/vertical_slice/main.py` — ループ本体（`run_vertical_slice` / `run_step`）。1ステップ内で複数ターンのtool-callingループを回す実装
- 読む: `scripts/vertical_slice/tools.py` — AIに渡すtool定義（`navigate`/`click`/`fill`/`press`/`select`/`check`/`uncheck`/`hover`/`finish_step`）
- 読む: `scripts/vertical_slice/prompts.py` — system/developerプロンプトの構成
- 読む: `scripts/stories/search-demo.yaml` — ステップ分割のYAML定義の実例

**関連仕様を確認するため（優先度: 中）**
- 読む: `SPEC.md` 2章 — 「1タスク＝1フレッシュコンテキスト」の原則（このステップがコード上で保証する対象）
- 読む: `.claude/skills/playwright-cli/references/test-generation.md` — 生成コード回収の作法。`expect`アサーションの組み込みは対象外（Step4）

**次ステップへの引き継ぎを確認するため（優先度: 低）**
- 読む: `big_plans/02-server-skeleton.md` — このステップの`CliExecutor`境界をどうネットワークサーバーへ切り出すか
- 読む: `big_plans/03-task-orchestration.md` — このステップの`finish_step`設計・多ターンループが、タスク完了判定ロジックの叩き台になる

## 触るファイル

### 新規（実装済み）
- `scripts/vertical_slice/main.py` — ループ本体・エントリポイント
- `scripts/vertical_slice/cli_executor.py` — playwright-cliをsubprocessで叩く薄いラッパー
- `scripts/vertical_slice/tools.py` — Responses APIに渡すtool（JSON Schema）定義
- `scripts/vertical_slice/prompts.py` — system/developerプロンプトのテンプレート
- `scripts/vertical_slice/story.py` — ストーリー・ステップ定義の読み込み
- `scripts/vertical_slice/config.py` — モデル名などの環境変数読み込み
- `scripts/stories/search-demo.yaml` — デモシナリオのステップ定義
- `tests/generated/search-demo.spec.ts` — 最終成果物（`npx playwright test`で実行可能）

## 決定事項・注意点／落とし穴

| 決定 | 理由 |
|---|---|
| ネットワークサーバーは作らない。「ツール定義」と「playwright-cli実行」はコード上のモジュール境界（`CliExecutor`）としてのみ分離する | SPEC.mdの「サーバー」責務（セッション維持・実行・記録）を先取りしつつ、HTTP等の越境は挟まない |
| OpenAI Responses APIは`previous_response_id`を使わず、タスク（ステップ）ごとに`input`をゼロから組み立てる | SPEC.md 2章「1タスク＝1フレッシュコンテキスト」を隠れた状態に依存せずコード上で厳密に保証するため |
| 1ステップ＝フレッシュコンテキストだが、ステップ内は複数ターンのtool-callingループにする（当初の「1ステップ＝1回の`responses.create()`」案は破棄） | 実行結果、1レスポンス内に複数tool callを確実に含めさせることができず、`finish_step`が呼ばれないまま失敗扱いになるケースが発生した。実行結果と最新snapshotを次ターンへ渡す多ターンループへ変更して解消（下記「実行結果」参照） |
| `finish_step`は他の操作系tool callとは別ターンで単独に呼ばせる | モデルが操作結果を確認せずに「完了」を見込みで宣言することを防ぐため |
| 確認のみのステップでは`expect`アサーションを生成しない（`finish_step`の`observation`に根拠を書かせるだけ） | アサーション生成は`test-generation.md`の方針に沿ってStep4のスコープとし、このステップには含めない |

## 実行結果

- 2026-07-18、`search-demo.yaml`のステップ1で、モデルが`click`は呼んだものの同じレスポンス内で`finish_step`を呼ばず、`finish_step_missing`としてfailure noteに記録して停止した（詳細: [big_plans/01-vertical-slice.md](../../../big_plans/01-vertical-slice.md) 実行結果メモ）。
- 対応として多ターンループへ変更（上記決定事項参照）。再実行後はステップ1〜3が正常完了し、ステップ4は`blocked`で停止した（検索モーダルが一覧を出さず候補ページへ直接遷移したため、モデルが「現在のsnapshotだけでは検索結果表示を確認できない」と正しく判断）。ツール呼び出し設計の問題ではなく、シナリオ（`search-demo.yaml`）の想定と実際のサイト挙動のズレによるもの。
- 結論: 「現在の画面情報だけで次のタスクが判断できる」という前提（SPEC.md 2章）は、ステップ1〜3では成立を確認できた。ステップ4のような「操作直後の遷移が想定と異なる」ケースは、スコープ外の境界線の一例として記録した。

## `.claude/rules` 更新ポイント

- 現時点では対象パスに該当する既存ルールが無く、`scripts/`配下の実装パターンもこのステップの1例のみのため、新規ルールファイルはまだ作成しない。Step2以降で`scripts/`配下の構成（サーバー化後のモジュール分割）が固まった時点で新設を検討する。
