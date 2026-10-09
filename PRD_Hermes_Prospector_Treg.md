# PRD — Plugin Hermes Prospector + Treg

**Versão:** 1.1  
**Data:** 09/10/2026  
**Nome de trabalho:** Hermes Prospector  
**ID proposto:** `hermes-prospector`  
**Entregável solicitado:** plugin instalável do Hermes, com painel web hospedado na VPS.  
**Idioma:** português do Brasil.

## 1. Problema e resultado esperado

O fluxo atual exige seis prompts longos para preparar o ambiente, conectar o Treg, definir uma campanha, construir um painel, buscar leads e configurar a rotina diária. O agente escreve código e resolve implantação durante a instalação. Isso demora, varia entre máquinas e pode terminar com um endereço local que o usuário não consegue abrir.

O plugin deve trazer o sistema pronto. A instalação configura componentes existentes, coleta os dados indispensáveis e publica o painel na mesma VPS onde o Hermes está instalado.

**Resultado esperado:** o usuário instala o plugin e recebe um painel web onde configura a chave do Treg, cria várias campanhas, busca e filtra leads e programa as execuções de cada campanha. Depois da instalação inicial, essas operações devem ser feitas pelo navegador, sem novos prompts, edição de arquivos ou terminal obrigatório.

**Restrições obrigatórias:**
- Não usar Cloudflare, cloudflared, Cloudflare Tunnel ou túneis para publicar o painel.
- Não exigir servidor, Python, Node ou túnel SSH no computador do usuário.
- Não modificar o núcleo do Hermes.
- Não gerar o código do painel durante a instalação.
- Não apagar o projeto ou os leads produzidos pelo fluxo anterior.
- Não apresentar contatos, custos ou capacidades de fontes fictícios.
- Não instalar nem divulgar uma integração com AISA.

## 2. Público, proposta e indicadores

Público principal: pequenos empresários, prestadores de serviços e agências que precisam encontrar empresas por nicho, cidade e estado, com pouca experiência em administração de servidores.

Caso inicial: criação de sites e SEO para clínicas odontológicas em Fortaleza/CE, João Pessoa/PB e Recife/PE. Esses dados são um exemplo editável, não uma restrição do produto.

### Metas de experiência

| Indicador | Meta de aceitação |
|---|---|
| Comandos iniciais | Um comando de instalação após obter o pacote de release; oferecer também instalação nativa documentada |
| Configuração | Até quatro etapas visíveis: acesso, conexão, público e conclusão |
| Operação pelo navegador | Chave, campanhas, filtros e programação sem terminal ou novos prompts |
| Instalação na VPS de referência | Meta de até 5 minutos, com Hermes instalado, acesso à internet e dependências disponíveis; medir antes de anunciar |
| Código gerado na instalação | Zero |
| Consultas pagas na instalação | Zero |
| Persistência | Painel e agendamento sobrevivem à desconexão do terminal e ao reboot |
| Reexecução do instalador | Retoma etapas pendentes e preserva credenciais, banco e serviços válidos |
| Primeiro resultado | Busca manual com progresso, quantidade real e custo rastreável |
| Acesso | URL pública correta; teste local não equivale a teste externo |

Não prometer prazo fixo quando download, DNS, firewall do provedor ou login no Treg forem bloqueios externos. Medir o tempo por etapa e registrar a causa de demora.

## 3. Escopo do MVP

### Incluído
- Plugin Python nativo do Hermes.
- Instalador idempotente para VPS Linux com systemd.
- Uma conta administradora e várias campanhas, cada uma com critérios e programação independentes.
- Área web de Configurações para cadastrar, testar e substituir a chave do Treg.
- Cliente Treg e adaptadores de descoberta/enriquecimento.
- Painel pronto com filtros, busca, paginação, contatos, status e CSV.
- Execução manual e recorrente.
- Orçamento por execução e mensal, histórico e custo real.
- Diagnóstico de instalação, acesso e conectividade.
- Atualização, desinstalação sem apagar dados e importação do projeto anterior.

### Fora do MVP
- Envio automático de WhatsApp, e-mail ou mensagens em redes sociais.
- Automação de login/scraping de redes sociais fora das ferramentas contratadas no Treg.
- CRM multiusuário, SaaS multitenant, cobrança de clientes e marketplace.
- Instalação silenciosa de uma versão nova do Hermes.
- Integração desktop obrigatória, Docker obrigatório e execução no computador pessoal.
- Geração de sites, checkout, pagamentos e agentes de vendas.

## 4. Jornada de instalação

### 4.1 Pré-requisitos e diagnóstico

