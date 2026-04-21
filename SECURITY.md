# Security Policy

## Supported versions

Only the latest minor release receives security updates.

## Reporting a vulnerability

Please **do not** open public GitHub issues for security reports. Instead, send
an email to the maintainers (listed in `pyproject.toml`) with:

- a clear description of the issue,
- reproduction steps or a minimal PoC,
- the affected version(s),
- the potential impact.

We aim to acknowledge reports within 72 hours and to publish a fix or
mitigation within 14 days for critical issues.

## Hardening guidelines

- **Never commit `.env` or any real secrets.** Use a secret manager (Vault,
  SOPS, AWS Secrets Manager, GitLab CI variables) in production.
- Generate a unique `FERNET_KEYS` value for each environment with
  `python scripts/generate_fernet_key.py`. Rotate keys by prepending a new one
  to the comma-separated list; old entries remain valid for decryption until
  you re-encrypt existing rows and remove them.
- Run the services as a non-root user (the provided Docker image already does).
- Restrict network access to PostgreSQL, Redis and RabbitMQ to the internal
  docker/k8s network — never expose them publicly.
- Keep bot tokens scoped per-environment; use webhooks with a reverse proxy
  (`caddy`, `traefik`) instead of long-polling for public-facing production.
- Enable TLS everywhere in production (Postgres, Redis, RabbitMQ).
