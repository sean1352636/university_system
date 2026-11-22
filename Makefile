# Education Management System - Makefile
# Development commands for the university system

.PHONY: lock supply-chain-check audit verify-install sbom supply-chain security-gate help install install-dev clean test test-all test-cov test-shared test-university test-security test-gui test-auth test-coverage test-coverage-report coverage-university coverage-university-core architecture-check layout-check lint format run seed portal docker load-test perf-test mutation-test load-test-ui

.DEFAULT_GOAL := help

# Use whatever Python is active (virtualenv, pyenv, system). Override on the
# command line if needed, e.g.  make test PYTHON=python3.12
PYTHON ?= python
PIP := $(PYTHON) -m pip
PYTEST := $(PYTHON) -m pytest

SRC := src/education_system
UNIVERSITY_SRC := $(SRC)/systems/university
COVERAGE_UNIVERSITY_MIN ?= 0.8
# Tests live in one tree at the repo root. (pyproject testpaths mirrors this.)
TESTS := tests
UNIVERSITY_TESTS := \
	tests/unit/systems/university \
	tests/integration/systems/university \
	tests/contract/university \
	tests/end_to_end/university \
	tests/smoke/university \
	tests/performance/benchmarks

help: ## Show this help
	@echo "Education Management System"
	@echo "==========================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ==========================================
# Setup
# ==========================================

install: ## Install the resolved production environment
	$(PIP) install -r requirements.lock

install-dev: ## Install the resolved development environment (includes production)
	$(PIP) install -r requirements-dev.lock

# ==========================================
# Running
# ==========================================

run: ## Run interactive launcher
	$(PYTHON) -m education_system

run-cli: ## Run CLI mode
	$(PYTHON) -m education_system --cli

run-gui: ## Run GUI mode
	$(PYTHON) -m education_system --gui

run-api: ## Run unified API server
	$(PYTHON) -m education_system.platform.delivery.api.unified_server

portal: ## Open the web UI in a browser (starts the API if needed)
	$(PYTHON) -m education_system --web

seed: ## Seed demo students: make seed N=50 (asks which system)
	$(PYTHON) -m education_system --seed $(or $(N),50)

# ==========================================
# Testing
# ==========================================

test: ## Run the default fast, non-GUI test suite
	$(PYTEST) $(TESTS) -v -m "not slow and not gui" --timeout=60

test-all: ## Run every test, including slow and GUI tests
	$(PYTEST) $(TESTS) -v --timeout=120

test-cov: ## Run tests with coverage
	$(PYTEST) $(TESTS) -v --cov=$(SRC) --cov-report=term-missing --cov-report=html:htmlcov -m "not slow and not gui" --timeout=60

test-shared: ## Run shared module tests
	$(PYTEST) tests/unit/platform/ -v --timeout=60

test-university: ## Run the default fast, non-GUI university suite
	$(PYTEST) $(UNIVERSITY_TESTS) -v -m "not slow and not gui" --timeout=60

test-security: ## Run university security and authentication tests (including legacy unmarked files)
	$(PYTEST) tests/security tests/unit/systems/university/infrastructure/security tests/unit/systems/university/infrastructure/auth -n 0 -v --timeout=60

test-gui: ## Run all GUI tests serially (use xvfb-run on headless Linux)
	$(PYTEST) $(TESTS) -m gui -n 0 -v --timeout=120

test-auth: ## Run shared auth infrastructure tests
	$(PYTEST) tests/unit/platform/identity/auth/ -v --timeout=60

test-coverage: ## Run tests with full coverage report (HTML + term-missing)
	$(PYTEST) $(TESTS) -v --cov=$(SRC) --cov-report=html:htmlcov --cov-report=term-missing -m "not slow and not gui" --timeout=60

test-coverage-report: ## Open HTML coverage report in browser
	xdg-open htmlcov/index.html

coverage-percent: ## Print the real total coverage % (for CI to publish, not just a badge)
	$(PYTEST) $(TESTS) --cov=$(SRC) --cov-report= -m "not slow and not gui" --timeout=60 -q
	$(PYTHON) -m coverage report --format=total

coverage-shared: ## Enforce the higher coverage bar on shared/core code (fail under 70%)
	$(PYTEST) tests/unit/platform \
		--cov=$(SRC)/platform --cov=$(SRC)/systems/university/infrastructure \
		--cov-report=term-missing --cov-fail-under=70 -m "not slow and not gui" --timeout=60

coverage-university: ## Measure the whole university tree and block coverage regressions
	$(PYTEST) $(UNIVERSITY_TESTS) \
		-m "not slow and not gui" --timeout=60 \
		--cov=$(UNIVERSITY_SRC) --cov-branch \
		--cov-report=xml:coverage-university.xml \
		--cov-fail-under=$(COVERAGE_UNIVERSITY_MIN)

coverage-university-core: ## Enforce coverage for modernised university core (fail under 60%)
	$(PYTEST) \
		tests/unit/systems/university/domains/admissions/test_admissions_lifecycle.py \
		tests/unit/systems/university/domains/learners/test_student_lifecycle.py \
		tests/unit/systems/university/domains/assessment/test_assessment_boards.py \
		tests/unit/systems/university/domains/academics/test_programme_governance.py \
		tests/unit/systems/university/domains/academics/research/test_pgr_service.py \
		tests/unit/systems/university/services/test_in_process_events.py \
		tests/unit/systems/university/services/test_operations.py \
		--cov=$(SRC)/systems/university/domains/admissions/domain/services/admissions_lifecycle.py \
		--cov=$(SRC)/systems/university/domains/learners/domain/student_lifecycle.py \
		--cov=$(SRC)/systems/university/domains/assessment/domain/boards \
		--cov=$(SRC)/systems/university/domains/curriculum/domain/programme_governance \
		--cov=$(SRC)/systems/university/domains/research/domain/research/pgr \
		--cov=$(SRC)/systems/university/services/events \
		--cov=$(SRC)/systems/university/services/operations.py \
		--cov-report=term-missing --cov-fail-under=60 --timeout=60 -n 0

