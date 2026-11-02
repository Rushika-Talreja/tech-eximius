# DeFi Contract Auditor — Makefile
# All targets must remain working. See AGENTS.md.
.PHONY: setup up down migrate api worker web test test-web lint precommit token-a token-b eval clean security-check demo demo-reset

PYTHON ?= $(if $(wildcard .venv/bin/python),$(abspath .venv/bin/python),python3)
PIP ?= $(PYTHON) -m pip
UV ?= uv

# ─── Environment ─────────────────────────────────────────────────────────────
setup:
	@echo "Installing Python deps..."
	@which $(UV) >/dev/null 2>&1 && $(UV) pip install -e "packages/schemas[dev]" -e "packages/auditor_core[dev]" -e "services/api[dev]" -e "services/worker[dev]" || $(PIP) install -e "packages/schemas[dev]" -e "packages/auditor_core[dev]" -e "services/api[dev]" -e "services/worker[dev]"
	@echo "Installing Node deps for Stitch frontend..."
	cd frontend && (npm ci || npm install)
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
	cd frontend && npm run dev

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
	cd frontend && npm run build

# ─── Lint / typecheck ─────────────────────────────────────────────────────────
lint:
	@which ruff >/dev/null 2>&1 && ruff check services/ packages/ corpus/ || true
	@which ruff >/dev/null 2>&1 && ruff format --check services/ packages/ corpus/ || true
	@which mypy >/dev/null 2>&1 && mypy services/ packages/ || true

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
	@echo "OpenAPI schema generated at openapi.json"

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
	cd frontend && rm -rf dist

# ─── Demo ─────────────────────────────────────────────────────────────────────
demo: up migrate
	@echo "Checking backend API..."
	@if ! (curl -s http://localhost:8000/v1/health >/dev/null 2>&1 || (test -f $(CURDIR)/data/api.pid && kill -0 $$(cat $(CURDIR)/data/api.pid) 2>/dev/null)); then \
		echo "Starting API server on http://localhost:8000..."; \
		(cd services/api && PYTHONPATH=. exec $(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > $(CURDIR)/data/api.log 2>&1 & echo $$! > $(CURDIR)/data/api.pid); \
		sleep 1.5; \
	fi
	@echo "Backend API is ready."
	@echo "Checking Stitch frontend..."
	@if ! (curl -s http://localhost:3000 >/dev/null 2>&1 || (test -f $(CURDIR)/data/frontend.pid && kill -0 $$(cat $(CURDIR)/data/frontend.pid) 2>/dev/null)); then \
		echo "Starting Stitch frontend on http://localhost:3000..."; \
		(cd frontend && exec npm run dev > $(CURDIR)/data/frontend.log 2>&1 & echo $$! > $(CURDIR)/data/frontend.pid); \
		sleep 1.5; \
	fi
	@echo "Seeding demo contracts..."
	@PYTHONPATH="packages/schemas:packages/auditor_core:services/api:services/worker" $(PYTHON) scripts/seed_demo.py
	@echo ""
	@echo "================================================================="
	@echo "                   DEFI AUDITOR DEMO READY                       "
	@echo "================================================================="
	@echo "  Stitch UI:     http://localhost:3000"
	@echo "  Backend API:   http://localhost:8000"
	@echo "  API Docs:      http://localhost:8000/docs"
	@echo "================================================================="
	@echo "See DEMO.md for the step-by-step 3-minute presenter guide."

demo-reset:
	@echo "Stopping demo processes..."
	@-test -f $(CURDIR)/data/api.pid && kill -9 $$(cat $(CURDIR)/data/api.pid) 2>/dev/null || true
	@-test -f $(CURDIR)/data/frontend.pid && kill -9 $$(cat $(CURDIR)/data/frontend.pid) 2>/dev/null || true
	@-pkill -9 -f "uvicorn app.main:app.*8000" 2>/dev/null || true
	@-pkill -9 -f "vite.*3000" 2>/dev/null || true
	@-lsof -ti:8000 | xargs kill -9 2>/dev/null || true
	@-lsof -ti:3000 | xargs kill -9 2>/dev/null || true
	@rm -f $(CURDIR)/data/*.pid $(CURDIR)/data/*.log
	@echo "Wiping demo database and storage..."
	@rm -f $(CURDIR)/data/auditor.db $(CURDIR)/data/auditor.db-shm $(CURDIR)/data/auditor.db-wal $(CURDIR)/data/demo_state.json
	@rm -rf $(CURDIR)/data/storage
	@mkdir -p $(CURDIR)/data/storage
	@echo "Reinitializing clean database..."
	@PYTHONPATH="packages/schemas:packages/auditor_core:services/api:services/worker" $(PYTHON) -c "import asyncio, sys; sys.path.insert(0, 'services/api'); from app.db.models import init_local_db; asyncio.run(init_local_db())"
	@echo "Demo state reset complete."
