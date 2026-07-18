# AI に画面テストを効率よくさせるためのツール作成

## 概要

- 人間が自然言語で、テストストーリーを記載する
- AI が細かいステップのタスクに分割し、1タスクごとにフレッシュなコンテキストで実行する
- Playwright CLI を使って、実際に画面を操作しながらテストを進める
- 最終成果物として、コード化された（そのまま再実行できる）Playwrightテストが出来上がる

## なぜこの構成か

- **コンテキスト汚染の回避 / コスト削減**
  1タスク＝1回のフレッシュなモデル呼び出しにすることで、余計な過去の会話に引きずられず、かつ呼び出しごとのコストを抑えられる
- **柔軟な再実行**
  タスクを細かく分けて記録を残すことで、途中のタスクからの再実行や、別パターンのテストへの分岐がしやすくなる
- **人間による監督**
  各タスク終了時に記録（スクリーンショット・生成コード）を残すことで、途中経過・最終結果を人間が確認でき、必要であれば強制停止もできる
- **既存資産の活用**
  ブラウザ操作・コード生成には自作せず [Playwright CLI](.claude/skills/playwright-cli/SKILL.md) を利用する。MCPのような閉じたプロトコルではなく薄いCLI呼び出しなので、間に独自ロジック（タスク管理・記録・再開など）を挟んでもアダプトコストが小さい

## 全体の流れ

```
人間: テストストーリー（自然言語）
  │
  ▼
サーバー: Playwright CLI 経由でブラウザセッションを起動・維持
  │
  ▼
AI: 1タスクずつ、フレッシュなコンテキストで
    「残りのストーリー」＋「現在の画面情報」を受け取り、
    Playwright CLI コマンドで画面を操作する
  │
  ▼
サーバー: 各タスクの操作ログ・スクリーンショット・生成コードを記録
  │
  ▼
最終成果物: Playwrightのテストコード（.spec.ts）
```

## 詳細仕様

タスク分割の設計、セッション管理、失敗時のふるまい、スコープ外事項などの詳細は [SPEC.md](SPEC.md) を参照。

## 進め方

実装をどう段階的に進めるかは [plan/](plan/) 以下にステップごとに記載。

## Step1（縦の一本通し）の実行方法

[plan/detail/01-vertical-slice.md](plan/detail/01-vertical-slice.md) の実装。

```bash
uv sync                       # Python依存関係のインストール
npm install                   # @playwright/test のインストール
cp .env.example .env
```

`.env` を開き、`OPENAI_API_KEY=` の行に自分のAPIキーを書き足す（例: `OPENAI_API_KEY=sk-...`）。
実行時に `main.py` が起動直後に読み込む（`load_dotenv()`）ので、シェルの環境変数として別途 `export` する必要はない。
mise等でプロジェクトの環境変数を管理している場合は、`.env` の代わりにそちら経由で `OPENAI_API_KEY` をセットしても動く（`os.environ` から読むのは同じため）。

```bash
uv run python -m scripts.vertical_slice.main --story scripts/stories/search-demo.yaml
```

成功すると `tests/generated/search-demo.spec.ts` が生成され、`npx playwright test` が自動実行される。
途中で停止した場合は `tests/generated/search-demo.failure-notes.json` に原因が記録される。
