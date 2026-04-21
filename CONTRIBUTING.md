# Contributing

Thank you for considering a contribution! This document describes the
conventions used in this repository.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate       # or .venv\Scripts\Activate.ps1 on Windows
pip install -e ".[dev]"
pre-commit install
```

Copy `.env.example` to `.env`, generate a Fernet key with
`python scripts/generate_fernet_key.py`, and start the infrastructure:

```bash
docker compose up -d postgres redis rabbitmq
alembic upgrade head
```

## Quality gates

All of the following must pass before a PR is merged:

```bash
make lint        # ruff
make typecheck   # mypy --strict
make test        # pytest + coverage
```

Continuous integration runs the same targets; see `.gitlab-ci.yml`.

## Code style

- Strict typing. We run `mypy --strict`; no `Any` without a justification.
- `ruff` is the single source of truth for formatting and linting.
- Public APIs are documented with short docstrings describing **why**, not
  what the code already shows.
- Prefer dataclasses / Pydantic models over untyped dicts.
- No blanket `except Exception: pass`. If you swallow an exception, log it.
- Database sessions must flow through the middleware / dependency layer — do
  not open sessions ad-hoc inside handlers.

## Commit messages

We follow **Conventional Commits**:

```
feat(wb_bot): add reviews auto-reply scheduler
fix(core/http): retry 5xx responses with jitter
docs(readme): update quickstart
```

## Submitting a PR

1. Open an issue describing the motivation (unless the change is trivial).
2. Create a feature branch off `main`.
3. Add or update tests for your change.
4. Run `make lint typecheck test` locally.
5. Open the PR; describe what and why.
6. A maintainer will review. After approval, squash-merge.

Thanks!
