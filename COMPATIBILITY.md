# Compatibilidade verificada

Data: 09/10/2026. Alvo informado pelo proprietário: Hermes `0.21.5`.

## Hermes

A tag oficial [v2026.9.24](https://github.com/NousResearch/hermes-agent/releases/tag/v2026.9.24) foi inspecionada no commit `f97608f178d1ffeca59860195ab7da295f7c8e5f`. `hermes_cli/__init__.py` define `__version__ = "0.21.5"`.

| Contrato | Evidência na tag | Uso no plugin |
|---|---|---|
| `register(ctx)` e `ctx.register_tool` | `hermes_cli/plugins.py`, `PluginContext.register_tool` | 10 ferramentas registradas sem I/O no registro |
| `ctx.register_cli_command` | `hermes_cli/plugins.py`, método público | `hermes prospector ...` |
| `plugin.yaml` v2 e `python_runtime: external` | `plugins_manifest.py` e `plugin_python_deps.py` | API incorporada usa o Python do Hermes; instalador legado usa venv separada |
| Dados por perfil | `plugins/plugin_storage.py` e `hermes_constants.get_hermes_home` | `<HERMES_HOME>/plugin-data/hermes-prospector` |
| Instalação por URL Git na UI | `web/src/pages/PluginsPage.tsx`, `web_routers/dashboard_ui.py` e `plugins_cmd.py` | Tela Plugins, com ativação após instalar |
| Aba e API de plugin do Dashboard | `web_server_dashboard.py`, `web/src/App.tsx` | `dashboard/manifest.json`, JS/CSS e `plugin_api.py` |
| Cron `--no-agent`, `--script`, `--paused` | `hermes_cli/subcommands/cron.py`; `cron/scheduler.py` | Uma tarefa por campanha; script enfileira |

Na tag `0.21.5`, o CLI do cron não expõe `--interpreter`; por isso o script `.sh` chama o Python do Hermes com `PYTHONPATH` apontando para o plugin. O scheduler exige scripts sob `<HERMES_HOME>/scripts`. A API de plugins do Dashboard é montada na inicialização; após instalar pela UI, pode ser necessário reiniciar o processo do Dashboard.

**Limite da evidência:** inspeção de código e testes locais, sem executar `hermes plugins doctor` na instalação real do usuário. A versão mínima está fixada em `>=0.21.5` no manifesto; uma versão posterior requer novo teste de integração.

## Treg

O [catálogo público](https://treg.to/catalog/endpoints/anyapi.google.serp.maps) foi consultado sem token. O endpoint `anyapi.google.serp.maps` é `POST`, aceita `query`, `location`, `limit` (1–20) e retorna exemplos de empresas com nome, endereço, telefone, site, URL do Maps e `placeId`. O catálogo o marcou elegível na consulta desta data, com referência de US$ 0,00175 por chamada. O worker confirma a capacidade novamente antes de buscar; preço e disponibilidade podem mudar.

O [protocolo Treg](https://treg.to/llms.txt) documenta `X-Treg-Token` (e `X-Treg-Org` para token de identidade), `X-Treg-Call-Id`, `X-Treg-Cost-Micro`, `X-Treg-Route-Max-Cost` e `Idempotency-Key`. O custo exato deve vir do header/ledger, não do corpo do provedor. A janela de replay da chave é de 24 horas.

Com chave temporária em arquivo `.env` ignorado pelo Git, oito chamadas reais custaram US$ 0,014 no total, todas reconciliadas. A busca `dentista` em Fortaleza retornou um lugar e foi persistida por uma rodada do worker. A instalação na VPS ainda não foi testada.
