#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]] || [[ "$(id -u)" == "0" ]]; then
  echo "Execute como o usuário do Hermes em Linux, não como root." >&2; exit 2
fi
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
DATA_DIR="$HERMES_HOME/plugin-data/hermes-prospector"
PLUGIN_DIR="$HERMES_HOME/plugins/hermes-prospector"
PROSPECTOR_BIN="$DATA_DIR/venv/bin/prospector"
SERVICE_NAME="hermes-prospector-$(id -un)"
PORT="$(cat "$DATA_DIR/deployment-port" 2>/dev/null || echo 8765)"
[[ -x "$PROSPECTOR_BIN" && -d "$PLUGIN_DIR/.git" ]] || { echo "Instalação Git do Prospector não encontrada." >&2; exit 2; }

OLD_COMMIT="$(git -C "$PLUGIN_DIR" rev-parse HEAD)"
BACKUP_PATH="$("$PROSPECTOR_BIN" --data-dir "$DATA_DIR" backup | python3 -c 'import json,sys;print(json.load(sys.stdin)["path"])')"
echo "Backup: $BACKUP_PATH"
sudo systemctl stop "$SERVICE_NAME"
restore() {
  echo "Atualização falhou; restaurando código e serviço anteriores." >&2
  git -C "$PLUGIN_DIR" checkout --detach "$OLD_COMMIT" >/dev/null 2>&1 || true
  "$DATA_DIR/venv/bin/python" -m pip install --disable-pip-version-check "$PLUGIN_DIR" >/dev/null 2>&1 || true
  sudo systemctl start "$SERVICE_NAME" || true
}
trap restore ERR
hermes plugins update hermes-prospector
"$DATA_DIR/venv/bin/python" -m pip install --disable-pip-version-check "$PLUGIN_DIR"
"$PROSPECTOR_BIN" --data-dir "$DATA_DIR" doctor
sudo systemctl start "$SERVICE_NAME"
sleep 2
curl -fsS --max-time 5 "http://127.0.0.1:$PORT/health" >/dev/null
trap - ERR
echo "Atualização concluída. Backup preservado em $BACKUP_PATH"
