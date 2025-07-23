# Playwright E2E Testing Implementation

## Overview

This document provides a comprehensive guide to the Playwright E2E testing implementation for the Linknode Energy Monitor project. The testing framework has been implemented in two phases, providing robust test coverage for critical functionality.

## Implementation Status

### ✅ Phase 1: Basic Smoke Tests (Completed)
- Basic Playwright setup with multi-browser support
- 18 smoke tests covering homepage and power monitoring
- GitHub Actions integration for automated testing
- Test artifacts and reporting

### ✅ Phase 2: Core Functionality Tests (Completed)
- Page Object Model architecture
- API mocking and integration testing
- Visual regression testing
- Performance metrics collection
- Accessibility testing
- Network condition simulation
- Advanced error handling

## Project Structure

```
rackspace/
├── .github/workflows/
│   └── e2e-tests.yml          # GitHub Actions workflow
├── e2e/
│   ├── fixtures/
│   │   ├── test-data.ts       # Test data constants
│   │   └── axe-setup.ts       # Accessibility configuration
│   ├── pages/
│   │   ├── BasePage.ts        # Base page object class
│   │   ├── HomePage.ts        # Homepage page object
│   │   └── GrafanaPage.ts     # Grafana dashboard page object
│   ├── tests/
│   │   ├── homepage.smoke.spec.ts           # Homepage smoke tests
│   │   ├── power-monitoring.smoke.spec.ts   # Power monitoring tests
│   │   ├── api/
│   │   │   └── api-integration.spec.ts     # API integration tests
│   │   ├── visual/
│   │   │   └── visual-regression.spec.ts   # Visual regression tests
│   │   ├── performance/
│   │   │   └── performance.spec.ts         # Performance tests
│   │   ├── accessibility/
│   │   │   └── accessibility.spec.ts       # Accessibility tests
│   │   ├── grafana-advanced.spec.ts        # Grafana interaction tests
│   │   ├── error-handling.spec.ts          # Error handling tests
│   │   ├── cross-origin.spec.ts            # CORS tests
│   │   └── network-conditions.spec.ts      # Network simulation tests
│   └── utils/
│       ├── test-helpers.ts        # Common test utilities
│       ├── api-mocks.ts          # API mocking utilities
│       ├── error-handling.ts     # Error handling utilities
│       ├── performance-metrics.ts # Performance collection
│       └── visual-testing.ts     # Visual testing utilities
├── playwright.config.ts          # Playwright configuration
├── package.json                  # Node.js dependencies
└── .env.example                  # Environment variables template
```

## Getting Started

### Prerequisites
- Node.js 18+ installed
- Git repository cloned locally
- Access to run GitHub Actions

### Installation

1. Install dependencies:
```bash
npm install
```

2. Install Playwright browsers:
```bash
npx playwright install --with-deps
```

3. Copy environment configuration:
```bash
cp .env.example .env
# Edit .env with your configuration
```

### Running Tests Locally

```bash
# Run all tests
npm test

# Run tests with UI
npm run test:headed

# Run specific test suites
npm run test:api          # API integration tests
npm run test:visual       # Visual regression tests
npm run test:perf         # Performance tests
npm run test:a11y         # Accessibility tests

# Debug tests
npm run test:debug

# Update visual snapshots
npm run update-snapshots
```

## Test Suites

### 1. Smoke Tests
- **Purpose**: Verify basic functionality works
- **Coverage**: Homepage load, UI elements, basic interactions
- **Run time**: ~2-3 minutes

### 2. API Integration Tests
- **Purpose**: Validate API endpoints and data flow
- **Features**:
  - Mock API responses for predictable testing
  - Test error scenarios
  - Validate request/response formats
- **Key tests**: Power stats, health checks, error handling

### 3. Visual Regression Tests
- **Purpose**: Detect unintended visual changes
- **Features**:
  - Screenshot comparison
  - Dynamic content masking
  - Responsive layout testing
