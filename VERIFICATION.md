# Verificação e aceite

## Executado localmente em 09/10/2026

- `uv sync --extra test`
- `uv run pytest -q`: 11 testes offline aprovados (sem token Treg), incluindo importação de legado, orçamento e reconciliação simulada.
- `node --check prospector/static/app.js`: sintaxe JavaScript válida.
- `bash -n install.sh update.sh uninstall.sh`: sintaxe dos scripts válida.
- `uv build`: sdist e wheel gerados após as alterações finais.

Os testes usam respostas simuladas e nomes de exemplo marcados. Eles não demonstram acesso à VPS, capacidade real das fontes ou custo de chamada.

## Pendente antes de release de produção

1. Em uma VPS de teste com Hermes `0.21.5`, executar `hermes plugins doctor CAMINHO_DO_PLUGIN --ci` e `hermes plugins validate CAMINHO_DO_PLUGIN --install-deps`.
2. Instalar com a URL do repositório, interromper e repetir o instalador; confirmar serviço, senha e banco preservados.
3. Validar login por URL externa, TLS/DNS ou IP restrito, bloqueio de API sem sessão e retorno após reboot.
4. Cadastrar chave Treg por canal privado e validar equipe/organização em endpoint gratuito.
5. Com orçamento de teste explícito, fazer uma busca em cidade brasileira; registrar endpoint, parâmetros, ID Treg, resultados e custo confirmado. Comparar com o ledger Treg.
6. Criar duas campanhas, ativar horários distintos e conferir tarefas Hermes reais, pausa/retomada e próximo disparo.
7. Simular falha após cobrança, recuperar custo pendente sem repetir chamada paga e testar atualização/rollback.
8. Comparar o formato real do projeto anterior com o importador CSV/JSON/JSONL; fazer prévia, backup e importação preservando a origem.
9. Capturar Dashboard, Configurações, Campanhas e Programação e medir instalação/consumo na VPS de referência.

Sem essas evidências, não anunciar a meta de instalação em cinco minutos nem uma instalação pronta em produção.
