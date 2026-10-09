#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]] || [[ "$(id -u)" == "0" ]]; then
  echo "Execute como o usuário do Hermes em Linux, não como root." >&2; exit 2
fi
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
DATA_DIR="$HERMES_HOME/plugin-data/hermes-prospector"
SERVICE_NAME="hermes-prospector-$(id -un)"
SITE_FILE="/etc/caddy/hermes-prospector-sites/$SERVICE_NAME.caddy"

if systemctl list-unit-files "$SERVICE_NAME.service" --no-legend 2>/dev/null | grep -q "$SERVICE_NAME"; then
  sudo systemctl disable --now "$SERVICE_NAME" || true
  sudo rm -f "/etc/systemd/system/$SERVICE_NAME.service"
  sudo systemctl daemon-reload
fi
if [[ -f "$SITE_FILE" ]]; then
  sudo rm -f "$SITE_FILE"
  if command -v caddy >/dev/null && sudo caddy validate --config /etc/caddy/Caddyfile; then
    sudo systemctl reload caddy
  fi
fi
hermes plugins remove hermes-prospector
echo "Plugin e serviço removidos. Banco, chave e backups preservados em $DATA_DIR"
echo "Revise regras de firewall criadas para acesso por IP antes de removê-las; outras aplicações podem usá-las."