Antes de alterar o servidor, o instalador identifica:
- Hostname, distribuição, arquitetura, usuário, privilégios e diretório do perfil Hermes.
- Versão do Hermes e suporte aos recursos do plugin.
- Python disponível, recursos de disco/RAM, portas, serviços e proxy existentes.
- Se o terminal realmente está conectado à VPS desejada.
- Instalação existente do plugin e projeto anterior `prospeccao-treg`.
- Acesso aos endpoints oficiais do Treg, sem executar buscas pagas.

Falha de pré-requisito deve resultar em mensagem curta, com a ação exata para corrigir. Não continuar fingindo que o plugin está pronto.

### 4.2 Instalação do pacote

O release deve conter código Python, templates e assets estáticos prontos, manifesto, metadados de versão, dependências limitadas e instalador.

O instalador usa o mecanismo nativo de instalação/ativação do Hermes suportado pela versão detectada. Ele pode orquestrar essas operações para oferecer uma entrada única, respeitando consentimentos e permissões exigidos pelo host.

A instalação não depende de o agente escrever arquivos por conversa. O usuário não precisa de npm, build de frontend ou compilação de assets na VPS.

**Contrato desejado:** baixar o release e executar `bash install.sh`. O comando só será publicado como funcional após o Codex implementar e testar o pacote; não inventar URL de repositório ou download.

### 4.3 Assistente curto

| Etapa | O usuário informa | O plugin executa |
|---|---|---|
| Acesso | Domínio, se houver; senha do painel | Serviço, proxy/TLS ou acesso por IP, autenticação |
| Conexão | Chave do Treg em Configurações, ou entrada privada no terminal se HTTPS ainda não estiver pronto | Validação de identidade/equipe e catálogo |
| Público | Nome da primeira campanha, nicho, cidades/UF, volume e orçamento | Salva campanha e monta plano de fontes |
| Conclusão | Escolha de buscar agora e/ou ativar rotina | Diagnóstico final, URL e resumo da configuração |

Valores sugeridos: até 30 novos leads por rodada; teto Treg de US$ 1 por rodada e US$ 30 por mês; 9h no fuso America/Fortaleza. São limites de configuração. A interface deve permitir alterá-los e explicar que a meta pode não ser atingida dentro do orçamento. O teto global padrão também é US$ 30 por mês, compartilhado entre as campanhas e editável em Configurações; não multiplicá-lo silenciosamente ao criar novas campanhas.

Não disparar busca paga nem ativar rotina diária apenas porque o plugin foi instalado. Essas ações devem ser escolhas explícitas no assistente ou no painel.

### 4.4 Estado da instalação

Persistir os estados:
`diagnostico → pacote_instalado → servico_ativo → acesso_configurado → credencial_validada → campanha_configurada → pronto`.

O painel pode abrir sem chave Treg para completar Configurações. Consultas pagas permanecem bloqueadas até validar a conexão.

Registrar separadamente bloqueios de DNS, firewall, autenticação, compatibilidade e alcance externo. Cada etapa deve poder ser retomada sem reinstalar o que já funciona.

## 5. Requisitos funcionais

### RF01 — Plugin nativo e integração com o Hermes

A implementação deverá registrar ferramentas e comandos pela API pública do Hermes, com carregamento leve. Importação e registro não devem abrir portas, chamar o Treg, criar tarefas ou instalar serviços.

O painel é um serviço complementar distribuído junto ao plugin. Ele não é uma extensão que só funciona no Hermes Desktop.

Toda execução deve usar o perfil e os caminhos absolutos corretos. Instalar em um perfil não pode alterar outro.

**Ferramentas propostas a implementar:**

| Ferramenta | Função | Resultado |
|---|---|---|
| `prospector_status` | Consultar configuração, serviços e campanha | Estado e bloqueios sem segredos |
| `prospector_configure` | Alterar critérios e limites não secretos por campaign_id | Configuração validada |
| `prospector_campaigns` | Listar campanhas | Estado, orçamento e próximas execuções |
| `prospector_campaign_create` | Criar campanha | ID e critérios validados |
| `prospector_campaign_update` | Editar ou arquivar por ID | Estado e programação atualizados |
| `prospector_run` | Enfileirar busca por campaign_id | ID de execução, sem bloquear a conversa |
| `prospector_runs` | Consultar progresso e histórico | Contagens, erros e custos |
| `prospector_list_leads` | Listar com filtros/paginação | Dados e evidências |
| `prospector_schedule` | Gerenciar rotina por campaign_id | ID da tarefa e próximo horário |
| `prospector_diagnose` | Conferir conectividade/instalação | Diagnóstico e correção possível |

Credenciais não devem ser argumento de ferramenta enviado ao modelo. O usuário as configura por entrada privada no terminal ou pelo painel HTTPS autenticado.

### RF02 — Cliente Treg e fontes

Usar a API oficial por uma camada independente da UI e do Hermes. Consultar a documentação vigente antes de implementar autenticação e formatos. Não criar MCP intermediário como requisito de instalação.

