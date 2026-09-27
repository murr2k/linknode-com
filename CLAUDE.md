# Linknode Energy Monitor: Claude Code Configuration

<!--
Project-specific instructions. Loads after the global ~/.claude/CLAUDE.md,
which already provides identity, cross-project rules, and workflow
preferences (not duplicated here).
-->

## What this is

Linknode Energy Monitor is a production web app that shows real-time household
power consumption at [linknode.com](https://linknode.com). A Raspberry Pi on the
home network reads the Eagle-200 smart meter's local API and POSTs XML to a
Flask ingest service on Fly.io (`linknode-eagle-monitor`), which stores every
reading in SQLite on a Fly volume and serves the stats, dashboard and live-stream
APIs. The static site is a Cloudflare Worker (static assets only) that charts the
data natively with uPlot. Lightweight project, no Ruflo.

Until 2026-09-27 this ran as four Fly apps (nginx site, Grafana, InfluxDB and the
ingest service); the other three were retired to cut cost to ~$2.58/month. See
`CHANGELOG.md` and `docs/THEORY_OF_OPERATION.md`.

## Run / build / test

```bash
npm install                  # first time (wrangler for the site)
run.cmd                      # local site preview: wrangler dev on http://127.0.0.1:8771
                             # (reads live data from the production API)

# Backend unit tests (also gate every eagle-monitor deploy in CI)
python -m venv .venv && .venv\Scripts\pip install -r fly/eagle-monitor/requirements.txt
.venv\Scripts\python -m unittest discover -s fly/eagle-monitor -p "test_*.py"

# Manual deploys (normally CI does it on push to main; see Invariants)
cd fly/eagle-monitor && flyctl deploy --remote-only    # ingest API
npx wrangler deploy --config web/wrangler.jsonc         # site (needs wrangler login)
```

The Playwright suites the `package.json` scripts refer to were deleted in
January 2026; those scripts no longer work.

## Architecture

| Path | What |
|---|---|
| `fly/eagle-monitor/` | The only Fly app. `app.py` (Flask: `/eagle` ingest, `/api/stats`, `/api/dashboard`, `/api/stream` SSE, `/health`), `store.py` (SQLite), `dashboard.py` (chart + panel math), `monitor_data_staleness.py` (Slack/Pushover outage alerts). |
| `web/public/` | The site: `index.html`, `_headers` (CSP and security headers), `404.html`, vendored uPlot. |
| `web/wrangler.jsonc` | Cloudflare Worker config: assets only, routes `linknode.com/*` and `www.linknode.com/*`. |
| `scripts/eagle_bypass.py`, `deploy/` | The Pi uploader (systemd `eagle-bypass.service`). |
| `.github/workflows/` | `deploy-fly.yml` (eagle-monitor), `deploy-web.yml` (site). |
| `docs/THEORY_OF_OPERATION.md` | System design + data flow (current, authoritative). |
| `docs/archive/` | Historical docs: the retired Kubernetes/Rackspace era and the Grafana/InfluxDB stack. |

## Invariants & "do not regress"

- **eagle-monitor runs exactly one machine.** The SQLite database lives on the
  `eagle_data` volume attached to it; a second machine would get its own
  separate database. Never `fly scale count` above 1. **Why:** the volume is
  the only copy of the history (plus Fly's daily snapshots, kept 14 days).
- **Never destroy the `eagle_data` volume** (`vol_re1oqe3mzqodx6d4`, ord).
  **Why:** everything since 2026-08-27 lives there; InfluxDB, which held the
  older history, was deliberately destroyed.
- **The site's CSP lives in `web/public/_headers`**, and its `connect-src` must
  list `https://linknode-eagle-monitor.fly.dev`. Change the API host and you must
  change both, or the page's fetches and live stream break silently.
- **eagle-monitor's CORS allow-list (`app.py`) must include `https://linknode.com`
  and `https://www.linknode.com`.** The page calls the API cross-origin.
- **Keep Rocket Loader off** for the linknode.com zone. It rewrites the page's
  scripts and conflicts with the CSP.
- **linknode.com, www and energy DNS records are proxied placeholders**
  (`AAAA 100::`). Worker routes serve the site; a Cloudflare redirect rule sends
  `energy.linknode.com` to `https://linknode.com/#energy-dashboard`. Don't point
  them back at Fly hostnames: those apps no longer exist.
- **No secrets in repo files** (scripts, docs, `.env`). **Why:** an InfluxDB
  token was once committed and lived in git history. Use Fly secrets and GitHub
  secrets only (`FLY_API_TOKEN`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`).
- **Pushing to `main` is a production deploy**: `deploy-fly.yml` for
  `fly/eagle-monitor/**`, `deploy-web.yml` for `web/**`. Treat `git push` as
  outward-facing.

## Project-specific tooling

- **flyctl**: manage the one Fly app (`fly status -a linknode-eagle-monitor`,
  `fly logs`, `fly secrets`, `fly volumes list`). Region `ord`. The Fly MCP server
  (`flyctl mcp server`) is installed at user scope.
- **wrangler** (repo devDependency): site preview and deploys.
- **Cloudflare API MCP** (`https://mcp.cloudflare.com/mcp`): zone work (DNS,
  redirect rules, zone settings, Worker routes).
- **`linknode-stats` skill**: how to read health from the Pi and `/api/stats`.

## Open questions / known gaps

- Fly `shared-cpu-1x` throttles to 6.25% of a core once burst credits run out;
  keep one-off data jobs in the machine light (see project memory).
- The disabled e2e/regression workflows reference deleted suites.
- Potential next work (none committed): longer history views, CSP without
  `'unsafe-inline'` (the page has inline scripts and styles).
