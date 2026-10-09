"""API do painel incorporado, montada pelo Hermes em /api/plugins/hermes-prospector/."""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from functools import wraps
from pathlib import Path
from threading import Event, Thread

from fastapi import APIRouter, HTTPException
from fastapi.routing import APIRoute

# O Hermes carrega este arquivo por caminho, sem instalar o pacote no ambiente.
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from prospector.service import DomainError, ProspectorService  # noqa: E402
from prospector.web import create_app  # noqa: E402
from prospector.worker import loop  # noqa: E402


@asynccontextmanager
async def lifespan(_app):
    # Inicializa o SQLite antes de iniciar o worker para evitar disputa no PRAGMA WAL.
    initial = ProspectorService()
    initial.close()
    stop = Event()
    worker = Thread(target=loop, args=(stop,), daemon=True)
    worker.start()
    try:
        yield
    finally:
        stop.set()
        worker.join(timeout=5)


router = APIRouter(lifespan=lifespan)
_standalone = create_app(start_worker=False, integrated=True)


def _guard(handler):
    @wraps(handler)
    def wrapped(*args, **kwargs):
        try:
            return handler(*args, **kwargs)
        except DomainError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return wrapped


for route in _standalone.routes:
    if not isinstance(route, APIRoute) or not route.path.startswith("/api/"):
        continue
    if route.path in ("/api/login", "/api/logout", "/api/session"):
        continue
    router.add_api_route(route.path[4:], _guard(route.endpoint), methods=route.methods,
                         name=route.name, response_class=route.response_class,
                         status_code=route.status_code)


@router.get("/health")
def health():
    return {"status": "ok", "mode": "hermes-dashboard"}
