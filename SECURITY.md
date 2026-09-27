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

Production is reachable at:

- `https://linknode.com` (and `www`): static site served by a Cloudflare Worker
  (`linknode-web`, config `web/wrangler.jsonc`)
- `https://linknode-eagle-monitor.fly.dev`: power-monitoring ingest and API, the
  only Fly.io app (Flask, SQLite on the `eagle_data` volume)
- `https://energy.linknode.com`: a Cloudflare redirect rule (301 to
  `https://linknode.com/#energy-dashboard`); no service behind it

Out of scope (decommissioned; historical docs only, under `docs/archive/`):

- The Fly apps `linknode-web` (nginx), `linknode-grafana` (Grafana) and
  `linknode-influxdb` (InfluxDB), destroyed on 2026-09-27
- The retired Rackspace/Kubernetes deployment

## Credential Management

- **No secrets are stored in this repository.** Credentials live in **Fly.io
  secrets** and **GitHub Actions secrets** only:
  - Fly (`linknode-eagle-monitor`): `EAGLE_PASSWORD` (ingest Basic auth),
    `SLACK_WEBHOOK_URL`, `PUSHOVER_API_TOKEN`, `PUSHOVER_USER_KEY`
  - GitHub: `FLY_API_TOKEN` (Fly deploy), `CLOUDFLARE_API_TOKEN` and
    `CLOUDFLARE_ACCOUNT_ID` (site deploy)
  - The Raspberry Pi uploader keeps its credentials in `/etc/eagle-bypass.env`
    (root, mode 0600) on the Pi, never in the repo
- Retired: `INFLUXDB_TOKEN` and `GRAFANA_ADMIN_PASSWORD` (GitHub), and the
  per-app secrets of the destroyed Fly apps.
- `.env` and `*.secret.*` files are git-ignored and must never be committed.
- Credentials are rotated when exposure is suspected.

### Historical incidents (retired systems)

- **Grafana anonymous Admin (fixed January 2026).** `GF_AUTH_ANONYMOUS_ORG_ROLE`
  was `Admin`, giving any anonymous visitor full admin rights (edit/delete
  dashboards and datasources). Externally reported and changed to `Viewer`.
  Grafana was retired on 2026-09-27.
- **Committed InfluxDB token (rotated January 2026).** The token
  `my-super-secret-auth-token` was committed and lived in git history; it was
  rotated and revoked. InfluxDB was retired on 2026-09-27.

## Security Measures in Place

- **Transport:** TLS/HTTPS enforced at Cloudflare (site) and the Fly proxy (API).
- **Site headers:** Content-Security-Policy, HSTS, X-Frame-Options,
  X-Content-Type-Options, Referrer-Policy and Permissions-Policy set in
  `web/public/_headers`. `connect-src` allows only the site itself and
  `https://linknode-eagle-monitor.fly.dev`; `frame-src` is `'none'`. Rocket
  Loader is off for the zone because it conflicts with the CSP.
- **Ingest:** `POST /eagle` requires HTTP Basic auth and is rate limited
  (60 requests/minute per client).
- **Read API:** `/api/stats`, `/api/dashboard`, `/api/stream` and `/health` are
  public and read-only (the optional `EAGLE_API_KEY` is not set). CORS is
  limited to an allow-list of site origins; the SSE stream sends
  `Access-Control-Allow-Origin: *`.
- **Data:** the `eagle_data` volume is encrypted at rest, with daily snapshots
  kept 14 days.
- **CI/CD:** automated security scanning runs on pushes and pull requests
  (`.github/workflows/security-scan.yml`), including a check that the required
  headers are present in `web/public/_headers`.

## Hardening Recommendations for Re-deployers

If you fork and self-host:

1. Set every secret via your platform's secret store (Fly secrets, GitHub
   secrets, or equivalent) — never inline in config or scripts.
2. Generate strong, unique tokens/passwords; rotate them on a schedule.
3. Keep the ingest endpoint behind authentication; set an API key if the read
   endpoints should not be public.
4. Terminate TLS at the edge and keep HSTS + CSP enabled.
5. Apply authentication and rate limiting to any publicly exposed write endpoint.
