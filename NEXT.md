# NEXT

現状（[FEATURES.md](FEATURES.md)）に対して、あると良いがまだ無い機能・部分的にしか対応していない機能をまとめる。SPEC.md 7章の通り安全性は元々「完全にスコープ外」という前提があるため、そこに属する項目は「未対応」ではなく設計上の割り切りとして記載する。

## 部分的にしか対応していない

- **進捗確認は完全にファイルベース**: `{stem}.history/*.steps.jsonl`/`*.tasks.jsonl`・スクリーンショット・`cost_summary.py --html` の静的コストダッシュボードのみで、実行中の進捗をライブ表示するビューア・Web UIは無い（SPEC.md 8章の「具体的な確認手段はUI含めて要検討」に対する現状の答え）。コストダッシュボードもrun終了後に手動で生成する一回きりのHTML出力で、自動更新はしない
- **`/run` はリクエスト内で同期実行**: ストリーミング配信APIが無く、HTTPクライアントは完了まで応答を待つ必要がある。長いストーリーだとリクエストが長時間ブロックする
- **強制停止は粒度が粗い**: `POST /sessions/{id}/stop` はステップ境界とリトライ試行境界でしか反映されず、実行中の1回のAI API呼び出し自体を割り込みで中断できない
- **リトライはブラウザ状態をロールバックしない**: 前の失敗試行が実際に行った操作の結果を引き継いだまま次の試行に進むため、副作用のある操作（送信済みフォーム等）が絡むステップのリトライは意図通りにならない場合がある
- **`add_expectation` が対応するmatcherが2種類のみ**: `toBeVisible`/`toHaveText` のみで、`toHaveValue`/`toBeChecked`/`toHaveCount`等は無い。AIが検証したい内容によっては表現できない
- **AIが呼べる操作の種類が限定的**: `navigate`/`click`/`fill`/`press`/`select`/`check`/`uncheck`/`hover`/`add_expectation`のみ。ドラッグ&ドロップ・ファイルアップロード・ダイアログ操作（`dialog-accept`等）は `playwright-cli` 自体には存在するがツールとして配線されていない（`edge-unsupported-action-demo.yaml`/`edge-unsupported-drag-demo.yaml`が「未対応であることを検知してblockedになる」ことを確認する目的のフィクスチャとして存在する）

## まだ無い

- **同一セッションへの並行アクセス制御**: 複数HTTPリクエストが同じ`session_id`に同時に来た場合の競合は未対応（Step2から変わらないスコープ外）。Step8で入ったロックは `SessionManager.create()`/`close()` のみを対象にした別問題（バックグラウンドの自動closeスレッドとの競合防止）
- **同一ストーリー名の並行実行時の出力衝突**: `/run`の出力パスは`session_id`ではなく`story.name`ベース（`tests/generated/{story.name}.spec.ts`）のため、同じストーリーを複数セッションで並行実行すると生成ファイルが競合する
- **停止済みセッションの「再開待ち」化（unstop相当API）**: 一度`/stop`された`session_id`はそのまま使えなくなり、`POST /sessions/resume`で新しい`session_id`を発行するフローしか無い
- **認証が必要なサイトへの対応**: ログイン情報の入力・保存は行わない設計判断（SPEC.md 7章）。継続的にスコープ外
- **破壊的操作（決済確定・退会等）への個別ガードレール**: URL許可リスト以外の、操作内容そのものに基づくガードは無い。継続的にスコープ外
- **マルチユーザー・権限管理**: 誰がどのセッションを開始・停止できるかの制御は無い。継続的にスコープ外
- **`resources/custom_pages` のクラウドデプロイ**: ローカルnginx配信のみで、GCP等へのTerraformデプロイは未実装（`.claude/rules/custom-pages.md`に置き場だけ言及あり）
- **CI連携**: 生成された`.spec.ts`を継続的インテグレーションで自動実行する仕組みは無い（`npx playwright test`を手動/`make test`で叩く運用のみ）
