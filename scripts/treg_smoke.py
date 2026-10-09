#!/usr/bin/env python3
"""Validação Treg gratuita por padrão; uma chamada paga somente com flags explícitas."""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path

from prospector import treg
from prospector.service import ProspectorService
from prospector.worker import process_one


PROJECT = Path(__file__).resolve().parents[1]


def private_credentials(path: Path) -> tuple[str, str | None]:
    path = path.expanduser().absolute()
    if (path == PROJECT or PROJECT in path.parents) and path != PROJECT / ".env":
        raise ValueError("Dentro do repositório, use somente o arquivo .env ignorado pelo Git")
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("A chave deve ser arquivo regular seu, sem link, com permissão 0600 ou 0400")
    if info.st_size == 0 or info.st_size > 4096:
        raise ValueError("Arquivo de chave vazio ou grande demais")
    contents = path.read_text(encoding="utf-8").strip()
    org = None
    if path.name == ".env":
        fields = {}
        for line in contents.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                raise ValueError("Linha inválida no .env; use TREG_TOKEN= e TREG_ORG=")
            name, value = line.split("=", 1)
            if name not in ("TREG_TOKEN", "TREG_ORG") or name in fields:
                raise ValueError("O .env de teste só aceita TREG_TOKEN e TREG_ORG uma vez cada")
            fields[name] = value.strip().strip('"').strip("'")
        token = fields.get("TREG_TOKEN", "")
        org = fields.get("TREG_ORG") or None
    else:
        token = contents
    if not token or "\n" in token or "\r" in token:
        raise ValueError("O arquivo deve conter somente a chave Treg")
    return token, org


def private_token(path: Path) -> str:
    return private_credentials(path)[0]


def micro_usd(value: str) -> int:
    try:
        amount = Decimal(value)
        micro = amount * 1_000_000
    except InvalidOperation as exc:
        raise ValueError("--max-usd inválido") from exc
    if micro != micro.to_integral_value() or not 0 < micro <= 10_000:
        raise ValueError("Use teto maior que zero e até US$ 0,01, com no máximo seis casas decimais")
    return int(micro)


def new_state_dir(path: Path) -> Path:
    path = path.expanduser().absolute()
    if path == PROJECT or PROJECT in path.parents:
        raise ValueError("O estado do teste pago deve ficar fora do repositório")
    path.mkdir(mode=0o700, parents=False, exist_ok=False)
    path.chmod(0o700)
    return path


def write_audit(path: Path, value: dict) -> None:
    target = path / "attempt.json"
    temp = path / "attempt.json.tmp"
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temp, target)


def paid_once(token: str, org: str | None, cap_micro: int, directory: Path,
              *, niche: str = "clínica odontológica") -> dict:
    if not niche.strip() or len(niche) > 120:
        raise ValueError("Nicho de teste inválido")
    directory = new_state_dir(directory)
    service = ProspectorService(directory / "prospector.db")
    try:
        service.update_global_budget(cap_micro, "America/Fortaleza")
        campaign = service.create_campaign(name="Teste controlado Treg", niche=niche,
            cities=[{"city": "Fortaleza", "uf": "CE"}], target_leads=1,
            run_cap_micro=cap_micro, monthly_cap_micro=cap_micro)
        service.conn.execute("UPDATE workspace_settings SET treg_org=? WHERE id=1", (org,))
        run = service.enqueue(campaign["id"])
        audit = {"run_id": run["id"], "state_dir": str(directory), "max_cost_micro": cap_micro,
                 "calls_allowed": 1, "state": "prepared", "niche": niche}
        write_audit(directory, audit)
        response_summary = {}

        def tracked_search(**kwargs):
            response = treg.search_maps(**kwargs)
            response_summary.update(response.diagnostic or {})
            return response

        result = process_one(service, token=token, search=tracked_search)
        attempted = service.conn.execute("SELECT COUNT(*) FROM tool_call WHERE execution_id=?", (run["id"],)).fetchone()[0]
        audit.update({"state": result["state"], "financial_state": result["financial_state"],
                      "cost_micro": result["cost_micro"], "leads": service.leads()["total"],
                      "attempted_calls": attempted, "pending_calls": len(service.pending_calls()),
                      "response_summary": response_summary, "error": result["error"]})
        write_audit(directory, audit)
        return audit
    finally:
        service.close()


