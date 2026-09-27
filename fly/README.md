# Fly.io Deployment Structure

This directory holds the one Fly.io app of the Linknode energy monitor:
`linknode-eagle-monitor`, the ingest and API service with its SQLite store. The site
(linknode.com) is not on Fly; it is a Cloudflare Worker configured in `web/`.

The former `influxdb/`, `grafana/` and `web/` (nginx) apps were destroyed on
2026-09-27. Their docs live in `docs/archive/`.

## ⚠️ Security Notice

**IMPORTANT**: This project requires secrets for authentication. Before deploying:
1. Read the [SECRETS_SETUP.md](SECRETS_SETUP.md) guide
2. Configure all required secrets using `fly secrets set`
3. Never commit secrets to version control

## Directory Structure

```
fly/
├── eagle-monitor/              # Ingest + API service (the only Fly app)
│   ├── Dockerfile              # Python 3.11 slim container
│   ├── fly.toml                # App config: volume mount, checks, 256MB VM
│   ├── app.py                  # Flask routes, auth, SSE, scheduler
│   ├── store.py                # SQLite time-series store
│   ├── dashboard.py            # /api/dashboard series and panel math
│   ├── monitor_data_staleness.py  # Slack/Pushover outage alerting
│   ├── security_monitor.py     # Security tracking
│   ├── test_*.py               # Unit tests (run by CI before deploy)
│   └── requirements.txt
│
├── README.md                   # This file
├── SECRETS_SETUP.md            # Secrets for the Fly app and CI
├── QUICK_CICD_SETUP.md         # GitHub Actions setup
└── FLY_TOKEN_UPDATE_PROCEDURE.md  # Rotating FLY_API_TOKEN
```

## Required Files

### Eagle Monitor Service
- **Dockerfile**: `python:3.11-slim` with Flask and APScheduler
- **fly.toml**: region `ord`, shared-cpu-1x 256MB, volume `eagle_data` mounted at
  `/data`, HTTP (`/health`) and TCP checks
- **app.py**, **store.py**, **dashboard.py**, **monitor_data_staleness.py**,
  **security_monitor.py**: application code
- **requirements.txt**: Python dependencies

## Deployment

Pushing to `main` with changes under `fly/eagle-monitor/**` runs
`.github/workflows/deploy-fly.yml`: unit tests, image capture for rollback, deploy,
health check. To deploy by hand:

```bash
cd fly/eagle-monitor
flyctl deploy --remote-only
```

**Run exactly one machine.** The SQLite database lives on the machine's volume, so a
second machine would get its own separate database. Never scale past one.

The volume `eagle_data` is 1GB, encrypted, with daily snapshots kept 14 days. Cost is
about $2.58/month (machine $2.43, volume $0.15).

## Environment Variables

Set in `fly/eagle-monitor/fly.toml` (`[env]`):

- **PORT**: `5000`
- **DB_PATH**: `/data/energy.db`
- **MONITOR_STATE_FILE**: `/data/monitor_state.json`

Optional, with defaults in `app.py`: `RETENTION_DAYS` (1825), `STALE_THRESHOLD_MINUTES`
(5), `EAGLE_USERNAME` (`eagle`), and the BC Hydro rate settings (`TIER1_RATE`,
`TIER2_RATE`, `DAILY_THRESHOLD_KWH`, `BILLING_CYCLE_START_DAY`, `BASIC_CHARGE_DAILY`).

## Secrets Setup

See [SECRETS_SETUP.md](SECRETS_SETUP.md) for detailed instructions on setting up the required secrets.

## Troubleshooting

- **Health and data issues**: See [docs/HEALTH_CHECKS.md](../docs/HEALTH_CHECKS.md)
- **Architecture and operations**: See [docs/THEORY_OF_OPERATION.md](../docs/THEORY_OF_OPERATION.md)
- **Service details**: See [eagle-monitor/README.md](eagle-monitor/README.md)
