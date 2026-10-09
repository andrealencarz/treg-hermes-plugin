from __future__ import annotations

import csv
import io
import os
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Event, Thread

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, Response as FastAPIResponse
from pydantic import BaseModel, Field

from . import auth, schedule, treg
from .db import now
from .secrets import read_token, save_token
from .service import DomainError, ProspectorService
from .worker import loop

STATIC = Path(__file__).parent / "static"


class CampaignIn(BaseModel):
    name: str
    niche: str
    service: str = ""
    cities: list[dict]
    target_leads: int = Field(30, ge=1, le=1000)
    run_cap_micro: int = Field(1_000_000, gt=0)
    monthly_cap_micro: int = Field(30_000_000, gt=0)
    timezone: str = "America/Fortaleza"


class CampaignUpdate(BaseModel):
    name: str | None = None
    niche: str | None = None
    cities: list[dict] | None = None
    target_leads: int | None = None
    run_cap_micro: int | None = None
    monthly_cap_micro: int | None = None


class StateIn(BaseModel):
    state: str


class StatusIn(BaseModel):
    status: str


class BudgetIn(BaseModel):
    global_monthly_cap_micro: int
    timezone: str = "America/Fortaleza"


class ScheduleIn(BaseModel):
    frequency: str
    days: list[int] = []
    times: list[str] = []
    timezone: str = "America/Fortaleza"
    once_at: str | None = None


class TokenIn(BaseModel):
    token: str
    org: str | None = None


class LoginIn(BaseModel):
    password: str


