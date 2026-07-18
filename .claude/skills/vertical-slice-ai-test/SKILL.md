---
name: vertical-slice-ai-test
description: Run scripts/vertical_slice/main.py end-to-end against a real AI API (real, billed calls) to verify a story YAML actually completes. Use when asked to "actually run"/"verify end-to-end"/"実際に実行して確認" a vertical slice story, not for unit-level or mocked checks.
allowed-tools: Bash(python:*) Bash(python3:*) Bash(npx playwright:*) Bash(npm run serve:pages:*)
---

# vertical_slice の実AI呼び出しテスト

`scripts/vertical_slice/main.py` を実ストーリーYAMLに対して最初から最後まで走らせ、完走するかを確認する手順。ユニットテストではなく、実際のAI API（`.env`の`OPENAI_API_KEY`）に課金される本番相当の呼び出しを行う。責務・ログ形式の詳細は [[vertical-slice-runner]] ルール（`.claude/rules/vertical-slice-runner.md`）を先に読むこと。

## 実行前に確認すること

- **これは実課金APIコールである。** 実行前に必ずユーザーに確認を取る（AskUserQuestion等）。無条件に自動実行しない。
- `.env` に有効な `OPENAI_API_KEY`（および必要なら `OPENAI_BASE_URL`/`AI_MODEL`。MiniMax等OpenAI互換エンドポイントを使う場合はこの2つも設定されているか確認）があるか確認する。
- 対象ストーリーの `seed_url` がローカルカスタムページ（`http://localhost:8080/...`）を指している場合、先に `npm run serve:pages` でnginxを起動しておく（[.claude/rules/custom-pages.md](../../rules/custom-pages.md)参照）。起動していないと最初の`open`で失敗する。

## 実行コマンド

```bash
python -m scripts.vertical_slice.main \
  --story scripts/stories/<name>.yaml \
  --session <name> \
  --out tests/generated/<name>.spec.ts \
  -v
```

- `--session` はplaywright-cliのセッション名。ストーリーごとに変えておくと、並行実行時や過去セッションの残骸との衝突を避けやすい。
- `-v` (`--verbose`) を付けるとDEBUGログになり、各ターンのAPIリクエスト/レスポンスも流れる。ステップの完走有無だけ見たいなら省いてよい。

## 落とし穴: `--out` は必ず `.spec.ts` で終わらせる

`runner.py` の `write_spec_file` は `--out` に渡されたパスへ**そのまま**書き込む（拡張子チェックなし）。生成後に自動実行される `npx playwright test <out_path>` は、渡されたパスを `playwright.config.ts` の `testMatch` パターン（デフォルトは `*.spec.ts` 系）でテストファイルとして認識できて初めて実行できる。

`--out tests/generated/custom-pages-demo`（拡張子なし）のように指定すると:
- AIパイプライン自体は全ステップ完走し、`tests/generated/custom-pages-demo` に生成コードは書き出される
- しかし直後の `npx playwright test` が **"No tests found"** で失敗する（ファイルパスを直接渡していても、拡張子がテストファイルパターンに一致しないと発見されない）
- ログ上は `all steps completed` と出ているのに、`npx playwright test failed` という一見矛盾する結果になり紛らわしい

**対策**: 常に `--out tests/generated/<name>.spec.ts` のようにフルの拡張子まで指定する。

もし既に拡張子なしで実行してしまった場合、**AIパイプラインを再実行して課金し直す必要はない**。生成済みファイルをリネームして手動でテストを流せば足りる:

```bash
mv tests/generated/<name> tests/generated/<name>.spec.ts
mv tests/generated/<name>.steps.jsonl tests/generated/<name>.spec.steps.jsonl  # 存在する場合のみ
npx playwright test tests/generated/<name>.spec.ts
```

## 出力の見方

- コンソールログ: 全ステップ完走時は `all steps completed`、途中で失敗すると `stopped early with failure notes; skipping npx playwright test` が出る。
- `<out>.spec.ts` — 収集した生成コードを1つの `test()` にまとめたPlaywrightテスト。
- `<out>.failure-notes.json` — 失敗があった場合のみ生成される。`step`/`reason`（`blocked`/`cli_error`/`no_tool_call`/`max_turns_exceeded`）を見て、どのステップで何が起きたか特定する。
- `<out>.steps.jsonl` — 全ターンの生ログ（プロンプト・モデル出力・ツール結果・`usage`）。停止理由を後から読み返す用。`tests/generated/`直下は`.gitignore`済みなので、リポジトリを汚さず自由に生成・破棄してよい。

## トークン消費・概算コストを集計する

`<out>.steps.jsonl` の各行の `usage` をステップ単位/全体で集計するには `scripts/internal/cost_summary.py` を使う:

```bash
python -m scripts.internal.cost_summary tests/generated/<name>.spec.steps.jsonl
```

単価は同階層の `scripts/internal/model_pricing.csv`（`model,input_price_per_1m,output_price_per_1m,cached_input_price_per_1m`、USD per 1M tokens）から、ログに記録された `model` で行を引いて使う。該当行がなければ `default` 行（初期値は全て0）にフォールバックする。実際の単価がわかったらそのモデル名の行をCSVに追記すること。ログが `model` フィールドを持たない古い形式の場合や、別モデルの単価で試算したい場合は `--model <name>` で上書きできる。

## snapshotサイズ・トークン消費を比較する

複数ストーリー（例: 外部サイト対象 vs 自作ページ対象）で1ステップあたりのsnapshotサイズを比較したい場合、`<out>.steps.jsonl` の各行から `snapshot` フィールドの長さを集計する:

```bash
python3 -c "
import json

def snapshot_lens(path):
    lens = []
    with open(path) as f:
        for line in f:
            obj = json.loads(line)
            def walk(o):
                if isinstance(o, dict):
                    for k, v in o.items():
                        if k == 'snapshot' and isinstance(v, str):
                            lens.append(len(v))
                        else:
                            walk(v)
                elif isinstance(o, list):
                    for v in o:
                        walk(v)
            walk(obj)
    return lens

lens = snapshot_lens('tests/generated/<name>.spec.steps.jsonl')
print('n=', len(lens), 'avg=', sum(lens) / len(lens), 'max=', max(lens))
"
```
