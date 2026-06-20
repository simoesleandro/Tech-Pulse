# Plan 001: Corrigir Três Vulnerabilidades de Segurança de Alto Impacto / Baixo Esforço

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**:
> ```
> git diff --stat b15548f..HEAD -- backend/app/deps/auth.py backend/app/main.py backend/app/services/scrapers/rss.py
> ```
> If any of these files changed since this plan was written, compare the
> "Current state" excerpts against live code before proceeding; on a mismatch,
> treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: security
- **Planned at**: commit `b15548f`, 2026-06-20

## Why this matters

Três problemas de segurança independentes, cada um trivial de corrigir, mas com impacto concreto em produção:

1. **Auth bypass silencioso**: quando `TECHPULSE_API_KEY` não está configurada, todos os endpoints de mutação (ingest, delete, seed, obsidian export) ficam abertos sem autenticação. Em produção isso é um vetor direto de abuso.
2. **CORS excessivamente permissivo**: `allow_credentials=True` combinado com `allow_methods=["*"]` e `allow_headers=["*"]` permite que qualquer origin listada em `CORS_ORIGINS` faça cross-origin mutations com credenciais.
3. **RSS parser sem defusedxml**: `xml.etree.ElementTree` não tem proteção contra todos os vetores de XXE/XML bomb em todas as versões de Python; `defusedxml` é a biblioteca padrão da indústria para parsing de XML não-confiável.

## Current state

### 1. Auth (`backend/app/deps/auth.py`)

```python
# auth.py:1-13 — estado atual
import os
from fastapi import Header, HTTPException

API_KEY = os.getenv("TECHPULSE_API_KEY", "").strip()

def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Exige X-API-Key quando TECHPULSE_API_KEY está configurada."""
    if not API_KEY:
        return          # ← silencioso: sem log, sem aviso, sem config explícita
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API key inválida ou ausente")
```

Rotas dependentes (sample): `POST /api/news`, `DELETE /api/news/{id}`, `PATCH /api/news/{id}/read`, `POST /api/ingest`, `POST /api/seed`, `POST /api/obsidian/export` — todas usam `dependencies=[Depends(require_api_key)]`.

### 2. CORS (`backend/app/main.py:22-28`)

```python
# main.py:22-28 — estado atual
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],      # ← wildcard: inclui DELETE, PATCH, PUT...
    allow_headers=["*"],      # ← wildcard: inclui Authorization, Cookie...
)
```

### 3. RSS parser (`backend/app/services/scrapers/rss.py:2,69`)

```python
# rss.py:2 — estado atual
import xml.etree.ElementTree as ET
# ...
# rss.py:69 — estado atual
root = ET.fromstring(response.content)   # ← sem defusedxml
```

### Convenções do projeto

- Python 3.11+, sem type-ignore comments. Imports organizados: stdlib → third-party → local.
- Log: `logger = logging.getLogger(__name__)` em cada módulo; mensagens em português ou inglês técnico.
- Ver `backend/app/services/scrapers/rss.py` para padrão de import e estrutura de módulo de scraper.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install defusedxml | `cd backend && pip install defusedxml` | exit 0 |
| Add to requirements | editar `backend/requirements.txt` | linha `defusedxml` presente |
| Run backend tests | `cd backend && pytest -q` | all pass (no new failures) |
| Check XML import | `python -c "import defusedxml.ElementTree as ET; print('ok')"` | prints `ok` |

## Scope

**In scope** (única arquivos a modificar):
- `backend/app/deps/auth.py`
- `backend/app/main.py`
- `backend/app/services/scrapers/rss.py`
- `backend/requirements.txt`

**Out of scope** (não tocar):
- `backend/app/config.py` — `cors_origins` já tem validação correta via env; não alterar o parsing.
- Qualquer rota ou handler — a autenticação é do lado do dep, não das rotas.
- `.env.example` — não alterar valores de exemplo; a mudança é comportamental, não de configuração.

## Git workflow

- Branch: `advisor/001-security-quick-wins`
- Commit por sub-tarefa (3 commits): `fix: warn on missing API key`, `fix: restrict CORS methods and headers`, `fix: use defusedxml for RSS XML parsing`
- Estilo do projeto (ver `git log --oneline`): `feat:`, `fix:`, `Add`, `Fix` — use `fix:`.
- Não fazer push nem abrir PR sem instrução do operador.

## Steps

### Step 1: Adicionar warning de startup quando API key está vazia

Em `backend/app/deps/auth.py`, adicionar log de warning no módulo level (executa na importação) para alertar quando a chave não está configurada.

**Estado alvo:**
```python
import logging
import os

from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)

API_KEY = os.getenv("TECHPULSE_API_KEY", "").strip()

if not API_KEY:
    logger.warning(
        "TECHPULSE_API_KEY não configurada — todos os endpoints de mutação estão SEM autenticação. "
        "Defina a variável de ambiente antes de expor a API publicamente."
    )


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Exige X-API-Key quando TECHPULSE_API_KEY está configurada."""
    if not API_KEY:
        return
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API key inválida ou ausente")
```

