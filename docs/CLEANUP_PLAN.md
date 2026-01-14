# Project Cleanup Plan

**Generated:** 2026-01-14
**Purpose:** Identify deprecated directories and files for potential removal

---

## Executive Summary

The linknode-com project has evolved through several infrastructure iterations:
1. **Kubernetes deployment** (archived July 2025)
2. **Cloudflare tunnel experiments** (abandoned)
3. **Current Fly.io deployment** (active)

This document identifies candidates for cleanup to reduce repository size and confusion.

---

## Directory Status Overview

| Directory | Size | Status | Recommendation |
|-----------|------|--------|----------------|
| `fly/` | 3.2M | **ACTIVE** | Keep - Production infrastructure |
| `docs/` | 40K | **ACTIVE** | Keep - Documentation |
| `e2e/` | 408K | **ACTIVE** | Keep - Test suite |
| `test-baselines/` | 2.9M | **ACTIVE** | Keep - Regression testing |
| `monitoring/` | 132K | **ACTIVE** | Keep - Operations toolkit |
| `scripts/` | 48K | **ACTIVE** | Keep - Build automation |
| `demo-app/` | 232K | **REVIEW** | Partial cleanup possible |
| `websites/` | 2.2M | **ACTIVE** | Keep - Separate projects |
| `.hive-mind/` | 1.8M | **ACTIVE** | Keep - Session cache |
| `.mcp/` | 8K | **ACTIVE** | Keep - MCP config |
| `cloudflare-setup/` | **40M** | **DEPRECATED** | **DELETE** - Contains 40M binary |
| `k8s-archive-20250724/` | 420K | **DEPRECATED** | **DELETE** or move to separate archive |
| `grafana-minimal-test/` | 56K | **DEPRECATED** | **DELETE** - Test artifact |
| `app/` | 68K | **DEPRECATED** | **DELETE** - Superseded by fly/eagle-monitor |

**Total potential savings: ~42M** (primarily from cloudflare-setup binary)

---

## Detailed Analysis

### SAFE TO DELETE

#### 1. `cloudflare-setup/` - 40M (HIGHEST PRIORITY)

**What it contains:**
- `cloudflared-linux-amd64.1` - 40M binary (should never be in git)
- Setup scripts for Cloudflare tunnels
- Worker JavaScript files
- Documentation for tunnel configuration

**Why deprecated:**
- Project now uses simple Cloudflare DNS CNAME to Fly.io
- No tunnels or workers in current architecture
- Binary file bloating repository

**Historical purpose:**
Attempted to use Cloudflare Tunnels to connect local services. Abandoned in favor of direct Fly.io deployment.

**Risk of deletion:** None - not referenced by any active code

---

#### 2. `k8s-archive-20250724/` - 420K

**What it contains:**
- Kubernetes manifests (deployments, services, configmaps)
- Archive script and documentation
- Original K8s implementation details

**Why deprecated:**
- Project migrated from Kubernetes to Fly.io on 2025-07-24
- Directory name explicitly indicates it's an archive
- All functionality recreated in `fly/` directory

**Historical purpose:**
Original production deployment on Kubernetes. Archived when Fly.io was adopted for simpler operations.

**Risk of deletion:** Low - purely historical reference. Consider keeping in a separate branch if needed for reference.

---

#### 3. `grafana-minimal-test/` - 56K

**What it contains:**
- Minimal Dockerfile for Grafana
- fly.toml configuration
- Single test screenshot (42K)

**Why deprecated:**
- One-time proof-of-concept test
- Full Grafana implementation exists in `fly/grafana/`
- No unique value

**Historical purpose:**
Quick test to validate Grafana could run on Fly.io before full implementation.

**Risk of deletion:** None

---

#### 4. `app/` - 68K

**What it contains:**
- `app.py` - Flask API server
- `power_monitor.py` - Original monitoring implementation
- `power_monitor_xml.py` - XML format support
- Dockerfile and requirements.txt

**Why deprecated:**
- Superseded by `fly/eagle-monitor/app.py` (20K, more sophisticated)
- Original implementation before Eagle-200 XML integration
- Not deployed anywhere

**Historical purpose:**
First version of power monitoring API. Replaced by XML-capable version in `fly/eagle-monitor/`.

**Risk of deletion:** Low - all functionality exists in `fly/eagle-monitor/`

---

