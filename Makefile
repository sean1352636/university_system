# Makefile for University Management System
# This file provides convenient commands for development, testing, and deployment

.PHONY: help install install-dev clean test test-coverage lint format type-check security-check run run-cli run-gui backup docs build deploy

# Default target
.DEFAULT_GOAL := help

# Python and pip executables
PYTHON := python3
PIP := pip3

# Project directories
SRC_DIR := university_system
TEST_DIR := university_system/tests

help: ## Show this help message
	@echo "University Management System - Make Commands"
	@echo "============================================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ==========================================
# Installation & Setup
# ==========================================

install: ## Install production dependencies
	$(PIP) install -r requirements.txt

install-dev: ## Install development dependencies
	$(PIP) install -r requirements.txt
	$(PIP) install -e ".[dev]"
	$(PIP) install pytest pytest-cov pytest-xdist pytest-timeout pytest-benchmark hypothesis black ruff mypy pre-commit

setup: install-dev ## Complete development setup
	pre-commit install
	mkdir -p logs backups data uploads
	@echo "Development environment setup complete!"

# ==========================================
# Cleaning
# ==========================================

clean: ## Remove build artifacts and cache files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	rm -rf build/ dist/ htmlcov/ .coverage .tox/
	@echo "Cleaned build artifacts and cache files"

clean-all: clean ## Remove all generated files including logs and databases
	rm -rf logs/ backups/ uploads/ temp/
	@echo "Cleaned all generated files"

# ==========================================
# Testing
# ==========================================

test: ## Run all tests
	$(PYTHON) -m pytest $(TEST_DIR) -v

test-fast: ## Run tests with multiple workers
	$(PYTHON) -m pytest $(TEST_DIR) -n auto -v

test-coverage: ## Run tests with coverage report
	$(PYTHON) -m pytest $(TEST_DIR) --cov=$(SRC_DIR) --cov-report=html --cov-report=term

test-unit: ## Run only unit tests
	$(PYTHON) -m pytest $(TEST_DIR) -m unit -v

test-integration: ## Run only integration tests
	$(PYTHON) -m pytest $(TEST_DIR) -m integration -v

test-security: ## Run security tests
	$(PYTHON) -m pytest $(TEST_DIR) -m security -v

test-watch: ## Run tests in watch mode
	$(PYTHON) -m pytest $(TEST_DIR) -f -v

test-workflows: ## Run integration workflow tests
	$(PYTHON) -m pytest $(TEST_DIR)/test_integration_workflows.py -v

test-e2e: ## Run end-to-end journey tests
	$(PYTHON) -m pytest $(TEST_DIR)/test_end_to_end_journeys.py -v

test-performance: ## Run performance benchmark tests
	$(PYTHON) -m pytest $(TEST_DIR)/test_performance_benchmarks.py -v -s

test-property: ## Run property-based tests (requires hypothesis)
	$(PYTHON) -m pytest $(TEST_DIR)/test_performance_benchmarks.py::TestPropertyBasedTesting -v

test-all-new: ## Run all new test suites (workflows + e2e + performance)
	$(PYTHON) -m pytest $(TEST_DIR)/test_integration_workflows.py $(TEST_DIR)/test_end_to_end_journeys.py $(TEST_DIR)/test_performance_benchmarks.py -v

# ==========================================
# Code Quality
# ==========================================

lint: ## Run linter (ruff)
	ruff check $(SRC_DIR)
	ruff check run.py

lint-fix: ## Fix linting issues automatically
	ruff check --fix $(SRC_DIR)
	ruff check --fix run.py

format: ## Format code with black
	black $(SRC_DIR) run.py --line-length 100
	isort $(SRC_DIR) run.py

format-check: ## Check code formatting without making changes
	black $(SRC_DIR) run.py --check --line-length 100
	isort $(SRC_DIR) run.py --check-only

type-check: ## Run static type checking with mypy
	mypy $(SRC_DIR)

security-check: ## Run security vulnerability checks
	pip-audit
	bandit -r $(SRC_DIR) -ll

security-scan-local: ## Run comprehensive local security scan
	@chmod +x scripts/security_scan.sh
	@./scripts/security_scan.sh

security-scan-detailed: ## Run detailed security scan with all findings
	@chmod +x scripts/security_scan.sh
	@./scripts/security_scan.sh --detailed

security-reports: ## Generate security reports
	@mkdir -p security-reports
	@echo "Generating security reports..."
	@bandit -r $(SRC_DIR) -f json -o security-reports/bandit.json --exclude $(TEST_DIR)
	@safety check --json > security-reports/safety.json || true
	@pip-audit --format json > security-reports/pip-audit.json || true
	@echo "Reports generated in security-reports/"

