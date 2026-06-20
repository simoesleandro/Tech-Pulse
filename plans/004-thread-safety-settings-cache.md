# Plan 004: Corrigir Thread-Safety do Cache de Feedback e Cache de Settings

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**:
> ```
> git diff --stat b15548f..HEAD -- backend/app/services/ai_agent.py backend/app/services/settings.py
> ```
> Se qualquer arquivo mudou, compare os excerpts antes de prosseguir.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug, perf
- **Planned at**: commit `b15548f`, 2026-06-20

## Why this matters

**Problema 1 — thread-unsafe feedback cache**: `_feedback_examples` é uma lista module-level em `ai_agent.py` atualizada por `update_feedback_cache()` a partir de rotas FastAPI. Sem lock, dois requests concorrentes podem corromper a lista durante iteração (in `_format_feedback_shots()`) ou causar lost updates. O resultado são exemplos de few-shot inconsistentes ou parcialmente corrompidos sendo injetados nos prompts do LLM — comportamento silencioso e difícil de depurar.

**Problema 2 — settings relido do disco por chamada**: `load_settings()` abre e parseia um arquivo JSON em cada chamada. Essa função é chamada em hot paths: na lifespan, no background ingest loop, e dentro de `run_ingest()` e `orquestrador_enriquecimento()` (a cada artigo enriquecido). File I/O repetitiva em loop de ingest é desnecessária — as settings mudam raramente e apenas via chamada explícita ao endpoint `POST /api/settings`.

## Current state

### Problema 1: `_feedback_examples` sem lock (`backend/app/services/ai_agent.py:406-422`)

```python
# ai_agent.py:406-422 — estado atual
AgentProgressCallback = Callable[[str, str, str | None], None]  # definição duplicada (linha 312 também)

_feedback_examples: list[dict] = []


def update_feedback_cache(examples: list[dict]) -> None:
    global _feedback_examples
    _feedback_examples = examples[-20:]   # ← assignment sem lock


def _format_feedback_shots() -> str:
    examples = _feedback_examples           # ← leitura sem lock
    if not examples:
        return ""
    lines = ["Calibração com feedback do usuário (priorize esses padrões):"]
    for ex in examples[-8:]:               # ← iteração sem lock
        lines.append(f"  [{ex['verdict']}] \"{ex['title'][:80]}\" (fonte: {ex['source']})")
    return "\n".join(lines) + "\n\n"
```

A duplicação de `AgentProgressCallback` (linha 312 e 404) também deve ser removida aqui.

### Problema 2: `load_settings()` sem cache (`backend/app/services/settings.py:33-43`)

```python
# settings.py:33-43 — estado atual
def load_settings() -> dict:
    if not SETTINGS_FILE.exists():
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:   # ← open() a cada chamada
            raw = json.load(f)
        merged = _merge_with_defaults(raw if isinstance(raw, dict) else {})
        return AppSettings.model_validate(merged).model_dump()
    except Exception:
        return AppSettings.model_validate(DEFAULT_SETTINGS).model_dump()
```

A função `save_settings()` (linhas 46-49) sobrescreve o arquivo quando settings mudam. Esse é o ponto correto para invalidar o cache.

### Onde `load_settings()` é chamada (contexto)

- `backend/app/lifespan.py:22,138` — startup e background loop
- `backend/app/services/ingest.py:586-588` — início de cada `run_ingest()`
- `backend/app/services/ai_agent.py:435-436` — dentro de `orquestrador_enriquecimento()` (a cada artigo)

### Convenções do projeto

- `threading.Lock` já é usado em `ingest.py:82-83` (`_cancel_event_lock`). Seguir o mesmo padrão.
- Module-level locks: definir como `_lock = threading.Lock()` no topo do módulo, após imports.
- O projeto usa `functools.lru_cache` em `config.py:45-47` — padrão válido para cache simples.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Run tests | `cd backend && pytest -q` | all pass |
| Test AI agent | `cd backend && pytest tests/test_ai_agent.py -v` | all pass |
| Test app config | `cd backend && pytest tests/test_app_config.py -v` | all pass |
| Test settings | `cd backend && pytest tests/test_settings_validation.py -v` | all pass |
| Import check | `cd backend && python -c "from app.services.ai_agent import update_feedback_cache, _format_feedback_shots; print('ok')"` | ok |

## Scope

**In scope**:
- `backend/app/services/ai_agent.py` — somente as funções `update_feedback_cache`, `_format_feedback_shots`, e a definição duplicada de `AgentProgressCallback`
- `backend/app/services/settings.py` — as funções `load_settings` e `save_settings`