Implementar:
- Descoberta no catálogo, leitura dos esquemas e seleção de endpoints.
- Adaptadores normalizados para empresas, contatos comerciais e perfis.
- Capability check que diferencie descoberta por nicho/cidade de consulta de perfil conhecido.
- Cache do catálogo, timeouts, tratamento de erros e retries limitados.
- Credencial por organização ou identidade conforme documentação.
- Registro de requisições e cobrança sem guardar o token em logs.
- Atualização explícita do catálogo e revalidação após mudanças de esquema.

Google Maps, LinkedIn e Instagram são fontes desejadas. O MVP pode funcionar com a cobertura efetivamente validada, mas deve indicar por fonte: disponível, sem suporte à descoberta, sem acesso, sem resultados ou falha. Não anunciar suporte a três fontes apenas por encontrar seus nomes no catálogo.

Preferir adaptadores previamente implementados e validados. Descoberta dinâmica não deve gerar código automaticamente para chamar um endpoint arbitrário.

Antes de uma busca, o painel informa fontes utilizáveis, requisitos faltantes e limite de gasto. Se a fonte exigir outro acesso, não chamar um provedor externo silenciosamente fora do Treg.

### RF03 — Campanha e execução

**Campanhas pelo painel:** criar, listar, visualizar, editar, duplicar, ativar, pausar e arquivar várias campanhas. Não limitar o MVP a uma campanha.

Campos: ID, nome, descrição opcional, serviço vendido, nicho, cidades/UF, fontes selecionadas, meta de leads, limites por execução/mês, estado, dias/horários, fuso e programação.

A lista exibe nome, nicho, regiões, estado, leads associados, gasto mensal, última e próxima execução. Oferece Editar, Ver leads, Buscar agora, Programar, Pausar/Retomar e Arquivar.

Salvar uma campanha não inicia busca paga. Ela nasce em rascunho; ativar rotina é ação separada. Duplicar copia critérios sem copiar histórico, leads ou agendamento ativo. Arquivar desativa a rotina e preserva os dados.

Edição vale para a próxima rodada; a rodada atual usa snapshot versionado da configuração. Arquivar durante uma execução impede próximas rodadas e sinaliza se a chamada em curso ainda está finalizando.

Campanhas têm cursores, histórico e locks próprios. No MVP, um worker processa a fila sequencialmente, respeitando limites globais.

Algoritmo determinístico:
1. Validar campanha, fontes e saldo do orçamento.
2. Criar execução e adquirir lock da campanha.
3. Calcular consultas, distribuição entre cidades e limites de páginas.
4. Persistir reservas de orçamento antes de cada chamada.
5. Consultar Treg, registrar resposta/custo e normalizar resultados.
6. Deduplicar, inserir/atualizar leads e preservar status comercial.
7. Persistir cursores/páginas, encerrar execução e atualizar histórico.
8. Liberar locks/reservas de forma transacional.

Limitar chamadas, páginas e duração; não iterar indefinidamente procurando 30 novos contatos quando os resultados se esgotarem. Rotacionar cidades/consultas e usar TTL de reconsulta para reduzir gastos repetidos. Deduplicação após retorno não elimina custo de uma busca já feita.

A execução passa por estados: `queued, running, succeeded, partial, failed, cancelled`. A confirmação financeira é um estado separado: `confirmed, pending, unavailable`.

### RF04 — Dados dos leads

Campos mínimos:
- ID interno, nome comercial, nicho, cidade, UF e país.
- Site, telefone comercial normalizado, e-mail comercial.
- Links de perfis e Google Maps quando retornados.
- Fonte, identificador externo, URL de evidência e data de coleta.
- Status comercial e observações.
- Primeira/última ocorrência e execução de origem.

Associar leads e campanhas por relação muitos-para-muitos. Uma empresa pode pertencer a duas campanhas sem duplicar a identidade global. Separar nas contagens: inéditos no banco, novos na campanha, atualizados e duplicados. Preservar status comercial global; observações específicas podem ser associadas à campanha.

Manter várias evidências/fontes associadas a uma empresa. Deduplicar primeiro por identificador externo, domínio e telefone; nome/localização só como combinação cautelosa. Não fundir filiais distintas por domínio compartilhado sem evidência adicional.

Ausência de site no resultado significa “site não informado”, não “empresa sem site”. Verificação efetiva de disponibilidade ou oportunidade SEO deve ter critério, data e evidência; isso não exige análise ampla com IA no MVP.

### RF05 — Dashboard na VPS

