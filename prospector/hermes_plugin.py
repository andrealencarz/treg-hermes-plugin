"""Adaptador fino para a API pública de plugins do Hermes v0.21.5."""
from __future__ import annotations

import json

from .service import ProspectorService


def _schema(name: str, description: str, properties: dict, required: list[str] | None = None):
    return {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties,
                           "required": required or [], "additionalProperties": False}}


def _s(description: str):
    return {"type": "string", "description": description}


TOOLS = [
    ("prospector_status", "Estado do painel, campanhas e orçamento; sem segredos.", {}, []),
    ("prospector_campaigns", "Lista campanhas do perfil ativo.", {}, []),
    ("prospector_campaign_create", "Cria campanha em rascunho; não inicia busca.",
     {"name": _s("Nome da campanha"), "niche": _s("Nicho de empresas"),
      "cities": {"type": "array", "items": {"type": "object", "properties":
                  {"city": _s("Cidade"), "uf": _s("UF")}, "required": ["city", "uf"]}}},
     ["name", "niche", "cities"]),
    ("prospector_configure", "Altera critérios e limites não secretos de uma campanha.",
     {"campaign_id": _s("ID da campanha"), "name": _s("Novo nome"), "niche": _s("Novo nicho"),
      "target_leads": {"type": "integer"}, "run_cap_micro": {"type": "integer"},
      "monthly_cap_micro": {"type": "integer"}}, ["campaign_id"]),
    ("prospector_campaign_update", "Atualiza ou arquiva campanha pelo ID.",
     {"campaign_id": _s("ID da campanha"), "state": {"type": "string", "enum": ["draft","active","paused","archived"]}},
     ["campaign_id", "state"]),
    ("prospector_run", "Enfileira uma busca paga após pedido explícito do usuário.",
     {"campaign_id": _s("ID da campanha")}, ["campaign_id"]),
    ("prospector_runs", "Histórico de rodadas, custos e falhas.",
     {"campaign_id": _s("Filtrar por campanha; opcional")}, []),
    ("prospector_list_leads", "Leads com busca e paginação.",
     {"campaign_id": _s("Filtrar por campanha; opcional"), "q": _s("Busca textual"),
     "page": {"type": "integer"}}, []),
    ("prospector_schedule", "Consulta ou ativa/pausa a programação nativa de uma campanha.",
     {"action": {"type": "string", "enum": ["list", "activate", "pause"]},
      "campaign_id": _s("ID da campanha para ativar/pausar")}, ["action"]),
    ("prospector_diagnose", "Diagnóstico local sem chamadas pagas ou segredos.", {}, []),
]


def _database_path():
    from hermes_constants import get_hermes_home
    return get_hermes_home() / "plugin-data" / "hermes-prospector" / "prospector.db"


def _handle(name: str, args: dict, **_kwargs) -> str:
    db = None
    try:
        db = ProspectorService(_database_path())
        if name == "prospector_status":
            value = db.status()
        elif name == "prospector_campaigns":
            value = db.campaigns()
        elif name == "prospector_campaign_create":
            value = db.create_campaign(name=args["name"], niche=args["niche"], cities=args["cities"])
        elif name == "prospector_configure":
            value = db.update_campaign(args["campaign_id"], **{key: args[key] for key in
                ("name", "niche", "target_leads", "run_cap_micro", "monthly_cap_micro") if key in args})
        elif name == "prospector_campaign_update":
            from . import schedule
            campaign_id, state = args["campaign_id"], args["state"]
            if state == "active":
                schedule.set_active(db, campaign_id, True)
                value = db.campaign(campaign_id)
            else:
                row = db.conn.execute("SELECT state FROM schedule_binding WHERE campaign_id=?", (campaign_id,)).fetchone()
                if row and row["state"] == "active":
                    schedule.set_active(db, campaign_id, False)
                value = db.set_campaign_state(campaign_id, state)
        elif name == "prospector_run":
            value = db.enqueue(args["campaign_id"])
        elif name == "prospector_runs":
            value = db.runs(args.get("campaign_id"))
        elif name == "prospector_list_leads":
            value = db.leads(campaign_id=args.get("campaign_id"), q=args.get("q", ""), page=args.get("page", 1))
        elif name == "prospector_schedule":
            from . import schedule
            if args["action"] == "list":
                value = schedule.schedules(db)
            else:
                value = schedule.set_active(db, args["campaign_id"], args["action"] == "activate")
        elif name == "prospector_diagnose":
            from . import treg
            value = {"local": db.status(), "catalog": treg.catalog_capability()}
        else:
            value = {"error": "Ferramenta desconhecida"}
        return json.dumps(value, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
    finally:
        if db:
            db.close()


def _setup_cli(parser):
    subs = parser.add_subparsers(dest="prospector_command", required=True)
    subs.add_parser("status", help="Estado resumido do Prospector")
    subs.add_parser("campaigns", help="Listar campanhas")
    run = subs.add_parser("run", help="Enfileirar busca manual")
    run.add_argument("campaign_id")
    subs.add_parser("runs", help="Histórico de buscas")


def _cli(args):
    name = {"status": "prospector_status", "campaigns": "prospector_campaigns",
            "run": "prospector_run", "runs": "prospector_runs"}[args.prospector_command]
    print(_handle(name, {"campaign_id": getattr(args, "campaign_id", None)}))


def register(ctx):
    """Somente registro. Não abre banco, rede, porta ou serviço."""
    for name, description, properties, required in TOOLS:
        ctx.register_tool(name=name, toolset="hermes_prospector",
                          schema=_schema(name, description, properties, required),
                          handler=lambda args, _name=name, **kwargs: _handle(_name, args, **kwargs))
    ctx.register_cli_command(name="prospector", help="Gerenciar o Hermes Prospector",
                             setup_fn=_setup_cli, handler_fn=_cli)
