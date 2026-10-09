from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

from . import __version__, auth, treg
from .config import data_dir
from .db import now
from .secrets import read_token, save_token
from .service import DomainError, ProspectorService


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="prospector", description="Hermes Prospector — administração local")
    p.add_argument("--data-dir", type=Path, help="Diretório persistente absoluto do perfil")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("doctor")
    admin = sub.add_parser("admin", help="Configurar senha do painel")
    admin.add_argument("action", choices=["set-password"])
    token = sub.add_parser("treg", help="Cadastrar chave por entrada privada")
    token.add_argument("action", choices=["set-token", "status"])
    token.add_argument("--org", help="Slug da equipe, exigido para token de identidade")
    campaign = sub.add_parser("campaign", help="Criar ou listar campanhas")
    campaign.add_argument("action", choices=["list", "create"])
    campaign.add_argument("--name")
    campaign.add_argument("--niche")
    campaign.add_argument("--city", action="append", default=[], help="Cidade,UF; repetir")
    run = sub.add_parser("run", help="Enfileirar busca manual")
    run.add_argument("campaign_id")
    sub.add_parser("runs")
    sub.add_parser("reconcile", help="Conferir cobranças pendentes no ledger Treg; sem novas buscas")
    sub.add_parser("worker-once")
    schedule_tick = sub.add_parser("schedule-tick")
    schedule_tick.add_argument("campaign_id")
    sub.add_parser("backup")
    legacy = sub.add_parser("import-legacy", help="Prévia ou importação transacional de CSV/JSON legado")
    legacy.add_argument("path", type=Path)
    legacy.add_argument("--apply", action="store_true", help="Executar após revisar a prévia")
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.data_dir:
        if not args.data_dir.is_absolute():
            print("--data-dir precisa ser absoluto", file=sys.stderr)
            return 2
        import os
        os.environ["PROSPECTOR_DATA_DIR"] = str(args.data_dir)
    service = None
    try:
        if args.command == "serve":
            import uvicorn
            from .web import app
            uvicorn.run(app, host=args.host, port=args.port, proxy_headers=True,
                        forwarded_allow_ips="127.0.0.1")
            return 0
        service = ProspectorService()
        if args.command == "status":
            result = {**service.status(), "treg_configured": bool(read_token()), "data_dir": str(data_dir())}
        elif args.command == "doctor":
            result = {"version": __version__, "data_dir": str(data_dir()), "database": "ok",
                      "admin_configured": bool(service.conn.execute("SELECT 1 FROM admin WHERE id=1").fetchone()),
                      "treg_configured": bool(read_token()),
                      "queued": service.status()["queued"],
                      "running": service.conn.execute("SELECT COUNT(*) FROM execution WHERE state='running'").fetchone()[0]}
            try:
                result["google_maps"] = treg.catalog_capability()
            except treg.TregError as exc:
                result["google_maps"] = {"status": "unavailable", "reason": str(exc)}
        elif args.command == "admin":
            password = getpass.getpass("Nova senha do painel (mínimo 12 caracteres): ")
            repeat = getpass.getpass("Repita a senha: ")
            if password != repeat:
                raise DomainError("As senhas não coincidem")
            auth.set_admin(service.conn, password)
            result = {"ok": True, "message": "Senha configurada"}
        elif args.command == "treg":
            if args.action == "status":
                result = {"configured": bool(read_token())}
            else:
                token = getpass.getpass("Chave Treg (entrada privada): ").strip()
                identity = treg.validate_token(token, args.org)
                save_token(token)
                service.conn.execute("UPDATE workspace_settings SET treg_org=? WHERE id=1", (args.org or None,))
                service.conn.execute("UPDATE credential_settings SET status='connected',org=?,validated_at=?,error=NULL WHERE id=1",
                                     (args.org or None, now()))
                result = {"configured": True, "identity": identity}
        elif args.command == "campaign":
            if args.action == "list":
                result = service.campaigns()
            else:
                cities = []
                for value in args.city:
                    if "," not in value:
                        raise DomainError("Use --city Cidade,UF")
                    city, uf = value.rsplit(",", 1)
                    cities.append({"city": city, "uf": uf})
                result = service.create_campaign(name=args.name or "", niche=args.niche or "", cities=cities)
        elif args.command == "run":
            if not read_token():
                raise DomainError("Configure a chave Treg antes de buscar")
            result = service.enqueue(args.campaign_id)
        elif args.command == "runs":
            result = service.runs()
        elif args.command == "reconcile":
            token = read_token()
            if not token:
                raise DomainError("Chave Treg não configurada")
            result = service.reconcile_pending(token=token)
        elif args.command == "worker-once":
            from .worker import process_one
            result = process_one(service) or {"queued": False}
        elif args.command == "schedule-tick":
            from .schedule import tick
            result = tick(service, args.campaign_id)
        elif args.command == "backup":
            from .backup import backup
            result = {"path": str(backup(service.conn))}
        elif args.command == "import-legacy":
            from .legacy import import_file, preview
            result = import_file(service, args.path) if args.apply else preview(args.path)
        else:
            raise DomainError("Comando desconhecido")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (DomainError, ValueError, treg.TregError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        if service:
            service.close()


if __name__ == "__main__":
    raise SystemExit(main())
