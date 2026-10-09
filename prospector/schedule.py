"""Agendamento nativo Hermes: cron chama um script que apenas enfileira a campanha."""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .db import now, transaction
from .service import DomainError, ProspectorService


def validate(frequency: str, days: list[int], times: list[str], tz: str, once_at: str | None = None) -> dict:
    if frequency not in ("once", "daily", "weekdays"):
        raise DomainError("Frequência inválida")
    try:
        zone = ZoneInfo(tz)
    except ZoneInfoNotFoundError as exc:
        raise DomainError("Fuso IANA inválido") from exc
    clean_times = sorted(set(times))
    for value in clean_times:
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise DomainError("Horário inválido; use HH:MM")
    clean_days = sorted(set(days))
    if any(not isinstance(day, int) or day < 0 or day > 6 for day in clean_days):
        raise DomainError("Dia da semana inválido")
    if frequency == "weekdays" and not clean_days:
        raise DomainError("Selecione pelo menos um dia da semana")
    if frequency != "once" and not clean_times:
        raise DomainError("Informe pelo menos um horário")
    parsed_once = None
    if frequency == "once":
        if not once_at:
            raise DomainError("Informe data e hora da execução única")
        try:
            parsed_once = datetime.fromisoformat(once_at)
        except ValueError as exc:
            raise DomainError("Data da execução única inválida") from exc
        if parsed_once.tzinfo is None:
            parsed_once = parsed_once.replace(tzinfo=zone)
        parsed_once = parsed_once.astimezone(zone)
        if parsed_once <= datetime.now(zone):
            raise DomainError("Data da execução única precisa ser futura")
    return {"frequency": frequency, "days": clean_days, "times": clean_times,
            "timezone": tz, "once_at": parsed_once.isoformat() if parsed_once else None}


def next_occurrences(spec: dict, count: int = 3, reference: datetime | None = None) -> list[str]:
    zone = ZoneInfo(spec["timezone"])
    current = (reference or datetime.now(timezone.utc)).astimezone(zone)
    if spec["frequency"] == "once":
        target = datetime.fromisoformat(spec["once_at"]).astimezone(zone)
        return [target.isoformat()] if target > current else []
    result = []
    for offset in range(0, 370):
        day = current.date() + timedelta(days=offset)
        if spec["frequency"] == "weekdays" and day.weekday() not in spec["days"]:
            continue
        for value in spec["times"]:
            hour, minute = map(int, value.split(":"))
            candidate = datetime.combine(day, time(hour, minute), zone)
            if candidate > current:
                result.append(candidate.isoformat())
            if len(result) >= count:
                return result[:count]
    return result


def _hermes_bin() -> str:
    sibling = Path(sys.executable).parent / "hermes"
    result = os.environ.get("HERMES_BIN") or shutil.which("hermes") or (str(sibling) if sibling.is_file() else None)
    if not result:
        raise DomainError("CLI Hermes não encontrada; configure HERMES_BIN no serviço")
    return result


def _run_hermes(*arguments: str) -> str:
    result = subprocess.run([_hermes_bin(), "cron", *arguments], capture_output=True,
                            text=True, timeout=30, check=False)
    if result.returncode:
        raise DomainError("Falha ao sincronizar agenda Hermes: " + (result.stderr or result.stdout).strip()[:300])
    return result.stdout


def _script_path(campaign_id: str) -> Path:
    from .config import hermes_home
    return hermes_home() / "scripts" / f"hermes-prospector-{campaign_id}.sh"