# ==========================================
# Code Quality
# ==========================================

lint: ## Lint all code
	$(PYTHON) -m ruff check $(SRC)/

lint-fix: ## Fix linting issues
	$(PYTHON) -m ruff check --fix $(SRC)/

format: ## Format code
	$(PYTHON) -m ruff format $(SRC)/

type-check: ## Type check
	$(PYTHON) -m mypy $(SRC)/ --ignore-missing-imports

architecture-check: ## Enforce boundaries and size limits for modernised core
	$(PYTHON) tools/university/check_architecture.py

layout-check: ## Ratchet the file/directory layout (see tools/check_layout.py)
	$(PYTHON) tools/check_layout.py

security-scan: ## Run bandit security scan
	$(PYTHON) -m bandit -r $(SRC)/ -c pyproject.toml -lll

# ==========================================
# Supply chain
# ==========================================

# Both locks resolve from pyproject.toml, which is the only place a direct
# dependency is declared. PROD_EXTRAS is the server-side feature set that ships
# in the container: the desktop (Tkinter) and deep-learning `ai` extras are
# deliberately excluded — install those explicitly where they are needed.
PROD_EXTRAS := --extra analytics --extra documents --extra commerce \
	--extra campus-services --extra integrations
DEV_EXTRAS := --extra dev --extra security --extra perf
PIPTOOLS := $(PYTHON) -m piptools compile --generate-hashes --allow-unsafe --strip-extras

lock: lock-prod lock-dev ## Regenerate both hash-pinned locks from pyproject.toml

lock-prod: ## Resolve the production environment -> requirements.lock
	$(PIP) install --quiet pip-tools
	$(PIPTOOLS) $(PROD_EXTRAS) --output-file=requirements.lock pyproject.toml
	@echo "requirements.lock regenerated — commit it with the pyproject.toml change."

lock-dev: ## Resolve the development environment -> requirements-dev.lock
	$(PIP) install --quiet pip-tools
	$(PIPTOOLS) $(PROD_EXTRAS) $(DEV_EXTRAS) --output-file=requirements-dev.lock pyproject.toml
	@echo "requirements-dev.lock regenerated — commit it with the pyproject.toml change."

supply-chain-check: ## Offline checks: declarative build, pinned runtime, hashed lock
	$(PYTHON) tools/supply_chain_check.py

audit: ## Scan pinned dependencies for known vulnerabilities (blocking)
	$(PIP) install --quiet pip-audit
	$(PYTHON) -m pip_audit --requirement requirements.lock --strict --progress-spinner off

verify-install: ## Prove the lock installs with hash verification into a throwaway venv
	rm -rf .verify-venv
	$(PYTHON) -m venv .verify-venv
	.verify-venv/bin/pip install --require-hashes --no-deps -r requirements.lock
	rm -rf .verify-venv
	@echo "requirements.lock installs cleanly under --require-hashes."

sbom: ## Emit a CycloneDX SBOM for the current environment
	$(PIP) install --quiet cyclonedx-bom
	$(PYTHON) -m cyclonedx_py environment -o sbom.json
	@echo "Wrote sbom.json"

supply-chain: supply-chain-check audit verify-install ## Full supply-chain gate

check: lint test ## Run lint + tests

# ==========================================
# Cleanup
# ==========================================

clean: ## Remove cache and build artifacts
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage build dist *.egg-info

clean-logs: ## Remove log files
	rm -rf var/logs/* 2>/dev/null || true

# ==========================================
# Docker
# ==========================================

docker-build: ## Build Docker image
	docker build -t education-system -f docker/Dockerfile .

docker-up: ## Start with docker-compose
	docker compose -f docker/docker-compose.yml up -d

docker-down: ## Stop docker-compose
	docker compose -f docker/docker-compose.yml down

docker-logs: ## View docker logs
	docker compose -f docker/docker-compose.yml logs -f app

# ==========================================
# CI Simulation
# ==========================================

ci: clean lint test-cov security-scan supply-chain-check ## Simulate full CI pipeline
	@echo "CI pipeline passed!"

# ==========================================
# Performance & Load Testing
# ==========================================

load-test: ## Run headless Locust load test (50 users, 60 s) — server must be running
	$(PYTHON) -m locust -f tests/performance/load/locustfile.py --headless -u 50 -r 5 --run-time 60s --host http://localhost:5000

load-test-ui: ## Open Locust web UI for interactive load testing — server must be running
	$(PYTHON) -m locust -f tests/performance/load/locustfile.py --host http://localhost:5000

perf-test: ## Run standalone SQLite benchmark (no server required)
	$(PYTHON) tests/performance/benchmarks/benchmark_db.py

mutation-test: ## Run focused mutation testing against the email boundary
	mutmut run --paths-to-mutate src/education_system/systems/university/infrastructure/email/smtp.py --tests-dir tests/unit/systems/university/infrastructure/email
