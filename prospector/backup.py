from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def backup(source: sqlite3.Connection):
    database = source.execute("PRAGMA database_list").fetchone()[2]
    if not database:
        raise ValueError("Backup exige banco persistente em arquivo")
    directory = Path(database).resolve().parent / "backups"
    directory.mkdir(mode=0o700, exist_ok=True)
    directory.chmod(0o700)
    target = directory / f"prospector-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}.db"
    with sqlite3.connect(target) as destination:
        source.backup(destination)
    target.chmod(0o600)
    return target
