# Verificação e aceite

## Executado localmente em 09/10/2026

- `uv sync --extra test`
- `bash scripts/test_local.sh`: 19 testes offline aprovados, incluindo a API do Dashboard e o script de agenda sem venv separada.
- Os mesmos 19 testes passaram também em Python 3.11.15, a versão mínima suportada.
- `node --check` validou o JS legado e o JS da aba integrada.
- `bash -n scripts/test_local.sh`: sintaxe do script de testes válida.
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

1. Instalar pela tela **Plugins** do Dashboard Hermes `0.21.5`, usando a URL Git e deixando **Ativar após instalar** ligado. Conferir se o scanner aceita a origem personalizada.
2. Reiniciar o Dashboard pelo controle da instalação; confirmar aba **Prospector**, API e dados preservados após reinício e atualização do plugin.
3. Validar login por URL externa, HTTPS, bloqueio da API integrada sem sessão Hermes e retorno após reboot.
4. Revalidar na VPS com uma chave Treg própria da instalação; o teste local não cobre rede, proxy ou perfil Hermes da VPS.
5. Repetir a busca positiva na VPS e conferir os contatos retornados no painel, sem aumentar o teto de teste sem autorização.
6. Criar duas campanhas, ativar horários distintos e conferir tarefas Hermes reais, pausa/retomada e próximo disparo.
7. Simular falha após cobrança, recuperar custo pendente sem repetir chamada paga e testar atualização/rollback.
8. Comparar o formato real do projeto anterior com o importador CSV/JSON/JSONL; fazer prévia, backup e importação preservando a origem.
9. Capturar Dashboard, Configurações, Campanhas e Programação e medir instalação/consumo na VPS de referência.

Sem essas evidências, não anunciar a meta de instalação em cinco minutos nem uma instalação pronta em produção.
