# Plan 012: Hype Score para Fontes RSS — Sinais de Frequência

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**:
> ```
> git diff --stat 61a5610..HEAD -- backend/app/services/hype.py backend/app/services/scrapers/rss.py backend/app/services/scrapers/base.py
> ```
> Se qualquer arquivo mudou, compare antes de prosseguir.

## Status

- **Priority**: P3
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: perf, ux
- **Planned at**: commit `61a5610`, 2026-06-20

## Why this matters

Artigos de RSS recebem hype_score=2 fixo, independente do conteúdo:

```python
# backend/app/services/hype.py:17
else:  # RSS feeds
    raw = 2.0
```

Blogs técnicos de alta qualidade (Cloudflare Blog, Oxide Computer, Martin Fowler, High Scalability) não têm upvotes ou reactions — mas o conteúdo pode ser o mais denso e relevante da semana. O score 2/5 fixo coloca esses artigos na mesma posição que qualquer RSS obscuro.

**O que este plano faz**: usar sinais que já existem nos feeds RSS para diferenciar o score:
- **`pub_date` do item**: artigo publicado há menos de 24h recebe bônus (é fresco)
- **Presença de `content_length`**: artigos longos têm mais substância (já existe como proxy de qualidade em vários sistemas)
- **Flag `is_featured`**: feeds que marcam artigos como featured/sticky

Para implementar isso, é preciso adicionar campos ao `RawArticle` e ao scraper RSS.

## Current state

### `backend/app/services/scrapers/base.py` — `RawArticle` atual

```python
@dataclass(frozen=True)
class RawArticle:
    title: str
    url: str
    source: str
    description_snippet: str = ""
    positive_reactions: int = 0
    comments_count: int = 0
    stars: int = 0
    ups: int = 0
```

Sem campos de RSS — `positive_reactions`, `comments_count`, `stars`, `ups` são sempre 0 para RSS.

### `backend/app/services/hype.py` — fórmula atual

```python
import math

from app.services.scrapers.base import RawArticle


def compute_hype_score(article: RawArticle) -> int:
    if article.source == "dev.to":
        raw = article.positive_reactions * 0.12 + article.comments_count * 0.2
    elif article.source == "github_trends":
        raw = math.log10(max(article.stars, 0) + 1) * 1.75
    elif article.source == "reddit":
        raw = math.log10(max(article.ups, 0) + 1) * 2.1
    elif article.source == "hacker_news":
        raw = math.log10(max(article.ups, 0) + 1) * 2.3 + article.comments_count * 0.05
    else:
        raw = 2.0  # ← RSS sempre 2

    return min(5, max(0, round(raw)))
```

### `backend/app/services/scrapers/rss.py`

Lê os campos do feed RSS. Para ver o que é disponível atualmente:

```
grep -n "entry\|pub_date\|published\|content\|summary" backend/app/services/scrapers/rss.py | head -30
```

Executar antes de escrever o plano — a presença de `pub_date` no feed RSS varia por fonte.

### `backend/app/services/scrapers/__init__.py`

Exporta `fetch_rss_feeds`. Para ver a assinatura:

```
grep -n "def fetch_rss_feeds" backend/app/services/scrapers/rss.py
```

## Scope

**In scope**:
- `backend/app/services/scrapers/base.py` — adicionar campos `pub_date: datetime | None` e `content_length: int` ao `RawArticle`
- `backend/app/services/scrapers/rss.py` — preencher os novos campos a partir dos dados do feed
- `backend/app/services/hype.py` — usar os novos campos para calcular score RSS

**Out of scope** (não tocar):
- Scrapers de dev.to, reddit, github_trends, hacker_news — sem mudanças
- `backend/app/models.py` — sem novas colunas (pub_date e content_length são usados apenas para o cálculo de hype, não persistidos separadamente)
- Frontend — zero mudanças

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Ver campos do scraper RSS | `grep -n "entry\|pub_date\|published\|content\|summary\|description" backend/app/services/scrapers/rss.py` | lista de matches |
| Run tests | `cd backend && pytest -q` | all pass |
| Import check | `cd backend && python -c "from app.services.hype import compute_hype_score; from app.services.scrapers.base import RawArticle; print('ok')"` | ok |

## Steps

### Step 0: Ler o scraper RSS antes de modificar

```
cat backend/app/services/scrapers/rss.py
```

Anotar: qual campo de data o scraper usa (entry.published, entry.updated, ou pub_date), e qual campo de conteúdo (entry.summary, entry.content, ou entry.description). Os Steps abaixo assumem feedparser-style — ajuste se o scraper usar outra abordagem.

### Step 1: Adicionar campos ao `RawArticle`

Em `backend/app/services/scrapers/base.py`, modificar o dataclass:

