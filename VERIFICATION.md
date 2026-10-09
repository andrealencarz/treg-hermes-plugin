# Verificação e aceite

## Executado localmente em 09/10/2026

- `uv sync --extra test`
- `bash scripts/test_local.sh`: 17 testes offline aprovados, incluindo contrato HTTP, limite de gasto, importação de legado, orçamento e reconciliação simulada.
- Os mesmos 17 testes passaram também em Python 3.11.15, a versão mínima suportada.
- `node --check prospector/static/app.js`: sintaxe JavaScript válida.
- `bash -n install.sh update.sh uninstall.sh`: sintaxe dos scripts válida.
- `uv build`: sdist e wheel gerados após as alterações finais.

Os testes usam respostas simuladas e nomes de exemplo marcados. Eles não demonstram acesso à VPS, capacidade real das fontes ou custo de chamada.

## Treg real, chave temporária, 09/10/2026

- `.venv/bin/python -m scripts.treg_smoke` validou identidade e catálogo gratuitamente.
- Oito tentativas com uma chamada cada, teto individual de US$ 0,01: o ledger confirmou US$ 0,00175 por chamada, **US$ 0,014 no total**, abaixo do teto autorizado de US$ 0,20. Todas terminaram liquidadas, sem reservas pendentes.
- A primeira resposta de 200 com `output.data = null` revelou uma falha no parser. A reserva foi reconciliada pelo ledger, sem repetir a requisição. Corrigimos o parser e adicionamos teste de regressão.
- A busca de “clínica odontológica” em Fortaleza retornou `found = false` e zero leads, inclusive com localização `Fortaleza, Brazil` e idioma padrão. O exemplo público `coffee` em `Austin, TX` e as consultas `dentist`/`dentista` em Fortaleza retornaram 1 item com `placeId`.
- Uma rodada completa do worker com “dentista” em Fortaleza salvou 1 lead, com custo confirmado de US$ 0,00175 e nenhuma pendência. Esse resultado valida o caminho local de consulta, normalização, persistência e cobrança para esse caso; não garante resultados para outros termos/cidades.
- A chave fica apenas em `.env` ignorado pelo Git, com permissão 0600; nenhuma chave foi salva nos relatórios. A chave temporária deve ser revogada após o teste.

## Pendente antes de release de produção

1. Em uma VPS de teste com Hermes `0.21.5`, executar `hermes plugins doctor CAMINHO_DO_PLUGIN --ci` e `hermes plugins validate CAMINHO_DO_PLUGIN --install-deps`.
2. Instalar com a URL do repositório, interromper e repetir o instalador; confirmar serviço, senha e banco preservados.
3. Validar login por URL externa, TLS/DNS ou IP restrito, bloqueio de API sem sessão e retorno após reboot.
4. Revalidar na VPS com uma chave Treg própria da instalação; o teste local não cobre rede, proxy ou perfil Hermes da VPS.
5. Repetir a busca positiva na VPS e conferir os contatos retornados no painel, sem aumentar o teto de teste sem autorização.
6. Criar duas campanhas, ativar horários distintos e conferir tarefas Hermes reais, pausa/retomada e próximo disparo.
7. Simular falha após cobrança, recuperar custo pendente sem repetir chamada paga e testar atualização/rollback.
8. Comparar o formato real do projeto anterior com o importador CSV/JSON/JSONL; fazer prévia, backup e importação preservando a origem.
9. Capturar Dashboard, Configurações, Campanhas e Programação e medir instalação/consumo na VPS de referência.

Sem essas evidências, não anunciar a meta de instalação em cinco minutos nem uma instalação pronta em produção.
