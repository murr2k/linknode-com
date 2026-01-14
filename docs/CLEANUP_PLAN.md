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

## Notes

- All deletions can be recovered from git history if needed
- Consider running `git gc` after cleanup to reclaim space
- The 40M cloudflare binary should ideally have been in .gitignore
