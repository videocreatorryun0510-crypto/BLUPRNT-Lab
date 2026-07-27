#!/bin/sh
set -eu

WORKBENCH_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_DIR=$(CDPATH= cd -- "$WORKBENCH_DIR/../.." && pwd)
PYTHON_COMMAND=${PYTHON:-python3}

if [ ! -d "$REPOSITORY_DIR/.venv" ]; then
  "$PYTHON_COMMAND" -m venv "$REPOSITORY_DIR/.venv"
fi

"$REPOSITORY_DIR/.venv/bin/python" -m pip install --upgrade pip
"$REPOSITORY_DIR/.venv/bin/python" -m pip install \
  -e "$REPOSITORY_DIR/Packages/knowledge-contracts[dev]" \
  -e "$REPOSITORY_DIR/Publishers/SourceBundlePublisher[dev]" \
  -e "$REPOSITORY_DIR/Publishers/PresentationRequestBuilder[dev]" \
  -e "$WORKBENCH_DIR[dev]"

echo "準備が完了しました。次は Prototypes/KnowledgeWorkbench/start.sh を実行してください。"