O comportamento de autenticação **não muda** — o warning é apenas informativo. Isso mantém compatibilidade com dev local (onde a key está vazia por design).

**Verify**: `cd backend && python -c "from app.deps.auth import require_api_key; print('ok')"` → prints `ok` (sem exception)

### Step 2: Restringir CORS a métodos e headers explícitos

Em `backend/app/main.py`, substituir wildcards por listas explícitas. A API usa apenas: GET, POST, PATCH, DELETE, OPTIONS. Headers necessários: `Content-Type`, `Authorization`, `X-API-Key`.

**Estado alvo:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)
```

**Verify**: `cd backend && python -c "from app.main import app; print('ok')"` → prints `ok`

**Verify**: `cd backend && pytest tests/test_api.py -q` → all pass

### Step 3: Adicionar `defusedxml` ao requirements.txt

No arquivo `backend/requirements.txt`, adicionar `defusedxml` na seção de dependências (após `python-dotenv`, antes de `pytest`):

```
defusedxml
```

**Verify**: `pip show defusedxml` → mostra versão instalada

### Step 4: Substituir `xml.etree.ElementTree` por `defusedxml` no RSS scraper

Em `backend/app/services/scrapers/rss.py`:

Linha 2 — substituir:
```python
import xml.etree.ElementTree as ET
```
Por:
```python
import defusedxml.ElementTree as ET
```

O resto do arquivo (`ET.fromstring`, `ET.Element`, `ET.ParseError`) continua funcionando identicamente — `defusedxml.ElementTree` é um drop-in replacement.

**Verify**: `cd backend && python -c "from app.services.scrapers.rss import parse_rss_feed; print('ok')"` → prints `ok`

### Step 5: Rodar a suite de testes completa

**Verify**: `cd backend && pytest -q` → all pass, 0 failures

## Test plan

Não é necessário criar novos testes para os 3 fixes (são todos comportamentais/configuração):

- **Step 1** (auth warning): o comportamento de autenticação não mudou. Teste existente `test_api.py` cobre cenários com e sem key. O warning ocorre em nível de log, não verificável por pytest sem captura de log.
- **Step 2** (CORS): o middleware CORS é testado pelo browser; os testes pytest atuais em `test_api.py` não testam CORS headers. Verificação manual: curl com `Origin` header.
- **Step 3+4** (defusedxml): `test_scrapers.py` cobre o parser RSS indiretamente. Confirme que passa sem changes.

Se quiser adicionar um teste para o parser RSS:
```python
# backend/tests/test_scrapers.py — adicionar ao final
def test_rss_parser_rejects_xml_bomb():
    """Garante que billion laughs não trava o parser."""
    xml_bomb = b"""<?xml version="1.0"?>
<!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;">]>
<rss><channel><item><title>&lol2;</title><link>http://x.com</link></item></channel></rss>"""
    import defusedxml.ElementTree as ET
    import pytest
    with pytest.raises(ET.DTDForbidden):
        ET.fromstring(xml_bomb)
```

**Verify**: `cd backend && pytest tests/test_scrapers.py -v` → all pass

## Done criteria

- [ ] `cd backend && pytest -q` exits 0, 0 failures
- [ ] `grep -n "allow_methods=\[.\"\*.\"\]" backend/app/main.py` → sem matches
- [ ] `grep -n "allow_headers=\[.\"\*.\"\]" backend/app/main.py` → sem matches
- [ ] `grep -n "import xml.etree.ElementTree" backend/app/services/scrapers/rss.py` → sem matches
- [ ] `grep -n "defusedxml" backend/app/services/scrapers/rss.py` → 1 match (o import)
- [ ] `grep -n "defusedxml" backend/requirements.txt` → 1 match
- [ ] `grep -n "logger.warning" backend/app/deps/auth.py` → 1 match
- [ ] Nenhum arquivo fora da lista **In scope** foi modificado (`git diff --name-only`)
- [ ] `plans/README.md` status row atualizada para DONE

## STOP conditions

Pare e reporte se:
- O código em `auth.py`, `main.py` ou `rss.py` não bater com os excerpts de "Current state" (drift).
- `pytest -q` falhar em testes existentes após qualquer step (antes de cada fix, confirme que os testes já passam).
- `defusedxml.ElementTree` não for um drop-in replacement (se `ET.ParseError` não existir no módulo, reporte; não tente workaround).
- Qualquer step exigir tocar em arquivo fora do scope.

## Maintenance notes

- **CORS future**: se novos endpoints precisarem de métodos HTTP adicionais (ex: PUT, HEAD), atualizar `allow_methods` em `main.py:25`.
- **Auth future**: se autenticação obrigatória for necessária em produção, o ponto de mudança é `deps/auth.py:10` — remova o `if not API_KEY: return` e adicione validação explícita de config.
- **defusedxml version**: pin a versão em `requirements.txt` antes de deploy em produção (`defusedxml>=0.7.1`).
- Deferred: rate limiting em endpoints — ver plan `005` quando escrito; não faz parte deste plano.
