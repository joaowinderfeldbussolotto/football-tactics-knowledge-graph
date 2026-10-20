#!/bin/bash
# Claude Code on the web: prepare the Python environment the paper scripts need.
# Runs only in cloud sessions, is idempotent (a second run finds everything installed) and needs
# no Neo4j, no Docker and no API key: the paper pipeline only reads versioned files.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

if [ ! -x .venv/bin/python ]; then
  uv venv --quiet .venv
fi
if ! .venv/bin/python -c "import football_graphrag, matplotlib, pytest" 2>/dev/null; then
  uv pip install --quiet --python .venv/bin/python -e ".[dev,paper]"
fi

# the scripts and tests run with the project's interpreter from now on
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export PATH=\"$PWD/.venv/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"
fi
echo "paper environment ready: python $(.venv/bin/python --version | cut -d' ' -f2), $(.venv/bin/python -c 'import matplotlib; print("matplotlib", matplotlib.__version__)')"
