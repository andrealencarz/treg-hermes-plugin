# Hermes Prospector + Treg

Plugin para Hermes `0.21.5` que organiza campanhas, leads, execuções, custos e programação na própria interface web do Hermes. As fontes selecionáveis são Google Maps, Instagram e páginas de empresas do LinkedIn via Treg. Instalar ou ativar o plugin não inicia buscas pagas.

**Estado:** versão `0.1.0.dev7`. A interface e os adaptadores foram testados localmente; Instagram e LinkedIn ainda precisam de validação com chamadas reais na instalação do usuário.

## Instalação pela interface do Hermes (v0.21.5)

A URL instala o código, mas ainda é preciso ativar o plugin, reiniciar o serviço do Dashboard e configurar o Treg. Todo o procedimento pode ser feito pelas interfaces web, sem terminal na VPS.

### Primeira instalação

1. No Dashboard do Hermes, abra **Plugins** e localize **Install from GitHub / Git URL**. Use esse formulário; a busca em **Plugin Catalog** não encontra este plugin personalizado.
2. Cole `https://github.com/andrealencarz/treg-hermes-plugin` em **Git URL or owner/repo**.
3. Marque **Enable after install** (**Ativar após instalar**) e clique **Install**. O Hermes pode avisar que a origem personalizada não foi revisada pelo catálogo.
4. Confirme que o Prospector aparece entre os plugins instalados e está habilitado.
5. No painel da hospedagem, **reinicie o serviço/projeto do Hermes que executa o Dashboard**. Na Hostinger, use **hPanel → VPS → Gerenciador Docker → projeto do Hermes → Ações → Reiniciar**. No Hermes 0.21.5, a API do plugin é carregada quando esse serviço inicia; o botão **Restart Gateway** da tela **System** não substitui esse reinício.
6. Recarregue o Dashboard com `⌘⇧R` (macOS) ou `Ctrl+Shift+R` (Windows/Linux) e abra **Prospector → Configurações**. Cadastre a chave Treg em uma sessão HTTPS. Se ela for um token de identidade, informe também o slug da organização. A chave é validada antes de ser salva.
7. Ajuste o teto mensal global e, ao criar uma campanha, o teto por rodada **antes** de clicar **Buscar agora**. A instalação e a validação da chave não iniciam buscas pagas.

O GitHub fornece apenas o código. Dados, banco e segredo ficam em `<HERMES_HOME>/plugin-data/hermes-prospector` no servidor; não coloque a chave na URL nem no repositório.

### Atualizar uma instalação existente

1. Em **Plugins**, encontre o Prospector instalado e use **Git pull** para obter a versão mais recente deste repositório. Confirme que a versão exibida mudou quando houver uma nova versão publicada.
2. Reinicie o serviço/projeto do Hermes pelo painel da hospedagem para carregar as alterações da API.
3. Faça uma recarga forçada no navegador e abra **Prospector**. Suas campanhas e configurações ficam no diretório de dados do plugin.

Se o menu **Prospector** aparecer, mas o formulário não carregar ou a página informar que a API não está ativa, repita o reinício do serviço do Dashboard e a recarga forçada. Confira também se o plugin continua habilitado em **Plugins**.

## Primeira campanha

1. Em **Configurações**, ajuste o teto mensal global. Para uma primeira validação pequena, use um teto de até US$ 0,20, observando qualquer gasto já realizado no mesmo mês.
2. Em **Campanhas**, crie um rascunho com nicho e cidade/UF, marque uma ou mais fontes e escolha um teto por rodada adequado. Use um termo curto, como `dentista`. O teste local com esse termo em Fortaleza retornou um lugar no Google Maps; os resultados variam por fonte, região e disponibilidade no Treg. Use **Editar** para alterar nome, nicho, serviço, cidades, fontes, meta e tetos; ou **Salvar fontes** para alterar apenas a seleção de fontes. Rodadas já enfileiradas preservam os dados anteriores.
3. Clique **Buscar agora**. A página **Execuções** mostra estado e custo; **Leads** permite filtrar, atualizar status e exportar CSV.
4. Em **Programação**, salve horários e fuso. A agenda fica pausada até clicar **Ativar**. O cron do Hermes executa um script sem LLM que enfileira e processa a rodada.

