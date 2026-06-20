# Implementation Plans — TechPulse

Gerado pelo skill `improve` em 2026-06-20, commit `b15548f`.

Execute na ordem abaixo. Cada executor: leia o plano completo antes de iniciar, respeite os STOP conditions, e atualize o status quando concluir.

## Execution order & status

| Plan | Title | Priority | Effort | Depends on | Status |
|------|-------|----------|--------|------------|--------|
| [001](001-security-quick-wins.md) | Corrigir Três Vulnerabilidades de Segurança de Alto Impacto / Baixo Esforço | P1 | S | — | DONE — branch `advisor/001-security-quick-wins` |
| [002](002-db-perf-indexes-pushdown.md) | Corrigir Queries que Carregam Toda a Tabela + Adicionar Índices Faltantes | P1 | M | — | DONE — branch `advisor/002-db-perf-indexes-pushdown` |
| [003](003-backend-dx-baseline.md) | Estabelecer Baseline de DX no Backend (ruff + mypy + cobertura + CI) | P1 | S | — | DONE — branch `advisor/003-backend-dx-baseline` |
| [004](004-thread-safety-settings-cache.md) | Corrigir Thread-Safety do Cache de Feedback e Cache de Settings | P2 | M | — | DONE — branch `advisor/004-thread-safety-settings-cache` |
| [005](005-semantic-dedup-on2-fix.md) | Corrigir Complexidade O(n²) na Deduplicação Semântica de Títulos | P2 | M | — | DONE — branch `advisor/005-semantic-dedup-on2-fix` |

Status values: `TODO` | `IN PROGRESS` | `DONE` | `BLOCKED (motivo)` | `REJECTED (motivo)`

## Dependency notes

- Plans 001, 002, 003 são **independentes** — podem ser executados em paralelo ou em qualquer ordem.
- Plans 004 e 005 também são independentes entre si e dos anteriores.
- Ordem recomendada se executando sequencialmente: **001 → 003 → 002 → 004 → 005** (segurança primeiro, depois DX para CI ter feedback, depois perf).

## Findings considered and rejected

Os seguintes achados foram identificados no audit mas não incluídos como planos nesta rodada:

- **`asyncio.run()` aninhado** (`ingest.py:544`, `routes/obsidian.py:131`): bug real, mas refactor exige mudanças amplas na camada de routing async. Planejado para sprint futura — escopo maior que os outros.
- **Dual migration (Alembic + `migrate_sqlite_schema`)** (`models.py:59-131`): dívida técnica confirmada, esforço L, sem risco imediato. Deferred até o projeto ter deploy em produção.
- **Rate limiting** (`routes/*`): válido, mas requer decisão de product (qual biblioteca, limites por endpoint). Deferred — não é blocker para dev local.
- **Frontend triple polling** (`hooks/usePipelineStatus.ts`): esforço M, impacto médio. Deferred para quando o projeto tiver múltiplos usuários.
- **Obsidian `httpx.Client` síncrono** (`obsidian.py`): blocking I/O em async — dívida real, mas requer refactor do módulo completo. Deferred.
- **Testes da camada repository** (`repositories/news.py`): gap de cobertura importante, mas trabalho incremental — adicionar à medida que bugs surgem.
- **`batch._pending = 0` acesso a atributo privado** (`ingest.py:521`): code smell, baixo risco. Fix trivial mas fora do escopo dos planos prioritários.

## Planos de Features — Round 2 (commit `61a5610`, 2026-06-20)

| Plan | Title | Priority | Effort | Depends on | Status |
|------|-------|----------|--------|------------|--------|
| [006](006-fts5-search-upgrade.md) | Upgrade Busca Textual de ILIKE para SQLite FTS5 | P1 | M | — | DONE — merged to main |
| [007](007-concept-cloud-dynamic.md) | Concept Cloud Dinâmico via ai_reasoning | P2 | S | — | DONE — merged to main |
| [008](008-rss-output-feed.md) | RSS Output Feed — /api/feed.rss | P2 | S | — | DONE — merged to main |
| [009](009-source-health-monitor.md) | Source Health Monitor — Painel de Status por Scraper | P2 | M | — | DONE — merged to main |
| [010](010-feedback-diversity.md) | Feedback Diversificado — TALVEZ + Cache por Fonte + Histórico | P2 | S | — | DONE — merged to main |
| [011](011-digest-webhook.md) | Digest Semanal por Webhook JSON | P3 | M | — | DONE — merged to main |
| [012](012-hype-rss-signals.md) | Hype Score para Fontes RSS — Sinais de Frequência | P3 | S | — | DONE — merged to main |
| [013](013-semantic-search-embeddings.md) | Semantic Search via Ollama Embeddings | P3 | L | — | DONE — merged to main |
| [014](014-personal-analytics.md) | Personal Analytics — GET /api/analytics | P3 | S | — | DONE — merged to main |

### Dependency notes — Round 2

- **006 e 009** podem colidir no número de migration Alembic: ambos criam uma migration nova. Se executados em paralelo, o segundo deve verificar `alembic current` e usar o próximo número disponível.
- **011 (Digest Webhook)** depende que `list_news_filtered` continue aceitando `q=None`. Se o plano 006 mudar a assinatura, verifique o plano 011 antes de executar.
- **008 e 011** ambos registram routers em `routes/__init__.py` — se executados em paralelo, haverá conflito de merge. Executar sequencialmente.
- **013 (Semantic Search)** exige `ollama pull nomic-embed-text` antes da execução. Verificar disponibilidade do Ollama.
- Todos os outros planos (007, 008, 010, 012, 014) são independentes entre si.

### Ordem recomendada de execução

Sequencial: **010 → 007 → 012 → 008 → 014 → 006 → 009 → 011 → 013**

Racional: começa pelos de menor esforço e risco (010, 007, 012), depois os que criam novas rotas (008, 014), depois os que tocam em Alembic/DB (006, 009), depois os que têm dependências externas (011, 013).

## Sugestões descartadas nesta rodada

- **Spaced Repetition (revisão de bookmarks)**: `last_reviewed_at` + filtro. Descartado por falta de demanda imediata — os bookmarks já têm pasta como organização.
- **Multi-user support**: `user_id` em tudo — aguardar deploy em produção antes de iniciar.
- **Email SMTP**: mais complexo que webhook (credenciais, templates HTML, SPF/DKIM). Coberto indiretamente pelo plano 011 via N8N/Zapier → email.
