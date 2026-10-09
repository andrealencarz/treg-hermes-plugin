# Histórico

## 0.1.0.dev2 — 09/10/2026

- Botão **Editar** e formulário completo nas campanhas do Dashboard Hermes.
- API de edição permite atualizar serviço e valida cidades, além de nome, nicho, fontes, meta e tetos.
- Testes da edição no painel e da persistência pela API.

## 0.1.0.dev1 — 09/10/2026

- Campanhas podem selecionar Google Maps, Instagram e LinkedIn, inclusive adicionar ou desmarcar fontes após a criação.
- Adaptadores normalizam os resultados das três fontes; leads registram a origem no painel e no CSV.
- Migração de campanhas existentes preserva Google Maps; rodadas já enfileiradas mantêm a seleção anterior.
- Catálogo e preço de cada ferramenta são conferidos antes da rodada; limites e reconciliação seguem por chamada.
- Testes locais de contrato, migração e execução com múltiplas fontes, sem chamadas pagas.

## 0.1.0.dev0 — 09/10/2026

- Aba Prospector e API incorporadas ao Dashboard Hermes 0.21.5; instalação por URL na tela Plugins.
- Conexões SQLite de requisição aceitam a troca de thread usada pelas dependências síncronas do FastAPI no Hermes.
- Worker iniciado com o Dashboard; script de cron usa o Python do Hermes, sem ambiente separado.
- Testes de integração local da API e scanner de instalação Hermes com resultado seguro.
- Estrutura nativa do plugin Hermes e serviço web Python.
- Campanhas múltiplas, descoberta Google Maps via Treg, fila, leads e reservas de orçamento.
- Painel com login, configuração Treg, campanhas, execuções, filtros, CSV e programação nativa em pausa por padrão.
- Testes offline e uma rodada real Treg local com custo reconciliado.

Versão em desenvolvimento. Validação da instalação no servidor Hermes e do acesso externo pendente.
