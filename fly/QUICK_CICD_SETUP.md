# Quick CI/CD Setup - Final Steps

Two GitHub Actions workflows deploy production on pushes to `main`:

| Workflow | Trigger paths | Deploys |
|----------|---------------|---------|
| `deploy-fly.yml` | `fly/eagle-monitor/**` | Fly app `linknode-eagle-monitor` (unit tests first, rollback image captured; the rollback itself has never run, see `docs/HEALTH_CHECKS.md`) |
| `deploy-web.yml` | `web/**` | Cloudflare Worker `linknode-web` (the linknode.com site) |

Docs-only changes deploy nothing.

## Add the Secrets to GitHub

1. Go to: https://github.com/murr2k/linknode-com/settings/secrets/actions
2. Click "New repository secret" for each:
   - **`FLY_API_TOKEN`**: a Fly.io deploy token. Create one with
     `fly tokens create org personal --name github-actions-deploy` (see
     [FLY_TOKEN_UPDATE_PROCEDURE.md](FLY_TOKEN_UPDATE_PROCEDURE.md)).
   - **`CLOUDFLARE_API_TOKEN`**: a Cloudflare API token that can edit Workers for the
     account and the `linknode.com` zone routes.
   - **`CLOUDFLARE_ACCOUNT_ID`**: the Cloudflare account ID.
3. Never paste token values into docs, commits or issues.

`INFLUXDB_TOKEN` and `GRAFANA_ADMIN_PASSWORD` are retired and can be deleted.

## Test Your Setup

Run either workflow by hand from the Actions tab (both accept `workflow_dispatch`), or
push a change under the trigger paths:

```bash
gh workflow run deploy-web.yml
gh workflow run deploy-fly.yml
gh run list -L 3
```

Then watch the deployment at:
https://github.com/murr2k/linknode-com/actions

After a site deploy, `https://linknode-web.murr2k.workers.dev/build-info.json` shows the
deployed commit. After a Fly deploy, `https://linknode-eagle-monitor.fly.dev/health`
should return `"status":"healthy"`.

## That's it! 🎉

Your CI/CD pipeline is now active. Every push to `main` that changes
`fly/eagle-monitor/**` or `web/**` deploys that part automatically. Treat `git push` to
`main` as a production deploy.
