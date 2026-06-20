# Plan 005: Corrigir Complexidade O(n²) na Deduplicação Semântica de Títulos

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**:
> ```
> git diff --stat b15548f..HEAD -- backend/app/services/ingest.py backend/tests/test_ingest.py
> ```
> Se qualquer arquivo mudou, compare os excerpts de "Current state" contra o código live antes de prosseguir.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: perf, tests
- **Planned at**: commit `b15548f`, 2026-06-20

## Why this matters

O algoritmo de deduplicação semântica compara cada novo artigo contra todos os títulos existentes dos últimos 45 dias usando similaridade bigrama. A implementação atual é O(n × m), onde n é o número de artigos novos e m é o número de títulos existentes. Para um ingest típico com 50 artigos novos × 3000 títulos existentes, isso é 150.000 comparações bigrama, cada uma recalculando os bigramas do título existente a cada chamada. Além disso, a lista `seen_titles` cresce durante o ingest e comparações contra ela adicionam mais O(k²) onde k é o tamanho do batch atual. O fix é pré-computar os bigramas dos títulos existentes em um set imutável e reutilizá-los — reduz a complexidade de O(n×m×|bigrams|) para O(n×m) com lookup O(1).

## Current state

### Funções de dedup (`backend/app/services/ingest.py:64-75, 619-636`)

```python
# ingest.py:64-75 — funções de bigram
def _title_bigrams(title: str) -> frozenset[str]:
    words = re.sub(r"[^\w\s]", "", title.lower()).split()
    return frozenset(f"{a}_{b}" for a, b in zip(words, words[1:]))


def _titles_are_similar(a: str, b: str, threshold: float = 0.65) -> bool:
    bg_a = _title_bigrams(a)
    bg_b = _title_bigrams(b)
    if not bg_a or not bg_b:
        return False
    union = len(bg_a | bg_b)
    return union > 0 and len(bg_a & bg_b) / union >= threshold
```

```python
# ingest.py:619-636 — uso no run_ingest() — estado atual
    _sem_cutoff = datetime.now(timezone.utc) - timedelta(days=45)
    existing_titles = list(
        db.scalars(
            select(NewsItem.title_original)
            .where(NewsItem.title_original != "")
            .where(NewsItem.created_at >= _sem_cutoff)
        ).all()
    )
    seen_titles: list[str] = list(existing_titles)   # ← list cresce durante o loop
    title_rejected = 0
    pending: list[RawArticle] = []
    for article in url_deduped:
        if any(_titles_are_similar(article.title, t) for t in seen_titles):  # ← O(m) por artigo, bigrams recalculados
            title_rejected += 1
        else:
            pending.append(article)
            seen_titles.append(article.title)   # ← acrescenta ao set para dedup intra-batch
```

### Problema de performance

Em cada chamada de `_titles_are_similar(a, b)`:
- `_title_bigrams(a)` é chamado (título do artigo novo) — repetido para cada `t` em `seen_titles`
- `_title_bigrams(b)` é chamado (cada título existente) — recalculado toda vez

Com 50 artigos novos × 3000 existentes: `_title_bigrams()` é chamado ~150.000 vezes (3000 para cada artigo novo), sendo 2999 chamadas repetidas por artigo.

### Convenções

- `frozenset` já é o tipo de retorno de `_title_bigrams()` — manter.
- `re.sub(r"[^\w\s]", "", title.lower()).split()` é o tokenizer — não alterar.
- Threshold padrão 0.65 — não alterar.
- `_titles_are_similar()` é pública e usada em testes — manter a assinatura.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Run all tests | `cd backend && pytest -q` | all pass |
| Run ingest tests | `cd backend && pytest tests/test_ingest.py -v` | all pass |
| Run new dedup tests | `cd backend && pytest tests/test_semantic_dedup.py -v` | all pass |
| Check import | `cd backend && python -c "from app.services.ingest import _title_bigrams, _titles_are_similar; print('ok')"` | ok |

## Scope

**In scope**:
- `backend/app/services/ingest.py` — somente as funções `_title_bigrams`, `_titles_are_similar` e o bloco de semantic dedup dentro de `run_ingest()` (linhas 619-636)
- `backend/tests/test_semantic_dedup.py` — criar novo arquivo de testes

**Out of scope** (não tocar):
- `_quick_reject()` — função diferente de pré-filtro por regex; não relacionada
- `_load_existing_urls()` — dedup por URL; escopo separado
- A lógica de `url_deduped` (linhas 609-617) — não alterar
- Qualquer outro caller de `_titles_are_similar()` se existir — verificar com `grep -rn "_titles_are_similar" backend/` antes de iniciar

## Git workflow

- Branch: `advisor/005-semantic-dedup-on2-fix`
- 2 commits: `tests: add unit tests for semantic dedup`, `perf: precompute bigrams for O(n) semantic dedup`
- **IMPORTANTE**: escrever os testes ANTES do fix (step 1 antes do step 2) para confirmar que o comportamento não muda.