```python
from datetime import datetime


@dataclass(frozen=True)
class RawArticle:
    title: str
    url: str
    source: str
    description_snippet: str = ""
    positive_reactions: int = 0
    comments_count: int = 0
    stars: int = 0
    ups: int = 0
    pub_date: datetime | None = None    # ← data de publicação original do feed
    content_length: int = 0             # ← tamanho do conteúdo em caracteres
```

Os novos campos têm default — isso garante que todos os scrapers existentes (dev.to, reddit, etc.) continuam funcionando sem modificação.

**Verify**: `cd backend && python -c "
from app.services.scrapers.base import RawArticle
from datetime import datetime, timezone
a = RawArticle(title='t', url='u', source='s')
print(a.pub_date, a.content_length)
"` → `None 0`

**Verify**: `cd backend && python -c "from app.services.scrapers import fetch_devto, fetch_reddit, fetch_hacker_news, fetch_github_trends; print('ok')"` → `ok` (scrapers existentes ainda importam)

### Step 2: Preencher os novos campos no scraper RSS

Em `backend/app/services/scrapers/rss.py`, onde o `RawArticle` é criado para artigos RSS, adicionar `pub_date` e `content_length`.

**Leia o arquivo primeiro** (Step 0) para identificar a linha exata. O padrão geral é:

```python
# Localizar onde RawArticle é instanciado no scraper RSS
# Exemplo hipotético — adaptar ao código real:
article = RawArticle(
    title=entry.title,
    url=entry.link,
    source=f"rss/{feed_slug}",
    description_snippet=snippet,
    # ADICIONAR:
    pub_date=_parse_pub_date(entry),
    content_length=len(entry.get("summary", "") or ""),
)
```

Adicionar a função helper `_parse_pub_date` antes do uso:

```python
from datetime import datetime, timezone
import time


def _parse_pub_date(entry) -> "datetime | None":
    """Extrai pub_date de um entry de feedparser. Retorna None se ausente."""
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val is not None:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None
```

**Verify após modificar**: `cd backend && python -c "from app.services.scrapers.rss import fetch_rss_feeds; print('import ok')"` → `import ok`

### Step 3: Atualizar a fórmula de hype para RSS

Em `backend/app/services/hype.py`, substituir o bloco `else: raw = 2.0`:

```python
import math
from datetime import datetime, timezone

from app.services.scrapers.base import RawArticle


def compute_hype_score(article: RawArticle) -> int:
    if article.source == "dev.to":
        raw = article.positive_reactions * 0.12 + article.comments_count * 0.2
    elif article.source == "github_trends":
        raw = math.log10(max(article.stars, 0) + 1) * 1.75
    elif article.source == "reddit":
        raw = math.log10(max(article.ups, 0) + 1) * 2.1
    elif article.source == "hacker_news":
        raw = math.log10(max(article.ups, 0) + 1) * 2.3 + article.comments_count * 0.05
    else:
        # RSS feeds — sem engagement social; usa sinais de qualidade do feed
        raw = _rss_hype(article)

    return min(5, max(0, round(raw)))


def _rss_hype(article: RawArticle) -> float:
    """Calcula hype para fontes RSS usando sinais de qualidade.

    Base: 2.0 (mantém backward compat para feeds sem metadados)
    Bônus de frescor: +0.5 se publicado há menos de 24h
    Bônus de substância: +0.5 se content_length > 2000 chars (artigo longo)
    Bônus de substância maior: +1.0 se content_length > 5000 chars (artigo denso)
    Máximo efetivo: 3.5 antes do cap de 5
    """
    score = 2.0

    # Bônus de frescor
    if article.pub_date is not None:
        age_hours = (datetime.now(timezone.utc) - article.pub_date).total_seconds() / 3600
        if 0 <= age_hours < 24:
            score += 0.5
        elif age_hours < 0:
            # pub_date no futuro — ignorar (dado inválido)
            pass

    # Bônus de substância (tamanho do conteúdo como proxy de profundidade)
    if article.content_length >= 5000:
        score += 1.0
    elif article.content_length >= 2000:
        score += 0.5

    return score
```

**Verify**: `cd backend && python -c "
from app.services.hype import compute_hype_score
from app.services.scrapers.base import RawArticle
from datetime import datetime, timezone

# Artigo RSS sem metadados — deve ser 2 (backward compat)
a1 = RawArticle(title='t', url='u', source='rss/test')
print('sem metadados:', compute_hype_score(a1))  # esperado: 2

# Artigo RSS fresco e longo — deve ser 3 ou 4
from datetime import timedelta
a2 = RawArticle(title='t', url='u', source='rss/test',
                pub_date=datetime.now(timezone.utc) - timedelta(hours=2),
                content_length=6000)
print('fresco e longo:', compute_hype_score(a2))  # esperado: 4
"` → `sem metadados: 2` e `fresco e longo: 4`

