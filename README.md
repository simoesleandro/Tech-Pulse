<div align="center">

<!-- Adicione docs/screenshot.png após capturar o dashboard -->
<img src="docs/screenshot.png" alt="TechPulse screenshot" width="100%">
<br/>

# TechPulse

**PT:** Feed de inteligência técnica filtrado por IA local. Zero ruído, só sinal.  
**EN:** Localized, AI-filtered engineering intelligence feed. Zero noise, just signal.

<br/>

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-22c55e?style=flat-square)](LICENSE)
[![Last Commit](https://img.shields.io/github/last-commit/simoesleandro/Tech-Pulse?style=flat-square&color=8b5cf6)](https://github.com/simoesleandro/Tech-Pulse/commits)
[![Issues](https://img.shields.io/github/issues/simoesleandro/Tech-Pulse?style=flat-square&color=f59e0b)](https://github.com/simoesleandro/Tech-Pulse/issues)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.137-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16-black?style=flat-square&logo=next.js)](https://nextjs.org)
[![Ollama](https://img.shields.io/badge/Ollama-Gemma4-000000?style=flat-square)](https://ollama.com)

<br/>

[📖 Documentação](system_design.html) &nbsp;·&nbsp;
[🐛 Reportar bug](https://github.com/simoesleandro/Tech-Pulse/issues) &nbsp;·&nbsp;
[💡 Sugerir feature](https://github.com/simoesleandro/Tech-Pulse/issues)

</div>

---

## 📋 Índice / Table of Contents

- [Sobre / About](#-sobre--about)
- [Demo](#-demo)
- [Funcionalidades / Features](#-funcionalidades--features)
- [Stack](#-stack)
- [Instalação / Setup](#-instalação--setup)
- [Uso / Usage](#-uso--usage)
- [Variáveis de Ambiente / Environment Variables](#-variáveis-de-ambiente--environment-variables)
- [Arquitetura / Architecture](#-arquitetura--architecture)
- [Testes / Tests](#-testes--tests)
- [Roadmap](#-roadmap)
- [Autor / Author](#-autor--author)

---

## 📌 Sobre / About

**PT:**  
O TechPulse mitiga a fadiga de informação de engenheiros de software, consolidando canais técnicos (Dev.to, Reddit, GitHub Trends) em um dashboard de alta densidade. Um pipeline de ingestão em background sanitiza, deduplica e classifica cada artigo via Gemma local (Ollama) antes de persistir no SQLite — a navegação no frontend permanece instantânea.

**EN:**  
TechPulse reduces information overload for software engineers by consolidating technical channels (Dev.to, Reddit, GitHub Trends) into a high-density dashboard. A background ingestion pipeline sanitizes, deduplicates, and classifies each article via local Gemma (Ollama) before persisting to SQLite — keeping the frontend browsing experience instant.

---

## 🎯 Demo

> Projeto local — sem deploy público. Clone e rode conforme instruções abaixo.

<details>
<summary>📸 Screenshots</summary>
<br/>

| Dashboard | System Design |
|-----------|---------------|
| Adicione `docs/screenshot-dashboard.png` | Veja [`system_design.html`](system_design.html) |

</details>

---

## ✨ Funcionalidades / Features

> **PT:** O que o projeto faz  
> **EN:** What the project does

- ✅ Ingestão automática de Dev.to, Reddit, Hacker News, GitHub Trends e RSS
- ✅ Pipeline multi-agente (Triador → Tradutor → Hype) ou modo unificado via Ollama/Groq
- ✅ Export Obsidian híbrido (vault local + REST API), orquestrador, MOCs e digest semanal
- ✅ Dashboard Next.js com painéis Sistema, Configurações, triagem rápida e drawer de detalhe
- ✅ Filtros avançados: hype mínimo, status Obsidian, pastas, busca por conceito
- ✅ Deduplicação por URL antes da inferência de IA
- 🚧 Deploy em produção *(em desenvolvimento / in progress)*

---

## 🛠 Stack

| Camada / Layer | Tecnologia / Technology |
|----------------|------------------------|
| Backend | FastAPI + SQLAlchemy + Pydantic |
| Frontend | Next.js 16 + Tailwind CSS 4 |
| Banco de dados / Database | SQLite |
| IA / AI | Gemma4 local via Ollama (opcional Groq) |
| Deploy | Local (dev) |
| Testes / Tests | `pytest` em `backend/tests/` + build Next.js no CI |

---

## 🚀 Instalação / Setup

### Pré-requisitos / Prerequisites

- Python 3.11+
- Node.js 20+
- [Ollama](https://ollama.com) com modelo `gemma4:12b` (ou `gemma`) — `ollama pull gemma4:12b`

### Instalação / Installation

```bash
# Clone o repositório / Clone the repository
git clone https://github.com/simoesleandro/Tech-Pulse
cd Tech-Pulse

# ── Backend ──
cd backend
python -m venv .venv
# Windows: .\.venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# ── Frontend ──
cd ../frontend
npm install
cp .env.local.example .env.local

# ── Variáveis de ambiente (raiz) ──
cd ..
cp .env.example .env
```

---

## 💻 Uso / Usage

### Subir a API

```bash
cd backend
.\.venv\Scripts\uvicorn app.main:app --reload   # Windows
# source .venv/bin/activate && uvicorn app.main:app --reload   # Linux/macOS
```

Swagger: `http://127.0.0.1:8000/docs`

### Subir o dashboard

```bash
cd frontend
npm run dev
```

Abra `http://localhost:3000`

### Disparar ingestão manual

```bash
curl -X POST http://127.0.0.1:8000/api/ingest
```

Ou use o botão **Atualizar feed** no painel **Ingestão**.

### Dados demo (sem Ollama)

```bash
curl -X POST http://127.0.0.1:8000/api/seed
```

Ou clique em **Dados demo** no painel **Ingestão** do dashboard.

### Painéis do dashboard

| Painel | Função |
|--------|--------|
| **Ingestão** | Atualizar feed, dados demo, progresso SSE |
| **Configurações** | Ingest em background, fontes ativas, auto-export Obsidian |
| **Sistema** | Backfill Obsidian, re-enrich legado, MOCs, digest semanal |
| **Filtros** | Hype mínimo/exato, status Obsidian, fonte, assunto |
| **Triagem rápida** | Atalhos `e` marcar lida · `s` salvar · `o` Obsidian · `j/k` navegar |

---

## 🔐 Variáveis de Ambiente / Environment Variables

| Variável | Descrição / Description | Padrão / Default |
|----------|------------------------|-----------------|
| `OLLAMA_URL` | Endpoint de geração do Ollama | `http://localhost:11434/api/generate` |
| `OLLAMA_MODEL` | Modelo local para classificação | `gemma4:12b` |
| `OLLAMA_TIMEOUT` | Timeout da inferência (segundos) | `60` |
| `INGEST_ON_STARTUP` | Ingerir ao iniciar o backend | `false` |
| `INGEST_BACKGROUND` | Loop de ingestão em background | `false` |
| `INGEST_INTERVAL_SECONDS` | Background loop interval (seconds) | `300` |
| `ALLOW_SEED` | Enable `POST /api/seed` demo endpoint | `true` |
| `NEXT_PUBLIC_API_URL` | API URL for the frontend | `http://localhost:8000` |

> Lista completa em / Full list in: [`.env.example`](.env.example)

---

## 🏗 Arquitetura / Architecture

```
Tech-Pulse/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI, CORS, rotas REST
│   │   ├── models.py         # ORM NewsItem (SQLite)
│   │   ├── schemas.py        # Validação Pydantic
│   │   └── services/         # Scrapers, Ollama, pipeline de ingestão
│   ├── test_api.py           # Testes dos endpoints REST (legado)
│   └── tests/                # Suite pytest (~80 cenários)
├── frontend/
│   ├── app/                  # Next.js App Router
│   ├── components/           # Dashboard, cards, filtros
│   └── lib/                  # API client e tipos
├── docs/                     # Screenshots e assets
├── system_design.html        # Documentação de arquitetura e marca
└── README.md
```

**Fluxo principal / Main flow:**

```
Scrapers (dev.to · reddit · github)
      ↓
Deduplicação por URL (SQLite)
      ↓
Classificação Ollama (RELEVANTE / LIXO)
      ↓
Persistência → API REST → Dashboard Next.js
```

---

## 🔄 Backfill (Obsidian + legado)

Endpoints para sincronizar estado antigo com o pipeline atual:

| Endpoint | Descrição |
|----------|-----------|
| `GET /api/backfill/status` | Contadores pendentes (Obsidian + re-enrich) |
| `POST /api/backfill/obsidian` | Marca `obsidian_exported_at` para notas já no vault |
| `POST /api/backfill/obsidian/mocs` | Cria/atualiza MOCs no vault |
| `POST /api/backfill/obsidian/digest` | Gera digest semanal no vault |
| `POST /api/backfill/re-enrich?limit=10` | Reprocessa itens legados (tradutor → hype) |

No dashboard, use o painel **Sistema** para executar essas operações com progresso SSE — sem PowerShell.

**PowerShell** (não use `curl -X`; use `Invoke-RestMethod`):

```powershell
# Status
Invoke-RestMethod -Uri "http://localhost:8000/api/backfill/status"

# Re-enriquecer até remaining = 0 (~15–25 min com lotes de 10, paralelo)
do {
  $r = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/backfill/re-enrich?limit=10"
  $r | Format-List
} while ($r.remaining -gt 0)
```

Itens legados são detectados quando `ai_reasoning` não contém `Novidade` e `Utilidade`. O backfill Obsidian roda no startup do backend; para vault local, defina `OBSIDIAN_VAULT_PATH` no `backend/.env`.

---

## 🧪 Testes / Tests

```bash
cd backend
.\.venv\Scripts\activate   # Windows

# Run pytest suite
pytest

# With verbose output
pytest -v
```

> **80+ cenários** cobrindo health, CRUD, filtros, Obsidian, ingest e agentes.

---

## 🗺 Roadmap

- [x] Core backend — SQLite + SQLAlchemy + `NewsItem` model
- [x] REST API FastAPI with CORS
- [x] Ingestion pipeline + Ollama classification
- [x] Next.js slate-dark dashboard
- [x] Pytest suite + GitHub Actions CI
- [x] Demo seed endpoint (`POST /api/seed`) + botão **Dados demo**
- [x] Painel Sistema (backfill Obsidian/re-enrich com SSE)
- [x] Filtros hype mínimo e status Obsidian
- [x] Drawer de detalhe + triagem rápida + digest semanal
- [ ] Screenshots in README (`docs/screenshot.png`)
- [ ] Production deploy (Fly.io / Vercel + VPS)

---

## 👤 Autor / Author

<div align="center">

**Leandro Simões**

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=flat-square&logo=linkedin&logoColor=white)](https://linkedin.com/in/leandro-sim%C3%B5es-7a0b3537b)
[![GitHub](https://img.shields.io/badge/GitHub-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/simoesleandro)
[![Portfolio](https://img.shields.io/badge/Portfolio-06b6d4?style=flat-square&logo=safari&logoColor=white)](https://simoesleandro.github.io/portfolio)

*Fullstack · IA Aplicada · Civic Tech*

</div>

---

<div align="center">

Feito com ☕ e IA em / Made with ☕ and AI in 🇧🇷 Rio de Janeiro

</div>
