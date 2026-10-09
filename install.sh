#!/usr/bin/env bash
set -euo pipefail

# Instalação na VPS Linux. Execute como o usuário dono do perfil Hermes, com sudo.
SOURCE=""
DOMAIN=""
PUBLIC_IP=""
OPERATOR_CIDR=""
PORT="8765"

usage() {
  cat <<'EOF'
Uso: bash install.sh [--source URL_GIT] [--domain dominio.example]
       bash install.sh [--source URL_GIT] --ip IP_PUBLICO --operator-cidr IP_OU_CIDR

O script instala o plugin Hermes, o serviço web e o acesso na própria VPS.
Nenhuma busca paga ou rotina é ativada durante a instalação.
EOF
}

while (($#)); do
  case "$1" in
    --source) SOURCE="${2:?}"; shift 2 ;;
    --domain) DOMAIN="${2:?}"; shift 2 ;;
    --ip) PUBLIC_IP="${2:?}"; shift 2 ;;
    --operator-cidr) OPERATOR_CIDR="${2:?}"; shift 2 ;;
    --port) PORT="${2:?}"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Opção desconhecida: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ "$(uname -s)" != "Linux" ]] || ! command -v systemctl >/dev/null; then
  echo "Este instalador requer Linux com systemd." >&2; exit 2
fi
if [[ "$(id -u)" == "0" ]]; then
  echo "Execute como o usuário do Hermes, não como root; sudo será usado só para serviços/proxy." >&2; exit 2
fi
if [[ -n "$DOMAIN" && -n "$PUBLIC_IP" ]]; then
  echo "Escolha domínio ou IP, não os dois." >&2; exit 2
fi
if [[ -z "$DOMAIN" && -z "$PUBLIC_IP" ]]; then
  echo "Informe --domain ou --ip. Não há URL pública sem um deles." >&2; exit 2
fi
if [[ -n "$PUBLIC_IP" && -z "$OPERATOR_CIDR" ]]; then
  echo "Acesso HTTP por IP exige --operator-cidr para restringir o firewall." >&2; exit 2
fi
if [[ -n "$PUBLIC_IP" ]]; then
  python3 - "$PUBLIC_IP" "$OPERATOR_CIDR" <<'PY'
import ipaddress, sys
try:
    ipaddress.ip_address(sys.argv[1])
    ipaddress.ip_network(sys.argv[2], strict=False)
except ValueError as exc:
    raise SystemExit(f"IP ou CIDR inválido: {exc}")
PY
fi
if [[ -n "$DOMAIN" ]] && ! [[ "$DOMAIN" =~ ^[a-zA-Z0-9.-]+$ ]]; then
  echo "Domínio inválido." >&2; exit 2
fi
if ! [[ "$PORT" =~ ^[0-9]+$ ]] || ((PORT < 1024 || PORT > 65535)); then
  echo "Porta inválida; use 1024–65535." >&2; exit 2
fi
command -v hermes >/dev/null || { echo "Hermes não encontrado no PATH." >&2; exit 2; }
command -v python3 >/dev/null || { echo "Python 3 não encontrado." >&2; exit 2; }
command -v sudo >/dev/null || { echo "sudo não encontrado." >&2; exit 2; }
python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 ou superior é necessário")
PY
HERMES_VERSION="$(hermes --version 2>&1)"
python3 - "$HERMES_VERSION" <<'PY'
import re, sys
match = re.search(r'(?<!\d)(\d+)\.(\d+)\.(\d+)', sys.argv[1])
if not match or tuple(map(int, match.groups())) < (0, 21, 5):
    raise SystemExit(f"Hermes 0.21.5 ou superior é necessário; encontrado: {sys.argv[1]}")
PY

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "$SOURCE" ]]; then
  SOURCE="$(git -C "$SCRIPT_DIR" remote get-url origin 2>/dev/null || true)"