### REVIEW NEEDED

#### 5. `demo-app/` - 232K

**What it contains:**
- Grafana dashboard JSON iterations
- K8s manifest examples (outdated)
- Eagle XML parsing prototypes
- Test implementations
- Cloudflare setup symlink

**Current usage:**
- Some dashboard JSONs may be referenced
- Used as development sandbox

**Recommendation:**
- Delete K8s manifests (duplicated in archive)
- Delete cloudflare-setup/ subdirectory
- Keep useful dashboard configs if referenced
- Consider consolidating with `fly/grafana/provisioning/`

**Potential savings:** ~100K after cleanup

---

### ROOT LEVEL FILES TO REVIEW

```
/home/murr2k/projects/linknode-com/
├── clear-energy-data.sh      # Keep - operational script
├── fly.toml                  # Review - may be redundant with fly/*/fly.toml
├── package.json              # Keep - npm scripts for testing
├── playwright.config.ts      # Keep - E2E test config
├── tsconfig.json             # Keep - TypeScript config
├── Screenshot 2025-08-06...  # DELETE - untracked screenshot
└── linknode-connect.sh       # Review - check if still used
```

---

## Recommended Cleanup Actions

### Phase 1: Safe Deletions (No Risk)

```bash
# Remove deprecated directories
rm -rf cloudflare-setup/
rm -rf grafana-minimal-test/
rm -rf app/

# Remove untracked files
rm "Screenshot 2025-08-06 180239.png"
```

**Savings: ~40.1M**

### Phase 2: Archive Decisions

**Option A: Delete K8s archive**
```bash
rm -rf k8s-archive-20250724/
```

**Option B: Move to separate branch**
```bash
git checkout -b archive/kubernetes-original
git checkout main
git rm -rf k8s-archive-20250724/
git commit -m "chore: Remove K8s archive from main (preserved in archive/kubernetes-original)"
```

**Savings: 420K**

### Phase 3: Demo App Cleanup

```bash
# Remove outdated K8s manifests from demo-app
rm -f demo-app/eagle-xml-*.yaml
rm -f demo-app/*-deployment.yaml
rm -f demo-app/*-configmap.yaml

# Remove cloudflare symlink
rm -rf demo-app/cloudflare-setup/
```

**Savings: ~50K**

---

## Current vs Proposed Structure

### Before Cleanup
```
linknode-com/                    # ~52M total
├── app/                         # 68K  - DEPRECATED
├── cloudflare-setup/            # 40M  - DEPRECATED (binary!)
├── demo-app/                    # 232K - MIXED
├── docs/                        # 40K  - ACTIVE
├── e2e/                         # 408K - ACTIVE
├── fly/                         # 3.2M - ACTIVE (production)
├── grafana-minimal-test/        # 56K  - DEPRECATED
├── k8s-archive-20250724/        # 420K - DEPRECATED
├── monitoring/                  # 132K - ACTIVE
├── scripts/                     # 48K  - ACTIVE
├── test-baselines/              # 2.9M - ACTIVE
├── websites/                    # 2.2M - ACTIVE
├── .hive-mind/                  # 1.8M - ACTIVE
└── .mcp/                        # 8K   - ACTIVE
```

### After Cleanup
```
linknode-com/                    # ~11M total (-41M)
├── demo-app/                    # 180K - CLEANED
├── docs/                        # 40K  - ACTIVE
├── e2e/                         # 408K - ACTIVE
├── fly/                         # 3.2M - ACTIVE (production)
├── monitoring/                  # 132K - ACTIVE
├── scripts/                     # 48K  - ACTIVE
├── test-baselines/              # 2.9M - ACTIVE
├── websites/                    # 2.2M - ACTIVE
├── .hive-mind/                  # 1.8M - ACTIVE
└── .mcp/                        # 8K   - ACTIVE
```

---

## Decision Points for User

1. **Delete cloudflare-setup/?** (40M savings, no risk)
   - [ ] Yes, delete entirely
   - [ ] No, keep for reference

2. **Delete app/?** (68K savings, low risk)
   - [ ] Yes, delete entirely
   - [ ] No, keep for reference

3. **Delete grafana-minimal-test/?** (56K savings, no risk)
   - [ ] Yes, delete entirely
   - [ ] No, keep for reference

