# Hermes Prospector + Treg

Plugin para Hermes `0.21.5` que organiza campanhas, leads, execuções, custos e programação na própria interface web do Hermes. A fonte inicial de descoberta é Google Maps via Treg. Instalar ou ativar o plugin não inicia buscas pagas.

**Estado:** versão `0.1.0.dev0`. A integração foi testada localmente contra o contrato do Hermes 0.21.5, mas ainda precisa de validação na instalação real do usuário.

## Instalar pela interface do Hermes

1. Abra o Dashboard do Hermes e entre em **Plugins**.
2. No campo de instalação por identificador/URL, cole `https://github.com/andrealencarz/treg-hermes-plugin`.
3. Deixe **Ativar após instalar** ligado e clique **Instalar**. A origem é personalizada, então o Hermes pode mostrar um aviso de fonte não revisada.
4. Reinicie o serviço **Dashboard/serve do Hermes** pelo painel da sua hospedagem e recarregue a página. O Hermes 0.21.5 monta a API dos plugins quando esse serviço inicia. Reiniciar somente o gateway pela tela Sistema não monta a API nova.
5. Abra **Prospector → Configurações** e cadastre sua chave Treg em uma sessão HTTPS. Para token de identidade, informe também o slug da organização. A chave é validada antes de ser salva.

O GitHub é apenas a origem do código. O plugin cria seus dados, banco e segredo em `<HERMES_HOME>/plugin-data/hermes-prospector` no servidor. A chave não entra no repositório.

## Primeira campanha

1. Em **Configurações**, ajuste o teto mensal global. Para uma primeira validação pequena, use um teto de até US$ 0,20, observando qualquer gasto já realizado no mesmo mês.
2. Em **Campanhas**, crie um rascunho com nicho e cidade/UF. Use um termo curto, como `dentista`, e um teto por rodada adequado. O teste local com esse termo em Fortaleza retornou um lugar; o resultado depende da região e do catálogo Treg.
3. Clique **Buscar agora**. A página **Execuções** mostra estado e custo; **Leads** permite filtrar, atualizar status e exportar CSV.
4. Em **Programação**, salve horários e fuso. A agenda fica pausada até clicar **Ativar**. O cron do Hermes executa um script sem LLM que enfileira e processa a rodada.

O teto global padrão do produto é US$ 30/mês e o teto padrão por rodada é US$ 1. Ajuste esses valores antes de qualquer busca. A autorização de US$ 0,20 dada para os testes locais não autoriza novas chamadas pagas na instalação.

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
