# Education Management System - Makefile
# Development commands for all 4 subsystems

.PHONY: help install install-dev clean test test-all test-cov test-shared test-university test-college test-secondary test-primary test-integration test-security test-gui test-auth test-coverage test-coverage-report lint format run seed portal docker load-test perf-test load-test-ui

.DEFAULT_GOAL := help

VENV := /home/seancatchpole989/venv/bin
PYTHON := $(VENV)/python
PIP := $(VENV)/pip
PYTEST := $(VENV)/pytest

SRC := education_system
TESTS := $(SRC)/shared/tests $(SRC)/university_system/tests $(SRC)/college_system/tests $(SRC)/secondary_school/tests $(SRC)/primary_school/tests

help: ## Show this help
	@echo "Education Management System"
	@echo "==========================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ==========================================
# Setup
# ==========================================

install: ## Install production dependencies
	$(PIP) install -r requirements.txt

install-dev: install ## Install dev dependencies
	$(PIP) install pytest pytest-cov pytest-timeout ruff bandit[toml] mypy

# ==========================================
# Running
# ==========================================

run: ## Run interactive launcher
	$(PYTHON) run.py

run-cli: ## Run CLI mode
	$(PYTHON) run.py --cli

run-gui: ## Run GUI mode
	$(PYTHON) run.py --gui

run-api: ## Run college API server
	$(PYTHON) -m education_system.college_system.api.api_server

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
	$(PYTEST) $(SRC)/shared/tests/ -v --timeout=60

test-university: ## Run university tests
	$(PYTEST) $(SRC)/university_system/tests/ -v --timeout=60

test-college: ## Run college tests
	$(PYTEST) $(SRC)/college_system/tests/ -v --timeout=60

test-secondary: ## Run secondary school tests
	$(PYTEST) $(SRC)/secondary_school/tests/ -v --timeout=60

test-primary: ## Run primary school tests
	$(PYTEST) $(SRC)/primary_school/tests/ -v --timeout=60

test-integration: ## Run cross-system integration tests
	$(PYTEST) $(SRC)/shared/tests/test_cross_system.py -v --timeout=60

test-security: ## Run security tests
	$(PYTEST) -m security -v --timeout=60

test-gui: ## Run GUI tests (mocked tkinter)
	$(PYTEST) -m gui -v --timeout=60

test-auth: ## Run shared auth infrastructure tests
	$(PYTEST) $(SRC)/shared/tests/test_auth_core.py $(SRC)/shared/tests/test_password_manager.py $(SRC)/shared/tests/test_mfa_service.py $(SRC)/shared/tests/test_session_manager.py $(SRC)/shared/tests/test_security.py -v --timeout=60

test-coverage: ## Run tests with full coverage report (HTML + term-missing)
	$(PYTEST) $(TESTS) -v --cov=$(SRC) --cov-report=html:htmlcov --cov-report=term-missing -m "not slow and not gui" --timeout=60

test-coverage-report: ## Open HTML coverage report in browser
	xdg-open htmlcov/index.html

# ==========================================
# Code Quality
# ==========================================

lint: ## Lint all code
	$(VENV)/ruff check $(SRC)/

lint-fix: ## Fix linting issues
	$(VENV)/ruff check --fix $(SRC)/

format: ## Format code
	$(VENV)/ruff format $(SRC)/

type-check: ## Type check
	$(VENV)/mypy $(SRC)/ --ignore-missing-imports

security-scan: ## Run bandit security scan
	$(VENV)/bandit -r $(SRC)/ -c pyproject.toml -lll

check: lint test ## Run lint + tests

# ==========================================
# Cleanup
# ==========================================

clean: ## Remove cache and build artifacts
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage build dist *.egg-info

clean-logs: ## Remove log files
	find $(SRC) -name "*.log" -delete 2>/dev/null || true

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
	$(VENV)/locust -f education_system/shared/tests/performance/locustfile.py --headless -u 50 -r 5 --run-time 60s --host http://localhost:5000

load-test-ui: ## Open Locust web UI for interactive load testing — server must be running
	$(VENV)/locust -f education_system/shared/tests/performance/locustfile.py --host http://localhost:5000

perf-test: ## Run standalone SQLite benchmark (no server required)
	$(PYTHON) education_system/shared/tests/performance/benchmark_db.py
