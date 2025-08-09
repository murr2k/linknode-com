# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Data staleness detection for power monitoring dashboard
  - Displays dashes (--) instead of stale values when data is older than 2 minutes
  - Shows age indicator: "Live" (<30s), "Updated Xs ago" (30-60s), "Updated Xm ago" (1-2m), "No data for Xh Xm" (>2m)
  - Prevents misleading display of outdated power consumption values
  - Automatically resumes showing real values when fresh data arrives

### Fixed
- Updated remaining hardcoded paths to use relative paths in scripts
  - `monitoring/test-api-endpoints.sh`: Fixed cloudflare-setup path reference
  - `monitoring/fix-eagle-404.sh`: Changed rackspace-connect.sh to linknode-connect.sh
  - `websites/website-manager/create-website.sh`: Now uses SCRIPT_DIR pattern for dynamic paths
  - `websites/website-manager/scripts/git-integration.sh`: Replaced all hardcoded paths with dynamic resolution
- All scripts now work correctly regardless of project directory name (linknode-com vs rackspace)
- Cloudflare DNS configuration issues causing 522 errors
- Fly.io auto-stop settings preventing reliable uptime
- Cleaned up orphaned volumes in InfluxDB and Grafana deployments

## [1.1.0] - 2025-01-28

### Changed
- Renamed repository from `rackspace-k8s-demo` to `linknode-com`
- Updated all scripts to use relative paths instead of absolute paths
- Scripts now use standard bash pattern for dynamic path resolution

### Added
- Security enhancements with CSP headers, API authentication, and rate limiting
- Comprehensive E2E testing with Playwright (3 phases, 30+ test scenarios)
- Regression testing baseline established for quality assurance
- Security monitoring and automated vulnerability scanning

### Infrastructure
- Migrated from Kubernetes to Fly.io for simplified deployment
- Deployed services: web (nginx), eagle-monitor, grafana, influxdb
- Live at https://linknode.com