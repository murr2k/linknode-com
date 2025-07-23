# Linknode Energy Monitoring Project Context

## Quick Start for Claude
This is a fully functional energy monitoring web application deployed on Fly.io. All infrastructure is working, comprehensive testing is in place, and regression baselines are established.

## Current State (2025-07-23)
- ✅ Website live at https://linknode.com
- ✅ All services operational
- ✅ Comprehensive E2E testing (3 phases)
- ✅ Regression baseline established (v1.0.0-baseline)
- ✅ CI/CD fully automated

## Key Commands
```bash
# Testing
npm test                    # Run all tests
npm run test:phase3        # Advanced tests
npm run baseline:compare   # Check for regressions

# Development
npm run baseline:capture   # Update baseline after changes
git push                   # Auto-deploys to Fly.io
```

## Recent Work Completed
1. Fixed CI/CD pipeline (Issue #5)
2. Implemented SEO (Issue #4)
3. Added Playwright E2E testing in 3 phases (Issue #1)
4. Established regression testing baseline
5. Added build status display to homepage

## Architecture
- **Frontend**: Static HTML/CSS/JS served by nginx
- **Backend**: Eagle Monitor API (Node.js)
- **Database**: InfluxDB for time series data
- **Monitoring**: Grafana dashboards
- **Hosting**: Fly.io (4 services)

## Testing Infrastructure
- **Phase 1**: Smoke tests (basic functionality)
- **Phase 2**: API mocking, visual regression, performance, a11y
- **Phase 3**: Advanced visual/performance profiling
- **Regression**: Baseline comparison system

## Important Files
- `REGRESSION_TEST_CHECKLIST.md` - Pre-release checklist
- `test-baselines/` - Visual and performance baselines
- `fly/` - Service configurations
- `e2e/` - Test suite

## Next Potential Work
- Performance optimization
- Historical data features
- Mobile app
- Alert notifications
- Multi-region deployment

---
*Use CLAUDE_FLOW_STATE.md for detailed session continuity*