- **Baselines**: Stored in `e2e/screenshots/`

### 4. Performance Tests
- **Purpose**: Ensure fast page loads and interactions
- **Metrics**:
  - Core Web Vitals (LCP, FID, CLS)
  - Resource loading times
  - Memory usage
- **Thresholds**: Configurable in test files

### 5. Accessibility Tests
- **Purpose**: Ensure WCAG 2.1 compliance
- **Coverage**:
  - Color contrast
  - Keyboard navigation
  - ARIA attributes
  - Screen reader compatibility

### 6. Network Condition Tests
- **Purpose**: Validate behavior under poor network conditions
- **Scenarios**:
  - Slow 3G
  - Offline mode
  - High latency
  - Intermittent connectivity

## CI/CD Integration

### GitHub Actions Workflow

The E2E tests run automatically on:
- Pull requests (all tests)
- Pushes to main branch (smoke tests only)
- Manual workflow dispatch (selective tests)

### Workflow Features
- Parallel test execution
- Multi-browser testing (Chrome, Firefox, Safari)
- Mobile viewport testing
- Test artifacts on failure
- HTML reports

### Triggering Tests

```yaml
# Manual trigger with options
workflow_dispatch:
  inputs:
    test-suite:
      description: 'Test suite to run'
      required: true
      default: 'all'
      type: choice
      options:
        - all
        - smoke
        - api
        - visual
        - performance
        - accessibility
```

## Best Practices

### 1. Writing Tests
- Use Page Object Model for maintainability
- Keep tests independent and atomic
- Use descriptive test names
- Group related tests with `describe` blocks
- Tag tests appropriately (@smoke, @api, etc.)

### 2. Handling Flaky Tests
- Use built-in retry logic
- Wait for specific conditions, not arbitrary timeouts
- Mock external dependencies when possible
- Use stable selectors (data-testid preferred)

### 3. Debugging
- Use `page.pause()` for interactive debugging
- Enable trace recording for failed tests
- Check screenshots and videos in artifacts
- Use `--debug` flag for step-by-step execution

### 4. Performance
- Run tests in parallel when possible
- Use API mocking to reduce external dependencies
- Minimize use of `page.waitForTimeout()`
- Cache browser installations in CI

## Troubleshooting

### Common Issues

1. **Tests timing out**
   - Increase timeout in playwright.config.ts
   - Check for missing await statements
   - Verify selectors are correct

2. **Visual tests failing**
   - Update snapshots if changes are intentional
   - Check for dynamic content that needs masking
   - Ensure consistent viewport sizes

3. **API tests failing**
   - Verify mock URLs match actual endpoints
   - Check CORS configuration
   - Ensure API is accessible from test environment

4. **CI/CD failures**
   - Check GitHub Actions logs
   - Verify secrets are configured
   - Ensure browsers are installed in CI

## Maintenance

### Regular Tasks
1. Update Playwright version quarterly
2. Review and update visual snapshots
3. Audit test coverage monthly
4. Clean up obsolete tests
5. Monitor test execution times

### Adding New Tests
1. Identify test category (smoke, api, visual, etc.)
2. Create test file in appropriate directory
3. Use existing utilities and page objects
4. Add appropriate tags for test filtering
5. Update documentation

## Future Enhancements (Phase 3)

Potential additions for comprehensive coverage:
- Database state validation
- Load testing integration
- Security scanning
- Multi-language testing
- A/B testing support
- Synthetic monitoring

## Resources

- [Playwright Documentation](https://playwright.dev)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Web Vitals](https://web.dev/vitals/)
- [WCAG Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)

## Support

For questions or issues:
1. Check the troubleshooting section
2. Review test logs and artifacts
3. Open an issue in the GitHub repository
4. Contact the development team

---

Last updated: 2025-07-23
Implemented by: AI-Augmented Development with Claude