## Steps

### Step 0: Verificar callers de `_titles_are_similar`

Antes de qualquer mudança, confirme que `_titles_are_similar` só é usada dentro de `ingest.py`:

```
grep -rn "_titles_are_similar" backend/
```

Resultado esperado: somente `backend/app/services/ingest.py` (2 matches: definição + uso). Se aparecer em outros arquivos, reporte antes de prosseguir.

### Step 1: Criar testes unitários para as funções de dedup (ANTES do fix)

Criar `backend/tests/test_semantic_dedup.py`. Esses testes documentam o comportamento atual e protegem contra regressão:

```python
# backend/tests/test_semantic_dedup.py
"""Testes unitários para deduplicação semântica de títulos (bigram similarity)."""
import pytest
from app.services.ingest import _title_bigrams, _titles_are_similar


class TestTitleBigrams:
    def test_basic_bigrams(self):
        bg = _title_bigrams("python async patterns")
        assert "python_async" in bg
        assert "async_patterns" in bg

    def test_punctuation_stripped(self):
        bg = _title_bigrams("Python: async patterns!")
        assert "python_async" in bg

    def test_case_insensitive(self):
        bg_lower = _title_bigrams("python async")
        bg_upper = _title_bigrams("PYTHON ASYNC")
        assert bg_lower == bg_upper

    def test_empty_title_returns_empty(self):
        assert _title_bigrams("") == frozenset()

    def test_single_word_returns_empty(self):
        assert _title_bigrams("python") == frozenset()

    def test_returns_frozenset(self):
        assert isinstance(_title_bigrams("hello world"), frozenset)


class TestTitlesSimilar:
    def test_identical_titles_are_similar(self):
        assert _titles_are_similar("Python async guide", "Python async guide")

    def test_clearly_different_titles(self):
        assert not _titles_are_similar(
            "Python async guide",
            "Kubernetes deployment best practices",
        )

    def test_similar_titles_above_threshold(self):
        # Títulos quase idênticos com reordenação leve
        assert _titles_are_similar(
            "Python 3.11 Async Patterns",
            "Python Async Patterns 3.11",
        )

    def test_empty_title_not_similar(self):
        assert not _titles_are_similar("", "Python async")
        assert not _titles_are_similar("Python async", "")

    def test_threshold_boundary(self):
        # Títulos com ~50% overlap não devem ser similares (threshold=0.65)
        assert not _titles_are_similar(
            "Python async programming guide",
            "JavaScript frontend development guide",
        )

    def test_custom_threshold(self):
        # Com threshold baixo, qualquer overlap é suficiente
        assert _titles_are_similar(
            "Python guide",
            "Python reference",
            threshold=0.1,
        )


class TestSemanticDedupIntegration:
    """Testa que o comportamento de dedup no run_ingest não muda após o fix."""

    def test_precomputed_bigrams_same_result(self):
        """Verifica que pré-computar bigrams não muda o resultado de similaridade."""
        titles = [
            "Python async guide",
            "How to use FastAPI correctly",
            "Kubernetes deployment tutorial",
        ]
        new_title = "Python Async Guide"  # similar ao primeiro

        # Resultado via _titles_are_similar (baseline)
        similar_via_function = any(
            _titles_are_similar(new_title, t) for t in titles
        )

        # Resultado via bigrams pré-computados (como será após o fix)
        precomputed = [_title_bigrams(t) for t in titles]
        new_bg = _title_bigrams(new_title)
        similar_via_precomputed = any(
            (
                (len(new_bg & bg) / len(new_bg | bg)) >= 0.65
                if new_bg and bg
                else False
            )
            for bg in precomputed
        )

        assert similar_via_function == similar_via_precomputed
```

**Verify**: `cd backend && pytest tests/test_semantic_dedup.py -v` → todos os testes passam (antes do fix)

### Step 2: Adicionar função auxiliar `_is_similar_to_any` com bigrams pré-computados

Em `backend/app/services/ingest.py`, adicionar uma nova função após `_titles_are_similar` (linha ~75):

```python
def _is_similar_to_any(
    title: str,
    precomputed: list[frozenset[str]],
    threshold: float = 0.65,
) -> bool:
    """Verifica se `title` é similar a qualquer bigram set em `precomputed`.

    Mais eficiente que chamar _titles_are_similar() em loop porque os bigrams
    dos títulos existentes são computados apenas uma vez fora do loop.
    """
    bg = _title_bigrams(title)
    if not bg:
        return False
    for existing_bg in precomputed:
        if not existing_bg:
            continue
        union = len(bg | existing_bg)
        if union > 0 and len(bg & existing_bg) / union >= threshold:
            return True
    return False
```

**Verify**: `cd backend && python -c "from app.services.ingest import _is_similar_to_any, _title_bigrams; bg = [_title_bigrams('python async')]; print(_is_similar_to_any('Python Async', bg))"` → `True`