4. **Handle k8s-archive-20250724/?** (420K)
   - [ ] Delete entirely
   - [ ] Move to archive branch
   - [ ] Keep as-is

5. **Clean demo-app/?** (~50K savings)
   - [ ] Yes, remove outdated K8s files
   - [ ] No, keep as-is

---

## Post-Cleanup Verification

After cleanup, verify system still works:

```bash
# Run E2E tests
npm run test:e2e

# Check production services
flyctl status -a linknode-web
flyctl status -a linknode-eagle-monitor
flyctl status -a linknode-grafana
flyctl status -a linknode-influxdb

# Verify dashboard displays data
curl -s https://linknode-eagle-monitor.fly.dev/health
```

---

## Phase 4: Root Directory Organization

The project root contains **84 loose files** that need organization:
- 11 PNG screenshots (1.8M)
- 47 markdown documents
- 17 shell scripts
- 5 JavaScript files
- 4 HTML files

### Current Root Directory Inventory

#### KEEP IN ROOT (Standard Project Files)
These files belong in the root per convention:

| File | Purpose |
|------|---------|
| `.env.example` | Environment template |
| `.gitignore` | Git ignore rules |
| `.nvmrc` | Node version specification |
| `CHANGELOG.md` | Project changelog |
| `LICENSE` | MIT license |
| `README.md` | Main project documentation |
| `SECURITY.md` | Security policy |
| `package.json` | NPM configuration |
| `package-lock.json` | NPM lock file |
| `tsconfig.json` | TypeScript configuration |
| `playwright.config.ts` | E2E test config |
| `playwright.config.phase3.ts` | Phase 3 test config |

#### DELETE - Screenshots (1.8M)
Screenshots should not be in version control. Delete all:

```
Screenshot 2025-07-19 125038.png      (59K)
Screenshot 2025-07-19 125540.png      (136K)
Screenshot 2025-07-19 130708.png      (52K)
Screenshot 2025-07-19 131932.png      (79K)
Screenshot 2025-07-19 132901.png      (203K)
Screenshot 2025-07-19 133625.png      (170K)
Screenshot 2025-07-19 202033.png      (326K)
grafana-dashboard-verification.png    (48K)
grafana-dashboard-with-fixes.png      (42K)
grafana-main-page.png                 (42K)
linknode-with-grafana.png             (646K)
```

**Savings: 1.8M**

#### MOVE TO `docs/` - Documentation Files
Historical and reference documentation:

| File | Category |
|------|----------|
| `ARCHITECTURE.md` | Architecture |
| `CAPABILITIES.md` | Features |
| `PROJECT_STATE.md` | Status |
| `PROJECT_STATUS.md` | Status (duplicate?) |
| `PIPELINE.md` | CI/CD |
| `GITHUB_SETUP.md` | Setup |
| `README-WSL.md` | Setup |

#### MOVE TO `docs/archive/` - Completed/Historical Docs
One-time reports and completed tasks:

| File | Why Archive |
|------|-------------|
| `BASELINE_ESTABLISHMENT.md` | Completed task |
| `CSP_DEPLOYMENT_SUMMARY.md` | Completed deployment |
| `CSP_IMPLEMENTATION_GUIDE.md` | Completed implementation |
| `DEPLOYMENT_VERIFICATION.md` | Completed verification |
| `DOMPURIFY_FIX_DEPLOYMENT_SUMMARY.md` | Completed fix |
| `DOMPURIFY_VULNERABILITY_FIX.md` | Completed fix |
| `FLY_MIGRATION_COMPLETE.md` | Migration done |
| `GRAFANA_BLACKOUT_SOLUTION.md` | Issue resolved |
| `GRAFANA_METER_FIX.md` | Issue resolved |
| `HIVE_MIND_COMPLETION_REPORT.md` | Completed report |
| `ISSUE_5_REPORT.md` | Closed issue |
| `PHASE1_E2E_SUMMARY.md` | Completed phase |
| `REGRESSION_BLACKOUT_FEATURE.md` | Feature complete |
| `REMOVE_GRAFANA_BLACKOUT.md` | Task complete |
| `SECURITY_IMPROVEMENTS.md` | Completed improvements |
| `SECURITY_UPDATE.md` | Completed update |
| `SECURITY_VERIFICATION_FINAL_REPORT.md` | Completed verification |
| `SEO_AUDIT_REPORT.md` | Completed audit |
| `SEO_DEPLOYMENT_CHECKLIST.md` | Completed deployment |
| `SEO_IMPLEMENTATION_GUIDE.md` | Completed implementation |
| `SIMULATED_DATA_REMOVAL.md` | Completed task |

