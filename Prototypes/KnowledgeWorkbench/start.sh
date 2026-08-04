#!/bin/sh
set -eu

WORKBENCH_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_DIR=$(CDPATH= cd -- "$WORKBENCH_DIR/../.." && pwd)

if [ ! -x "$REPOSITORY_DIR/.venv/bin/uvicorn" ]; then
  echo "先に Prototypes/KnowledgeWorkbench/setup.sh を実行してください。"
  exit 1
fi

# A one-time command such as KNOWLEDGE_PROVIDER=fixture takes precedence over .env.
REQUESTED_PROVIDER=${KNOWLEDGE_PROVIDER:-}
if [ -f "$WORKBENCH_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$WORKBENCH_DIR/.env"
  set +a
fi
if [ -n "$REQUESTED_PROVIDER" ]; then
  export KNOWLEDGE_PROVIDER=$REQUESTED_PROVIDER
fi

# Local Publisher adapters remain separately versioned packages. Expose their
# editable source tree even before setup.sh is rerun in an existing environment.
export PYTHONPATH="$REPOSITORY_DIR/Publishers/PresentationEngineAdapter/src:$REPOSITORY_DIR/Publishers/PresentationPromptBuilder/src:$REPOSITORY_DIR/Publishers/ProviderPayloadResolver/src:$REPOSITORY_DIR/Publishers/PresentationRequestBuilder/src:$REPOSITORY_DIR/Publishers/SourceBundlePublisher/src${PYTHONPATH:+:$PYTHONPATH}"

cd "$WORKBENCH_DIR"
exec "$REPOSITORY_DIR/.venv/bin/uvicorn" knowledge_workbench.main:app \
  --app-dir src \
  --host 127.0.0.1 \
  --port 8000