### Step 3: Refatorar o bloco de semantic dedup em `run_ingest()`

Em `backend/app/services/ingest.py`, substituir as linhas 619-636 (o bloco `existing_titles` → `pending`) pelo seguinte:

```python
    # Semantic dedup: drop articles whose title is very similar to one already in DB
    # Limit to last 45 days to keep the bigram comparison set bounded
    _sem_cutoff = datetime.now(timezone.utc) - timedelta(days=45)
    existing_titles = list(
        db.scalars(
            select(NewsItem.title_original)
            .where(NewsItem.title_original != "")
            .where(NewsItem.created_at >= _sem_cutoff)
        ).all()
    )
    # Pré-computa bigrams dos títulos existentes UMA VEZ (O(m))
    seen_bigrams: list[frozenset[str]] = [_title_bigrams(t) for t in existing_titles]
    title_rejected = 0
    pending: list[RawArticle] = []
    for article in url_deduped:
        if _is_similar_to_any(article.title, seen_bigrams):
            title_rejected += 1
        else:
            pending.append(article)
            seen_bigrams.append(_title_bigrams(article.title))  # adiciona ao set para dedup intra-batch
```

**Diferenças vs. estado anterior:**
- `seen_titles: list[str]` substituída por `seen_bigrams: list[frozenset[str]]` — bigrams pré-computados
- `any(_titles_are_similar(...) for t in seen_titles)` substituído por `_is_similar_to_any(article.title, seen_bigrams)` — sem recompute
- `seen_titles.append(article.title)` substituído por `seen_bigrams.append(_title_bigrams(article.title))` — armazena bigrams, não string

**Verify**: `cd backend && python -c "from app.services.ingest import run_ingest; print('import ok')"` → `import ok`

### Step 4: Rodar todos os testes

**Verify**: `cd backend && pytest tests/test_semantic_dedup.py tests/test_ingest.py -v` → all pass

**Verify**: `cd backend && pytest -q` → all pass, 0 failures

## Test plan

Os testes criados no Step 1 (`test_semantic_dedup.py`) cobrem:
- `_title_bigrams()`: normalização, pontuação, case-insensitivity, edge cases (vazio, uma palavra)
- `_titles_are_similar()`: casos positivos, negativos, boundary, threshold customizado
- Integração: prova que bigrams pré-computados produzem o mesmo resultado que a função original

**Verify**: `cd backend && pytest tests/test_semantic_dedup.py -v --tb=short` → 11 tests pass

## Done criteria

- [ ] `cd backend && pytest -q` exits 0
- [ ] `grep -n "_is_similar_to_any" backend/app/services/ingest.py` → 2 matches (definição + uso)
- [ ] `grep -n "seen_titles" backend/app/services/ingest.py` → 0 matches (variável antiga removida)
- [ ] `grep -n "seen_bigrams" backend/app/services/ingest.py` → 3+ matches
- [ ] `backend/tests/test_semantic_dedup.py` existe com ≥ 11 testes
- [ ] `cd backend && pytest tests/test_semantic_dedup.py -v` → all pass
- [ ] `cd backend && pytest tests/test_ingest.py -v` → all pass
- [ ] Nenhum arquivo fora da lista **In scope** foi modificado
- [ ] `plans/README.md` status row atualizada para DONE

## STOP conditions

Pare e reporte se:
- `grep -rn "_titles_are_similar" backend/` retornar matches fora de `ingest.py` — a função pode ter callers não mapeados; ajuste o scope antes de continuar.
- Qualquer teste em `test_semantic_dedup.py` falhar antes do fix (Step 1) — isso indica que a implementação atual não se comporta como esperado; reporte as discrepâncias.
- Qualquer teste em `test_ingest.py` falhar após o Step 3 — a refatoração não deve alterar comportamento.
- O threshold 0.65 precisar ser alterado para que os testes passem — o threshold é uma constante de domínio que não deve mudar neste plano.

## Maintenance notes

- **Escala futura**: com 100k+ artigos nos últimos 45 dias, `seen_bigrams` ainda crescerá para O(100k) entries. Nesse ponto, considerar substituir por um índice invertido (dict de bigram → set of title indices) para lookup O(1) por bigram. Não implementar agora — não é necessário no volume atual.
- **`_titles_are_similar()` pública**: continua disponível para uso direto em testes e outros callers. Não remover — apenas parou de ser chamada no loop principal.
- **Threshold 0.65**: ajustar requer re-calibração manual. Se usuários reportarem duplicatas passando ou artigos únicos sendo rejeitados, esse é o parâmetro a revisar.
- **`_is_similar_to_any()` deve ser testada isoladamente**: se a lógica de similaridade for alterada no futuro, `test_semantic_dedup.py::TestSemanticDedupIntegration::test_precomputed_bigrams_same_result` detectará divergência.
