# Session Handoff — Linknode Energy Monitor

> **For:** the next Claude instance picking up this work.
> **Date:** 2026-05-24 · **User:** murr2k@gmail.com

## TL;DR

This session added a **Pushover emergency siren** to the power-meter outage
alerting, **fixed broken CI auto-deploy** (expired Fly token), made the
**Mermaid diagrams theme-adaptive**, and built a **Markdown→whitepaper HTML
renderer**. Everything code/doc-related is committed and deployed except two
untracked preview artifacts (see below).

## Repo state

- Branch **`main`** @ `e5cb5cc` — pushed (origin/main matches).
- This session's commits (newest first):
  - `e5cb5cc` docs: make Mermaid diagrams theme-adaptive
  - `5b22ab0` docs(pushover): advertise Pushover alerting + add dedup regression tests
  - `70d74c2` feat(eagle-monitor): add Pushover siren alert on data-staleness outage
- **Untracked / not committed** (intentionally left for a decision):
  - `docs/THEORY_OF_OPERATION.html` — rendered whitepaper preview
  - `scripts/render_doc.py` — reusable Markdown→whitepaper HTML renderer

## What we did (chronological)

1. **Pushover siren alert** — `fly/eagle-monitor/monitor_data_staleness.py`.
   New `_send_pushover_alert()` fires an **emergency-priority (priority=2)**
   push with `sound:siren`, `retry:60`, `expire:3600` — repeats until the user
   acknowledges in the app. Fires **only on the healthy→unhealthy transition**
   (one alert per outage); **recovery stays Slack-only**. Credentials read from
   env: `PUSHOVER_API_TOKEN` / `PUSHOVER_USER_KEY`. Wired through `app.py` (~L119).
2. **Fixed CI auto-deploy** — every push-deploy since ~2025-07 had been
   failing Fly auth (`missing third-party discharge token`); production was
   being updated by manual `fly deploy`. Root cause: the `FLY_API_TOKEN` GitHub
   secret's discharge token had expired. Rotated to a fresh **org deploy token**
   (`fly tokens create org personal --name github-actions-deploy`) and reset the
   GitHub secret. Push-to-`main` now deploys green again (verified, multi-service).
3. **Regression tests** — `fly/eagle-monitor/test_monitor_data_staleness.py`,
   now **21 tests**. Added: Pushover-on-outage, not-on-recovery, skipped-when-
   unconfigured, and two that assert **exactly one alert per sustained outage /
   recovery** (locks in the state-transition de-duplication).
4. **Advertised the feature** — README "Outage Alerting" group; `fly/web/index.html`
   "Monitoring & Alerting" Technology Stack entry (live on linknode.com); CHANGELOG
   `Added` (Pushover) + `Fixed` (restored CI auto-deploy).
5. **Theme-adaptive Mermaid** — stripped hardcoded `style ... fill:` overrides
   from `docs/THEORY_OF_OPERATION.md` (7) and `docs/BC_HYDRO_RATE_ANALYSIS.md` (4)
   so the renderer's theme drives colors (legible in light AND dark). README and
   HONEYWELL had no overrides. All 4 affected diagrams validated via Mermaid MCP.
6. **Whitepaper renderer** — `scripts/render_doc.py` (uses python `markdown`).
   Keeps Mermaid blocks as client-side `<pre class="mermaid">` (v11 CDN, `neutral`
   theme), HTML-escapes diagram source so `<br/>` survives, and auto-inserts a
   blank line before tables glued under `**bold:**` labels (strict Markdown needs
   it; GitHub doesn't). Produced `docs/THEORY_OF_OPERATION.html` (10 diagrams, 9 tables).

## Deployed / live state

- **eagle-monitor**: Pushover code live; `PUSHOVER_API_TOKEN` + `PUSHOVER_USER_KEY`
  Fly secrets show `Deployed`; `/health` healthy.
- **web**: Technology Stack update live (`curl https://linknode.com` shows the Pushover line).
- **CI**: `deploy-fly.yml` auto-deploy working again.

## Open items / decisions pending

- **`pushover_expire`** left at 1h. User was satisfied after we verified
  one-message-per-event; lowering it only matters for *unacknowledged* alerts.
- **THEORY html + renderer**: awaiting user choice — commit as-is? generate a
  **PDF**? **vendor Mermaid** locally for offline viewing? (Currently needs internet
  for the CDN.)
- **Workflow**: user chose **commit directly to `main`** this session, but their
  history is **PR-based** (`#37`–`#40`). Confirm before assuming direct-to-main next time.

## Security / housekeeping (flagged, NOT done)

- Pushover **user key + API token appeared in the chat transcript**. They only
  allow sending pushes to the user's devices (not account access). Can rotate via
  Pushover dashboard, then re-run `fly secrets set ...`. **Not stored in this repo.**
- **Old expired Fly token** (id `945736ca…`) still appears in `fly tokens list` —
  can be revoked for hygiene (it's already broken).
- The **new** org deploy token's discharge may also expire eventually → watch for
  the same `missing third-party discharge token` failure signature.
- **Dependabot**: 15 vulnerabilities flagged on the repo (2 high, 12 moderate, 1 low) — unaddressed.
- CI uses **Node 20 actions** (deprecation warnings): `actions/checkout@v4`, `dorny/paths-filter@v3`.

## Environment notes (this machine)

- **Windows**; shell is git-bash. Python **3.14**, **no venv** — `requests` and
  `markdown` were `pip install`ed this session into the global interpreter.
- **No `pytest`** → run tests with `python test_monitor_data_staleness.py` (from
  `fly/eagle-monitor/`). **No `jq`** → parse JSON with python (and use
  `encoding='utf-8'` — some files contain emoji).
- `fly` CLI authed as murr2k@gmail.com; `gh` authed as murr2k. Single Fly org: `personal`.
- **Deploy trigger**: push to `main` touching `fly/**` runs `.github/workflows/deploy-fly.yml`
  (deploys only changed services). **Docs-only changes do NOT deploy.**
- Mermaid MCP validator returns huge SVG output that exceeds the inline limit; it
  saves full JSON to a tool-results file — parse `valid`/`diagramType` with python.

## Quick commands

```bash
# Run the monitor test suite (21 tests)
cd fly/eagle-monitor && python test_monitor_data_staleness.py

# Re-render any doc to whitepaper HTML
python scripts/render_doc.py docs/THEORY_OF_OPERATION.md docs/THEORY_OF_OPERATION.html

# Check Fly secrets / deploy status
fly secrets list -a linknode-eagle-monitor
gh run list --workflow=deploy-fly.yml -L 3
```