Interface profissional em PT-BR, responsiva e legível em gravação 16:9:
- Cards de total, novos na rodada, cidades atendidas e custo.
- Busca por nome, nicho, telefone, e-mail e domínio.
- Filtros combináveis por campanha, cidade, UF, nicho, fonte, status e período de coleta.
- Paginação no backend com 20/50/100 itens, total, intervalo exibido e navegação anterior/próxima.
- Ordenação por nome, cidade e data; mudar busca ou filtro volta à primeira página.
- Filtros e página na URL; tabela, cards e exportação usam os mesmos critérios.
- Detalhes, fontes/evidências e links de contatos comerciais.
- Status: Novo, Em análise, Contatado, Proposta enviada, Fechado.
- CSV respeitando filtros; neutralizar fórmulas de planilha na exportação.
- Histórico com progresso, duração, fontes, contagens e cobrança.
- Páginas completas de Configurações Treg, Campanhas e Programação, conforme RF11; não substituir por instruções de terminal.
- Botões Buscar agora, Pausar rotina e Retomar rotina.
- Estado vazio honesto e falhas explicadas por ação possível.

O frontend usa rotas relativas ou a URL pública do backend. Não deve apontar para localhost do visitante. A API e o painel devem exigir autenticação; acesso por URL direta a uma API não pode contornar o login.

Não exibir detalhes de SDK, endpoints ou stack no fluxo normal. Concentrar informação técnica no diagnóstico.

### RF06 — Custo real e orçamento

Calcular gastos em inteiros de micro-USD; converter apenas para exibir valores. Evitar cálculos financeiros em ponto flutuante.

Manter por chamada: execução, endpoint, identificador Treg, tentativa, chave de idempotência, reserva, custo confirmado, estado e horários.

- Usar a cobrança do Treg, nunca um valor arbitrário no corpo do provedor.
- Conforme a documentação consultada, preservar `X-Treg-Call-Id` e `X-Treg-Cost-Micro`; confirmar limites de cobrança e reconciliação na implementação.
- Não inferir custo exato apenas da diferença de saldo da conta, que pode incluir outros usos.
- Distinguir preço previsto, valor reservado, custo final e pendência.
- Aplicar teto por chamada e reservas atômicas contra o orçamento restante.
- Tratar cobrança ainda desconhecida como pendência que consome a reserva, não como custo zero.
- Reconciliar pendências antes de liberar o saldo reservado.
- Contabilizar chamadas cobradas mesmo quando ocorrer falha posterior no pipeline.
- Reusar chave de idempotência em retry da mesma operação; usar nova chave numa busca realmente nova.
- Impedir que busca manual e agendada ultrapassem o teto juntas.
- Reservar e liquidar cada custo nos orçamentos da campanha e global. Duas campanhas não podem usar o mesmo saldo restante.
- Teto global esgotado bloqueia novas chamadas de todas as campanhas, sem apagar rotinas.

Teto mensal da campanha: mês civil no seu fuso. Teto global: mês civil num único fuso configurável, padrão America/Fortaleza. Reservas e gastos armazenam ambos os períodos. Um mês com 31 dias pode ter a última rodada bloqueada; mostrar “orçamento mensal esgotado” e indicar se é limite da campanha ou global.

Exibir custo da execução, custo por novo lead quando aplicável e estimativa para 30 rodadas semelhantes apenas quando a base estiver confirmada. Separar Treg de VPS/modelo de IA. “Custo indisponível” não equivale a “grátis”.

### RF07 — Agendamento e autonomia

Usar o agendamento nativo do Hermes, com detecção do recurso suportado na instalação. Preferir o modo de execução de script sem LLM, quando disponível, porque o pipeline de busca já é código pronto.

Programar pela interface, sem expressão cron obrigatória nem prompt: Uma vez em data/hora, Todos os dias ou Dias da semana, com um ou mais horários e fuso IANA. Mostrar resumo e próximas três ocorrências antes de salvar. Modo não suportado pelo Hermes instalado deve aparecer indisponível com diagnóstico, sem simular suporte.

Criar/atualizar uma tarefa por campanha/perfil, ou o conjunto mínimo necessário para seus horários, com IDs estáveis. Alterar programação não duplica disparos nem executa retroativamente. Validar dias, horários e datas futuras.

Salvar atualiza o scheduler real. Não mostrar rotina ativa se a sincronização falhar. Não editar arquivos internos de tarefas nem manter outro cron/timer duplicado.

Se a versão não suportar modo de script, admitir fallback de sessão agente com uma instrução mínima que invoque a ferramenta de busca existente. Documentar que esse modo usa o modelo e pode ter custos adicionais. Não refazer pesquisas de catálogo nem construir o painel a cada rodada.

A rotina lê configuração persistida e credenciais privadas, mantém lock, respeita orçamento e atualiza histórico. Não depende do contexto da conversa de instalação.

Verificar gateway/agendador ativo, retorno após reboot, horário local e próximo disparo. Deixar uma única camada responsável por recuperação de execução perdida; a retomada de fila não deve duplicar trabalho já cobrado.

