# Step 1: Story YAMLへの`intent`フィールド追加

> [00-overview.md](00-overview.md) の続き。実装・実行済み。

## やること

- `Story`/`load_story`（`scripts/vertical_slice/story.py`）に、シナリオの検証意図（何をテストしたいか・何ができることを確認したいか）を書く必須フィールド`intent`を追加する。Step2以降で追加する全ての新規stories（`02`〜`05`）は、このフィールドを最初から埋めて作成する。
- 既存の追跡対象3ファイル（`search-demo.yaml` / `search-demo-branch.yaml` / `custom-pages-demo.yaml`）にも`intent`を追記する。あわせて、`search-demo-branch.yaml`にあった「なぜ`seed_url`が実質未使用か」という長めのインラインコメントを、`intent`フィールドでは説明しきれない実装上の注記だけを残す形に整理し直す（内容の重複を解消する）。

## 読むべきファイル・実行推奨Grep

**既存のStoryロード実装・利用箇所を確認するため（優先度: 高）**
- 読む: `scripts/vertical_slice/story.py` — `Story`/`Step`データクラスと`load_story`の現在の実装（`name`は`.get()`によるフォールバック付き、`seed_url`/`steps`は`data[...]`による必須アクセス。`intent`は後者と同じ必須アクセスの作法に揃える）
- Grep: `load_story\(|Story\(` — `scripts/vertical_slice/main.py`・`scripts/server/session_manager.py`など、`Story`を生成・消費する全箇所を洗い出し、フィールド追加による影響範囲（無いはず）を確認する

**影響を受ける既存YAML・ドキュメントを確認するため（優先度: 高）**
- 読む: `scripts/stories/search-demo.yaml` / `search-demo-branch.yaml` / `custom-pages-demo.yaml` — 追記対象の現在の内容
- 読む: `.claude/rules/vertical-slice-runner.md` の`story.py`の説明行、`.claude/plan/main/01-vertical-slice.md`の同等の記述 — スキーマを説明している箇所（前者は仕様の生きたドキュメントとして更新し続けている実績があり、`intent`もここに追記する。後者は「実装・実行済み」の当時のスナップショットとして扱われており、Step5時点でも更新されていないため、本ステップでも追記しない）

## 触るファイル

### 変更
- `scripts/vertical_slice/story.py` — `Story`に`intent: str`フィールドを追加。`load_story`で`data["intent"]`として必須読み込みする
- `scripts/stories/search-demo.yaml` / `search-demo-branch.yaml` / `custom-pages-demo.yaml` — `intent`フィールドを追記。`search-demo-branch.yaml`はインラインコメントを整理
- `.claude/rules/vertical-slice-runner.md` — `story.py`の説明行に`intent`フィールドの役割（ドキュメンテーション専用、実行時ロジックには使わない）を追記

## 決定事項・注意点／落とし穴

| 決定 | 理由 |
|---|---|
| `intent`は`name`（`.get()`によるフォールバックあり）ではなく`seed_url`/`steps`と同じ必須フィールド（`data["intent"]`、無いと`KeyError`）にする | 「書けるフィールド」を用意するだけでなく、新規stories追加時に書き忘れを機械的に防ぐため。既存stories側の追記漏れが無いことは本ステップの実行で担保する |
| `intent`は生成される`.spec.ts`には一切反映しない（`runner.write_spec_file`は変更しない） | 実行時パイプライン（Step4で完成済みのコード組み立てロジック）に手を入れず、`intent`はあくまで人間・AI読者向けのドキュメンテーション専用フィールドとして閉じるため。反映させたくなった場合は改めて別プランで検討する |
| `search-demo-branch.yaml`の既存コメントは全文削除せず、「`seed_url`が実質未使用である」という実装上の注記1行だけ残し、詳細説明は`intent`と`.claude/plan/main/05-recording-and-resume.md`への参照に譲る | コメントと`intent`で同じ説明を二重に持たない。ただし`seed_url`が使われない理由はYAML単体を読んだ人がその場で分かるべき情報なので、注記自体は消さない |
| `.claude/plan/main/01-vertical-slice.md`は更新しない | この文書は「実装・実行済み（2026-07-18）」という当時のスナップショットとして書かれており、Step5実装時点でも追記されていない（生きたスキーマ説明は`.claude/rules/vertical-slice-runner.md`に一本化されている）。ここに追記すると二重管理になる |

## `.claude/rules` 更新ポイント

- `vertical-slice-runner.md`（既存ファイルへの追記、対象パスに変更は無いのでフロントマター変更は不要）
  - `story.py`の説明行に`intent`フィールド（必須・ドキュメンテーション専用・欠落時`KeyError`）を追記
