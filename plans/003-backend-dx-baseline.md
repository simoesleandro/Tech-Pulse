# Plan 003: Estabelecer Baseline de DX no Backend (ruff + mypy + cobertura + CI)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**:
> ```
> git diff --stat b15548f..HEAD -- backend/requirements.txt backend/pytest.ini .github/workflows/ci.yml
> ```
> Se qualquer arquivo mudou, compare os excerpts de "Current state" contra o código live antes de prosseguir.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none (pode rodar em paralelo com plan 001 e 002)
- **Category**: dx
- **Planned at**: commit `b15548f`, 2026-06-20

## Why this matters

O backend não tem linter, type checker nem relatório de cobertura. O CI só roda `pytest -q` — nenhum erro de tipo ou violação de estilo é detectado automaticamente. Isso significa que bugs de tipo (ex: `None.strip()` em `ai_reasoning`) só aparecem em runtime, refactors acumulam dívida silenciosa, e novos contribuidores não têm feedback rápido. Adicionar `ruff` (linter/formatter), `mypy` (type checker) e `pytest-cov` (cobertura) ao CI fecha esse gap com custo mínimo.

## Current state

### `backend/requirements.txt` (estado atual, linhas 1-11)

```
fastapi
uvicorn[standard]
sqlalchemy>=2.0
pydantic>=2.0
requests
httpx
python-dotenv
pytest
pytest-asyncio
alembic
```

Sem ruff, mypy, nem pytest-cov.

### `backend/pytest.ini` (estado atual)

```ini
[pytest]
asyncio_mode = auto
```

Sem configuração de cobertura.

### `.github/workflows/ci.yml` — job `backend` (estado atual, linhas 13-28)

```yaml
  backend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: backend/requirements.txt
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run pytest
        run: pytest -q
```

Sem steps de lint, type check ou cobertura.

### Convenções

- `requirements.txt` é o único arquivo de dependências (sem pyproject.toml, setup.cfg).
- CI usa `actions/setup-python@v5` com cache via `cache-dependency-path`.
- Python 3.11+ — mypy deve ser configurado para `python_version = "3.11"`.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install tools | `cd backend && pip install -r requirements.txt` | exit 0 |
| Run ruff check | `cd backend && ruff check app/` | exit 0 ou lista de violations |
| Run ruff format | `cd backend && ruff format --check app/` | exit 0 ou lista de diffs |
| Run mypy | `cd backend && mypy app/ --ignore-missing-imports` | exit 0 ou lista de errors |
| Run tests + coverage | `cd backend && pytest --cov=app --cov-report=term-missing -q` | all pass + coverage table |

## Scope

**In scope**:
- `backend/requirements.txt`
- `backend/pytest.ini`
- `backend/ruff.toml` (criar novo)
- `.github/workflows/ci.yml`

**Out of scope** (não tocar):
- Nenhum arquivo de código em `backend/app/` — este plano **não corrige** erros que ruff/mypy encontrar. O objetivo é apenas instalar e configurar as ferramentas. Fixar os erros reportados é trabalho separado.
- `frontend/` — escopo deste plano é backend apenas.
- `pyproject.toml` — o projeto não usa pyproject.toml; não criar.

## Git workflow

- Branch: `advisor/003-backend-dx-baseline`
- Commits: `dx: add ruff, mypy, pytest-cov to requirements`, `dx: configure ruff and pytest coverage`, `ci: add lint and typecheck steps to backend job`
- Não fazer push nem abrir PR sem instrução.

## Steps

### Step 1: Adicionar ferramentas ao `requirements.txt`

No arquivo `backend/requirements.txt`, adicionar ao final:

```
ruff
mypy
pytest-cov
```

**Verify**: `cd backend && pip install -r requirements.txt` → exit 0

**Verify**: `cd backend && ruff --version` → imprime versão (ex: `ruff 0.x.x`)

**Verify**: `cd backend && mypy --version` → imprime versão

### Step 2: Criar `backend/ruff.toml`

Criar o arquivo `backend/ruff.toml` com configuração conservadora que não quebre código existente:

```toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
# Regras ativas: pyflakes (F), pycodestyle erros (E), isort (I), bugbear (B)
# Excluir regras que conflitam com padrões existentes do projeto
select = ["F", "E", "I", "B"]
ignore = [
    "E501",   # line too long — controlado por formatter
    "B008",   # do not perform function calls in argument defaults (FastAPI usa isso)
    "B904",   # raise in except — estilo legítimo no projeto
]

[tool.ruff.lint.isort]
known-first-party = ["app"]

[tool.ruff.format]
quote-style = "double"
```

**Verify**: `cd backend && ruff check app/ --statistics` → lista de violações por regra (ou `exit 0` se nenhuma)