def catalog_example_once(token: str, org: str | None, cap_micro: int, directory: Path,
                         *, query: str = "coffee", location: str = "Austin, TX") -> dict:
    """Uma chamada de diagnóstico; inspeciona forma, sem armazenar contatos."""
    if not query.strip() or not location.strip() or len(query) > 120 or len(location) > 120:
        raise ValueError("Consulta/local do teste inválidos")
    directory = new_state_dir(directory)
    local_id = str(uuid.uuid4())
    idempotency_key = str(uuid.uuid4())
    audit = {"state_dir": str(directory), "max_cost_micro": cap_micro,
             "calls_allowed": 1, "local_call_id": local_id, "state": "prepared",
             "idempotency_key": idempotency_key,
             "example": {"query": query, "location": location, "limit": 1}}
    write_audit(directory, audit)
    try:
        result = treg.search_maps(token=token, org=org, query=query, city="diagnostic", uf="XX",
            location_override=location, language=None, limit=1,
            idempotency_key=idempotency_key, max_cost_micro=cap_micro, local_call_id=local_id)
        audit.update({"state": "responded", "cost_micro": result.cost_micro,
                      "treg_call_id": result.call_id, "response_summary": result.diagnostic})
    except treg.TregError as exc:
        audit.update({"state": "uncertain", "cost_micro": exc.cost_micro,
                      "treg_call_id": exc.call_id, "error": str(exc)})
    write_audit(directory, audit)
    return audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=PROJECT / ".env",
                        help="Arquivo privado .env (padrão: .env na raiz do repositório)")
    parser.add_argument("--org", help="Slug da equipe para token de identidade")
    parser.add_argument("--paid", action="store_true", help="Autoriza exatamente uma chamada paga")
    parser.add_argument("--catalog-example", action="store_true",
                        help="Usa o exemplo público coffee/Austin para diagnosticar o endpoint")
    parser.add_argument("--probe-query", default="coffee", help="Consulta para --catalog-example")
    parser.add_argument("--probe-location", default="Austin, TX", help="Local para --catalog-example")
    parser.add_argument("--niche", default="clínica odontológica", help="Nicho da campanha de teste em Fortaleza")
    parser.add_argument("--max-usd", help="Teto da única chamada paga, até US$ 0,01")
    parser.add_argument("--state-dir", type=Path, help="Diretório novo e externo ao repositório para auditoria")
    args = parser.parse_args(argv)
    if args.paid != bool(args.max_usd) or args.paid != bool(args.state_dir):
        parser.error("--paid exige --max-usd e --state-dir; sem --paid, a validação é gratuita")
    if args.catalog_example and not args.paid:
        parser.error("--catalog-example exige --paid")
    if (args.probe_query != "coffee" or args.probe_location != "Austin, TX") and not args.catalog_example:
        parser.error("--probe-query e --probe-location exigem --catalog-example")
    try:
        token, file_org = private_credentials(args.env_file)
        org = args.org or file_org
        treg.validate_token(token, org)
        capability = treg.catalog_capability()
        if not capability["discovery"] or not capability["platform_eligible"] or capability["blocked"]:
            raise ValueError("Endpoint Google Maps não está disponível no catálogo; nenhuma busca foi feita")
        report = {"authenticated": True, "source": capability["source"],
                  "endpoint": capability["endpoint"], "catalog_cost_reference": capability["cost"],
                  "paid_calls": 0}
        if args.paid:
            if args.catalog_example:
                report["paid_test"] = catalog_example_once(token, org, micro_usd(args.max_usd), args.state_dir,
                    query=args.probe_query, location=args.probe_location)
                report["paid_calls"] = 1
            else:
                report["paid_test"] = paid_once(token, org, micro_usd(args.max_usd), args.state_dir,
                                                niche=args.niche)
                report["paid_calls"] = report["paid_test"]["attempted_calls"]
        print(json.dumps(report, ensure_ascii=False, indent=2))
        expected = "responded" if args.catalog_example else "succeeded"
        return 0 if not args.paid or report["paid_test"]["state"] == expected else 1
    except (OSError, ValueError, treg.TregError) as exc:
        print(f"Teste interrompido: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
