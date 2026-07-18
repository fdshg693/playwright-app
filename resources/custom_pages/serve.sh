#!/usr/bin/env bash
# resources/custom_pages/pages/ を system nginx でローカル配信する。
# フォアグラウンド起動のみ（daemon off; はnginx.conf側で指定済み）。停止はCtrl+C。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NGINX_DIR="$SCRIPT_DIR/nginx"

mkdir -p "$NGINX_DIR/run"

exec /usr/sbin/nginx -p "$NGINX_DIR" -c nginx.conf