### RF08 — Publicação e serviços

O serviço do painel roda na VPS do Hermes, sob usuário dedicado ou usuário da instalação, sem executar a aplicação como root.

- Domínio existente: HTTPS por proxy já presente ou Caddy/Nginx, sem Cloudflare.
- Backend atrás de proxy: pode permanecer em loopback; quem atende a internet é o proxy.
- IP direto: binding externo na porta configurada, autenticação e URL com protocolo real.
- HTTP provisório: restringir ao IP do operador até habilitar HTTPS; não apresentar como publicação HTTPS concluída.
- Firewall: abrir somente portas necessárias, sem desativá-lo nem bloquear SSH.
- Hostinger: quando faltar permissão no firewall do provedor, fornecer a regra exata como pendência manual.
- Reutilizar proxy existente sem substituir configurações de outros serviços.
- Serviço persistente com reinício e startup no reboot, caminhos absolutos e permissões mínimas.
- Health check local separado da checagem externa.
- Nunca fornecer `0.0.0.0`, `localhost` ou `127.0.0.1` como URL pública.

Se HTTPS exigir DNS ainda não configurado, mostrar o registro necessário e estado pendente. Não inventar domínio, IP ou sucesso de verificação externa.

### RF09 — Migração, manutenção e remoção

Detectar o projeto anterior, incluindo `~/.hermes/projects/prospeccao-treg`, mas confirmar seu formato antes de importar.

Oferecer prévia com contagem de registros, backup e importação transacional. Preservar status, observações, evidências e custos. Manter a origem intacta. Reexecutar importação não pode duplicar leads. Não executar arquivos do projeto anterior para lê-los.

Atualizações devem manter dados/configuração fora do diretório de código, aplicar migrações versionadas e permitir recuperação do backup. Falha de atualização não pode derrubar uma instalação anterior funcional sem informar e restaurar o estado possível.

Desinstalação remove somente plugin, serviços e configuração que o instalador criou. Conserva banco e backups por padrão. Eliminar dados exige opção separada e explícita.

### RF10 — Diagnóstico

Comando e tela de diagnóstico com:
- Versões do plugin/Hermes e perfil.
- Estado do serviço, porta, disco e banco.
- Estado do Treg, fontes e orçamento.
- Estado do agendamento e próxima rodada.
- URL, TLS, DNS e firewall com bloqueios específicos.
- Logs recentes sem tokens, senhas ou contatos completos.

Um erro deve apontar ação possível, como adicionar registro DNS, abrir porta no firewall da Hostinger, renovar credencial ou selecionar fonte compatível. Não recomendar Cloudflare/túneis.

### RF11 — Áreas obrigatórias do painel

#### Configurações → Integração Treg
- Campo “Chave da API Treg” como entrada de senha, sem preencher com o segredo existente.
- Botões Testar conexão, Salvar chave e Substituir chave.
- Estados: Não configurado, Conectado, Chave inválida e Erro de conexão; data da validação.
- Validar em leitura sem custo antes de substituir uma chave ativa. Falha de rede não prova que a chave é inválida.
- Exibir equipe/organização e saldo quando retornados pela API, sem expor o segredo.
- Ao salvar, limpar o campo. GET de configurações, logs e exportações retornam apenas metadados.
- Enviar o segredo somente por HTTPS e guardá-lo no servidor. Se o acesso provisório for HTTP, explicar a pendência de HTTPS; permitir a entrada privada no terminal como alternativa inicial.
- Executores já iniciados mantêm snapshot seguro; novos usam a credencial nova. Não apagar custos/reservas da organização anterior.
- Preferências incluem teto global mensal e fuso, separados dos limites das campanhas.

#### Dashboard → Leads
- Busca visível, filtros combinados, chips ativos e botão Limpar filtros.
- Seleção de Todas as campanhas ou campanha específica.
- Tabela paginada, total, intervalo de resultados, seletor 20/50/100 e ordenação.
- Cards e CSV respeitam filtros e explicam o período dos indicadores.
- Detalhes mostram campanhas associadas, contatos, evidências, fontes e status.
- Sem resultados, sugerir limpar filtros; nunca substituir por dados fictícios.

#### Campanhas
- Botão Nova campanha, lista com busca/filtros/paginação e página de detalhes.
- Formulário agrupado: nome/público, regiões/fontes, volume/orçamento e revisão.
- Adicionar/remover várias cidades com UF e validar campos.
- Detalhes com resumo, leads associados, execuções, custo da campanha e saldo global.
- Ações Criar, Editar, Duplicar, Buscar agora, Programar, Pausar/Retomar e Arquivar.
- Buscar agora mostra campanha, fontes e limite; confirmação enfileira e apresenta progresso.
- Erro de validação preserva preenchimento e aponta o campo inválido.
- Arquivar conserva histórico e leads; não é exclusão definitiva.