fi
if [[ -z "$SOURCE" ]]; then
  echo "Informe --source com a URL Git do repositório publicado." >&2; exit 2
fi
if [[ "$SOURCE" != https://* && "$SOURCE" != git@* ]]; then
  echo "A origem do plugin precisa ser URL HTTPS ou Git SSH." >&2; exit 2
fi

HERMES_BIN="$(command -v hermes)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
if [[ "$HERMES_HOME" != /* ]]; then echo "HERMES_HOME precisa ser absoluto." >&2; exit 2; fi
if [[ "$HERMES_HOME" == *' '* || "$HERMES_HOME" == *$'\n'* ]]; then
  echo "Este instalador não aceita espaço ou quebra de linha em HERMES_HOME." >&2; exit 2
fi
DATA_DIR="$HERMES_HOME/plugin-data/hermes-prospector"
PLUGIN_DIR="$HERMES_HOME/plugins/hermes-prospector"
VENV_DIR="$DATA_DIR/venv"
SERVICE_NAME="hermes-prospector-$(id -un)"
INSTALL_STATE="$DATA_DIR/install-state.txt"
mkdir -p "$DATA_DIR"
chmod 700 "$DATA_DIR"
printf '%s\n' "$PORT" > "$DATA_DIR/deployment-port"

if [[ ! -f "$PLUGIN_DIR/plugin.yaml" ]]; then
  hermes plugins install "$SOURCE" --enable
else
  hermes plugins enable hermes-prospector
fi
printf '%s\n' 'pacote_instalado' > "$INSTALL_STATE"
if [[ ! -d "$VENV_DIR" ]]; then python3 -m venv "$VENV_DIR"; fi
"$VENV_DIR/bin/python" -m pip install --disable-pip-version-check "$PLUGIN_DIR"
PROSPECTOR_BIN="$VENV_DIR/bin/prospector"
"$PROSPECTOR_BIN" --data-dir "$DATA_DIR" doctor

if ! "$VENV_DIR/bin/python" - "$DATA_DIR/prospector.db" <<'PY'
import sqlite3, sys
with sqlite3.connect(sys.argv[1]) as db:
    raise SystemExit(0 if db.execute('SELECT 1 FROM admin WHERE id=1').fetchone() else 1)
PY
then
  "$PROSPECTOR_BIN" --data-dir "$DATA_DIR" admin set-password
fi

if [[ -n "$PUBLIC_IP" ]]; then
  command -v ufw >/dev/null || { echo "Modo IP exige ufw ativo para restringir o acesso." >&2; exit 2; }
  sudo ufw status | grep -q 'Status: active' || { echo "Ative/configure ufw sem bloquear SSH antes do modo IP." >&2; exit 2; }
  sudo ufw status verbose | grep -q 'Default: deny (incoming)' || { echo "Modo IP exige política de entrada deny no ufw." >&2; exit 2; }
  sudo ufw allow from "$OPERATOR_CIDR" to any port "$PORT" proto tcp
  BIND_ADDRESS="0.0.0.0"
  COOKIE_SECURE="0"
  PUBLIC_URL="http://$PUBLIC_IP:$PORT"
else
  BIND_ADDRESS="127.0.0.1"
  COOKIE_SECURE="1"
  PUBLIC_URL="https://$DOMAIN"
fi

UNIT_PATH="/etc/systemd/system/$SERVICE_NAME.service"
UNIT_TEMP="$(mktemp)"
cat > "$UNIT_TEMP" <<EOF
[Unit]
Description=Hermes Prospector ($USER)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$(id -un)
Group=$(id -gn)
WorkingDirectory=$DATA_DIR
Environment=HERMES_HOME=$HERMES_HOME
Environment=PROSPECTOR_DATA_DIR=$DATA_DIR
Environment=HERMES_BIN=$HERMES_BIN
Environment=PROSPECTOR_BIN=$PROSPECTOR_BIN
Environment=PROSPECTOR_COOKIE_SECURE=$COOKIE_SECURE
ExecStart=$PROSPECTOR_BIN --data-dir $DATA_DIR serve --host $BIND_ADDRESS --port $PORT
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=$HERMES_HOME
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
sudo install -m 0644 "$UNIT_TEMP" "$UNIT_PATH"
rm -f "$UNIT_TEMP"
sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"
printf '%s\n' 'servico_ativo' > "$INSTALL_STATE"

if [[ -n "$DOMAIN" ]]; then
  if ! command -v caddy >/dev/null; then
    if command -v apt-get >/dev/null && ! command -v nginx >/dev/null; then
      sudo apt-get update
      sudo apt-get install -y caddy
    else
      echo "Caddy não encontrado. Instale Caddy ou configure o proxy existente e execute novamente." >&2
      exit 2
    fi
  fi
  CADDYFILE="/etc/caddy/Caddyfile"
  [[ -f "$CADDYFILE" ]] || { echo "Caddyfile não encontrado em $CADDYFILE" >&2; exit 2; }
  SITE_DIR="/etc/caddy/hermes-prospector-sites"
  SITE_FILE="$SITE_DIR/$SERVICE_NAME.caddy"
  sudo install -d -m 0755 "$SITE_DIR"
  sudo cp "$CADDYFILE" "$DATA_DIR/Caddyfile.before-prospector"
  if [[ -f "$SITE_FILE" ]]; then sudo cp "$SITE_FILE" "$DATA_DIR/Caddyfile.site.before-prospector"; fi
  printf '%s {\n    reverse_proxy 127.0.0.1:%s\n}\n' "$DOMAIN" "$PORT" | sudo tee "$SITE_FILE" >/dev/null
  if ! sudo grep -Fq "import $SITE_DIR/*.caddy" "$CADDYFILE"; then
    printf '\nimport %s/*.caddy\n' "$SITE_DIR" | sudo tee -a "$CADDYFILE" >/dev/null
  fi
  if ! sudo caddy validate --config "$CADDYFILE"; then
    sudo cp "$DATA_DIR/Caddyfile.before-prospector" "$CADDYFILE"
    if [[ -f "$DATA_DIR/Caddyfile.site.before-prospector" ]]; then
      sudo cp "$DATA_DIR/Caddyfile.site.before-prospector" "$SITE_FILE"
    else
      sudo rm -f "$SITE_FILE"
    fi
    echo "Configuração Caddy inválida; configuração anterior restaurada." >&2
    exit 2
  fi
  if ! sudo systemctl reload caddy; then
    sudo cp "$DATA_DIR/Caddyfile.before-prospector" "$CADDYFILE"
    if [[ -f "$DATA_DIR/Caddyfile.site.before-prospector" ]]; then
      sudo cp "$DATA_DIR/Caddyfile.site.before-prospector" "$SITE_FILE"
    else
      sudo rm -f "$SITE_FILE"
    fi
    sudo systemctl reload caddy || true
    echo "Falha ao recarregar Caddy; configuração anterior restaurada." >&2
    exit 2
  fi
  printf '%s\n' 'acesso_configurado' > "$INSTALL_STATE"
fi

if ! curl -fsS --max-time 5 "http://127.0.0.1:$PORT/health" >/dev/null; then
  echo "Serviço criado, mas health check local falhou. Execute: sudo journalctl -u $SERVICE_NAME -n 50" >&2
  exit 2
fi

echo "Painel configurado: $PUBLIC_URL"
echo "Confirme o acesso de fora da VPS; health check local não comprova DNS, TLS ou firewall do provedor."
if [[ -n "$PUBLIC_IP" ]]; then
  echo "Acesso HTTP provisório: cadastre a chave por: $PROSPECTOR_BIN --data-dir '$DATA_DIR' treg set-token"
fi
echo "Nenhuma busca paga ou rotina foi ativada."
