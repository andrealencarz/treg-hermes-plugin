"""Importação conservadora de um arquivo plano do projeto anterior; nunca executa código legado."""
from __future__ import annotations

import csv
import json
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

from .backup import backup
from .db import now, transaction
from .service import DomainError, ProspectorService


def _pick(row: dict, *names: str):
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _rows(path: Path) -> list[dict]:
    path = path.expanduser()
    if path.is_symlink() or not path.is_file():
        raise DomainError("Informe um arquivo regular CSV, JSON ou JSONL; links não são aceitos")
    if path.stat().st_size > 20 * 1024 * 1024:
        raise DomainError("Arquivo legado maior que 20 MiB; divida antes de importar")
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
    elif path.suffix.lower() == ".jsonl":
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    elif path.suffix.lower() == ".json":
        body = json.loads(path.read_text(encoding="utf-8"))
        rows = body.get("leads") if isinstance(body, dict) else body
    else:
        raise DomainError("Formato não suportado; use CSV, JSON ou JSONL")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise DomainError("Formato legado inválido; esperado lista de registros")
    return rows


def preview(path: Path) -> dict:
    rows = _rows(path)
    invalid = [index + 1 for index, row in enumerate(rows) if not _pick(row, "name", "nome", "nome_empresa", "empresa")]
    cost_rows = sum(bool(_pick(row, "cost_micro", "custo_micro", "cost_usd", "custo_usd")) for row in rows)
    return {"path": str(path.resolve()), "records": len(rows), "invalid_rows": invalid[:20],
            "cost_rows": cost_rows, "can_import": bool(rows) and not invalid,
            "source_untouched": True}


def _micro(row: dict) -> int | None:
    direct = _pick(row, "cost_micro", "custo_micro")
    if direct:
        try:
            value = int(direct)
            return value if value >= 0 else None
        except ValueError:
            return None
    usd = _pick(row, "cost_usd", "custo_usd")
    if usd:
        try:
            value = int(Decimal(usd.replace(",", ".")) * 1_000_000)
            return value if value >= 0 else None
        except InvalidOperation:
            return None
    return None


def import_file(service: ProspectorService, path: Path) -> dict:
    rows = _rows(path)
    check = preview(path)
    if not check["can_import"]:
        raise DomainError("Prévia encontrou registros inválidos; origem preservada")
    backup_path = backup(service.conn)
    origin = str(path.resolve())
    campaign_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "hermes-prospector:legacy:" + origin))
    execution_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "hermes-prospector:legacy-run:" + origin))
    timestamp = now()
    imported = 0
    with transaction(service.conn):
        if not service.campaign(campaign_id):
            service.conn.execute("""INSERT INTO campaign(id,name,niche,cities_json,state,created_at,updated_at)
                VALUES(?,'Importação legado','Dados importados','[]','archived',?,?)""",
                (campaign_id, timestamp, timestamp))
            service.conn.execute("""INSERT INTO execution(id,campaign_id,campaign_snapshot_json,state,created_at,finished_at)
                VALUES(?,?,'{}','succeeded',?,?)""", (execution_id, campaign_id, timestamp, timestamp))
        for index, row in enumerate(rows):
            if service.conn.execute("SELECT 1 FROM legacy_record WHERE source_path=? AND row_index=?",
                                    (origin, index)).fetchone():
                continue
            name = _pick(row, "name", "nome", "nome_empresa", "empresa")
            city = _pick(row, "city", "cidade")
            uf = _pick(row, "uf", "estado").upper()
            phone = "".join(c for c in _pick(row, "phone", "telefone", "whatsapp") if c.isdigit() or c == "+")
            website = _pick(row, "website", "site")
            parsed = urlsplit(website)
            if parsed.scheme not in ("http", "https"):
                website = ""
                parsed = urlsplit(website)
            domain = (parsed.hostname or "").lower()
            status = _pick(row, "status", "status_comercial") or "Novo"
            if status not in {"Novo", "Em análise", "Contatado", "Proposta enviada", "Fechado"}:
                status = "Novo"
            external = _pick(row, "id", "place_id", "external_id") or f"{origin}#{index}"
            existing = service.conn.execute("SELECT lead_id AS id FROM lead_source WHERE source='legacy' AND external_id=?",
                                            (external,)).fetchone()
            if not existing and phone and city:
                existing = service.conn.execute("""SELECT id FROM lead WHERE phone=? AND city=? AND uf=?
                    AND lower(name)=lower(?) LIMIT 1""", (phone, city, uf, name)).fetchone()
            lead_id = existing["id"] if existing else str(uuid.uuid4())
            if not existing:
                service.conn.execute("""INSERT INTO lead(id,name,niche,city,uf,domain,website,phone,email,status,first_seen_at,last_seen_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (lead_id, name, _pick(row, "niche", "nicho"),
                    city, uf, domain or None, website or None, phone or None,
                    _pick(row, "email", "e_mail") or None, status, timestamp, timestamp))
            service.conn.execute("""INSERT OR IGNORE INTO lead_source(lead_id,source,external_id,evidence_url,collected_at)
                VALUES(?,?,?,?,?)""", (lead_id, "legacy", external,
                _pick(row, "evidence_url", "url_evidencia", "maps_url") or None, timestamp))
            service.conn.execute("""INSERT OR IGNORE INTO lead_campaign(lead_id,campaign_id,first_execution_id,first_seen_at,last_seen_at,notes)
                VALUES(?,?,?,?,?,?)""", (lead_id, campaign_id, execution_id, timestamp, timestamp,
                _pick(row, "notes", "observacoes")))
            service.conn.execute("""INSERT INTO legacy_record(source_path,row_index,lead_id,raw_json,cost_micro,imported_at)
                VALUES(?,?,?,?,?,?)""", (origin, index, lead_id, json.dumps(row, ensure_ascii=False),
                _micro(row), timestamp))
            imported += 1
    return {"campaign_id": campaign_id, "records_imported": imported, "records_total": len(rows),
            "backup": str(backup_path), "source_untouched": True}