**Out of scope** (não tocar):
- `backend/app/routes/news.py` — a chamada a `update_feedback_cache()` não muda de interface
- `backend/app/lifespan.py` — a chamada a `load_settings()` não muda de interface
- `backend/app/services/ingest.py` — as chamadas a `load_settings()` não mudam
- `backend/app/services/ai_agent.py` — somente os trechos mapeados; não tocar nos agentes (triador, tradutor, hype, unified)

## Git workflow

- Branch: `advisor/004-thread-safety-settings-cache`
- 2 commits: `fix: add threading lock to feedback examples cache`, `perf: cache settings in memory, invalidate on save`
- Não fazer push nem abrir PR sem instrução.

## Steps

### Step 1: Adicionar lock ao `_feedback_examples` e remover duplicata de type alias

Em `backend/app/services/ai_agent.py`:

**1a. Remover a segunda definição de `AgentProgressCallback`** (linha ~404). Manter apenas a primeira (linha 312, logo após `class HypeAssessment`). Verifique qual das duas está na linha 312 e qual na 404 — remova a segunda ocorrência. A assinatura é `Callable[[str, str, str | None], None]`.

**1b. Adicionar lock e modificar as funções de cache.** Logo após os imports no topo do arquivo (antes de qualquer definição de constante), adicionar:

```python
import threading
```

(Se `threading` já estiver importado em outro ponto do arquivo, não duplicar — apenas verificar.)

Substituir o bloco `_feedback_examples` e suas duas funções pelo seguinte:

```python
# Module-level cache of user feedback examples used for few-shot prompting.
_feedback_lock = threading.Lock()
_feedback_examples: list[dict] = []


def update_feedback_cache(examples: list[dict]) -> None:
    global _feedback_examples
    with _feedback_lock:
        _feedback_examples = list(examples[-20:])


def _format_feedback_shots() -> str:
    with _feedback_lock:
        examples = list(_feedback_examples)  # snapshot; release lock antes de iterar
    if not examples:
        return ""
    lines = ["Calibração com feedback do usuário (priorize esses padrões):"]
    for ex in examples[-8:]:
        lines.append(f"  [{ex['verdict']}] \"{ex['title'][:80]}\" (fonte: {ex['source']})")
    return "\n".join(lines) + "\n\n"
```

> O snapshot `list(_feedback_examples)` dentro do lock garante que a iteração ocorre fora do lock, evitando deadlock se `_format_feedback_shots` for chamada de um contexto que já segura o lock.

**Verify**: `cd backend && python -c "from app.services.ai_agent import update_feedback_cache, _format_feedback_shots; update_feedback_cache([{'title':'t','source':'s','verdict':'RELEVANTE'}]); print(_format_feedback_shots())"` → imprime o bloco de calibração

**Verify**: `grep -n "AgentProgressCallback" backend/app/services/ai_agent.py` → exatamente **1** match (não 2)

### Step 2: Adicionar cache in-memory ao `load_settings()`

Em `backend/app/services/settings.py`:

Adicionar cache module-level com invalidação por `save_settings()`:

```python
# settings.py — estado alvo completo
import json
import threading
from pathlib import Path

from app.schemas import AppSettings

SETTINGS_FILE = Path(__file__).resolve().parents[2] / "settings.json"

DEFAULT_SETTINGS: dict = AppSettings(
    background_ingest_enabled=False,
    obsidian_auto_export=False,
    pipeline_mode="unified",
    sources={
        "dev_to": True,
        "reddit": True,
        "github_trends": True,
        "hacker_news": True,
        "rss_feeds": True,
    },
).model_dump()

_settings_lock = threading.Lock()
_settings_cache: dict | None = None


def _merge_with_defaults(data: dict) -> dict:
    merged = {**DEFAULT_SETTINGS, **data}
    default_sources = DEFAULT_SETTINGS["sources"]
    sources = merged.get("sources")
    if isinstance(sources, dict):
        merged["sources"] = {**default_sources, **sources}
    else:
        merged["sources"] = default_sources
    return merged


def load_settings() -> dict:
    global _settings_cache
    with _settings_lock:
        if _settings_cache is not None:
            return dict(_settings_cache)  # retorna cópia; nunca expõe o cache mutável
    # Cache miss: ler do disco
    if not SETTINGS_FILE.exists():
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        merged = _merge_with_defaults(raw if isinstance(raw, dict) else {})
        result = AppSettings.model_validate(merged).model_dump()
    except Exception:
        result = AppSettings.model_validate(DEFAULT_SETTINGS).model_dump()
    with _settings_lock:
        _settings_cache = result
    return dict(result)


def save_settings(settings: dict) -> None:
    global _settings_cache
    validated = AppSettings.model_validate(_merge_with_defaults(settings)).model_dump()
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(validated, f, indent=2, ensure_ascii=False)
    with _settings_lock:
        _settings_cache = None  # invalida o cache; próxima chamada a load_settings() relê do disco
```