### Step 4: Rodar testes

**Verify**: `cd backend && pytest -q` → all pass

## Test plan

Adicionar `backend/tests/test_hype_rss.py`:

```python
"""Testes para o hype score de fontes RSS."""
import pytest
from datetime import datetime, timezone, timedelta

from app.services.hype import compute_hype_score, _rss_hype
from app.services.scrapers.base import RawArticle


def _rss_article(**kwargs) -> RawArticle:
    defaults = {"title": "t", "url": "u", "source": "rss/test"}
    defaults.update(kwargs)
    return RawArticle(**defaults)


def test_rss_without_metadata_returns_2():
    """Backward compat: RSS sem pub_date ou content_length → score 2."""
    article = _rss_article()
    assert compute_hype_score(article) == 2


def test_rss_fresh_article_gets_bonus():
    """Artigo publicado há menos de 24h recebe bônus."""
    article = _rss_article(pub_date=datetime.now(timezone.utc) - timedelta(hours=6))
    score = compute_hype_score(article)
    assert score > 2


def test_rss_old_article_no_freshness_bonus():
    """Artigo de mais de 24h não recebe bônus de frescor."""
    old_pub = datetime.now(timezone.utc) - timedelta(days=5)
    article = _rss_article(pub_date=old_pub)
    score = compute_hype_score(article)
    assert score == 2


def test_rss_long_article_gets_bonus():
    """Artigo longo (>2000 chars) recebe bônus de substância."""
    article = _rss_article(content_length=3000)
    score = compute_hype_score(article)
    assert score > 2


def test_rss_very_long_article_gets_bigger_bonus():
    """Artigo muito longo (>5000 chars) recebe bônus maior."""
    article = _rss_article(content_length=6000)
    long_score = compute_hype_score(article)
    medium_article = _rss_article(content_length=3000)
    medium_score = compute_hype_score(medium_article)
    assert long_score > medium_score


def test_rss_fresh_and_long_caps_at_5():
    """Score não ultrapassa 5 mesmo com todos os bônus."""
    article = _rss_article(
        pub_date=datetime.now(timezone.utc) - timedelta(hours=1),
        content_length=10000,
    )
    assert compute_hype_score(article) <= 5


def test_non_rss_sources_unchanged():
    """Fórmulas de dev.to, reddit, etc. não mudam."""
    hn = RawArticle(title="t", url="u", source="hacker_news", ups=100)
    score = compute_hype_score(hn)
    assert score > 0
```

**Verify**: `cd backend && pytest tests/test_hype_rss.py -v` → todos passam

## Done criteria

- [ ] `grep -n "pub_date\|content_length" backend/app/services/scrapers/base.py` → 2+ matches
- [ ] `grep -n "_rss_hype" backend/app/services/hype.py` → 2+ matches (definição + chamada)
- [ ] `grep -n "raw = 2.0" backend/app/services/hype.py` → 0 matches (removido)
- [ ] `cd backend && pytest -q` → all pass
- [ ] `cd backend && pytest tests/test_hype_rss.py -v` → all pass
- [ ] `cd backend && python -c "from app.services.scrapers.base import RawArticle; a = RawArticle(title='t', url='u', source='s'); print(a.pub_date)"` → `None`

## STOP conditions

Pare e reporte se:
- O scraper RSS não usar feedparser-style e os campos `published_parsed`/`updated_parsed` não existirem — leia o arquivo completo (Step 0) e ajuste `_parse_pub_date` para o formato real.
- `pub_date` retornar `datetime` sem timezone (naive) — o cálculo de `age_hours` falhará. Use `.replace(tzinfo=timezone.utc)` na conversão.
- Testes de ingest (`test_ingest.py`) falharem — os scrapers de outros sources (dev.to, reddit) criavam RawArticle sem os novos campos; como os campos têm default, não deveria quebrar. Se quebrar, os novos campos não têm default — verifique o dataclass.

## Maintenance notes

- **Backward compat garantida**: os campos `pub_date` e `content_length` têm defaults (`None` e `0`). Todos os scrapers que não são RSS continuam funcionando sem mudanças.
- **Calibração dos thresholds**: `24h` para frescor e `2000/5000` para substância são estimativas iniciais. Ajuste baseado no feedback de uso real — se artigos RSS ainda parecem subvalorizados, aumente os bônus.
- **`content_length` vs `description_snippet`**: o scraper RSS pode não ter o conteúdo completo (alguns feeds só enviam summary). `content_length` reflete o que está disponível no feed — não o artigo completo.
