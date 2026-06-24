# Linknode Energy Monitor — Claude Code Configuration

<!--
Project-specific instructions. Loads after the global ~/.claude/CLAUDE.md,
which already provides identity, cross-project rules, and workflow
preferences — not duplicated here.
-->

## What this is

Linknode Energy Monitor is a production web app that shows real-time household
power consumption. An Eagle-200 smart meter on the home network POSTs XML to a
Flask ingest service, which writes to InfluxDB (time-series); Grafana renders
the dashboards and an nginx-served static site embeds them at
[linknode.com](https://linknode.com). It runs as four Fly.io apps
(`linknode-web`, `linknode-eagle-monitor`, `linknode-grafana`,
`linknode-influxdb`). Lightweight project — no Ruflo. The repo root is primarily
the **Playwright E2E/regression harness**; the deployed services live under
`fly/`.

## Run / build / test

There is **no local long-running entry point** — the app is the deployed Fly.io
stack, so there is no `run.cmd`. "Running" locally means exercising the E2E
suite (which targets production) or deploying a service. Commands work from
PowerShell or Git Bash.

```bash
npm install                  # first time
npx playwright install       # browser binaries (or: npm run playwright:install)

# Test (Playwright; targets the live site)
npm test                     # full suite
npm run test:api             # @api    integration
npm run test:visual          # @visual regression
npm run test:perf            # @performance
npm run test:a11y            # @accessibility
npm run test:phase3          # advanced visual/perf profiling

# Regression baselines
npm run baseline:compare     # compare live site to test-baselines/baseline.json
npm run baseline:capture     # re-capture after an intentional change

# Deploy (a push to main auto-deploys via GitHub Actions — see Invariants)
cd fly/web && flyctl deploy            # or eagle-monitor / grafana / influxdb
```

## Architecture

| Path | What |
|---|---|
| `fly/web/` | nginx + `index.html` (static front end, embeds Grafana). CSP lives in `fly/web/nginx.conf`. |
| `fly/eagle-monitor/` | Python/Flask ingest API (`app.py`) — parses Eagle-200 XML, writes InfluxDB, serves `/api/stats`, `/health`. |
| `fly/grafana/` | Grafana config + provisioned dashboards (`fly.toml`, `grafana.ini`). |
| `fly/influxdb/` | InfluxDB time-series store. |
| `e2e/` | Playwright tests (`tests/`, `pages/`, `utils/`). |
| `scripts/` | `capture-baseline.ts` / `compare-baseline.ts` + deploy helpers. |
| `test-baselines/` | Regression baselines (`baseline.json`, visual screenshots). |
| `docs/THEORY_OF_OPERATION.md`, `docs/ARCHITECTURE.md` | System design + data flow (current, authoritative). |
| `docs/archive/` | Historical docs, incl. the retired Kubernetes/Rackspace era. |

## Invariants & "do not regress"

- **Grafana anonymous role must stay `Viewer`** (`GF_AUTH_ANONYMOUS_ORG_ROLE` in
  `fly/grafana/fly.toml`). **Why:** it was once `Admin`, giving any anonymous
  visitor full admin (edit/delete dashboards, datasources). Externally reported,
  fixed Jan 2026. Never widen it.
- **No secrets in repo files** (scripts, docs, `.env`). **Why:** an InfluxDB
  token (`my-super-secret-auth-token`) was committed and lived in git history;
  rotated & revoked Jan 2026. Use Fly secrets + GitHub secrets only.
- **Keep the `energy.linknode.com` Fly cert + its two Cloudflare DNS records.**
  `_fly-ownership` TXT and `_acme-challenge` CNAME (both **DNS-only / grey
  cloud**) must stay so Fly can auto-renew. **Why:** the cert lapsed once and the
  subdomain returned Cloudflare 525 (SSL handshake failed) for ~2 months.
- **If you change the Grafana host, update the CSP.** `index.html` embeds
  `linknode-grafana.fly.dev`, which is whitelisted in `fly/web/nginx.conf`
  (`frame-src` / `connect-src` / `script-src`). Change one without the other and
  the embed silently breaks.
- **Pushing to `main` is a production deploy** via
  `.github/workflows/deploy-fly.yml`. Treat `git push` as outward-facing.

## Project-specific tooling

- **flyctl** — deploy/manage the four Fly apps (`fly status -a linknode-<svc>`,
  `fly certs ...`, `fly secrets ...`). App org/region: `ord`.
- **Playwright** — E2E + visual + a11y + perf, plus a custom baseline-compare
  regression system under `scripts/`.

## Open questions / known gaps

- Actively developed — recent work (May 2026) added eagle-monitor in-process
  staleness monitoring + Pushover outage alerting; accumulating work lives in
  `CHANGELOG.md` under `[Unreleased]`.
- The retired **Kubernetes/Rackspace** docs were archived to `docs/archive/`
  (`PROJECT_STATE.md`, `PROJECT_STATUS.md`); `README.md` is the authoritative
  current overview.
- Potential next work (none committed): historical-data views, multi-region.
