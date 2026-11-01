# DeFi Contract Auditor — Makefile
# All targets must remain working. See AGENTS.md.
.PHONY: setup up down migrate api worker web console gen-console-types test test-web lint precommit token-a token-b gen-types eval clean security-check demo demo-reset

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
	@PYTHONPATH="packages/schemas:packages/auditor_core:services/api:services/worker" $(PYTHON) -c "import asyncio; from app.db.models import init_local_db; asyncio.run(init_local_db())"

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

security-check:
	@echo "Running Milestone 8 Security Hardening & Guardrail Checks..."
	@PYTHONPATH="packages/schemas:packages/auditor_core:services/api:services/worker" \
	SOLC_SELECT_DIR="$(CURDIR)/.venv/.solc-select" \
	$(PYTHON) -m pytest \
		services/api/tests/test_sandbox.py \
		services/api/tests/test_log_scrub.py \
		services/api/tests/test_cross_tenant.py \
		services/api/tests/test_evidence_constraint.py \
		services/api/tests/test_retention_and_delete.py \
		services/api/tests/test_uploads.py \
		services/api/tests/test_redteam.py \
		services/api/tests/test_proofs_and_invariants_m6_m7.py \
		-v --tb=short && \
	(echo "\n==============================================" && \
	 echo "         === SECURITY CHECKS PASSED ===       " && \
	 echo "==============================================") || \
	(echo "\n==============================================" && \
	 echo "         === SECURITY CHECKS FAILED ===       " && \
	 echo "==============================================" && exit 1)

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

# ─── Demo ─────────────────────────────────────────────────────────────────────
demo: up migrate
	@echo "Checking backend API..."
	@if ! (curl -s http://localhost:8000/v1/health >/dev/null 2>&1 || (test -f $(CURDIR)/data/api.pid && kill -0 $$(cat $(CURDIR)/data/api.pid) 2>/dev/null)); then \
		echo "Starting API server on http://localhost:8000..."; \
		(cd services/api && PYTHONPATH=. exec $(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > $(CURDIR)/data/api.log 2>&1 & echo $$! > $(CURDIR)/data/api.pid); \
		sleep 1.5; \
	fi
	@echo "Backend API is ready."
	@echo "Checking test console..."
	@if ! (curl -s http://localhost:3001 >/dev/null 2>&1 || (test -f $(CURDIR)/data/console.pid && kill -0 $$(cat $(CURDIR)/data/console.pid) 2>/dev/null)); then \
		echo "Starting Test Console on http://localhost:3001..."; \
		(cd "tester frontend" && exec npm run dev > $(CURDIR)/data/console.log 2>&1 & echo $$! > $(CURDIR)/data/console.pid); \
		sleep 1.5; \
	fi
	@echo "Seeding demo contracts..."
	@PYTHONPATH="packages/schemas:packages/auditor_core:services/api:services/worker" $(PYTHON) scripts/seed_demo.py
	@echo ""
	@echo "================================================================="
	@echo "                   DEFI AUDITOR DEMO READY                       "
	@echo "================================================================="
	@echo "  Test Console:  http://localhost:3001"
	@echo "  Backend API:   http://localhost:8000"
	@echo "  API Docs:      http://localhost:8000/docs"
	@echo "================================================================="
	@echo "See DEMO.md for the step-by-step 3-minute presenter guide."

demo-reset:
	@echo "Stopping demo processes..."
	@-test -f $(CURDIR)/data/api.pid && kill -9 $$(cat $(CURDIR)/data/api.pid) 2>/dev/null || true
	@-test -f $(CURDIR)/data/console.pid && kill -9 $$(cat $(CURDIR)/data/console.pid) 2>/dev/null || true
	@-pkill -9 -f "uvicorn app.main:app.*8000" 2>/dev/null || true
	@-pkill -9 -f "next.*3001" 2>/dev/null || true
	@-lsof -ti:8000 | xargs kill -9 2>/dev/null || true
	@-lsof -ti:3001 | xargs kill -9 2>/dev/null || true
	@rm -f $(CURDIR)/data/*.pid $(CURDIR)/data/*.log
	@echo "Wiping demo database and storage..."
	@rm -f $(CURDIR)/data/auditor.db $(CURDIR)/data/auditor.db-shm $(CURDIR)/data/auditor.db-wal $(CURDIR)/data/demo_state.json
	@rm -rf $(CURDIR)/data/storage
	@mkdir -p $(CURDIR)/data/storage
	@echo "Reinitializing clean database..."
	@PYTHONPATH="packages/schemas:packages/auditor_core:services/api:services/worker" $(PYTHON) -c "import asyncio, sys; sys.path.insert(0, 'services/api'); from app.db.models import init_local_db; asyncio.run(init_local_db())"
	@echo "Demo state reset complete."