check: lint type-check ## Run all code quality checks
	@echo "All code quality checks passed!"

# ==========================================
# Running the Application
# ==========================================

run: ## Run with interactive menu
	$(PYTHON) run.py

run-cli: ## Run in CLI mode
	$(PYTHON) run.py --cli

run-gui: ## Run in GUI mode
	$(PYTHON) run.py --gui

run-tests-all: ## Run all test suite
	$(PYTHON) $(TEST_DIR)/run_all_tests.py

# ==========================================
# Database Operations
# ==========================================

db-backup: ## Create database backup
	@mkdir -p backups
	@$(PYTHON) -c "from university_system.infrastructure.database.database_utils import backup_database; backup_database()"
	@echo "Database backup created"

db-restore: ## Restore database from backup (specify BACKUP_FILE=path/to/backup.db)
	@if [ -z "$(BACKUP_FILE)" ]; then \
		echo "Error: BACKUP_FILE not specified. Usage: make db-restore BACKUP_FILE=path/to/backup.db"; \
		exit 1; \
	fi
	@$(PYTHON) -c "from university_system.infrastructure.database.database_utils import restore_database; restore_database('$(BACKUP_FILE)')"
	@echo "Database restored from $(BACKUP_FILE)"

db-reset: ## Reset database (WARNING: Deletes all data!)
	@echo "WARNING: This will delete all database data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -f university_system.db; \
		$(PYTHON) -c "from university_system.infrastructure.database.database_utils import init_db; init_db()"; \
		echo "Database reset complete"; \
	fi

# ==========================================
# Documentation
# ==========================================

docs: ## Generate documentation
	@echo "Generating documentation..."
	# Add your documentation generation command here
	# e.g., sphinx-build -b html docs/ docs/_build/

docs-serve: ## Serve documentation locally
	@echo "Serving documentation..."
	# Add your documentation server command here
	# e.g., cd docs/_build && python -m http.server 8000

# ==========================================
# Building & Distribution
# ==========================================

build: clean ## Build distribution packages
	$(PYTHON) -m build
	@echo "Build complete! Packages in dist/"

build-wheel: ## Build wheel package only
	$(PYTHON) -m build --wheel

# ==========================================
# Development Utilities
# ==========================================

shell: ## Start Python shell with project context
	$(PYTHON) -i -c "import sys; sys.path.insert(0, '.'); from university_system import *"

deps-list: ## List all installed dependencies
	$(PIP) list

deps-outdated: ## Check for outdated dependencies
	$(PIP) list --outdated

deps-update: ## Update all dependencies (use with caution)
	$(PIP) install --upgrade -r requirements.txt

deps-freeze: ## Freeze current dependencies to requirements-lock.txt
	$(PIP) freeze > requirements-lock.txt
	@echo "Dependencies frozen to requirements-lock.txt"

# ==========================================
# Git Helpers
# ==========================================

pre-commit: format lint test ## Run pre-commit checks
	@echo "Pre-commit checks passed!"

git-clean: ## Remove untracked files (dry run)
	git clean -xdn

git-clean-force: ## Remove untracked files (WARNING: irreversible!)
	git clean -xdf

# ==========================================
# CI/CD Simulation
# ==========================================

ci: clean install-dev lint type-check test-coverage ## Simulate CI pipeline
	@echo "CI pipeline simulation complete!"

# ==========================================
# Monitoring & Logs
# ==========================================

logs: ## View application logs
	@if [ -f logs/university_system.log ]; then \
		tail -f logs/university_system.log; \
	else \
		echo "No log file found at logs/university_system.log"; \
	fi

logs-tail: ## Tail last 50 lines of logs
	@if [ -f logs/university_system.log ]; then \
		tail -n 50 logs/university_system.log; \
	else \
		echo "No log file found at logs/university_system.log"; \
	fi

logs-clear: ## Clear all log files
	@rm -f logs/*.log
	@echo "Log files cleared"

# ==========================================
# Performance & Profiling
# ==========================================

profile: ## Run profiler on main application
	$(PYTHON) -m cProfile -o profile.stats run.py --cli
	@echo "Profile saved to profile.stats"

profile-view: ## View profiling results
	$(PYTHON) -m pstats profile.stats

# ==========================================
# Project Information
# ==========================================

info: ## Display project information
	@echo "University Management System"
	@echo "============================"
	@echo "Python Version: $$($(PYTHON) --version)"
	@echo "Pip Version: $$($(PIP) --version)"
	@echo "Project Structure:"
	@tree -L 2 -d $(SRC_DIR) || echo "  (install 'tree' command for directory listing)"
	@echo ""
	@echo "Lines of Code:"
	@find $(SRC_DIR) -name "*.py" | xargs wc -l | tail -1
