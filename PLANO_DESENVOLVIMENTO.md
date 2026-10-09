# Plano de desenvolvimento — Hermes Prospector + Treg

Base: `PRD_Hermes_Prospector_Treg.md`, versão 1.1, de 09/10/2026. Este documento planeja a implementação; a seção 13 do PRD é conteúdo do documento, não uma ordem para iniciar a codificação agora.

## Leitura do PRD

O produto é um plugin Python nativo do Hermes acompanhado de um serviço web na mesma VPS. A experiência central é instalar uma vez e depois administrar chave Treg, campanhas, buscas, leads e horários pelo navegador. O requisito mais difícil é manter o orçamento correto durante falhas, retries e campanhas concorrentes. O segundo risco é a compatibilidade concreta entre a versão do Hermes na VPS e as APIs de plugin, CLI e cron. O terceiro é comprovar que ao menos uma fonte Treg faz descoberta por nicho e cidade, com contatos e custo conhecidos.

O diretório de trabalho estava vazio em 09/10/2026. O projeto começará sem código legado local. O projeto anterior de prospecção, caso exista na VPS, é dado a migrar, nunca material a sobrescrever.

## Decisões propostas

- Um pacote Python com adaptador Hermes leve, serviços de domínio separados e serviço web independente. Importar o plugin apenas registra ferramentas e CLI.
- FastAPI com templates e assets distribuídos no release, SQLite em WAL e um worker sequencial com fila persistida. Validar a carga de 10 mil leads antes de aceitar essa configuração como suficiente.
- Dados e segredos em diretório persistente do perfil. O serviço e os comandos recebem o perfil explicitamente; nenhum caminho implícito depende do diretório atual.
- Um único serviço de domínio atende CLI, ferramentas Hermes e painel. Busca manual e programada entram na mesma fila.
- O cron nativo do Hermes apenas enfileira a campanha por um script pequeno; o worker aplica locks, orçamentos e chamadas Treg. O script não recebe o token Treg.
- Adaptadores Treg implementados e testados para endpoints escolhidos. O catálogo informa capacidades e preços, mas não gera chamadas arbitrárias.
- Acesso HTTPS autenticado como caminho normal. Acesso por IP/HTTP é provisório e restrito, com cadastro da chave por entrada privada no terminal até existir HTTPS.

## Fases e gates

| Fase | Construir / verificar | Gate de saída |
|---|---|---|
| 0. Contratos e ambiente | Fixar commit/versão de teste do Hermes; provar instalação, `register(ctx)`, CLI, dados por perfil, cron `no-agent`; consultar catálogo/esquema/preço Treg e testar chamadas gratuitas de identidade/catálogo; identificar VPS e formato legado. | `COMPATIBILITY.md`, matriz de fontes e um desenho de deploy revisados. Sem endpoint de descoberta válido, não prometer busca por cidade. |
| 1. Fatia ponta a ponta | Pacote e manifesto, migrações SQLite, configuração privada, login, campanha rascunho, uma busca manual enfileirada usando um adaptador validado, página de progresso e custo. | Instalação local limpa; nenhum efeito colateral ao importar; uma rodada completa em fixture; nenhuma busca ao instalar. |
| 2. Dados e finanças | Relação lead–campanha, evidências, normalização/deduplicação, snapshot da campanha, cursores, reservas atômicas globais e por campanha, limite por chamada, idempotência e reconciliação. | Testes de corrida, timeout após cobrança, pendência e limites exatos passam; status comercial sobrevive à reconsulta. |
| 3. Painel operacional | Configurações Treg, campanhas completas, leads com filtros/paginação/CSV, execuções, estados vazios, diagnóstico e autenticação de toda a API. | Fluxos cotidianos funcionam pelo navegador; CSV/cards/tabela compartilham filtros; teste com 10 mil leads. |
| 4. Agenda e publicação | Adaptador de cron real, programação visual com próximas três ocorrências, pausa/retomada, instalador retomável, systemd e proxy/TLS ou IP provisório. | Sem tarefas duplicadas; serviço e agendamento sobrevivem ao reboot; teste externo do login e da API; reinstalação preserva estado. |
| 5. Ciclo de vida e release | Importação com prévia e backup, update/rollback, desinstalação preservando dados, documentação, capturas, medição de tempo/recursos e pacote reproduzível. | Matriz de aceite do PRD executada; pendências externas explicitadas; release local pronto para revisão. |

