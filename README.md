# Hermes Prospector + Treg

Plugin Python nativo do Hermes com painel web na mesma VPS para campanhas de descoberta de empresas. O painel, o worker e os assets são distribuídos prontos. A instalação não executa busca paga nem ativa rotina.

## Estado desta versão

Este repositório contém uma implementação local em desenvolvimento (`0.1.0.dev0`). Ela foi testada offline, mas **ainda não foi validada em uma VPS Hermes real nem com uma chave Treg**. Não publique como release de produção sem executar `VERIFICATION.md` na sua VPS.

A primeira fonte é Google Maps via `anyapi.google.serp.maps`. O catálogo público confirma os parâmetros `query`, `location` e `limit` (1–20) e informa preço de referência por chamada; o custo efetivo vem do header de cobrança do Treg. LinkedIn e Instagram não aparecem como fontes de descoberta nesta versão.

## Pré-requisitos

- VPS Linux com systemd, Hermes **0.21.5 ou superior** e Python 3.11+.
- Usuário não root que é dono do perfil Hermes, com `sudo` para serviço/proxy.
- URL HTTPS do repositório Git publicado por você. Esta documentação não presume uma URL.
- Para domínio: DNS apontando para a VPS e Caddy (o instalador tenta instalar via `apt-get` quando não há Nginx).
- Para IP provisório: IP público, `ufw` ativo com política de entrada `deny` e CIDR do operador.

## Instalação

Depois de publicar o repositório, obtenha o código e execute, na VPS do Hermes:

```bash
git clone URL_DO_REPOSITORIO hermes-prospector
bash hermes-prospector/install.sh --source URL_DO_REPOSITORIO --domain SEU_DOMINIO
```

Sem domínio, use `--ip IP_PUBLICO --operator-cidr SEU_IP/32`. O acesso será HTTP provisório restrito pelo `ufw`; nesse modo, cadastre a chave pelo terminal privado, não no navegador. O instalador cria a senha do painel por entrada privada, instala o plugin no Hermes, prepara o serviço systemd e configura Caddy quando há domínio. Ele pode ser executado novamente sem recriar banco, senha ou tarefas.

Abra a URL informada no fim da instalação. Acesso externo, DNS, TLS e firewall do provedor devem ser conferidos a partir de outro dispositivo. O health check local não prova acesso público.

## Uso

1. Entre no painel e cadastre/teste a chave Treg em **Configurações**, se estiver em HTTPS. Uma chave nova só substitui a anterior após validação gratuita.
2. Crie uma campanha em rascunho com nicho e cidades/UF. O teto global inicial é US$ 30/mês, compartilhado entre campanhas; o teto padrão por rodada é US$ 1.
3. Clique **Buscar agora** após revisar a campanha e o teto. A fila processa uma rodada por vez; a página **Execuções** mostra contagens e custo.
4. Em **Programação**, salve horários e fuso, veja a prévia e ative a rotina separadamente. O cron do Hermes apenas enfileira a busca; o worker a executa sem LLM.

No terminal privado, se necessário:

```bash
~/.hermes/plugin-data/hermes-prospector/venv/bin/prospector treg set-token
hermes prospector status
hermes prospector campaigns
hermes prospector runs
```

O comando de chave pede o segredo sem colocá-lo em argumentos do processo. Para token de identidade, acrescente `--org SLUG_DA_EQUIPE`. Ajuste `HERMES_HOME` se usa outro perfil.

## Dados e segurança

O banco, a chave e os backups ficam em `<HERMES_HOME>/plugin-data/hermes-prospector`; o código fica em `<HERMES_HOME>/plugins/hermes-prospector`. O token não é enviado a ferramentas do modelo nem retornado por GET. A API exige login e proteção CSRF; o CSV neutraliza fórmulas. O serviço usa o usuário do Hermes, não root.

Em caso de resposta perdida do Treg, a reserva permanece pendente. Esta versão não repete automaticamente uma chamada possivelmente cobrada. Verifique a chamada no Treg antes de liberar uma pendência ou iniciar uma busca equivalente.

## Desenvolvimento local

```bash
uv sync --extra test
uv run pytest -q
uv build
```

Para inspecionar o painel localmente, configure uma senha com `uv run prospector admin set-password` e inicie `PROSPECTOR_COOKIE_SECURE=0 uv run prospector serve`. Use dados de teste em `PROSPECTOR_DATA_DIR` para não tocar o perfil Hermes real.

Consulte [COMPATIBILITY.md](COMPATIBILITY.md) para contratos verificados e [VERIFICATION.md](VERIFICATION.md) para o aceite na VPS. A licença deve ser definida pelo proprietário antes de qualquer publicação externa.