#### MOVE TO `docs/e2e/` - E2E Testing Documentation

| File | Purpose |
|------|---------|
| `E2E_PHASE2_GUIDE.md` | Phase 2 guide |
| `E2E_PHASE3_GUIDE.md` | Phase 3 guide |
| `E2E_TESTING_IMPLEMENTATION.md` | Implementation details |
| `E2E_TESTING_README.md` | Testing overview |
| `REGRESSION_TEST_CHECKLIST.md` | Test checklist |

#### MOVE TO `docs/slack/` - Slack Integration Docs

| File | Purpose |
|------|---------|
| `SLACK_NOTIFICATIONS_MODERN_SETUP.md` | Modern setup |
| `SLACK_NOTIFICATIONS_SETUP.md` | Original setup |
| `SLACK_SETUP_RECOMMENDED.md` | Recommendations |

#### DELETE - Obsolete Documentation
K8s-related docs (infrastructure removed):

| File | Why Delete |
|------|------------|
| `nodeport-access.md` | K8s-specific, no longer applicable |
| `secure-access.md` | K8s-specific, no longer applicable |
| `setup-kubectl.md` | K8s-specific, no longer applicable |

#### MOVE TO `scripts/` - Shell Scripts

| File | Category |
|------|----------|
| `apply-selective-storage-fix.sh` | Fix script |
| `check-ports.sh` | Diagnostic |
| `clear-energy-data.sh` | Operations |
| `clear-energy-data-direct.sh` | Operations |
| `deploy-csp-update.sh` | Deployment |
| `deploy-grafana-security-update.sh` | Deployment |
| `deploy-security-fixes.sh` | Deployment |
| `prepare-deployment.sh` | Deployment |
| `refresh-dashboard.sh` | Operations |
| `setup-slack-notifications.sh` | Setup |
| `ssh-tunnel-setup.sh` | Setup |
| `start-claude-with-mcp.sh` | Development |
| `start-secure-access.sh` | Access |
| `test-xml-locally.sh` | Testing |
| `update-dashboard-live.sh` | Operations |
| `verify-security-live.sh` | Verification |
| `wsl-access.sh` | Access |

#### MOVE TO `scripts/` or DELETE - JavaScript/Python Files

| File | Recommendation |
|------|----------------|
| `capture-grafana-direct.js` | Move to scripts/ or delete (one-time) |
| `capture-grafana-screenshot.js` | Move to scripts/ or delete (one-time) |
| `capture-grafana-with-console.js` | Move to scripts/ or delete (one-time) |
| `test-grafana-api.js` | Move to e2e/ or delete |
| `verify-grafana-fixes.js` | Move to scripts/ or delete (one-time) |
| `delete-energy-data.py` | Move to scripts/ |

#### DELETE - Test Artifacts and Temporary Files

| File | Why Delete |
|------|------------|
| `test-api.html` | One-time test file |
| `test-grafana-viewer.html` | One-time test file |
| `grafana-viewer-no-blackout.html` | Test artifact |
| `demo-page-content.html` | Old demo file |

#### REVIEW - Configuration Files

| File | Action |
|------|--------|
| `fly.toml` | DELETE - Convenience file, each service has its own |
| `claude-mcp-config.json` | MOVE to `.mcp/` |
| `fix-fly-token.md` | MOVE to `docs/` |

#### REVIEW - Claude Flow State Files

| File | Action |
|------|--------|
| `CLAUDE_FLOW_RESTART.md` | DELETE or move to `.hive-mind/` |
| `CLAUDE_FLOW_STATE.md` | DELETE or move to `.hive-mind/` |
| `MURRAYKOPIT_SITE_TODO.md` | DELETE - stale todo list |

---

### Phase 4 Execution Plan

#### Step 1: Delete Screenshots and Test Artifacts (~1.8M)
```bash
# Delete all screenshots
rm -f *.png

# Delete test HTML files
rm -f test-api.html test-grafana-viewer.html
rm -f grafana-viewer-no-blackout.html demo-page-content.html
```

#### Step 2: Create Documentation Structure
```bash
mkdir -p docs/archive docs/e2e docs/slack
```

