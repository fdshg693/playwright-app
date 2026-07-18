.DEFAULT_GOAL := help

STORY   ?=
SESSION ?= $(basename $(notdir $(STORY)))
OUT     ?= tests/generated/$(SESSION).spec.ts
HOST    ?= 127.0.0.1
PORT    ?= 8000
COST_TARGET ?= tests/generated/
COST_HTML   ?= cost_dashboard.html
RESUME_TASKS_LOG ?=
RESUME_BEFORE    ?=

.PHONY: help setup env install-browsers serve-pages server slice resume test cost cost-html clean

help: ## 主要コマンド一覧を表示
	@echo "主要コマンド:"
	@echo "  make setup                       依存関係インストール (uv sync + npm install)"
	@echo "  make env                         .env を .env.example から作成（既に存在すれば何もしない）"
	@echo "  make install-browsers            Playwright用ブラウザバイナリをインストール (npx playwright install)"
	@echo "  make serve-pages                 カスタムページをnginxでローカル配信 (npm run serve:pages)"
	@echo "  make server [HOST=.. PORT=..]    セッションサーバー起動 (scripts/server/main.py)"
	@echo "  make slice STORY=scripts/stories/<name>.yaml [SESSION=.. OUT=..]"
	@echo "                                    vertical_slice を実AI APIに対して実行（課金注意、実行前に確認すること）"
	@echo "  make resume STORY=.. RESUME_TASKS_LOG=<out>.tasks.jsonl RESUME_BEFORE=<step_id> [SESSION=.. OUT=..]"
	@echo "                                    記録済みtasks.jsonlから途中再開/分岐実行する（課金注意、実行前に確認すること）"
	@echo "  make test [PW_ARGS=..]           npx playwright test を実行"
	@echo "  make cost [COST_TARGET=..]       cost_summary.py でトークン/コストを集計 (デフォルト: tests/generated/)"
	@echo "  make cost-html [COST_TARGET=.. COST_HTML=..]"
	@echo "                                    run-history を自己完結HTMLダッシュボードとして書き出す (デフォルト出力: cost_dashboard.html)"
	@echo "  make clean                       __pycache__ / playwright-report / test-results を削除"

setup: ## Python/Node の依存関係をインストール
	uv sync
	npm install

env: ## .env を .env.example から作成する（既存なら何もしない）
	[ -f .env ] || cp .env.example .env

install-browsers: ## Playwright用ブラウザバイナリをインストールする
	npx playwright install

serve-pages: ## resources/custom_pages を nginx でローカル配信（フォアグラウンド、Ctrl+Cで停止）
	npm run serve:pages

server: ## セッションサーバーを起動する
	uv run python -m scripts.server.main --host $(HOST) --port $(PORT)

slice: ## vertical_slice を実ストーリーYAMLに対して実行する（実課金APIコール、実行前に必ずユーザーへ確認すること）
	@if [ -z "$(STORY)" ]; then \
		echo "STORY=scripts/stories/<name>.yaml を指定してください（例: make slice STORY=scripts/stories/search-demo.yaml）"; \
		exit 1; \
	fi
	uv run python -m scripts.vertical_slice.main --story $(STORY) --session $(SESSION) --out $(OUT) -v

resume: ## 記録済みtasks.jsonlから途中再開/分岐実行する（実AI APIコール、実行前に必ずユーザーへ確認すること）
	@if [ -z "$(STORY)" ] || [ -z "$(RESUME_TASKS_LOG)" ] || [ -z "$(RESUME_BEFORE)" ]; then \
		echo "STORY=scripts/stories/<name>.yaml RESUME_TASKS_LOG=<out>.tasks.jsonl RESUME_BEFORE=<step_id> を指定してください"; \
		exit 1; \
	fi
	uv run python -m scripts.vertical_slice.main --story $(STORY) --session $(SESSION) --out $(OUT) \
		--resume-tasks-log $(RESUME_TASKS_LOG) --resume-before-step $(RESUME_BEFORE) -v

test: ## 生成済みPlaywrightテストを実行する
	npx playwright test $(PW_ARGS)

cost: ## トークン消費・概算コストを集計する
	uv run python -m scripts.internal.cost_summary $(COST_TARGET)

cost-html: ## run-history を自己完結HTMLダッシュボードとして書き出す
	uv run python -m scripts.internal.cost_summary $(COST_TARGET) --html $(COST_HTML)

clean: ## __pycache__ / playwright-report / test-results を削除する
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	rm -rf playwright-report test-results