**Verify**: `cd backend && python -c "from app.services.settings import load_settings, save_settings; s1 = load_settings(); s2 = load_settings(); print('cache ok:', s1 == s2)"` → `cache ok: True`

**Verify**: `cd backend && python -c "
from app.services.settings import load_settings, save_settings, _settings_cache
import app.services.settings as m
load_settings()
print('populated:', m._settings_cache is not None)
save_settings(m._settings_cache or {})
print('invalidated:', m._settings_cache is None)
"` → ambas as linhas True/None

### Step 3: Rodar suite completa

**Verify**: `cd backend && pytest -q` → all pass, 0 failures

**Verify**: `cd backend && pytest tests/test_ai_agent.py tests/test_app_config.py tests/test_settings_validation.py -v` → all pass

## Test plan

Adicionar ao arquivo de testes de settings existente (`backend/tests/test_settings_validation.py`) ou criar `backend/tests/test_settings_cache.py`:

```python
# backend/tests/test_settings_cache.py
import app.services.settings as settings_module
from app.services.settings import load_settings, save_settings


def test_load_settings_returns_cached_result(tmp_path, monkeypatch):
    """Segunda chamada a load_settings() não lê o disco."""
    monkeypatch.setattr(settings_module, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings_module, "_settings_cache", None)

    open_calls = []
    original_open = open

    def tracking_open(path, *args, **kwargs):
        if str(path) == str(tmp_path / "settings.json"):
            open_calls.append(path)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", tracking_open)

    load_settings()  # primeira chamada — lê do disco (ou cria arquivo)
    initial_calls = len(open_calls)
    load_settings()  # segunda chamada — deve usar cache
    assert len(open_calls) == initial_calls, "load_settings() leu o disco na segunda chamada"


def test_save_settings_invalidates_cache(tmp_path, monkeypatch):
    """save_settings() deve zerar o cache."""
    monkeypatch.setattr(settings_module, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings_module, "_settings_cache", None)

    load_settings()
    assert settings_module._settings_cache is not None
    save_settings(settings_module._settings_cache)
    assert settings_module._settings_cache is None, "Cache não foi invalidado após save_settings()"
```

Pattern a seguir: `backend/tests/test_settings_validation.py`.

**Verify**: `cd backend && pytest tests/test_settings_cache.py -v` → all pass

## Done criteria

- [ ] `cd backend && pytest -q` exits 0
- [ ] `grep -c "AgentProgressCallback" backend/app/services/ai_agent.py` → retorna `1` (não 2)
- [ ] `grep -n "_feedback_lock" backend/app/services/ai_agent.py` → 1+ matches
- [ ] `grep -n "_settings_lock" backend/app/services/settings.py` → 1+ matches
- [ ] `grep -n "_settings_cache" backend/app/services/settings.py` → 3+ matches (definição + leitura + invalidação)
- [ ] `cd backend && pytest tests/test_ai_agent.py tests/test_settings_validation.py -v` → all pass
- [ ] Nenhum arquivo fora da lista **In scope** foi modificado
- [ ] `plans/README.md` status row atualizada para DONE

## STOP conditions

Pare e reporte se:
- `grep "AgentProgressCallback" backend/app/services/ai_agent.py` retornar mais de 2 matches (havia mais usos não mapeados).
- Testes de AI agent falharem após o step 1 — a interface de `update_feedback_cache()` e `_format_feedback_shots()` não pode mudar.
- `load_settings()` retornar `None` após a mudança.
- Qualquer teste de ingest falhar após o step 2 (settings cache não pode quebrar o fluxo de ingest).

## Maintenance notes

- **Invalidação de cache**: `_settings_cache = None` é o único ponto de invalidação. Se settings forem modificadas por um processo externo (ex: edição manual do arquivo), o cache ficará stale até o próximo restart. Isso é aceitável para o caso de uso atual (usuário edita via UI → `save_settings()` é chamado).
- **`_settings_cache` em testes**: testes que modificam settings devem usar `monkeypatch.setattr(settings_module, "_settings_cache", None)` no setUp ou usar `tmp_path` para isolar o arquivo.
- **Future**: se o projeto evoluir para multi-process (ex: gunicorn com workers), o cache in-memory deixará de ser compartilhado entre workers. Nesse caso, considerar Redis ou revalidação por file mtime.