def create_app(*, db_file: Path | None = None, start_worker: bool = True) -> FastAPI:
    stop = Event()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        thread = None
        if start_worker:
            thread = Thread(target=loop, args=(stop,), kwargs={"path": db_file}, daemon=True)
            thread.start()
        yield
        stop.set()
        if thread:
            thread.join(timeout=5)

    app = FastAPI(title="Hermes Prospector", lifespan=lifespan, docs_url=None, redoc_url=None)

    def service():
        instance = ProspectorService(db_file)
        try:
            yield instance
        finally:
            instance.close()

    def current(request: Request, db: ProspectorService = Depends(service)):
        session = auth.get_session(db.conn, request.cookies.get("prospector_session"))
        if not session:
            raise HTTPException(status_code=401, detail="Faça login")
        return session

    def mutation(request: Request, session=Depends(current)):
        csrf = request.headers.get("X-CSRF-Token", "")
        if not csrf or csrf != session["csrf_token"]:
            raise HTTPException(status_code=403, detail="Proteção CSRF: recarregue a página")
        return session

    def require_https(request: Request):
        host = request.url.hostname or ""
        if request.url.scheme != "https" and host not in ("127.0.0.1", "localhost", "testserver"):
            raise HTTPException(status_code=403, detail="Cadastre a chave somente por HTTPS ou terminal privado")

    @app.exception_handler(DomainError)
    async def domain_error(_request: Request, exc: DomainError):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/assets/app.js")
    def javascript():
        return FileResponse(STATIC / "app.js", media_type="text/javascript")

    @app.get("/assets/style.css")
    def stylesheet():
        return FileResponse(STATIC / "style.css", media_type="text/css")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/login")
    def login(payload: LoginIn, request: Request, response: Response, db: ProspectorService = Depends(service)):
        try:
            result = auth.login(db.conn, payload.password, request.client.host if request.client else "unknown")
        except ValueError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        if not result:
            raise HTTPException(status_code=401, detail="Senha incorreta")
        token, csrf = result
        response.set_cookie("prospector_session", token, httponly=True, secure=os.environ.get("PROSPECTOR_COOKIE_SECURE", "1") != "0",
                            samesite="strict", max_age=43200)
        return {"csrf": csrf}

    @app.post("/api/logout")
    def logout(request: Request, response: Response, db: ProspectorService = Depends(service), _=Depends(mutation)):
        auth.logout(db.conn, request.cookies.get("prospector_session"))
        response.delete_cookie("prospector_session")
        return {"ok": True}

    @app.get("/api/session")
    def session(info=Depends(current)):
        return {"csrf": info["csrf_token"]}

    @app.get("/api/status")
    def status(db: ProspectorService = Depends(service), _=Depends(current)):
        return {**db.status(), "treg_configured": bool(read_token())}

    @app.get("/api/campaigns")
    def campaigns(db: ProspectorService = Depends(service), _=Depends(current)):
        return db.campaigns()

    @app.post("/api/campaigns")
    def create_campaign(payload: CampaignIn, db: ProspectorService = Depends(service), _=Depends(mutation)):
        return db.create_campaign(**payload.model_dump())

    @app.patch("/api/campaigns/{campaign_id}")
    def update_campaign(campaign_id: str, payload: CampaignUpdate, db: ProspectorService = Depends(service), _=Depends(mutation)):
        return db.update_campaign(campaign_id, **payload.model_dump(exclude_none=True))

    @app.post("/api/campaigns/{campaign_id}/duplicate")
    def duplicate_campaign(campaign_id: str, db: ProspectorService = Depends(service), _=Depends(mutation)):
        return db.duplicate_campaign(campaign_id)

    @app.patch("/api/campaigns/{campaign_id}/state")
    def campaign_state(campaign_id: str, payload: StateIn, db: ProspectorService = Depends(service), _=Depends(mutation)):
        binding = db.conn.execute("SELECT state FROM schedule_binding WHERE campaign_id=?", (campaign_id,)).fetchone()
        if binding and binding["state"] == "active" and payload.state in ("paused", "archived", "draft"):
            schedule.set_active(db, campaign_id, False)
        return db.set_campaign_state(campaign_id, payload.state)

    @app.get("/api/schedules")
    def schedules(db: ProspectorService = Depends(service), _=Depends(current)):
        return schedule.schedules(db)

    @app.post("/api/schedules/{campaign_id}/preview")
    def preview_schedule(campaign_id: str, payload: ScheduleIn, db: ProspectorService = Depends(service), _=Depends(current)):
        if not db.campaign(campaign_id):
            raise HTTPException(status_code=404, detail="Campanha não encontrada")
        spec = schedule.validate(**payload.model_dump())
        return {"next_occurrences": schedule.next_occurrences(spec)}

    @app.put("/api/schedules/{campaign_id}")
    def save_schedule(campaign_id: str, payload: ScheduleIn, db: ProspectorService = Depends(service), _=Depends(mutation)):
        return schedule.save(db, campaign_id, **payload.model_dump())

    @app.post("/api/schedules/{campaign_id}/activate")
    def activate_schedule(campaign_id: str, db: ProspectorService = Depends(service), _=Depends(mutation)):
        return schedule.set_active(db, campaign_id, True)

    @app.post("/api/schedules/{campaign_id}/pause")
    def pause_schedule(campaign_id: str, db: ProspectorService = Depends(service), _=Depends(mutation)):
        return schedule.set_active(db, campaign_id, False)

    @app.post("/api/campaigns/{campaign_id}/runs")
    def enqueue(campaign_id: str, db: ProspectorService = Depends(service), _=Depends(mutation)):
        if not read_token():
            raise DomainError("Configure a chave Treg antes de buscar")
        return db.enqueue(campaign_id)

    @app.get("/api/runs")
    def runs(campaign_id: str | None = None, db: ProspectorService = Depends(service), _=Depends(current)):
        return db.runs(campaign_id)

    @app.get("/api/runs/pending")
    def pending_calls(db: ProspectorService = Depends(service), _=Depends(current)):
        return db.pending_calls()

    @app.post("/api/runs/reconcile")
    def reconcile(db: ProspectorService = Depends(service), _=Depends(mutation)):
        token = read_token()
        if not token:
            raise DomainError("Chave Treg não configurada")
        return db.reconcile_pending(token=token)

    @app.get("/api/runs/{run_id}")
    def run(run_id: str, db: ProspectorService = Depends(service), _=Depends(current)):
        value = db.run(run_id)
        if not value:
            raise HTTPException(status_code=404, detail="Rodada não encontrada")
        return value

    @app.get("/api/leads")
    def leads(campaign_id: str | None = None, q: str = "", page: int = 1, size: int = 20,
              city: str | None = None, uf: str | None = None, niche: str | None = None,
              source: str | None = None, status: str | None = None, sort: str = "recent",
              db: ProspectorService = Depends(service), _=Depends(current)):
        return db.leads(campaign_id=campaign_id, q=q, page=page, size=size, city=city, uf=uf,
                        niche=niche, source=source, status=status, sort=sort)

    @app.get("/api/leads/export.csv")
    def export_csv(campaign_id: str | None = None, q: str = "", city: str | None = None,
                   uf: str | None = None, niche: str | None = None, source: str | None = None,
                   status: str | None = None, sort: str = "recent",
                   db: ProspectorService = Depends(service), _=Depends(current)):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Nome", "Nicho", "Cidade", "UF", "Site", "Telefone", "E-mail", "Status", "Coletado"])
        page_number = 1
        while True:
            batch = db.leads(campaign_id=campaign_id, q=q, page=page_number, size=100,
                             city=city, uf=uf, niche=niche, source=source, status=status, sort=sort)
            for row in batch["items"]:
                values = [row.get(key) or "" for key in ("name", "niche", "city", "uf", "website", "phone", "email", "status", "last_seen_at")]
                writer.writerow(["'" + str(v) if str(v).startswith(("=", "+", "-", "@", "\t", "\r")) else v for v in values])
            if page_number * 100 >= batch["total"]:
                break
            page_number += 1
        return FastAPIResponse(content="\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8",
                               headers={"Content-Disposition": "attachment; filename=leads.csv"})

    @app.get("/api/leads/{lead_id}")
    def lead(lead_id: str, db: ProspectorService = Depends(service), _=Depends(current)):
        value = db.lead(lead_id)
        if not value:
            raise HTTPException(status_code=404, detail="Lead não encontrado")
        return value

    @app.patch("/api/leads/{lead_id}/status")
    def lead_status(lead_id: str, payload: StatusIn, db: ProspectorService = Depends(service), _=Depends(mutation)):
        return db.set_lead_status(lead_id, payload.status)

    @app.put("/api/settings/budget")
    def update_budget(payload: BudgetIn, db: ProspectorService = Depends(service), _=Depends(mutation)):
        return db.update_global_budget(payload.global_monthly_cap_micro, payload.timezone)

    @app.get("/api/settings/treg")
    def treg_settings(db: ProspectorService = Depends(service), _=Depends(current)):
        row = db.conn.execute("SELECT status,org,validated_at,error FROM credential_settings WHERE id=1").fetchone()
        return {"configured": bool(read_token()), **dict(row)}

    @app.post("/api/settings/treg/test")
    def test_token(payload: TokenIn, request: Request, _=Depends(mutation)):
        require_https(request)
        try:
            identity = treg.validate_token(payload.token, payload.org)
        except treg.TregError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"valid": True, "identity": identity}

    @app.put("/api/settings/treg")
    def set_token(payload: TokenIn, request: Request, db: ProspectorService = Depends(service), _=Depends(mutation)):
        require_https(request)
        try:
            identity = treg.validate_token(payload.token, payload.org)
        except treg.TregError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        save_token(payload.token)
        db.conn.execute("UPDATE workspace_settings SET treg_org=? WHERE id=1", (payload.org or None,))
        db.conn.execute("UPDATE credential_settings SET status='connected',org=?,validated_at=?,error=NULL WHERE id=1",
                        (payload.org or None, now()))
        return {"configured": True, "identity": identity}

    return app


app = create_app()
