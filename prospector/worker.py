from __future__ import annotations

import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from threading import Event

from . import treg
from .secrets import read_token
from .service import DomainError, ProspectorService
from .sources import SOURCES, normalize


def process_one(service: ProspectorService, *, token: str | None = None,
                search=treg.search_maps) -> dict | None:
    run = service.claim()
    if not run:
        return None
    execution_id = run["id"]
    campaign = run["campaign_snapshot"]
    settings = service.conn.execute("SELECT treg_org FROM workspace_settings WHERE id=1").fetchone()
    org = settings["treg_org"] if settings else None
    token = token or read_token()
    if not token:
        service.finish(execution_id, state="failed", error="Chave Treg não configurada")
        return service.run(execution_id)
    sources = campaign.get("sources") or [campaign.get("source", "google_maps")]
    if search is treg.search_maps:
        try:
            for source in sources:
                capability = treg.source_capability(source)
                if not capability["discovery"] or not capability["platform_eligible"] or capability["blocked"]:
                    service.finish(execution_id, state="failed", error=f"Fonte {source} sem suporte ou acesso no catálogo Treg")
                    return service.run(execution_id)
                try:
                    expected = int((Decimal(str(capability["cost"]["usd"])) * 1_000_000).to_integral_value(rounding="ROUND_CEILING"))
                except (KeyError, TypeError, ValueError, InvalidOperation):
                    service.finish(execution_id, state="failed", error=f"Preço da fonte {source} indisponível no catálogo Treg")
                    return service.run(execution_id)
                if expected > min(SOURCES[source].estimate_micro, campaign["run_cap_micro"]):
                    service.finish(execution_id, state="failed", error=f"Preço da fonte {source} excede o teto por chamada")
                    return service.run(execution_id)
        except (treg.TregError, KeyError) as exc:
            service.finish(execution_id, state="failed", error=str(exc))
            return service.run(execution_id)
    completed = 0
    calls = 0
    errors = []
    try:
        stop = False
        for region in campaign["cities"]:
            for source in sources:
                if service.run(execution_id)["new_campaign"] >= campaign["target_leads"]:
                    stop = True
                    break
                city, uf = region["city"], region["uf"]
                if not service.region_due(campaign["id"], city=city, uf=uf, query=campaign["niche"], source=source):
                    continue
                remaining = campaign["target_leads"] - service.run(execution_id)["new_campaign"]
                call = service.reserve(execution_id, city=city, source=source,
                                       amount_micro=min(SOURCES[source].estimate_micro, campaign["run_cap_micro"]))
                calls += 1
                try:
                    kwargs = dict(token=token, org=org, query=campaign["niche"], city=city, uf=uf,
                                  limit=min(20, remaining), idempotency_key=call["idempotency_key"],
                                  max_cost_micro=call["reserved_micro"], local_call_id=call["id"])
                    result = search(**kwargs) if source == "google_maps" else treg.search_source(source=source, **kwargs)
                except treg.TregError as exc:
                    service.settle(call["id"], cost_micro=exc.cost_micro, treg_call_id=exc.call_id, error=str(exc))
                    errors.append(f"{source}: {exc}")
                    # Resposta desconhecida pode ter sido cobrada; não faça mais chamadas.
                    stop = True
                    break
                service.settle(call["id"], cost_micro=result.cost_micro, treg_call_id=result.call_id)
                if result.cost_micro is None:
                    errors.append("Custo Treg indisponível; reserva mantida")
                    stop = True
                    break
                service.mark_region(campaign["id"], city=city, uf=uf, query=campaign["niche"], source=source)
                for item in result.items:
                    lead = normalize(source, item, city=city, uf=uf, niche=campaign["niche"])
                    if service.add_lead(execution_id, lead):
                        completed += 1
            if stop:
                break
    except DomainError as exc:
        errors.append(str(exc))
    except Exception:
        errors.append("Falha interna na rodada; verifique o diagnóstico")
    if not calls and not errors:
        errors.append("Todas as regiões foram consultadas recentemente; aguarde o prazo de reconsulta")
    state = "partial" if errors and completed else "failed" if errors else "succeeded"
    service.finish(execution_id, state=state, error="; ".join(errors) or None)
    return service.run(execution_id)


def loop(stop: Event, *, path: Path | None = None, interval: float = 2.0):
    while not stop.is_set():
        service = ProspectorService(path)
        try:
            processed = process_one(service)
        finally:
            service.close()
        if not processed:
            stop.wait(interval)
