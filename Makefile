# =========================================================================
# Developer shortcuts. Usage: `make <target>`.
# On Windows, install GNU Make (`choco install make`) or use the underlying
# commands directly.
# =========================================================================

PY ?= python
PIP ?= $(PY) -m pip
COMPOSE ?= docker compose

.PHONY: help install lint fmt typecheck test test-unit test-int cov \
        up down logs ps build \
        migrate migration \
        wb-bot ozon-bot task-bot network-bot admin-api worker beat \
        clean

help:
	@echo "Common targets:"
	@echo "  install       Install package + dev extras in editable mode"
	@echo "  lint          Run ruff lint"
	@echo "  fmt           Run ruff formatter"
	@echo "  typecheck     Run mypy"
	@echo "  test          Run full test suite"
	@echo "  test-unit     Run unit tests only"
	@echo "  test-int      Run integration tests (requires stack)"
	@echo "  cov           Coverage report"
	@echo "  up / down     docker compose up / down"
	@echo "  build         Build docker images"
	@echo "  migrate       Apply alembic migrations"
	@echo "  migration m=\"msg\"  Autogenerate a new migration"

install:
	$(PIP) install -U pip
	$(PIP) install -e ".[dev]"
	pre-commit install || true

lint:
	ruff check src tests

fmt:
	ruff format src tests
	ruff check --fix src tests

typecheck:
	mypy src

test:
	pytest

test-unit:
	pytest -m "not integration"

test-int:
	pytest -m integration

cov:
	pytest --cov-report=html
	@echo "HTML report: htmlcov/index.html"

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down -v

logs:
	$(COMPOSE) logs -f --tail=200

ps:
	$(COMPOSE) ps

build:
	$(COMPOSE) build

migrate:
	alembic upgrade head

migration:
	@if [ -z "$(m)" ]; then echo "Usage: make migration m=\"your message\""; exit 1; fi
	alembic revision --autogenerate -m "$(m)"

wb-bot:       ; wb-bot
ozon-bot:     ; ozon-bot
task-bot:     ; task-planner-bot
network-bot:  ; network-bot
admin-api:    ; admin-api
worker:       ; helpers-worker
beat:         ; helpers-beat

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
