# GitHub Actions Workflows Documentation

This directory contains all GitHub Actions workflows for the Linknode project. Each workflow serves a specific purpose in our CI/CD pipeline.

## Workflow Overview

| Workflow | Purpose | Triggers | Required Secrets |
|----------|---------|----------|------------------|
| [deploy-fly.yml](#deploy-flyio) | Deploy services to Fly.io | Push to main, Manual | `FLY_API_TOKEN` |
| [e2e-tests.yml](#e2e-tests) | Run comprehensive E2E test suite | PR, Push to main, Manual | None |
| [e2e-tests-phase3.yml](#e2e-tests-phase-3) | Advanced visual and performance tests | Push to main (specific paths), Manual | None |
| [regression-tests.yml](#regression-tests) | Compare against baseline for regressions | PR, Push to main, Manual | None |
| [security-scan.yml](#security-scanning) | Security vulnerability scanning | PR, Push to main, Daily schedule | None |

## Detailed Documentation

### Deploy to Fly.io
**File:** `deploy-fly.yml`

**Purpose:** Deploys all services (InfluxDB, Eagle Monitor, Grafana, Web) to Fly.io production environment.

**Features:**
- Version capture before deployment for rollback capability
- Retry logic (3 attempts) with health checks
- Automatic rollback on failure
- Service-specific or all-services deployment
- Final health verification

**Triggers:**
- Push to `main` branch (when files in `fly/` change)
- Manual dispatch with service selection

**Required Secrets:**
- `FLY_API_TOKEN`: Authentication token for Fly.io deployments
  - Obtain: Run `flyctl auth token`
  - Scope: Organization or personal
  - Rotation: Every 90 days recommended

**Optional Secrets:**
- `SLACK_WEBHOOK_URL`: For deployment notifications
  - Format: `https://hooks.slack.com/services/...`

### E2E Tests
**File:** `e2e-tests.yml`

**Purpose:** Runs comprehensive end-to-end tests across multiple browsers and test categories.

**Test Categories:**
- Browser tests (Chromium, Firefox, WebKit)
- API integration tests
- Visual regression tests
- Performance tests
- Accessibility tests
- Mobile tests

**Features:**
- Parallel execution using matrix strategy
- NPM and Playwright browser caching
- Conditional test type selection
- Comprehensive test reporting
- Artifact collection

**Triggers:**
- Pull requests to `main`
- Push to `main` branch
- Manual dispatch with test type selection

**Performance Optimizations:**
- Consolidated from 6 separate jobs to 3 job groups
- Browser caching reduces setup time by ~2 minutes
- NPM caching saves 30-60 seconds per job

### E2E Tests Phase 3
**File:** `e2e-tests-phase3.yml`

**Purpose:** Advanced visual and performance testing with extensive viewport coverage.

**Test Coverage:**
- Multi-viewport visual testing (mobile to 4K)
- Cross-browser consistency checks
- Performance profiling with HAR files
- Memory usage analysis
- Animation performance testing

**Triggers:**
- Push to `main` (when test files change)
- Manual dispatch with test category selection

**Special Requirements:**
- Uses `playwright.config.phase3.ts` configuration
- Generates detailed performance reports
- Creates visual baseline comparisons

### Regression Tests
**File:** `regression-tests.yml`

**Purpose:** Compares current state against established baselines to catch unintended changes.

**Features:**
- Visual regression comparison
- Performance metric tracking
- Feature validation
- Baseline capture mode
- Automated PR comments with results

**Triggers:**
- Pull requests to `main`
- Push to `main` branch
- Manual dispatch with baseline options

**Baseline Management:**
- Capture mode: Creates new baseline
- Compare mode: Checks against existing baseline
- Auto-update: On significant releases

### Security Scanning
**File:** `security-scan.yml`

**Purpose:** Automated security vulnerability detection across code and dependencies.

**Scan Types:**
- Security headers validation (nginx configs)
- Dependency vulnerability scanning (npm, Python)
- Code security analysis (Semgrep)
- API authentication verification
- Secrets detection (Gitleaks)
- Docker security scanning (Trivy)

**Triggers:**
- Pull requests to `main`
- Push to `main` or `develop`
- Daily schedule (2 AM UTC)
- Manual dispatch

**Issue Creation:**
- Automatically creates GitHub issues for security findings
- Tags: `security`, `automated`

## Common Troubleshooting

### Workflow Failures

#### Deploy to Fly.io
- **Authentication failed**: Check `FLY_API_TOKEN` is valid
- **Deployment timeout**: Services may need more time, check Fly.io dashboard
- **Health check failed**: Verify service endpoints are responding
- **Rollback triggered**: Check deployment logs for root cause

#### E2E Tests
- **Browser install failed**: Clear cache and retry
- **Test timeout**: Check if target site is accessible
- **Screenshot differences**: Review visual changes, update baseline if intentional
- **Flaky tests**: Consider adding retry logic or wait conditions

#### Security Scans
- **False positives**: Review findings, add suppressions if needed
- **Scan timeout**: Some scans may take longer on large codebases
- **Permission errors**: Ensure workflow has necessary permissions

### Running Workflows Locally

To test workflows locally, use [act](https://github.com/nektos/act):

```bash
# Test e2e workflow
act -W .github/workflows/e2e-tests.yml

# Test with specific event
act pull_request -W .github/workflows/security-scan.yml

# With secrets
act -s FLY_API_TOKEN="your-token" -W .github/workflows/deploy-fly.yml
```

## Secrets Management

### Required Secrets

1. **FLY_API_TOKEN**
   - Required for: deploy-fly.yml
   - Purpose: Authenticate with Fly.io API
   - Setup: `flyctl auth token`

### Optional Secrets

1. **SLACK_WEBHOOK_URL**
   - Used by: All workflows
   - Purpose: Send notifications to Slack
   - Setup: Create Slack app with incoming webhooks
   - Note: Workflows function without this secret

### Adding New Secrets

1. Go to Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Add name and value
4. Update workflow documentation

## Best Practices

1. **Caching**
   - Always cache dependencies (npm, pip, etc.)
   - Cache tool installations (Playwright, etc.)
   - Use hash-based cache keys

2. **Timeouts**
   - Set appropriate timeouts for each job
   - Consider network latency and service startup time

3. **Permissions**
   - Use minimal required permissions
   - Document why each permission is needed

4. **Error Handling**
   - Always include error messages in outputs
   - Use `continue-on-error: false` for critical steps
   - Implement retry logic for flaky operations

5. **Artifacts**
   - Use consistent retention periods
   - Name artifacts descriptively
   - Clean up old artifacts regularly

## Maintenance

### Regular Tasks

1. **Monthly**
   - Review and update dependencies
   - Check for deprecated actions
   - Verify secret rotation schedule

2. **Quarterly**
   - Audit workflow permissions
   - Review artifact retention policies
   - Update baseline snapshots

3. **Annually**
   - Major version updates
   - Workflow optimization review
   - Documentation update

## Contributing

When adding or modifying workflows:

1. Test locally with `act` if possible
2. Create PR with detailed description
3. Ensure all required secrets are documented
4. Update this README with any changes
5. Consider impact on CI/CD costs

For questions or issues, contact the maintainers or create an issue in the repository.