O teto global padrão do produto é US$ 30/mês e o teto padrão por rodada é US$ 1. Ajuste esses valores antes de qualquer busca. A autorização de US$ 0,20 dada para os testes locais não autoriza novas chamadas pagas na instalação.

Cada fonte selecionada faz uma chamada por cidade, sujeita aos tetos da rodada, da campanha e do espaço de trabalho. Google Maps procura estabelecimentos; Instagram procura perfis públicos por termo e cidade no texto da busca; LinkedIn procura páginas de empresas por termo e localização. A localização de um perfil do Instagram não é verificada pela fonte. O painel mostra a origem de cada lead e o CSV inclui a coluna **Fontes**. As integrações sociais foram validadas com contratos públicos e respostas simuladas; a primeira execução real deve ser feita com teto pequeno e conferida em **Execuções**.

## Análise de sites dos leads

Em **Leads**, use **Analisar site** em um lead ou **Analisar sites da página** para verificar até 20 leads ainda sem análise, com até três verificações simultâneas. A análise consulta a página pública diretamente, sem Treg e sem custo de API. O resultado salvo mostra disponibilidade, tipo de página, plataforma reconhecida e data da verificação. **Detalhes da análise** lista os sinais encontrados; o CSV também inclui essas colunas. Se o site do lead mudar, a análise antiga deixa de ser exibida até nova verificação.

O seletor **Situação do site** filtra por **Sem site**, **Site ruim**, **Site bom** ou **Não analisado**; o CSV respeita a seleção. **Site ruim** inclui páginas inacessíveis, plataformas de terceiros e sites próprios com SEO abaixo de 60. **Site bom** exige site próprio no ar e SEO de pelo menos 60. **Não analisado** inclui URLs sem verificação ou com resultado inconclusivo.

O indicador de SEO (0 a 100) é uma triagem técnica da página inicial: título, meta description, H1, diretiva noindex, URL canônica, idioma e viewport. Ele não mede posição no Google. Em páginas de links, delivery, marketplace e redes sociais, o SEO do site próprio não é avaliado. HTTP 401/403/429 aparece como **Acesso bloqueado**, distinto de **Fora do ar / inacessível**. O detalhe indica falhas de DNS, tempo limite ou TLS; a consulta tem limite de tempo e tamanho, e endereços internos ou privados são recusados.

## Segurança e custos

A API integrada usa a autenticação e a proteção de rotas de plugins do Dashboard Hermes. O segredo Treg fica em arquivo privado no perfil Hermes e não é retornado pela API. Em caso de resposta perdida do Treg, a reserva permanece pendente e a chamada não é repetida automaticamente. Confira o ledger e use **Reconciliar custos** em **Execuções** antes de repetir uma busca equivalente.

O painel precisa ser acessado por HTTPS para cadastrar a chave fora do host local. A instalação real precisa ser validada conforme [VERIFICATION.md](VERIFICATION.md), incluindo acesso, reinicialização e cron no servidor.

## Desenvolvimento e testes locais

```bash
uv sync --extra test
bash scripts/test_local.sh
uv build
```

Os testes offline não fazem chamadas pagas. Para validar uma chave temporária, crie um `.env` privado a partir de `.env.example`, com permissão `0600`; o Git ignora esse arquivo. O teste gratuito de identidade/catálogo é `.venv/bin/python -m scripts.treg_smoke`. Uma chamada paga exige `--paid`, `--max-usd` e um diretório de auditoria novo. Consulte [VERIFICATION.md](VERIFICATION.md) antes de usar. Revogue uma chave temporária após o teste.

Instale e atualize este plugin pela interface do Hermes.
