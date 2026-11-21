#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ "$(uname -s)" != Darwin ]; then
  echo 'This runner currently requires macOS sandbox-exec.' >&2
  exit 2
fi
for command_name in git python3 npm sandbox-exec; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name" >&2
    exit 2
  fi
done
if [ "${1:-}" != '' ] && [ "${1:-}" != '--login' ]; then
  echo 'Usage: ./setup.sh [--login]' >&2
  exit 2
fi
cd "$ROOT"
npm ci --no-audit --no-fund
python3 -m unittest discover -s tests -q
echo 'Installed Qwen Code and passed local runner checks.'
if [ "${1:-}" = '--login' ]; then
  exec "$ROOT/login-qwen.sh"
fi
