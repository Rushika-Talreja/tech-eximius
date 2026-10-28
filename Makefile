# DeFi Contract Auditor — Makefile
# All targets must remain working. See AGENTS.md.
.PHONY: setup up down migrate api worker web console gen-console-types test test-web lint precommit token-a token-b gen-types eval clean

PYTHON ?= $(if $(wildcard .venv/bin/python),$(abspath .venv/bin/python),python3)
PIP ?= $(PYTHON) -m pip
UV ?= uv

# ─── Environment ─────────────────────────────────────────────────────────────
setup:
	@echo "Installing Python deps..."
	@which $(UV) >/dev/null 2>&1 && $(UV) pip install -e "packages/schemas[dev]" -e "packages/auditor_core[dev]" -e "services/api[dev]" -e "services/worker[dev]" || $(PIP) install -e "packages/schemas[dev]" -e "packages/auditor_core[dev]" -e "services/api[dev]" -e "services/worker[dev]"
	@echo "Installing Node deps..."
	cd apps/web && (npm ci || npm install)
	@echo "Installing pre-commit hooks..."
	@which pre-commit >/dev/null 2>&1 && pre-commit install || true
	@echo "Setup complete."

# ─── Infrastructure (Local Standalone) ──────────────────────────────────────
up:
	@mkdir -p data/storage
	@echo "Local storage and environment ready (zero-Docker local hosting)."

down:
	@echo "Local services stopped."

# ─── Database ─────────────────────────────────────────────────────────────────
migrate:
	@python3 -c "import asyncio; from app.db.models import init_local_db; asyncio.run(init_local_db())" 2>/dev/null || (cd services/api && alembic upgrade head)

# ─── Runtime ──────────────────────────────────────────────────────────────────
api:
	cd services/api && $(PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	cd services/worker && $(PYTHON) -m app.main

web:
	cd apps/web && npm run dev

console:
	cd "tester frontend" && npm run dev

gen-console-types:
	@echo "Generating OpenAPI schema..."
	@curl -s http://localhost:8000/openapi.json > openapi.json 2>/dev/null || (cd services/api && $(PYTHON) -c "from app.main import app; import json; print(json.dumps(app.openapi()))" > ../../openapi.json)
	@echo "Generating TypeScript types for test console..."
	cd "tester frontend" && npx openapi-typescript ../openapi.json -o src/types/backend.d.ts
	@echo "Types generated at tester frontend/src/types/backend.d.ts"

# ─── Testing ──────────────────────────────────────────────────────────────────
test:
	$(PYTHON) -m pytest services/ packages/ -x -v --tb=short

test-web:
	cd apps/web && npm test

# ─── Lint / typecheck ─────────────────────────────────────────────────────────
lint:
	@which ruff >/dev/null 2>&1 && ruff check services/ packages/ corpus/ || true
	@which ruff >/dev/null 2>&1 && ruff format --check services/ packages/ corpus/ || true
	@which mypy >/dev/null 2>&1 && mypy services/ packages/ || true
	@cd apps/web && (which npx >/dev/null 2>&1 && npx eslint . && npx prettier --check . || true)

precommit:
	@which pre-commit >/dev/null 2>&1 && pre-commit run --all-files || echo "pre-commit command not found; run pip install pre-commit"

# ─── Auth dev helpers ─────────────────────────────────────────────────────────
token-a:
	@cd services/api && PYTHONPATH=. $(PYTHON) -m app.devtools.mint_token --user a

token-b:
	@cd services/api && PYTHONPATH=. $(PYTHON) -m app.devtools.mint_token --user b

# ─── Code generation ──────────────────────────────────────────────────────────
gen-types:
	@echo "Generating OpenAPI schema..."
	cd services/api && $(PYTHON) -c "from app.main import app; import json; print(json.dumps(app.openapi()))" > ../../openapi.json
	@echo "Generating TypeScript types..."
	@mkdir -p apps/web/src/lib/api
	cd apps/web && ("$(CURDIR)/tester frontend/node_modules/.bin/openapi-typescript" ../../openapi.json -o src/lib/api/schema.d.ts 2>/dev/null || npx openapi-typescript ../../openapi.json -o src/lib/api/schema.d.ts)
	@echo "Types generated at apps/web/src/lib/api/schema.d.ts"

# ─── Evaluation ───────────────────────────────────────────────────────────────
eval:
	pytest eval/ -x -v --tb=short

# ─── Sandbox runner ───────────────────────────────────────────────────────────
build-sandbox:
	@echo "Docker skipped — running analyzers locally via subprocess."

# ─── Corpus ───────────────────────────────────────────────────────────────────
ingest-corpus:
	python -m auditor_core.corpus.ingest corpus/seed/

# ─── Cleanup ──────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	cd apps/web && rm -rf .next out
