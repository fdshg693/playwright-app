.DEFAULT_GOAL := help

STORY   ?=
SESSION ?= $(basename $(notdir $(STORY)))
OUT     ?= tests/generated/$(SESSION).spec.ts
HOST    ?= 127.0.0.1
PORT    ?= 8000
COST_TARGET ?= tests/generated/

.PHONY: help setup env serve-pages server slice test cost clean

help: ## 主要コマンド一覧を表示
	@echo "主要コマンド:"
	@echo "  make setup                       依存関係インストール (uv sync + npm install)"
	@echo "  make env                         .env を .env.example から作成（既に存在すれば何もしない）"
	@echo "  make serve-pages                 カスタムページをnginxでローカル配信 (npm run serve:pages)"
	@echo "  make server [HOST=.. PORT=..]    セッションサーバー起動 (scripts/server/main.py)"
	@echo "  make slice STORY=scripts/stories/<name>.yaml [SESSION=.. OUT=..]"
	@echo "                                    vertical_slice を実AI APIに対して実行（課金注意、実行前に確認すること）"
	@echo "  make test [PW_ARGS=..]           npx playwright test を実行"
	@echo "  make cost [COST_TARGET=..]       cost_summary.py でトークン/コストを集計 (デフォルト: tests/generated/)"
	@echo "  make clean                       __pycache__ / playwright-report / test-results を削除"

setup: ## Python/Node の依存関係をインストール
	uv sync
	npm install

env: ## .env を .env.example から作成する（既存なら何もしない）
	[ -f .env ] || cp .env.example .env

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

test: ## 生成済みPlaywrightテストを実行する
	npx playwright test $(PW_ARGS)

cost: ## トークン消費・概算コストを集計する
	uv run python -m scripts.internal.cost_summary $(COST_TARGET)

clean: ## __pycache__ / playwright-report / test-results を削除する
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	rm -rf playwright-report test-results
