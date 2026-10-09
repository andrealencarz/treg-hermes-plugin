from __future__ import annotations

import os
import tempfile

from .config import require_private_directory, secret_path


def read_token() -> str | None:
    path = secret_path()
    return path.read_text(encoding="utf-8").strip() if path.exists() else None


def save_token(token: str) -> None:
    if not token or "\n" in token or "\r" in token:
        raise ValueError("Chave inválida")
    directory = require_private_directory()
    fd, temporary = tempfile.mkstemp(prefix=".treg-token-", dir=directory)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(token)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, secret_path())
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

