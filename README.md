# Hermes Prospector + Treg

Plugin para Hermes `0.21.5` que organiza campanhas, leads, execuções, custos e programação na própria interface web do Hermes. As fontes selecionáveis são Google Maps, Instagram e páginas de empresas do LinkedIn via Treg. Instalar ou ativar o plugin não inicia buscas pagas.

**Estado:** versão `0.1.0.dev6`. A interface e os adaptadores foram testados localmente; Instagram e LinkedIn ainda precisam de validação com chamadas reais na instalação do usuário.

## Instalar pela interface do Hermes

1. Abra o Dashboard do Hermes e entre em **Plugins**.
2. No campo de instalação por identificador/URL, cole `https://github.com/andrealencarz/treg-hermes-plugin`.
3. Deixe **Ativar após instalar** ligado e clique **Instalar**. A origem é personalizada, então o Hermes pode mostrar um aviso de fonte não revisada.
4. Reinicie o serviço **Dashboard/serve do Hermes** pelo painel da sua hospedagem e recarregue a página. O Hermes 0.21.5 monta a API dos plugins quando esse serviço inicia. Reiniciar somente o gateway pela tela Sistema não monta a API nova.
5. Abra **Prospector → Configurações** e cadastre sua chave Treg em uma sessão HTTPS. Para token de identidade, informe também o slug da organização. A chave é validada antes de ser salva.

O GitHub é apenas a origem do código. O plugin cria seus dados, banco e segredo em `<HERMES_HOME>/plugin-data/hermes-prospector` no servidor. A chave não entra no repositório.

## Primeira campanha

1. Em **Configurações**, ajuste o teto mensal global. Para uma primeira validação pequena, use um teto de até US$ 0,20, observando qualquer gasto já realizado no mesmo mês.
2. Em **Campanhas**, crie um rascunho com nicho e cidade/UF, marque uma ou mais fontes e escolha um teto por rodada adequado. Use um termo curto, como `dentista`. O teste local com esse termo em Fortaleza retornou um lugar no Google Maps; os resultados variam por fonte, região e disponibilidade no Treg. Use **Editar** para alterar nome, nicho, serviço, cidades, fontes, meta e tetos; ou **Salvar fontes** para alterar apenas a seleção de fontes. Rodadas já enfileiradas preservam os dados anteriores.
3. Clique **Buscar agora**. A página **Execuções** mostra estado e custo; **Leads** permite filtrar, atualizar status e exportar CSV.
4. Em **Programação**, salve horários e fuso. A agenda fica pausada até clicar **Ativar**. O cron do Hermes executa um script sem LLM que enfileira e processa a rodada.

O teto global padrão do produto é US$ 30/mês e o teto padrão por rodada é US$ 1. Ajuste esses valores antes de qualquer busca. A autorização de US$ 0,20 dada para os testes locais não autoriza novas chamadas pagas na instalação.

Cada fonte selecionada faz uma chamada por cidade, sujeita aos tetos da rodada, da campanha e do espaço de trabalho. Google Maps procura estabelecimentos; Instagram procura perfis públicos por termo e cidade no texto da busca; LinkedIn procura páginas de empresas por termo e localização. A localização de um perfil do Instagram não é verificada pela fonte. O painel mostra a origem de cada lead e o CSV inclui a coluna **Fontes**. As integrações sociais foram validadas com contratos públicos e respostas simuladas; a primeira execução real deve ser feita com teto pequeno e conferida em **Execuções**.

## Análise de sites dos leads

Em **Leads**, use **Analisar site** em um lead ou **Analisar sites da página** para verificar até 20 leads ainda sem análise, com até três verificações simultâneas. A análise consulta a página pública diretamente, sem Treg e sem custo de API. O resultado salvo mostra disponibilidade, tipo de página, plataforma reconhecida e data da verificação. **Detalhes da análise** lista os sinais encontrados; o CSV também inclui essas colunas. Se o site do lead mudar, a análise antiga deixa de ser exibida até nova verificação.

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