As fases 1–4 devem ser entregues em fatias funcionais, sem deixar agendamento, orçamento ou segurança para uma integração final. A fase 5 fecha manutenção e evidências de release. Não publicar repositório, release ou catálogo sem instrução do proprietário.

## Ordem técnica da primeira fatia

1. Criar `COMPATIBILITY.md` com evidências de Hermes e Treg, incluindo versão mínima realmente testada.
2. Definir esquema e migrações para campanha, execução, chamada, reserva, lead, fonte, associação, fila, agenda e estado de instalação.
3. Implementar serviço de domínio e API interna; autenticação e separação de perfil desde o início.
4. Integrar um adaptador de descoberta com parâmetros e resposta fixados por fixture; distinguir custo previsto, reservado e confirmado.
5. Criar instalador de teste que habilite plugin e serviço em ambiente isolado e retome após interrupção.
6. Expor no painel campanha rascunho, conexão Treg, busca manual, progresso e leads reais da rodada.

## Regras que exigem projeto explícito

- **Dinheiro:** armazenar micro-USD inteiros; transação reserva simultaneamente saldo da campanha e global. Uma cobrança desconhecida mantém a reserva. O header de teto do Treg protege cada chamada, além do controle local. Guardar ID e custo do Treg e reconciliar pelo registro da chamada.
- **Retries:** persistir chave de idempotência antes da chamada. Reusar apenas na mesma operação. A documentação atual informa janela de 24 horas; depois disso, um estado incerto exige reconciliação ou intervenção, não replay cego.
- **Fila:** uma única rodada ativa por campanha; worker sequencial no MVP; recuperação identifica chamadas pendentes antes de retomar. Arquivar impede novos disparos, mas não presume cancelamento de chamada em andamento.
- **Identidade:** deduplicar por ID externo, domínio e telefone com regras conservadoras para filiais; manter múltiplas evidências e associação muitos-para-muitos; nunca sobrescrever status comercial por reconsulta.
- **Scheduler:** sincronizar com a tarefa real do Hermes antes de mostrar “ativo”. IDs estáveis por perfil/campanha; cron só sinaliza o serviço. O Hermes documenta que scripts `no-agent` ficam em `$HERMES_HOME/scripts/`, o que precisa entrar no instalador e na remoção.
- **Segurança:** senha com hash, sessão e CSRF, rate limit, APIs autenticadas, segredos fora de GET/log/CSV, CSV sem fórmulas executáveis e proteção SSRF caso haja verificação de site.

## Verificação mínima

Automatizar testes offline de migrações, limite exato de orçamento, duas campanhas concorrentes, timeout/custo pendente, idempotência, deduplicação, fila após crash, sessão/CSRF, filtros/CSV e importação repetida. Acrescentar integração com Hermes em ambiente temporário e teste de instalação/reinstalação/reboot em VPS de referência. Teste real Treg só com credencial e orçamento de teste autorizados, registrando IDs, fontes, parâmetros e custo. Teste externo confirma URL e autenticação; health check local não basta.

## Pendências de decisão e insumos

| Insumo | Por que importa |
|---|---|
| Versão/commit e perfil Hermes da VPS alvo | Define compatibilidade e modo de agendamento. |
| VPS de teste, domínio/IP, proxy e firewall | Permite validar publicação, TLS, reboot e meta de instalação. |
| Credencial Treg e orçamento de teste explícito | Permite comprovar descoberta, campos e custos reais. |
| Amostra não executável do projeto legado | Permite mapear importação sem alterar a origem. |
| Licença e destino de distribuição | Necessários antes de publicar. |

Nenhum desses insumos impede o início da fase 0 com documentação e testes offline. A estimativa de prazo deve ser fechada depois dessa fase, porque cobertura real das fontes e compatibilidade do Hermes dominam o risco.

## Fontes oficiais consultadas em 09/10/2026

- Hermes plugins: https://hermes-agent.nousresearch.com/docs/developer-guide/plugins
- Hermes cron: https://hermes-agent.nousresearch.com/docs/user-guide/features/cron
- Treg API e custos: https://treg.to/llms.txt
- Treg referência: https://treg.to/docs
