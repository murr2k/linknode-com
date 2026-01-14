# E2E Testing with Playwright

This document describes the End-to-End (E2E) testing setup for the Linknode Energy Monitor application using Playwright.

## Overview

The E2E testing suite provides automated browser testing for linknode.com, ensuring the application works correctly across different browsers and devices. The tests are designed to run both locally and in CI/CD pipelines via GitHub Actions.

## Test Structure

```
e2e/
├── tests/                  # Test specifications
│   ├── homepage.smoke.spec.ts      # Homepage smoke tests
│   └── power-monitoring.smoke.spec.ts  # Power monitoring feature tests
├── fixtures/               # Test data and configurations
│   └── test-data.ts       # Centralized test data
└── utils/                  # Helper functions
    └── test-helpers.ts    # Reusable test utilities
```

## Test Coverage

### Homepage Smoke Tests (`homepage.smoke.spec.ts`)
- Page load verification
- Title and meta tag validation
- Key UI elements visibility
- Service status indicators
- SEO compliance checks
- Responsive design verification

### Power Monitoring Tests (`power-monitoring.smoke.spec.ts`)
- Power consumption widget functionality
- Real-time data updates
- API integration tests
- Grafana dashboard embedding
- Service health monitoring

## Local Development

### Prerequisites
- Node.js 20.x or higher
- npm or yarn package manager

### Installation

1. Install dependencies:
```bash
npm install
```

2. Install Playwright browsers:
```bash
npx playwright install
```

For systems requiring sudo access:
```bash
npx playwright install-deps
```

### Running Tests

Run all tests:
```bash
npm test
```

Run tests in headed mode (visible browser):
```bash
npm run test:headed
```

Run tests with UI mode:
```bash
npm run test:ui
```

Debug tests:
```bash
npm run test:debug
```

Run specific test file:
```bash
npx playwright test e2e/tests/homepage.smoke.spec.ts
```

Run tests for specific browser:
```bash
npx playwright test --project=chromium
npx playwright test --project=firefox
npx playwright test --project=webkit
```

### View Test Reports

After running tests, view the HTML report:
```bash
npm run test:report
```

## CI/CD Integration

The E2E tests are automatically run on:
- Every push to the `main` branch
- Every pull request targeting `main`
- Manual workflow dispatch

### GitHub Actions Workflow

The workflow (`/.github/workflows/e2e-tests.yml`) includes:

1. **Multi-browser testing**: Tests run on Chromium, Firefox, and WebKit
2. **Mobile testing**: Separate job for mobile viewport tests
3. **Test artifacts**: Screenshots, videos, and traces are uploaded on failures
4. **Test results**: JUnit XML reports for test result visualization
5. **Parallel execution**: Tests run in parallel for faster feedback

### Workflow Features

- **Matrix strategy**: Tests run across multiple browsers simultaneously
- **Artifact retention**: Test results kept for 30 days
- **Failure handling**: Always uploads artifacts, even on test failures
- **Test summary**: Aggregates results from all browser runs

## Configuration

### Playwright Configuration (`playwright.config.ts`)

Key settings:
- **Base URL**: https://linknode.com
- **Test timeout**: 60 seconds per test
- **Retries**: 2 retries on CI, 0 locally
- **Trace**: Collected on first retry
- **Screenshots**: Captured on failures
- **Video**: Recorded on failures
- **Parallel execution**: Enabled by default

### Browser Projects

Tests run on:
- Desktop Chrome
- Desktop Firefox
- Desktop Safari (WebKit)
- Mobile Chrome (Pixel 5)
- Mobile Safari (iPhone 12)

## Best Practices

1. **Page Object Model**: Consider implementing POM for complex test scenarios
2. **Test Independence**: Each test should be able to run independently
3. **Explicit Waits**: Use Playwright's built-in waiting mechanisms
4. **Meaningful Assertions**: Include descriptive error messages
5. **Test Data Management**: Centralize test data in fixtures

## Troubleshooting

### Common Issues

1. **Browser installation fails**:
   - Run with sudo: `sudo npx playwright install-deps`
   - Or use Docker container with pre-installed browsers

2. **Tests timeout**:
   - Check network connectivity to linknode.com
   - Increase timeout in playwright.config.ts
   - Verify services are running

3. **API tests fail**:
   - Ensure CORS is properly configured
   - Check if services are accessible from test environment

### Debug Tips

1. Use `--debug` flag for step-by-step debugging
2. Enable `headless: false` in config for visual debugging
3. Use `page.pause()` in tests to pause execution
4. Check test artifacts in `test-results/` directory

## Phase 2 Implementation

Phase 2 has been implemented with comprehensive testing capabilities. See [E2E Phase 2 Guide](./E2E_PHASE2_GUIDE.md) for detailed documentation.

### Phase 2 Features Implemented
- ✅ Visual regression testing with screenshot comparison
- ✅ Performance testing with Core Web Vitals metrics
- ✅ Accessibility testing with axe-core integration
- ✅ API mocking and integration testing
- ✅ Error handling and retry logic
- ✅ Network condition simulation
- ✅ Page Object Model implementation
- ✅ Advanced Grafana dashboard testing
- ✅ Cross-origin resource validation

### New Test Commands
```bash
# Run specific test types
npm run test:api         # API integration tests
npm run test:visual      # Visual regression tests
npm run test:perf        # Performance tests
npm run test:a11y        # Accessibility tests

# Update visual snapshots
npm run update-snapshots
```

## Future Enhancements

### Phase 3 Considerations
- Advanced user scenarios and multi-step workflows
- Load testing integration with k6 or Artillery
- Security testing (XSS, CSRF, headers)
- Integration with monitoring tools (Sentry, DataDog)
- Custom reporting dashboards
- Test data management system
- AI-powered test generation
- Cross-browser testing on real devices

## Maintenance

- Review and update tests when UI changes
- Keep Playwright version up to date
- Monitor test execution times
- Clean up old test artifacts regularly
- Review flaky tests and improve stability

## Resources

- [Playwright Documentation](https://playwright.dev)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)