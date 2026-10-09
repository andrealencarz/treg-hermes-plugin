from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import treg
from .db import connect, now, transaction
from .sources import SOURCES, normalize, selected


class DomainError(ValueError):
    pass


def _period(tz: str) -> str:
    return datetime.now(ZoneInfo(tz)).strftime("%Y-%m")


def _obj(row):
    return dict(row) if row else None


class ProspectorService:
    def __init__(self, path: Path | None = None):
        self.conn = connect(path)

    def close(self):
        self.conn.close()

    def create_campaign(self, *, name: str, niche: str, cities: list[dict], service: str = "",
                        target_leads: int = 30, run_cap_micro: int = 1_000_000,
                        monthly_cap_micro: int = 30_000_000, timezone: str = "America/Fortaleza",
                        sources: list[str] | None = None) -> dict:
        name, niche = name.strip(), niche.strip()
        if not name or not niche or len(name) > 120 or len(niche) > 120:
            raise DomainError("Informe nome e nicho com até 120 caracteres")
        if not cities or len(cities) > 30:
            raise DomainError("Informe de 1 a 30 cidades")
        clean = []
        for entry in cities:
            city = str(entry.get("city") or "").strip()
            uf = str(entry.get("uf") or "").strip().upper()
            if not city or len(city) > 100 or len(uf) != 2 or not uf.isalpha():
                raise DomainError("Cidade e UF inválidas")
            if {"city": city, "uf": uf} not in clean:
                clean.append({"city": city, "uf": uf})
        if not 1 <= target_leads <= 1000 or run_cap_micro <= 0 or monthly_cap_micro <= 0:
            raise DomainError("Meta ou orçamento inválido")
        try:
            sources = selected(sources if sources is not None else ["google_maps"])
        except ValueError as exc:
            raise DomainError(str(exc)) from exc
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise DomainError("Fuso IANA inválido") from exc
        campaign_id = str(uuid.uuid4())
        timestamp = now()
        with transaction(self.conn):
            self.conn.execute("""INSERT INTO campaign(id,name,service,niche,cities_json,source,sources_json,target_leads,
                run_cap_micro,monthly_cap_micro,timezone,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (campaign_id, name, service.strip(), niche, json.dumps(clean, ensure_ascii=False),
                 sources[0], json.dumps(sources),
                 target_leads, run_cap_micro, monthly_cap_micro, timezone, timestamp, timestamp))
        return self.campaign(campaign_id)

    def campaign(self, campaign_id: str) -> dict | None:
        row = _obj(self.conn.execute("SELECT * FROM campaign WHERE id=?", (campaign_id,)).fetchone())
        if row:
            row["cities"] = json.loads(row.pop("cities_json"))
            row["sources"] = json.loads(row.pop("sources_json"))
        return row

    def campaigns(self) -> list[dict]:
        return [self.campaign(row["id"]) for row in self.conn.execute("SELECT id FROM campaign ORDER BY created_at DESC")]

    def update_campaign(self, campaign_id: str, *, name: str | None = None, niche: str | None = None,
                        cities: list[dict] | None = None, target_leads: int | None = None,
                        run_cap_micro: int | None = None, monthly_cap_micro: int | None = None,
                        sources: list[str] | None = None) -> dict:
        old = self.campaign(campaign_id)
        if not old or old["state"] == "archived":
            raise DomainError("Campanha inexistente ou arquivada")
        values = {"name": name if name is not None else old["name"],
                  "niche": niche if niche is not None else old["niche"],
                  "cities": cities if cities is not None else old["cities"],
                  "sources": sources if sources is not None else old["sources"],
                  "target_leads": target_leads if target_leads is not None else old["target_leads"],
                  "run_cap_micro": run_cap_micro if run_cap_micro is not None else old["run_cap_micro"],
                  "monthly_cap_micro": monthly_cap_micro if monthly_cap_micro is not None else old["monthly_cap_micro"]}
        # Reutiliza a validação de criação sem persistir uma campanha provisória.
        if not str(values["name"]).strip() or not str(values["niche"]).strip():
            raise DomainError("Nome e nicho são obrigatórios")
        if not values["cities"] or any(not x.get("city") or len(str(x.get("uf", ""))) != 2 for x in values["cities"]):
            raise DomainError("Cidades inválidas")
        if not 1 <= values["target_leads"] <= 1000 or values["run_cap_micro"] <= 0 or values["monthly_cap_micro"] <= 0:
            raise DomainError("Meta ou orçamento inválido")
        try:
            values["sources"] = selected(values["sources"])
        except ValueError as exc:
            raise DomainError(str(exc)) from exc
        with transaction(self.conn):
            self.conn.execute("""UPDATE campaign SET name=?,niche=?,cities_json=?,source=?,sources_json=?,target_leads=?,
                run_cap_micro=?,monthly_cap_micro=?,version=version+1,updated_at=? WHERE id=?""",
                (values["name"].strip(), values["niche"].strip(), json.dumps(values["cities"], ensure_ascii=False),
                 values["sources"][0], json.dumps(values["sources"]),
                 values["target_leads"], values["run_cap_micro"], values["monthly_cap_micro"], now(), campaign_id))
        return self.campaign(campaign_id)

    def duplicate_campaign(self, campaign_id: str) -> dict:
        original = self.campaign(campaign_id)
        if not original:
            raise DomainError("Campanha não encontrada")
        return self.create_campaign(name=f"{original['name']} (cópia)", niche=original["niche"],
            cities=original["cities"], service=original["service"], target_leads=original["target_leads"],
            run_cap_micro=original["run_cap_micro"], monthly_cap_micro=original["monthly_cap_micro"],
            timezone=original["timezone"], sources=original["sources"])

    def set_campaign_state(self, campaign_id: str, state: str) -> dict:
        if state not in {"draft", "active", "paused", "archived"}:
            raise DomainError("Estado inválido")
        old = self.campaign(campaign_id)
        if not old or old["state"] == "archived":
            raise DomainError("Campanha inexistente ou arquivada")
        with transaction(self.conn):
            self.conn.execute("UPDATE campaign SET state=?,updated_at=? WHERE id=?", (state, now(), campaign_id))
        return self.campaign(campaign_id)

    def enqueue(self, campaign_id: str) -> dict:
        campaign = self.campaign(campaign_id)
        if not campaign or campaign["state"] == "archived":
            raise DomainError("Campanha inexistente ou arquivada")
        snapshot = json.dumps(campaign, ensure_ascii=False)
        execution_id = str(uuid.uuid4())
        with transaction(self.conn):
            active = self.conn.execute("""SELECT id FROM execution WHERE campaign_id=?
                AND state IN ('queued','running') LIMIT 1""", (campaign_id,)).fetchone()
            if active:
                raise DomainError("A campanha já tem uma rodada pendente")
            self.conn.execute("""INSERT INTO execution(id,campaign_id,campaign_snapshot_json,state,created_at)
                VALUES(?,?,?,'queued',?)""", (execution_id, campaign_id, snapshot, now()))
            self.conn.execute("INSERT INTO job_queue(execution_id) VALUES(?)", (execution_id,))
        return self.run(execution_id)

    def run(self, execution_id: str) -> dict | None:
        row = _obj(self.conn.execute("SELECT * FROM execution WHERE id=?", (execution_id,)).fetchone())
        if row:
            row["campaign_snapshot"] = json.loads(row.pop("campaign_snapshot_json"))
        return row

    def runs(self, campaign_id: str | None = None) -> list[dict]:
        if campaign_id:
            rows = self.conn.execute("SELECT id FROM execution WHERE campaign_id=? ORDER BY created_at DESC LIMIT 100", (campaign_id,))
        else:
            rows = self.conn.execute("SELECT id FROM execution ORDER BY created_at DESC LIMIT 100")
        return [self.run(row["id"]) for row in rows]

    def claim(self) -> dict | None:
        with transaction(self.conn):
            row = self.conn.execute("SELECT execution_id FROM job_queue WHERE state='queued' ORDER BY rowid LIMIT 1").fetchone()
            if not row:
                return None
            execution_id = row["execution_id"]
            self.conn.execute("UPDATE job_queue SET state='running',claimed_at=?,attempts=attempts+1 WHERE execution_id=?", (now(), execution_id))
            self.conn.execute("UPDATE execution SET state='running',started_at=? WHERE id=?", (now(), execution_id))
        return self.run(execution_id)

    def _used(self, scope: str, period: str, campaign_id: str | None = None) -> int:
        column = "campaign_period" if scope == "campaign" else "global_period"
        extra = " AND b.campaign_id=?" if campaign_id else ""
        params = (period, campaign_id) if campaign_id else (period,)
        row = self.conn.execute(f"""SELECT COALESCE(SUM(CASE WHEN b.state='held' THEN b.amount_micro
            ELSE COALESCE(t.cost_micro,b.amount_micro) END),0) AS used
            FROM budget_reservation b JOIN tool_call t ON t.id=b.tool_call_id
            WHERE b.{column}=?{extra}""", params).fetchone()
        return row["used"]

    def reserve(self, execution_id: str, *, city: str, amount_micro: int = 10_000,
                source: str = "google_maps") -> dict:
        if source not in SOURCES:
            raise DomainError("Fonte inválida")
        run = self.run(execution_id)
        if not run or run["state"] != "running":
            raise DomainError("Rodada não está em execução")
        campaign = run["campaign_snapshot"]
        settings = self.conn.execute("SELECT * FROM workspace_settings WHERE id=1").fetchone()
        cp, gp = _period(campaign["timezone"]), _period(settings["timezone"])
        with transaction(self.conn):
            run_used = self.conn.execute("""SELECT COALESCE(SUM(CASE WHEN b.state='held' THEN b.amount_micro
                ELSE COALESCE(t.cost_micro,b.amount_micro) END),0) AS used
                FROM tool_call t JOIN budget_reservation b ON b.tool_call_id=t.id WHERE t.execution_id=?""",
                (execution_id,)).fetchone()["used"]
            if run_used + amount_micro > campaign["run_cap_micro"]:
                raise DomainError("Orçamento da rodada insuficiente para a próxima chamada")
            if self._used("campaign", cp, campaign["id"]) + amount_micro > campaign["monthly_cap_micro"]:
                raise DomainError("Orçamento mensal da campanha esgotado")
            if self._used("global", gp) + amount_micro > settings["global_monthly_cap_micro"]:
                raise DomainError("Orçamento mensal global esgotado")
            call_id = str(uuid.uuid4())
            key = str(uuid.uuid4())
            timestamp = now()
            self.conn.execute("""INSERT INTO tool_call(id,execution_id,endpoint,idempotency_key,city,reserved_micro,created_at)
                VALUES(?,?,?,?,?,?,?)""", (call_id, execution_id, SOURCES[source].endpoint, key, city, amount_micro, timestamp))
            self.conn.execute("""INSERT INTO budget_reservation(tool_call_id,campaign_id,campaign_period,global_period,amount_micro,state,created_at)
                VALUES(?,?,?,?,?,'held',?)""", (call_id, campaign["id"], cp, gp, amount_micro, timestamp))
        return {"id": call_id, "idempotency_key": key, "reserved_micro": amount_micro}

    def region_due(self, campaign_id: str, *, city: str, uf: str, query: str,
                   source: str = "google_maps") -> bool:
        row = self.conn.execute("""SELECT expires_at FROM search_cursor WHERE campaign_id=? AND source=?
            AND city=? AND uf=? AND query=?""", (campaign_id, source, city, uf, query)).fetchone()
        return not row or row["expires_at"] <= now()

    def mark_region(self, campaign_id: str, *, city: str, uf: str, query: str, ttl_days: int = 7,
                    source: str = "google_maps"):
        timestamp = now()
        expires = (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat()
        with transaction(self.conn):
            self.conn.execute("""INSERT INTO search_cursor(campaign_id,source,city,uf,query,last_collected_at,expires_at)
                VALUES(?,?,?,?,?,?,?) ON CONFLICT(campaign_id,source,city,uf,query)
                DO UPDATE SET last_collected_at=excluded.last_collected_at,expires_at=excluded.expires_at""",
                (campaign_id, source, city, uf, query, timestamp, expires))

    def settle(self, call_id: str, *, cost_micro: int | None, treg_call_id: str | None,
               error: str | None = None) -> None:
        row = self.conn.execute("SELECT reserved_micro,execution_id FROM tool_call WHERE id=?", (call_id,)).fetchone()
        if not row:
            raise DomainError("Chamada não encontrada")
        if cost_micro is not None and not 0 <= cost_micro <= row["reserved_micro"]:
            raise DomainError("Cobrança excedeu a reserva; requer reconciliação manual")
        with transaction(self.conn):
            self.conn.execute("""UPDATE tool_call SET treg_call_id=?,cost_micro=?,financial_state=?,settled_at=?,error=? WHERE id=?""",
                              (treg_call_id, cost_micro, "confirmed" if cost_micro is not None else "pending",
                               now() if cost_micro is not None else None, error, call_id))
            if cost_micro is not None:
                self.conn.execute("UPDATE budget_reservation SET state='settled' WHERE tool_call_id=?", (call_id,))
            summary = self.conn.execute("""SELECT COUNT(*) FILTER (WHERE financial_state='pending') AS pending,
                COALESCE(SUM(cost_micro),0) AS cost FROM tool_call WHERE execution_id=?""",
                (row["execution_id"],)).fetchone()
            self.conn.execute("UPDATE execution SET cost_micro=?,financial_state=? WHERE id=?",
                              (summary["cost"], "pending" if summary["pending"] else "confirmed", row["execution_id"]))

    def pending_calls(self) -> list[dict]:
        return [dict(row) for row in self.conn.execute("""SELECT id,execution_id,treg_call_id,reserved_micro,created_at,error
            FROM tool_call WHERE financial_state='pending' ORDER BY created_at""")]

    def reconcile_pending(self, *, token: str) -> list[dict]:
        """Consulta auditoria/ledger; não repete a requisição cobrada."""
        settings = self.conn.execute("SELECT treg_org FROM workspace_settings WHERE id=1").fetchone()
        org = settings["treg_org"] if settings else None
        outcomes = []
        for local in self.pending_calls():
            call_id = local["treg_call_id"]
            try:
                if not call_id:
                    call_id = treg.find_call(token=token, org=org, local_call_id=local["id"])
                if not call_id:
                    outcomes.append({"local_call_id": local["id"], "state": "pending",
                                     "reason": "ID Treg ainda não localizado; reserva mantida"})
                    continue
                remote = treg.get_call(token=token, org=org, call_id=call_id)
                entries = remote.get("ledger") or []
                terminal = any(e.get("kind") in ("settle", "release") for e in entries)
                if not terminal:
                    outcomes.append({"local_call_id": local["id"], "state": "pending",
                                     "reason": "Ledger ainda sem liquidação ou liberação"})
                    continue
                cost = remote.get("charged_micro")
                if not isinstance(cost, int) or cost < 0:
                    raise DomainError("Custo do ledger inválido")
                self.settle(local["id"], cost_micro=cost, treg_call_id=call_id)
                outcomes.append({"local_call_id": local["id"], "state": "confirmed",
                                 "cost_micro": cost, "treg_call_id": call_id})
            except (treg.TregError, DomainError) as exc:
                outcomes.append({"local_call_id": local["id"], "state": "pending", "reason": str(exc)})
        return outcomes

    def add_place(self, execution_id: str, item: dict, *, city: str, uf: str, niche: str) -> str | None:
        lead = normalize("google_maps", item, city=city, uf=uf, niche=niche)
        return self.add_lead(execution_id, lead)

    def add_lead(self, execution_id: str, lead: dict | None) -> str | None:
        if lead is None:
            return None
        city, uf, niche = lead["city"], lead["uf"], lead["niche"]
        timestamp = now()
        with transaction(self.conn):
            existing = self.conn.execute("SELECT lead_id FROM lead_source WHERE source=? AND external_id=?",
                                         (lead["source"], lead["external_id"])).fetchone()
            lead_id = existing["lead_id"] if existing else None
            if not lead_id and lead["phone"]:
                match = self.conn.execute("""SELECT id FROM lead WHERE phone=? AND city=? AND uf=?
                    AND lower(name)=lower(?) LIMIT 1""",
                    (lead["phone"], city, uf, lead["name"])).fetchone()
                lead_id = match["id"] if match else None
            if not lead_id and lead["domain"]:
                match = self.conn.execute("""SELECT id FROM lead WHERE domain=? AND city=? AND uf=?
                    AND lower(name)=lower(?) LIMIT 1""",
                    (lead["domain"], city, uf, lead["name"])).fetchone()
                lead_id = match["id"] if match else None
            if not lead_id:
                lead_id = str(uuid.uuid4())
                self.conn.execute("""INSERT INTO lead(id,name,niche,city,uf,domain,website,phone,email,first_seen_at,last_seen_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (lead_id, lead["name"], niche, city, uf,
                    lead["domain"], lead["website"], lead["phone"], lead["email"], timestamp, timestamp))
                self.conn.execute("UPDATE execution SET new_global=new_global+1 WHERE id=?", (execution_id,))
            else:
                self.conn.execute("""UPDATE lead SET website=COALESCE(?,website),domain=COALESCE(?,domain),
                    phone=COALESCE(?,phone),last_seen_at=? WHERE id=?""",
                    (lead["website"], lead["domain"], lead["phone"], timestamp, lead_id))
                self.conn.execute("UPDATE execution SET updated=updated+1 WHERE id=?", (execution_id,))
            self.conn.execute("""INSERT INTO lead_source(lead_id,source,external_id,evidence_url,collected_at)
                VALUES(?,?,?,?,?) ON CONFLICT(source,external_id) DO UPDATE SET evidence_url=excluded.evidence_url,
                collected_at=excluded.collected_at""",
                (lead_id, lead["source"], lead["external_id"], lead["evidence_url"], timestamp))
            campaign_id = self.run(execution_id)["campaign_id"]
            association = self.conn.execute("SELECT 1 FROM lead_campaign WHERE lead_id=? AND campaign_id=?",
                                            (lead_id, campaign_id)).fetchone()
            if not association:
                self.conn.execute("""INSERT INTO lead_campaign(lead_id,campaign_id,first_execution_id,first_seen_at,last_seen_at)
                    VALUES(?,?,?,?,?)""", (lead_id, campaign_id, execution_id, timestamp, timestamp))
                self.conn.execute("UPDATE execution SET new_campaign=new_campaign+1 WHERE id=?", (execution_id,))
            else:
                self.conn.execute("UPDATE lead_campaign SET last_seen_at=? WHERE lead_id=? AND campaign_id=?",
                                  (timestamp, lead_id, campaign_id))
                self.conn.execute("UPDATE execution SET duplicate=duplicate+1 WHERE id=?", (execution_id,))
        return lead_id

    def finish(self, execution_id: str, *, state: str, error: str | None = None):
        if state not in {"succeeded", "partial", "failed", "cancelled"}:
            raise DomainError("Estado final inválido")
        with transaction(self.conn):
            financial = self.conn.execute("""SELECT COUNT(*) AS pending,
                COALESCE(SUM(cost_micro),0) AS cost FROM tool_call WHERE execution_id=? AND financial_state='pending'""",
                (execution_id,)).fetchone()["pending"]
            cost = self.conn.execute("SELECT COALESCE(SUM(cost_micro),0) AS cost FROM tool_call WHERE execution_id=?",
                                     (execution_id,)).fetchone()["cost"]
            self.conn.execute("""UPDATE execution SET state=?,financial_state=?,cost_micro=?,error=?,finished_at=? WHERE id=?""",
                (state, "pending" if financial else "confirmed", cost, error, now(), execution_id))
            self.conn.execute("UPDATE job_queue SET state=? WHERE execution_id=?", (state, execution_id))

    def leads(self, *, campaign_id: str | None = None, q: str = "", page: int = 1, size: int = 20,
              city: str | None = None, uf: str | None = None, niche: str | None = None,
              source: str | None = None, status: str | None = None,
              sort: str = "recent") -> dict:
        if page < 1 or size not in (20, 50, 100):
            raise DomainError("Paginação inválida")
        where = ["1=1"]
        params: list = []
        if campaign_id:
            where.append("EXISTS (SELECT 1 FROM lead_campaign lc WHERE lc.lead_id=l.id AND lc.campaign_id=?)")
            params.append(campaign_id)
        if q.strip():
            where.append("(l.name LIKE ? OR l.domain LIKE ? OR l.phone LIKE ? OR l.email LIKE ? OR l.niche LIKE ?)")
            params.extend([f"%{q.strip()}%"] * 5)
        for column, value in (("city", city), ("uf", uf), ("niche", niche), ("status", status)):
            if value:
                where.append(f"l.{column}=?")
                params.append(value)
        if source:
            where.append("EXISTS (SELECT 1 FROM lead_source ls WHERE ls.lead_id=l.id AND ls.source=?)")
            params.append(source)
        clause = " AND ".join(where)
        total = self.conn.execute(f"SELECT COUNT(*) AS n FROM lead l WHERE {clause}", params).fetchone()["n"]
        ordering = {"recent": "l.last_seen_at DESC", "name": "l.name COLLATE NOCASE ASC",
                    "city": "l.city COLLATE NOCASE ASC"}.get(sort)
        if ordering is None:
            raise DomainError("Ordenação inválida")
        rows = self.conn.execute(f"SELECT l.* FROM lead l WHERE {clause} ORDER BY {ordering} LIMIT ? OFFSET ?",
                                 (*params, size, (page - 1) * size)).fetchall()
        items = [dict(r) for r in rows]
        for lead in items:
            lead["sources"] = [r["source"] for r in self.conn.execute(
                "SELECT source FROM lead_source WHERE lead_id=? ORDER BY source", (lead["id"],))]
        return {"total": total, "page": page, "size": size, "items": items}

    def lead(self, lead_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM lead WHERE id=?", (lead_id,)).fetchone()
        if not row:
            return None
        value = dict(row)
        value["sources"] = [dict(r) for r in self.conn.execute("SELECT source,external_id,evidence_url,collected_at FROM lead_source WHERE lead_id=?", (lead_id,))]
        value["campaigns"] = [dict(r) for r in self.conn.execute("SELECT campaign_id,notes,first_seen_at,last_seen_at FROM lead_campaign WHERE lead_id=?", (lead_id,))]
        return value

    def set_lead_status(self, lead_id: str, status: str) -> dict:
        if status not in {"Novo", "Em análise", "Contatado", "Proposta enviada", "Fechado"}:
            raise DomainError("Status comercial inválido")
        with transaction(self.conn):
            changed = self.conn.execute("UPDATE lead SET status=? WHERE id=?", (status, lead_id)).rowcount
            if not changed:
                raise DomainError("Lead não encontrado")
        return self.lead(lead_id)

    def update_global_budget(self, amount_micro: int, timezone: str) -> dict:
        if amount_micro <= 0:
            raise DomainError("Teto global precisa ser positivo")
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise DomainError("Fuso IANA inválido") from exc
        with transaction(self.conn):
            self.conn.execute("UPDATE workspace_settings SET global_monthly_cap_micro=?,timezone=? WHERE id=1",
                              (amount_micro, timezone))
        return self.status()

    def status(self) -> dict:
        settings = self.conn.execute("SELECT * FROM workspace_settings WHERE id=1").fetchone()
        return {"campaigns": self.conn.execute("SELECT COUNT(*) AS n FROM campaign").fetchone()["n"],
                "leads": self.conn.execute("SELECT COUNT(*) AS n FROM lead").fetchone()["n"],
                "queued": self.conn.execute("SELECT COUNT(*) AS n FROM job_queue WHERE state='queued'").fetchone()["n"],
                "global_monthly_cap_micro": settings["global_monthly_cap_micro"],
                "global_period": _period(settings["timezone"]),
                "global_used_micro": self._used("global", _period(settings["timezone"]))}
