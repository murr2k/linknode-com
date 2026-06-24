# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Linknode Energy Monitor, please report
it **privately** — do not open a public GitHub issue.

- **Email:** murr2k@gmail.com
- Include: a description of the issue, affected URL/endpoint or component, and
  steps to reproduce (a proof-of-concept if available).
- You can expect an initial acknowledgement within a few days. Confirmed issues
  will be fixed and deployed as a priority; please allow reasonable time for a fix
  before any public disclosure.

Responsible disclosure is appreciated and credited — for example, the Grafana
anonymous-access hardening in `1.2.0` was the result of an external report (see
`CHANGELOG.md`).

## Scope

Production lives on Fly.io and is reachable at:

- `https://linknode.com` — web front end (nginx)
- `https://linknode-grafana.fly.dev` / `https://energy.linknode.com` — Grafana
- `https://linknode-eagle-monitor.fly.dev` — power-monitoring API

The retired Rackspace/Kubernetes deployment is **out of scope** (decommissioned;
historical docs only, under `docs/archive/`).

## Credential Management

- **No secrets are stored in this repository.** Application credentials live in
  **Fly.io secrets** (per app) and **GitHub Actions secrets** (for CI/CD) — e.g.
  `INFLUXDB_TOKEN`, `EAGLE_PASSWORD`, `GF_SECURITY_ADMIN_PASSWORD`,
  `FLY_API_TOKEN`.
- `.env` and `*.secret.*` files are git-ignored and must never be committed.
- Credentials are rotated when exposure is suspected. The InfluxDB API token was
  rotated and the prior token revoked in January 2026.

## Security Measures in Place

- **Transport:** TLS/HTTPS enforced; HSTS and a Content-Security-Policy set in
  `fly/web/nginx.conf`.
- **Grafana:** anonymous users are limited to the read-only **Viewer** role;
  admin actions require authentication. (Do not widen the anonymous role — see
  the invariants in `CLAUDE.md`.)
- **API:** authentication and rate limiting on the Eagle monitor service.
- **CI/CD:** automated security scanning runs on pushes and pull requests
  (`.github/workflows/security-scan.yml`).

## Hardening Recommendations for Re-deployers

If you fork and self-host:

1. Set every secret via your platform's secret store (Fly secrets, GitHub
   secrets, or equivalent) — never inline in config or scripts.
2. Generate strong, unique tokens/passwords; rotate them on a schedule.
3. Keep Grafana anonymous access at Viewer (or disable it) and protect the admin
   login.
4. Terminate TLS at the edge and keep HSTS + CSP enabled.
5. Apply authentication and rate limiting to any publicly exposed API endpoint.