> **Nota**: é esperado que ruff reporte violações. O objetivo deste step é confirmar que a ferramenta roda sem crash, não que o código está limpo. As violations serão corrigidas em commits futuros (fora deste plano).

### Step 3: Criar `backend/mypy.ini`

Criar `backend/mypy.ini`:

```ini
[mypy]
python_version = 3.11
ignore_missing_imports = true
warn_return_any = false
warn_unused_configs = true
# Gradual typing: módulos sem type annotations não falham o check
disallow_untyped_defs = false
check_untyped_defs = true
```

**Verify**: `cd backend && mypy app/ 2>&1 | tail -5` → mostra resumo (erros ou `Success: no issues found`)

> **Nota**: é esperado que mypy reporte erros. O objetivo é confirmar que roda, não que o código tem zero erros de tipo.

### Step 4: Configurar cobertura no `pytest.ini`

Adicionar configuração de cobertura ao `backend/pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
addopts = --cov=app --cov-report=term-missing --cov-fail-under=0
```

> O `--cov-fail-under=0` garante que o CI não quebre por cobertura baixa inicialmente. A meta de cobertura pode ser aumentada incrementalmente.

**Verify**: `cd backend && pytest -q 2>&1 | grep -E "(PASSED|FAILED|coverage)"` → mostra linhas de coverage

### Step 5: Adicionar steps de lint e typecheck ao CI

No arquivo `.github/workflows/ci.yml`, dentro do job `backend`, adicionar steps **após** o step de `Run pytest`:

```yaml
      - name: Lint (ruff)
        run: ruff check app/ --output-format=github
        continue-on-error: true

      - name: Format check (ruff)
        run: ruff format --check app/
        continue-on-error: true

      - name: Type check (mypy)
        run: mypy app/ 2>&1 | tail -20
        continue-on-error: true
```

> `continue-on-error: true` é intencional neste primeiro momento: os steps reportam violations sem quebrar o CI. Quando o código estiver limpo (plano futuro), mudar para `continue-on-error: false`.

O job `backend` após a mudança deve ficar:

```yaml
  backend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: backend/requirements.txt
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run pytest
        run: pytest -q
      - name: Lint (ruff)
        run: ruff check app/ --output-format=github
        continue-on-error: true
      - name: Format check (ruff)
        run: ruff format --check app/
        continue-on-error: true
      - name: Type check (mypy)
        run: mypy app/ 2>&1 | tail -20
        continue-on-error: true
```

**Verify**: `cd backend && pytest -q` → all pass (nenhuma regressão por ter adicionado --cov)

## Test plan

Este plano não cria novos testes. A verificação é que a suite existente continua passando com as novas ferramentas instaladas.

**Verify final**: `cd backend && pytest -q --tb=short` → all pass + coverage report exibido

## Done criteria

- [ ] `cd backend && pip install -r requirements.txt && ruff --version && mypy --version` → todos exitam 0
- [ ] `backend/ruff.toml` existe com `target-version = "py311"`
- [ ] `backend/mypy.ini` existe com `python_version = 3.11`
- [ ] `backend/pytest.ini` contém `addopts = --cov=app`
- [ ] `.github/workflows/ci.yml` job `backend` contém step "Lint (ruff)"
- [ ] `.github/workflows/ci.yml` job `backend` contém step "Type check (mypy)"
- [ ] `cd backend && pytest -q` exits 0 (nenhuma regressão)
- [ ] Nenhum arquivo em `backend/app/` foi modificado
- [ ] `plans/README.md` status row atualizada para DONE

## STOP conditions

Pare e reporte se:
- `pip install -r requirements.txt` falhar por conflito de versão — não tente resolver; reporte o conflito.
- `pytest -q` começar a falhar após adicionar `--cov` ao `pytest.ini` — reporte o erro exato.
- O formato do CI YAML ficar inválido — valide com `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` antes de commitar.
- `ruff check app/` crashar (não apenas reportar violations — isso é esperado) — reporte a exceção.

## Maintenance notes

- **Próximo passo**: depois que este plano estiver no CI, criar um plano separado para corrigir os erros reportados por ruff/mypy e mudar `continue-on-error: true` para `false` no CI.
- **Cobertura**: aumentar `--cov-fail-under` incrementalmente (ex: 40% → 50% → 60%) à medida que testes forem adicionados.
- **Cache do CI**: o `cache-dependency-path` aponta para `requirements.txt` — qualquer nova dependência invalida o cache automaticamente.
- **mypy strict**: não ativar `disallow_untyped_defs = true` prematuramente — o codebase tem muitas funções sem anotação; ativar gradualmente por módulo.
