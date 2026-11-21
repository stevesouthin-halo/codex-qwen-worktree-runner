#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd /private/tmp
exec "$ROOT/node_modules/.bin/node" "$ROOT/node_modules/@qwen-code/qwen-code/cli-entry.js" --auth-type qwen-subscription
