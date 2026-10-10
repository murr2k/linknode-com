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
data natively with uPlot. Since 2026-10-10 the Pi also uploads the Honeywell T5
thermostat's log, and the site charts heating run time against the outdoor
temperature and forecasts the FortisBC gas bill. Lightweight project, no Ruflo.

Until 2026-09-27 this ran as four Fly apps (nginx site, Grafana, InfluxDB and the
ingest service); the other three were retired, and the machine moved from `ord` to
`iad`, to cut cost to ~$2.09/month. See
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
| `fly/eagle-monitor/` | The only Fly app. `app.py` (Flask: `/eagle` ingest, `/api/stats`, `/api/dashboard`, `/api/stream` SSE, `/health` liveness, `/health/data` telemetry freshness), `store.py` (SQLite), `dashboard.py` (chart + panel math), `monitor_data_staleness.py` (Slack/Pushover outage alerts), `site_traffic.py` (the site's traffic figures from Cloudflare, published as `site_traffic` in `/api/stats`). Heating: `/thermostat` ingest and `/api/heating` in `app.py`, `thermostat.py` (run time from the event log), `gas.py` (FortisBC bill and the gas usage model), `weather.py` (outdoor temperature from Open-Meteo). |
| `web/public/` | The site: `index.html`, `_headers` (CSP and security headers), `404.html`, vendored uPlot. |
| `web/wrangler.jsonc` | Cloudflare Worker config: assets only, routes `linknode.com/*` and `www.linknode.com/*`. |
| `scripts/eagle_bypass.py`, `deploy/` | The Pi uploader (systemd `eagle-bypass.service`). |
| `scripts/t5_upload.py`, `deploy/t5-upload.service` | The Pi's thermostat uploader (systemd `t5-upload.service`): posts the rows the `t5-runtime` logger writes to `/thermostat`. The logger itself belongs to the `1344-network` repo. Installed by hand, not by CI. |
| `scripts/linknode_watchdog.py`, `deploy/linknode-watchdog.*` | The Pi watchdog (systemd timer): Pushover siren when the ingest service or the site stops answering. Installed by hand, not by CI. |
| `.github/workflows/` | `deploy-fly.yml` (eagle-monitor), `deploy-web.yml` (site). |
| `docs/THEORY_OF_OPERATION.md` | System design + data flow (current, authoritative). |
| `docs/archive/` | Historical docs: the retired Kubernetes/Rackspace era and the Grafana/InfluxDB stack. |

## Invariants & "do not regress"

- **eagle-monitor runs exactly one machine.** The SQLite database lives on the
  `eagle_data` volume attached to it; a second machine would get its own
  separate database. Never `fly scale count` above 1. **Why:** the volume is
  the only copy of the history (plus Fly's daily snapshots, kept 14 days).
- **Never destroy the `eagle_data` volume** (`vol_491xj8k1y8wlgl3r`, iad).
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
- **The Pi watchdog's backstop must stay well above the alarm's threshold.**
  `WATCH_BACKSTOP_SECS` in `/etc/linknode-watchdog.env` on the Pi is 86400;
  `STALE_THRESHOLD_MINUTES` in `fly/eagle-monitor/fly.toml` is 30 (and must be an
  integer, or the service does not start). **Why:** at or below the threshold the
  watchdog's siren comes within minutes of the alarm's on every outage.
- **The Pi's files are installed over SSH, not by CI** (`deploy/README.md`). The
  watchdog judges `/health/data`, `/api/stats` and the page by the shape of their
  replies: before a push that renames or removes what it reads, install a watchdog that
  accepts both the old and the new reply.
- **Pushing to `main` is a production deploy**: `deploy-fly.yml` for
  `fly/eagle-monitor/**`, `deploy-web.yml` for `web/**`. Treat `git push` as
  outward-facing.

## Project-specific tooling

- **flyctl**: manage the one Fly app (`fly status -a linknode-eagle-monitor`,
  `fly logs`, `fly secrets`, `fly volumes list`). Region `iad` (moved from `ord`
  2026-09-27: `iad`/`ewr` have no regional price markup, `ord` is 1.25x). The Fly MCP server
  (`flyctl mcp server`) is installed at user scope.
- **wrangler** (repo devDependency): site preview and deploys.
- **Cloudflare API MCP** (`https://mcp.cloudflare.com/mcp`): zone work (DNS,
  redirect rules, zone settings, Worker routes).
- **`linknode-stats` skill**: how to read health from the Pi and the ingest service
  (`/health/data`, `/api/stats`).

## Open questions / known gaps

- **Outage alerting: the bar.** linknode.com is not mission critical. The alerting only
  has to say that the system has stopped reporting, so it can be fixed within a day or
  two: an outage that is never reported, and noise, matter; the speed of an alert matters
  little. A review on 2026-10-03 found many defects. Seven fixes were agreed against that
  bar and made the same day; `docs/ALERTING.md` ("Changes made on 2026-10-03") lists them
  and names the defects deliberately left alone. Do not gold-plate the alerting beyond
  that bar.

- **BC Hydro billing values change every April 1** (Step 1 rate and basic charge under
  BCUC order G-42-25; the rate rider and transit levy change too). The defaults live in
  `fly/eagle-monitor/app.py` and are checked by tests that reproduce the Jul 30 and Sep 29,
  2026 bills (`test_api.TestBilling`); when a new bill shows different values, update the
  defaults and those tests' expected lines together. Each new bill also carries the next
  meter read date: set the `BILLING_NEXT_READ` default in `app.py` to it, or the cycle
  length and the Bill Forecast's end date fall back to the nominal 26th.

- **Gas is modelled, not metered.** FortisBC reads the meter monthly, so `gas.py` estimates
  usage as `GAS_BASE_GJ_PER_DAY` (0.046, from the summer 2026 bills) plus the furnace's input
  rating for each hour the thermostat called for heat. `FURNACE_INPUT_BTUH` is unset, so a
  60,000 BTU/h placeholder is used and the page says so: set it in `fly.toml` when the
  nameplate value is known, then check the model against each winter bill (the meter resolves
  about 0.13 GJ). The summer base load is high for a range alone and probably includes pilot
  lights; not confirmed.

- **FortisBC values change with the bills.** The per-GJ rates in `gas.py` moved on Jul 1, 2026
  (storage and transport) and are checked by `test_heating.TestGasBill` against real bills:
  update both together. Each bill also carries its meter read date: add it to the
  `GAS_READ_DATES` default (comma separated), or the period falls back to starting on the 1st.

- **The Pi is shared with the `1344-network` project**, which owns the `t5-runtime` logger and
  the Pi's Wi-Fi link to the thermostat's network. `t5_upload.py` only reads that logger's two
  files. After any change on the Pi check all four units (`eagle-bypass.service`,
  `linknode-watchdog.timer`, `t5-runtime.service`, `t5-upload.service`).

- Fly `shared-cpu-1x` throttles to 6.25% of a core once burst credits run out;
  keep one-off data jobs in the machine light (see project memory).
- The disabled e2e/regression workflows reference deleted suites.
- Potential next work (none committed): longer history views, CSP without
  `'unsafe-inline'` (the page has inline scripts and styles).
