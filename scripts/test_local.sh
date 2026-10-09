#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -x .venv/bin/python ]]; then
  echo "Prepare o ambiente: uv sync --extra test" >&2
  exit 2
fi

.venv/bin/python -m pytest -q
if [[ -x .venv311/bin/python ]]; then
  .venv311/bin/python -m pytest -q
fi
if command -v node >/dev/null; then
  node --check prospector/static/app.js
  node --check dashboard/dist/index.js
  node tests/dashboard_ui_smoke.js
fi
bash -n scripts/test_local.sh
.venv/bin/python -m compileall -q prospector scripts
echo "Verificações locais offline concluídas; nenhuma chamada paga foi feita."
