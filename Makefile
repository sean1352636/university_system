# Education Management System - Makefile
# Development commands for the university system

.PHONY: help install install-dev clean test test-all test-cov test-shared test-university test-security test-gui test-auth test-coverage test-coverage-report lint format run seed portal docker load-test perf-test load-test-ui

.DEFAULT_GOAL := help

# Use whatever Python is active (virtualenv, pyenv, system). Override on the
# command line if needed, e.g.  make test PYTHON=python3.12
PYTHON ?= python
PIP := $(PYTHON) -m pip
PYTEST := $(PYTHON) -m pytest

SRC := program/education_system
# Tests live in one tree at the repo root. (pyproject testpaths mirrors this.)
TESTS := program/tests

help: ## Show this help
	@echo "Education Management System"
	@echo "==========================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ==========================================
# Setup
# ==========================================

install: ## Install production dependencies
	$(PIP) install -r requirements.txt

install-dev: ## Install runtime + development/CI dependencies
	$(PIP) install -r requirements-dev.txt

# ==========================================
# Running
# ==========================================

run: ## Run interactive launcher
	$(PYTHON) run.py

run-cli: ## Run CLI mode
	$(PYTHON) run.py --cli

run-gui: ## Run GUI mode
	$(PYTHON) run.py --gui

run-api: ## Run unified API server
	$(PYTHON) -m education_system.platform.delivery.api.unified_server

portal: ## Run self-service web portal
	$(PYTHON) run.py --portal

seed: ## Seed databases with demo data
	$(PYTHON) run.py --seed

# ==========================================
# Testing
# ==========================================

test: ## Run all tests
	$(PYTEST) $(TESTS) -v -m "not slow and not gui" --timeout=60

test-all: ## Run all tests including slow
	$(PYTEST) $(TESTS) -v --timeout=120

test-cov: ## Run tests with coverage
	$(PYTEST) $(TESTS) -v --cov=$(SRC) --cov-report=term-missing --cov-report=html:htmlcov -m "not slow and not gui" --timeout=60

test-shared: ## Run shared module tests
	$(PYTEST) program/tests/platform/ -v --timeout=60

test-university: ## Run university tests
	$(PYTEST) program/tests/systems/university/ -v --timeout=60

test-security: ## Run security tests
	$(PYTEST) -m security -v --timeout=60

test-gui: ## Run GUI tests (mocked tkinter)
	$(PYTEST) -m gui -v --timeout=60

test-auth: ## Run shared auth infrastructure tests
	$(PYTEST) program/tests/platform/identity/auth/ -v --timeout=60

test-coverage: ## Run tests with full coverage report (HTML + term-missing)
	$(PYTEST) $(TESTS) -v --cov=$(SRC) --cov-report=html:htmlcov --cov-report=term-missing -m "not slow and not gui" --timeout=60

test-coverage-report: ## Open HTML coverage report in browser
	xdg-open htmlcov/index.html

coverage-percent: ## Print the real total coverage % (for CI to publish, not just a badge)
	$(PYTEST) $(TESTS) --cov=$(SRC) --cov-report= -m "not slow and not gui" --timeout=60 -q
	$(PYTHON) -m coverage report --format=total

coverage-shared: ## Enforce the higher coverage bar on shared/core code (fail under 70%)
	$(PYTEST) program/tests/platform \
		--cov=$(SRC)/platform --cov=$(SRC)/systems/university/infrastructure \
		--cov-report=term-missing --cov-fail-under=70 -m "not slow and not gui" --timeout=60

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

security-scan: ## Run bandit security scan
	$(PYTHON) -m bandit -r $(SRC)/ -c pyproject.toml -lll

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

ci: clean lint test-cov security-scan ## Simulate full CI pipeline
	@echo "CI pipeline passed!"

# ==========================================
# Performance & Load Testing
# ==========================================

load-test: ## Run headless Locust load test (50 users, 60 s) — server must be running
	$(PYTHON) -m locust -f program/tests/platform/performance/locustfile.py --headless -u 50 -r 5 --run-time 60s --host http://localhost:5000

load-test-ui: ## Open Locust web UI for interactive load testing — server must be running
	$(PYTHON) -m locust -f program/tests/platform/performance/locustfile.py --host http://localhost:5000

perf-test: ## Run standalone SQLite benchmark (no server required)
	$(PYTHON) program/tests/platform/performance/benchmark_db.py