#### Step 3: Move Documentation Files
```bash
# Active docs → docs/
git mv ARCHITECTURE.md CAPABILITIES.md PROJECT_STATE.md docs/
git mv PROJECT_STATUS.md PIPELINE.md GITHUB_SETUP.md README-WSL.md docs/
git mv EAGLE_DEVICE_CONFIGURATION.md fix-fly-token.md docs/

# Archive docs → docs/archive/
git mv BASELINE_ESTABLISHMENT.md CSP_*.md DEPLOYMENT_VERIFICATION.md docs/archive/
git mv DOMPURIFY_*.md FLY_MIGRATION_COMPLETE.md GRAFANA_*.md docs/archive/
git mv HIVE_MIND_COMPLETION_REPORT.md ISSUE_5_REPORT.md PHASE1_E2E_SUMMARY.md docs/archive/
git mv REGRESSION_BLACKOUT_FEATURE.md REMOVE_GRAFANA_BLACKOUT.md docs/archive/
git mv SECURITY_IMPROVEMENTS.md SECURITY_UPDATE.md SECURITY_VERIFICATION_FINAL_REPORT.md docs/archive/
git mv SEO_*.md SIMULATED_DATA_REMOVAL.md docs/archive/

# E2E docs → docs/e2e/
git mv E2E_*.md REGRESSION_TEST_CHECKLIST.md docs/e2e/

# Slack docs → docs/slack/
git mv SLACK_*.md docs/slack/

# Delete obsolete K8s docs
git rm nodeport-access.md secure-access.md setup-kubectl.md
```

#### Step 4: Move Scripts
```bash
git mv apply-selective-storage-fix.sh check-ports.sh scripts/
git mv clear-energy-data*.sh deploy-*.sh scripts/
git mv prepare-deployment.sh refresh-dashboard.sh scripts/
git mv setup-slack-notifications.sh ssh-tunnel-setup.sh scripts/
git mv start-*.sh test-xml-locally.sh scripts/
git mv update-dashboard-live.sh verify-security-live.sh wsl-access.sh scripts/
git mv delete-energy-data.py scripts/

# Move or delete JS test files
git mv capture-grafana*.js verify-grafana-fixes.js test-grafana-api.js scripts/
```

#### Step 5: Clean Up Config and State Files
```bash
# Delete convenience fly.toml
git rm fly.toml

# Move MCP config
git mv claude-mcp-config.json .mcp/

# Delete stale state files
git rm CLAUDE_FLOW_RESTART.md CLAUDE_FLOW_STATE.md MURRAYKOPIT_SITE_TODO.md
```

---

### Root Directory After Phase 4

```
linknode-com/
├── .claude/
├── .github/
├── .hive-mind/
├── .mcp/
│   └── claude-mcp-config.json    # Moved
├── demo-app/
├── docs/
│   ├── archive/                   # 21 historical docs
│   ├── e2e/                       # 5 E2E docs
│   ├── slack/                     # 3 Slack docs
│   ├── ARCHITECTURE.md
│   ├── CAPABILITIES.md
│   ├── CLEANUP_PLAN.md
│   ├── EAGLE_DEVICE_CONFIGURATION.md
│   ├── fix-fly-token.md
│   ├── GITHUB_SETUP.md
│   ├── HEALTH_CHECKS.md
│   ├── PIPELINE.md
│   ├── PROJECT_STATE.md
│   ├── PROJECT_STATUS.md
│   ├── README-WSL.md
│   ├── REGRESSION_TESTING.md
│   ├── THEORY_OF_OPERATION.md
│   └── WORKFLOW_NOTIFICATIONS.md
├── e2e/
├── fly/
├── monitoring/
├── scripts/                       # +20 scripts moved here
├── test-baselines/
├── websites/
├── .env.example
├── .gitignore
├── .nvmrc
├── CHANGELOG.md
├── LICENSE
├── package.json
├── package-lock.json
├── playwright.config.ts
├── playwright.config.phase3.ts
├── README.md
├── SECURITY.md
└── tsconfig.json
```

**Root directory: 84 files → 14 files**

---

## Notes

- All deletions can be recovered from git history if needed
- Consider running `git gc` after cleanup to reclaim space
- The 40M cloudflare binary should ideally have been in .gitignore
- Phase 4 moves files rather than deleting them, preserving history