#### Programação
- Lista por campanha com estado, frequência, fuso, última/próxima execução e motivo de bloqueio.
- Formulário: Uma vez, Todos os dias ou Dias da semana; data quando necessária, horários, dias e fuso.
- Botões Salvar programação, Ativar, Pausar e Retomar.
- Resumo legível e próximas três ocorrências antes de salvar.
- Diferenciar rotina pausada, bloqueio de orçamento e agendador indisponível.
- Alterar programação não executa busca imediatamente; Buscar agora é separado.
- Reconciliar estado com o scheduler após reboot/falha, sem tarefas duplicadas.
- Painel e ferramentas do Hermes usam os mesmos serviços de domínio.

**Navegação principal:** Dashboard, Campanhas, Programação, Execuções e Configurações. Essas páginas devem permitir configurar e operar a prospecção depois da instalação.

## 6. Arquitetura de referência

Esta é uma decisão de produto/implementação proposta, não uma exigência do SDK:

| Componente | Responsabilidade |
|---|---|
| Adaptador Hermes | Registra ferramentas/comandos; encaminha operações ao serviço |
| CLI/instalador | Configuração, implantação, diagnóstico e lifecycle |
| Serviço FastAPI | Autenticação, API, painel, fila persistente e worker |
| Pipeline de prospecção | Consulta planejada, normalização e deduplicação |
| Cliente/adaptadores Treg | Autenticação, endpoints, limites e cobrança |
| SQLite | Campanha, leads, execuções, fila, reservas e evidências |
| Templates/assets prontos | Interface sem build na VPS |
| Adaptador de agendamento | Gestão da tarefa nativa e compatibilidade |
| systemd/proxy | Persistência e acesso externo |

Preferir Python, FastAPI, SQLite com WAL e templates server-rendered com JavaScript simples. React só se houver benefício demonstrado, com assets já compilados no release. Não introduzir Redis, PostgreSQL ou Node em runtime para este MVP.

O serviço deve consumir fila durável. Ferramenta/chat e botão do painel enfileiram o mesmo tipo de tarefa. Implementar lock entre processos, transações curtas e recuperação de interrupção sem repetir chamadas cobradas.

Separar domínio e infraestrutura para testes: o pipeline não depende de prompts, o SDK Hermes não controla a lógica financeira e a UI não chama Treg diretamente.

Dados e segredos ficam em diretório persistente do perfil; código fica no pacote. Usar o mecanismo público de dados do plugin quando disponível e documentar o fallback. Não armazenar grandes coleções de leads em pequenas configurações do Hermes.

## 7. Contrato de comandos a implementar

Os nomes abaixo são a interface desejada do novo plugin; não são comandos já existentes antes da implementação:

| Comando proposto | Comportamento |
|---|---|
| `hermes prospector setup` | Assistente curto e retomável |
| `hermes prospector status` | Estado resumido e URL |
| `hermes prospector doctor` | Diagnóstico sem custo de busca |
| `hermes prospector run` | Enfileirar rodada manual |
| `hermes prospector runs` | Histórico |
| `hermes prospector schedule` | Configurar rotina |
| `hermes prospector pause` / `resume` | Gerenciar rotina |
| `hermes prospector import` | Prévia e importação do legado |
| `hermes prospector backup` | Backup consistente |
| `hermes prospector uninstall` | Remover componentes próprios, preservando dados |

Adicionar `--json` para diagnóstico/status e modo não interativo usando configuração privada, sem token ou senha literal nos argumentos do processo.

O fluxo normal pode terminar após `setup`; os demais comandos são manutenção. Se a API CLI do Hermes instalado não permitir a árvore proposta, fornecer CLI própria equivalente e documentar a incompatibilidade, sem alterar o núcleo.

## 8. Modelo de dados

| Entidade | Dados essenciais |
|---|---|
| campaign | ID, nome, descrição, critérios, versão, orçamento, fuso e estado |
| lead_campaign | Associação, primeira/última ocorrência e observações específicas |
| credential_settings | Organização, referência privada do segredo, estado e data de validação |
| workspace_settings | Teto global e fuso do orçamento compartilhado |
| lead | Identidade normalizada e status comercial |
| lead_source | Fonte, ID externo, evidência e timestamp |
| execution | Campanha, estado, contagens, duração e falhas |
| tool_call | Endpoint, ID Treg, idempotência e estado financeiro |
| budget_reservation | Valor reservado, período, execução e liquidação |
| search_cursor | Fonte/consulta/região, página/cursores e TTL |
| job_queue | Estado, lock, tentativas e recuperação |
| schedule_binding | Campanha, perfil, modo, dias/horários, fuso, IDs Hermes e próximas ocorrências |
| install_state | Etapas, recursos criados e bloqueios |
| schema_migration | Versão e data da migração |

