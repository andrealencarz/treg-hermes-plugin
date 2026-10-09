from __future__ import annotations

import os
from pathlib import Path


def hermes_home() -> Path:
    configured = os.environ.get("HERMES_HOME")
    if configured:
        return Path(configured).expanduser()
    try:
        from hermes_constants import get_hermes_home
        return get_hermes_home()
    except ImportError:
        return Path.home() / ".hermes"


def data_dir() -> Path:
    """Diretório persistente do perfil ativo; configurável para o serviço systemd."""
    configured = os.environ.get("PROSPECTOR_DATA_DIR")
    if configured:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            raise ValueError("PROSPECTOR_DATA_DIR precisa ser absoluto")
        return path
    return hermes_home() / "plugin-data" / "hermes-prospector"


def db_path() -> Path:
    return data_dir() / "prospector.db"


def secret_path() -> Path:
    return data_dir() / "treg-token"


def require_private_directory() -> Path:
    path = data_dir()
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path
