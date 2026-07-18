# scripts/stories/

`scripts/vertical_slice/story.py` の `load_story()` が読み込むstory YAML置き場。1ファイル＝1シナリオで、`python -m scripts.vertical_slice.main --story scripts/stories/<name>.yaml` や `scripts/server/` 経由でvertical sliceに流し込む入力になる（責務の詳細は [.claude/rules/vertical-slice-runner.md](../../.claude/rules/vertical-slice-runner.md)）。

## YAMLの書式

```yaml
name: <シナリオ名。省略時はファイル名（拡張子抜き）>
intent: >
  このシナリオで何を確認したいか（自由記述、複数行可）。
seed_url: "http://localhost:8080/xxx.html"
steps:
  - id: 1
    instruction: <1ステップ分の指示。1行で書く>
  - id: 2
    instruction: <...>
```

- `name` / `seed_url` / `steps` / `intent` は `Story`/`Step`（`story.py`）のフィールドにそのまま対応する。`intent` は必須（欠けると`load_story`が`KeyError`で落ちる）。
- `intent` は実行ロジックに一切使われない人間・AI読者向けドキュメンテーション専用フィールド。何を検証したい・できることを確認したいシナリオかを書く。

## `steps[].instruction` は必ず1行で書く

**ここが今回ハマった点。** `runner.py` の `write_spec_file` は各ステップの生成コード先頭に

```python
f"// {block.step.id}. {block.step.instruction}"
```

というf-stringでコメント行を組み立てる（改行のエスケープや複数行対応はしていない）。`instruction` に生の改行（YAMLの `|` ブロックリテラルなど）を入れると、2行目以降が `//` の付かない生テキストとしてそのまま `.spec.ts` に書き出され、TypeScriptの構文エラーになる。`npx playwright test` は "No tests found" ではなく直接 `SyntaxError` で落ちる。

- `instruction` は常に1行の文字列（YAMLの通常のスカラーまたは `>`（折り畳み）で書いても改行を残さない形）にする。
- `intent` はこの制約を受けない（生成コードに一切反映されないため、`>` で複数行に折り畳んでよい）。
- ステップの操作対象（`fill`など）に複数行の値を入力させたい場合は、instruction自体を1行にしたまま、値の中の改行を `\n` という2文字のリテラルとして書き、「`\n`は実際の改行として入力する」のようにAIへの解釈指示を添える。AIは`fill`ツール呼び出し時にその`\n`を実際の改行に変換して渡せる（`advanced-form-demo.yaml`のstep 2が実例）。

```yaml
# NG: instructionに生の改行が入り、生成される.spec.tsが壊れる
steps:
  - id: 2
    instruction: |
      欄に以下を入力する:
      1行目
      2行目

# OK: instructionは1行のまま、値内の改行は \n という文字で表現する
steps:
  - id: 2
    instruction: 欄に「1行目\n2行目」を入力する（\nは実際の改行として入力する）
```

## resume/分岐用シナリオ

`search-demo-branch.yaml` のように、別ストーリーの `.tasks.jsonl` から `resume` して分岐実行させるためだけのYAMLは以下の点で通常のシナリオと異なる：

- `steps[].id` は分岐元ストーリーと連番である必要はない（分岐元の続きの番号から始めてよい）。
- `seed_url` は実行時に使われない（`run-code`によるreplayで代替される）が、`Story`データクラスが必須フィールドとして要求するためダミー値を残す。理由をコメントで明記しておく。