Aplicar índices aos campos de filtros/deduplicação, constraints onde a identidade for segura e chaves estrangeiras. Alteração de status comercial não deve ser sobrescrita por reconsulta.

## 9. Segurança e requisitos não funcionais

- Segredos armazenados com permissão restrita; configuração comum não contém token.
- Senha com hash adequado, sessão protegida, rate limit de login e proteção CSRF nas mutações.
- Redação de logs e diagnósticos; teste que procure tokens nos artefatos exportados.
- Validação de URL/inputs, consultas SQL parametrizadas e subprocessos sem interpolação insegura.
- Verificação de sites com proteção contra SSRF, bloqueando localhost, redes privadas e destinos de metadados da VPS.
- Sem telemetria externa padrão.
- Agente trata textos vindos de leads como dados, não como instruções.
- Aplicação funciona sem usar LLM em seu pipeline determinístico.
- VPS de referência para medir: Linux com systemd, 2 vCPU/4 GB RAM, Hermes já funcionando; registrar consumo real do serviço adicional.
- Consultas paginadas devem continuar responsivas em uma base de teste de 10 mil leads.
- Interface atualiza progresso sem bloquear a requisição durante uma busca longa.
- Timezone explícito e UTC para timestamps internos.
- Documentação distingue requisitos de infraestrutura de custos e limites do Treg.

## 10. Plano de implementação para o Codex

### Fase 0 — Validar contratos
Inspecionar documentação e código públicos da versão do Hermes usada nos testes. Registrar instalação, ativação, ferramentas, CLI, dados persistentes e agendamento suportados em COMPATIBILITY.md. Definir versão mínima com evidência, não por palpite.

Inspecionar catálogo, esquemas, autenticação, preços e limites atuais do Treg. Selecionar pelo menos um adaptador de descoberta com operação válida. Não realizar testes pagos sem credencial e orçamento de teste autorizados.

### Fase 1 — Base instalável
Criar pacote/manifesto, registro de plugin, CLI, instalador com retomada, esquema SQLite, armazenamento de segredos e serviço persistente. Não colocar lógica de instalação dentro do registro/importação do plugin.

### Fase 2 — Busca e finanças
Implementar cliente, adaptadores, múltiplas campanhas, associações de leads, fila, deduplicação, reservas por campanha/globais, limites, idempotência e reconciliação. Criar testes offline com fixtures claramente marcadas.

### Fase 3 — Painel e implantação
Entregar assets prontos, login, busca/filtros/paginação/CSV, histórico, área de chave Treg, gestão de campanhas, programação visual e acesso público direto na VPS. Validar cenário com e sem domínio e sem Cloudflare.

### Fase 4 — Rotina, legado e release
Implementar agendamento, reboot, importação, backup, update/rollback, remoção e diagnóstico. Medir instalação e preparar release/tutorial curto.

Não parar em um esqueleto ou tutorial que manda o usuário reenviar os seis prompts. Entregar o código, instalador e evidência dos critérios atendidos. Não publicar repositório, release ou catálogo externo sem instrução do proprietário.

## 11. Critérios de aceite e testes

| Cenário | Resultado necessário |
|---|---|
| Instalação limpa | Pacote, configuração e serviços corretos; nenhuma busca paga automática |
| Instalador executado novamente | Sem perda de dados, credencial, tarefa ou duplicação de serviço |
| Interrupção no meio | Retoma da etapa faltante e informa bloqueio |
| Hermes incompatível | Falha clara sem modificar core ou atualizar silenciosamente |
| Importação/registro do plugin | Sem efeitos de rede, serviços ou cobrança |
| Perfil alternativo | Isolamento de configuração e dados |
| Token inválido/saldo insuficiente | Mensagem correta; nenhuma falsa conexão ou busca bem-sucedida |
| Chave cadastrada no painel | HTTPS, armazenamento privado, estado validado e segredo ausente em GET/logs |
| Substituição de chave inválida | Credencial anterior válida preservada até validar a nova |
| Várias campanhas | Critérios/cursores/rotinas isolados e orçamento global compartilhado |
| Campanha duplicada/arquivada | Cópia em rascunho; arquivo pausa rotina e preserva histórico |
| Lead em duas campanhas | Uma identidade, duas associações, filtros corretos |
| Busca + filtros + paginação | Combinação no backend, totais/CSV corretos e reset da página |
| Programação visual | Dias/horários/fuso geram tarefas reais com próximas ocorrências |
| Alterar/pausar uma rotina | Sem disparos antigos duplicados; demais campanhas inalteradas |
| Teto global | Reservas simultâneas não excedem o saldo global |
| Fonte que só aceita URL de perfil | Não rotulada como descoberta por cidade |
| Duas solicitações simultâneas | Lock/fila evita rodada duplicada |
| Timeout depois de cobrança | Reconciliação/idempotência evita dupla cobrança quando recuperável |
| Custo pendente | Reserva não liberada como se fosse gratuito |
| Limite exato | Nenhuma chamada autorizada além do saldo reservado/restante |
| Mês com 31 dias | Limite mensal prevalece sobre rotina diária |
| Reinício durante busca | Histórico recuperável sem replay cego de chamada cobrada |
| Reconsulta de lead | Atualiza evidência; preserva status/observações |
| CSV | Filtros corretos e fórmulas neutralizadas |
| Acesso externo | URL abre login de fora da VPS; API exige autenticação |
| Sem domínio | Acesso por IP conforme política provisória e pendências explícitas |
| Reboot | Serviço/agendador voltam e próximo horário permanece correto |
| Legado importado duas vezes | Sem duplicação nem alteração da origem |
| Atualização com falha | Backup/recuperação e dados preservados |
| Desinstalação padrão | Remove somente recursos próprios; conserva dados |
| Sem Cloudflare | Ausência de dependência/configuração de Cloudflare e túneis |

