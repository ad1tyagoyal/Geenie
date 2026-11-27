.DEFAULT_GOAL := help

# Detect OS for cross-platform compatibility (Windows vs Unix/macOS)
ifeq ($(OS),Windows_NT)
	VENV_DIR := .venv
	PYTHON := $(VENV_DIR)\Scripts\python.exe
else
	VENV_DIR := .venv
	PYTHON := $(VENV_DIR)/bin/python
endif

# Always invoke pip and modules via python -m to avoid Windows App Control / WDAC blocking .exe stubs in .venv
PIP := $(PYTHON) -m pip

.PHONY: help venv install install-dev run test lint format clean

help: ## Show available commands
	@echo.
	@echo Available commands:
	@echo   make venv         - Create Python virtual environment (.venv)
	@echo   make install      - Install dependencies from requirements.txt
	@echo   make install-dev  - Install dev tools (pytest, ruff, black)
	@echo   make run          - Run data pipeline ingestion
	@echo   make test         - Run all unit tests (unittest)
	@echo   make lint         - Run linter (ruff)
	@echo   make format       - Format code (ruff format)
	@echo   make clean        - Remove Python cache files (__pycache__, .pyc)
	@echo.

venv: ## Create virtual environment
	python -m venv $(VENV_DIR)

install: ## Install production dependencies
	$(PIP) install -r requirements.txt

install-dev: install ## Install development tools
	$(PIP) install pytest ruff black

run: ## Run main / sample script
	$(PYTHON) -m data_pipeline.ingestion.twelve_data_client

test: ## Run all unit tests
	$(PYTHON) -c "import pathlib, sys, unittest; mods = sorted(p.with_suffix('').as_posix().replace('/', '.') for p in pathlib.Path('test').rglob('*.py') if p.name != '__init__.py'); suite = unittest.defaultTestLoader.loadTestsFromNames(mods); res = unittest.TextTestRunner(verbosity=2).run(suite); sys.exit(0 if res.wasSuccessful() else 1)"

lint: ## Check code for errors and styling
	$(PYTHON) -m ruff check .

format: ## Auto-format code
	$(PYTHON) -m ruff format .

clean: ## Clean cache files and bytecode
ifeq ($(OS),Windows_NT)
	@powershell -NoProfile -Command "Get-ChildItem -Recurse -Include __pycache__,.pytest_cache,.ruff_cache | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue; Get-ChildItem -Recurse -Include *.pyc,*.pyo | Remove-Item -Force -ErrorAction SilentlyContinue"
else
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
endif