def _write_script(campaign_id: str):
    from .config import data_dir
    executable = os.environ.get("PROSPECTOR_BIN")
    if executable and not Path(executable).is_absolute():
        raise DomainError("PROSPECTOR_BIN precisa ser absoluto")
    path = _script_path(campaign_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if executable:
        prefix = shlex.quote(executable)
    else:
        plugin_root = Path(__file__).resolve().parents[1]
        prefix = "PYTHONPATH=" + shlex.quote(str(plugin_root)) + " " + shlex.quote(sys.executable) + " -m prospector.cli"
    common = prefix + " --data-dir " + shlex.quote(str(data_dir()))
    tick = common + " schedule-tick " + shlex.quote(campaign_id)
    worker = common + " worker-once"
    path.write_text("#!/bin/sh\nset -eu\n" + tick + "\n" + worker + "\n", encoding="utf-8")
    path.chmod(0o700)
    return path


def _row_to_spec(row) -> dict:
    return {"campaign_id": row["campaign_id"], "frequency": row["frequency"],
            "days": json.loads(row["days_json"]), "times": json.loads(row["times_json"]),
            "timezone": row["timezone"], "once_at": row["once_at"], "state": row["state"],
            "hermes_job_id": row["hermes_job_id"], "last_occurrence_key": row["last_occurrence_key"],
            "next_occurrences": next_occurrences(dict(row) | {"days": json.loads(row["days_json"]),
                                           "times": json.loads(row["times_json"])})}


def schedules(service: ProspectorService) -> list[dict]:
    return [_row_to_spec(row) for row in service.conn.execute("SELECT * FROM schedule_binding ORDER BY updated_at DESC")]


def save(service: ProspectorService, campaign_id: str, *, frequency: str,
         days: list[int], times: list[str], timezone: str, once_at: str | None = None) -> dict:
    campaign = service.campaign(campaign_id)
    if not campaign or campaign["state"] == "archived":
        raise DomainError("Campanha inexistente ou arquivada")
    spec = validate(frequency, days, times, timezone, once_at)
    _write_script(campaign_id)
    existing = service.conn.execute("SELECT hermes_job_id FROM schedule_binding WHERE campaign_id=?", (campaign_id,)).fetchone()
    job_id = existing["hermes_job_id"] if existing else None
    if job_id:
        _run_hermes("pause", job_id)
    else:
        output = _run_hermes("create", "every 1m", "--no-agent", "--script", _script_path(campaign_id).name,
                             "--name", f"Hermes Prospector {campaign_id}", "--deliver", "local", "--paused")
        match = re.search(r"Created job:\s*([\w-]+)", output)
        if not match:
            raise DomainError("Hermes criou tarefa sem ID legível; confira `hermes cron list --all`")
        job_id = match.group(1)
    with transaction(service.conn):
        service.conn.execute("""INSERT INTO schedule_binding(campaign_id,frequency,days_json,times_json,timezone,once_at,state,hermes_job_id,updated_at)
            VALUES(?,?,?,?,?,?,'paused',?,?) ON CONFLICT(campaign_id) DO UPDATE SET
            frequency=excluded.frequency,days_json=excluded.days_json,times_json=excluded.times_json,
            timezone=excluded.timezone,once_at=excluded.once_at,state='paused',last_occurrence_key=NULL,
            hermes_job_id=excluded.hermes_job_id,updated_at=excluded.updated_at""",
            (campaign_id, frequency, json.dumps(spec["days"]), json.dumps(spec["times"]),
             timezone, spec["once_at"], job_id, now()))
    return _row_to_spec(service.conn.execute("SELECT * FROM schedule_binding WHERE campaign_id=?", (campaign_id,)).fetchone())


def set_active(service: ProspectorService, campaign_id: str, active: bool) -> dict:
    row = service.conn.execute("SELECT * FROM schedule_binding WHERE campaign_id=?", (campaign_id,)).fetchone()
    if not row or not row["hermes_job_id"]:
        raise DomainError("Salve a programação antes de ativar")
    if service.campaign(campaign_id)["state"] == "archived":
        raise DomainError("Campanha arquivada")
    _run_hermes("resume" if active else "pause", row["hermes_job_id"])
    with transaction(service.conn):
        service.conn.execute("UPDATE schedule_binding SET state=?,updated_at=? WHERE campaign_id=?",
                             ("active" if active else "paused", now(), campaign_id))
        service.conn.execute("UPDATE campaign SET state=?,updated_at=? WHERE id=?",
                             ("active" if active else "paused", now(), campaign_id))
    return _row_to_spec(service.conn.execute("SELECT * FROM schedule_binding WHERE campaign_id=?", (campaign_id,)).fetchone())


def tick(service: ProspectorService, campaign_id: str, reference: datetime | None = None) -> dict:
    with transaction(service.conn):
        row = service.conn.execute("SELECT * FROM schedule_binding WHERE campaign_id=?", (campaign_id,)).fetchone()
        campaign = service.campaign(campaign_id)
        if not row or row["state"] != "active" or not campaign or campaign["state"] != "active":
            return {"queued": False, "reason": "Rotina inativa"}
        current = (reference or datetime.now(timezone.utc)).astimezone(ZoneInfo(row["timezone"]))
        minute = current.strftime("%H:%M")
        due = False
        if row["frequency"] == "once":
            target = datetime.fromisoformat(row["once_at"]).astimezone(current.tzinfo)
            due = target.date() == current.date() and target.strftime("%H:%M") == minute
        elif row["frequency"] == "daily":
            due = minute in json.loads(row["times_json"])
        else:
            due = current.weekday() in json.loads(row["days_json"]) and minute in json.loads(row["times_json"])
        key = current.strftime("%Y-%m-%dT%H:%M")
        if not due or row["last_occurrence_key"] == key:
            return {"queued": False, "reason": "Fora do horário ou já enfileirada"}
        active = service.conn.execute("SELECT 1 FROM execution WHERE campaign_id=? AND state IN ('queued','running')",
                                      (campaign_id,)).fetchone()
        if active:
            return {"queued": False, "reason": "Rodada anterior ainda ativa"}
        execution_id = str(uuid.uuid4())
        service.conn.execute("""INSERT INTO execution(id,campaign_id,campaign_snapshot_json,state,created_at)
            VALUES(?,?,?,'queued',?)""", (execution_id, campaign_id, json.dumps(campaign, ensure_ascii=False), now()))
        service.conn.execute("INSERT INTO job_queue(execution_id) VALUES(?)", (execution_id,))
        service.conn.execute("UPDATE schedule_binding SET last_occurrence_key=? WHERE campaign_id=?", (key, campaign_id))
        if row["frequency"] == "once":
            service.conn.execute("UPDATE schedule_binding SET state='completed' WHERE campaign_id=?", (campaign_id,))
    return {"queued": True, "execution_id": execution_id}