Testes unitários/integrados offline devem cobrir dinheiro, locks, deduplicação, idempotência, fila, migrações e autenticação. Fixtures não podem aparecer como leads reais no produto.

Teste real com Treg deve declarar fontes, parâmetros, quantidade, IDs de chamadas e custo, usando orçamento de teste explícito. Se não houver credencial/VPS de teste, marcar validação real como pendente, não inventar resultados.

## 12. Entregáveis obrigatórios

- Repositório completo do plugin e serviço.
- Manifesto e pacote de release com instalador.
- README em PT-BR com fluxo de instalação curto.
- COMPATIBILITY.md com versões efetivamente testadas.
- Documentação de configuração privada, domínio/IP e firewall da Hostinger.
- Atualização, backup, rollback, importação e remoção.
- Testes, fixtures e relatório de verificação.
- Capturas do Dashboard, Configurações Treg, Campanhas e Programação; medição de tempo/recursos.
- Relatório de testes reais ou lista explícita de pendências.
- CHANGELOG e instruções de build reproduzível.
- Licença definida pelo proprietário antes de publicar.

## 13. Instrução inicial para colar no Codex

> Implemente o plugin descrito neste PRD. Primeiro valide os contratos atuais do Hermes e do Treg e registre a compatibilidade. Depois construa o plugin nativo, o serviço e o painel prontos, com instalador idempotente e assistente curto. O painel deve rodar na VPS onde o Hermes está instalado e abrir pelo IP ou domínio no meu navegador, sem Cloudflare e sem túneis. Implemente a área web para cadastrar/testar/substituir a chave do Treg, dashboard com filtros/busca/paginação, gestão de várias campanhas e programação visual das execuções. Essas funções são obrigatórias no MVP e devem funcionar pelo navegador sem prompts ou terminal no uso cotidiano. Não gere o sistema durante a instalação, não modifique o core do Hermes, não exponha credenciais e não apague dados do projeto anterior. Execute os testes disponíveis e entregue evidência. Identifique como pendentes os testes que dependem de credencial ou VPS indisponíveis. Não publique externamente sem instrução. Não implemente envio automático de mensagens aos leads.

## 14. Referências oficiais e limites da especificação

Consultadas em 09/10/2026:
- Plugins Hermes: https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins
- Desenvolvimento de plugins: https://hermes-agent.nousresearch.com/docs/developer-guide/plugins
- Agendamento: https://hermes-agent.nousresearch.com/docs/user-guide/features/cron
- Treg, protocolo para agentes: https://treg.to/llms.txt
- Treg, API: https://treg.to/docs
- Caddy, proxy reverso: https://caddyserver.com/docs/quick-starts/reverse-proxy

**Base factual resumida:** Hermes documenta plugins nativos com manifesto e registro Python, ferramentas/comandos públicos, instalação/ativação e armazenamento persistente por perfil. Documenta também agendamento com execução de scripts e sessões agente. O Treg documenta autenticação REST por cabeçalho próprio, catálogo, execução e metadados de cobrança. Caddy documenta proxy e HTTPS por domínio.

**Decisões propostas neste PRD:** nome do produto, stack do serviço, ferramentas/comandos do Prospector, telas, orçamento padrão, metas de tempo e algoritmo. São funcionalidades a implementar, não recursos já existentes ou resultados medidos.

O contrato consultado pode diferir do Hermes instalado na VPS. O Codex deve revalidar os detalhes no começo da implementação e não presumir suporte apenas porque uma página atual o descreve.
