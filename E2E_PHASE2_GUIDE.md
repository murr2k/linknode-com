# E2E Testing Phase 2 - Implementation Guide

This guide documents the Phase 2 implementation of Playwright E2E testing for linknode.com, covering advanced testing patterns and comprehensive test coverage.

## Overview

Phase 2 builds upon the foundation established in Phase 1, adding:
- API mocking and integration testing
- Visual regression testing
- Performance metrics collection
- Accessibility testing
- Error handling and retry logic
- Network condition simulation
- Advanced Grafana dashboard testing

## New Features Implemented

### 1. Page Object Model (POM)

The Page Object Model pattern has been implemented for better test maintainability:

```typescript
// Example usage
import { HomePage } from '../pages/HomePage';

test('example test', async ({ page }) => {
  const homePage = new HomePage(page);
  await homePage.goto();
  const powerValue = await homePage.getCurrentPowerValue();
});
```

**Key Page Objects:**
- `BasePage` - Base class with common functionality
- `HomePage` - Homepage specific methods and locators
- `GrafanaPage` - Grafana dashboard interactions

### 2. API Mocking Framework

Comprehensive API mocking for reliable and fast tests:

```typescript
import { APIMocker, mockResponses } from '../utils/api-mocks';

const apiMocker = new APIMocker(page);
await apiMocker.mock({
  url: /\/api\/stats/,
  method: 'GET',
  response: mockResponses.powerStats.success
});
```

**Features:**
- Pre-defined mock responses
- Dynamic response generation
- Request interception and logging
- CORS header simulation

### 3. Visual Regression Testing

Screenshot comparison and visual testing:

```typescript
import { VisualTester } from '../utils/visual-testing';

const visualTester = new VisualTester(page, testInfo);
await visualTester.compareFullPage('homepage-full', {
  mask: ['#current-power', '.timestamp']
});
```

**Capabilities:**
- Full page screenshots
- Component screenshots
- Responsive layout testing
- Cross-browser visual comparison
- Dynamic content masking

### 4. Performance Testing

Comprehensive performance metrics collection:

```typescript
import { PerformanceCollector } from '../utils/performance-metrics';

const collector = new PerformanceCollector(page);
const metrics = await collector.collect();
```

**Metrics Collected:**
- Core Web Vitals (LCP, FID, CLS)
- Navigation timing
- Resource loading
- Memory usage
- Network statistics

### 5. Accessibility Testing

Integration with axe-core for WCAG compliance:

```typescript
test('accessibility', async ({ page, makeAxeBuilder }) => {
  const results = await makeAxeBuilder().analyze();
  expect(results.violations).toHaveLength(0);
});
```

**Tests Include:**
- WCAG 2.1 AA compliance
- Keyboard navigation
- Screen reader compatibility
- Color contrast validation
- ARIA landmarks

### 6. Error Handling & Retry Logic

Robust error handling with automatic retries:

```typescript
import { ErrorHandler } from '../utils/error-handling';

const errorHandler = new ErrorHandler({ page, testInfo });
await errorHandler.retry(async () => {
  // Flaky operation
}, { maxAttempts: 3, delay: 1000 });
```

**Features:**
- Automatic retry with exponential backoff
- Error state capture (screenshots, logs)
- Smart element waiting
- Network failure recovery

### 7. Network Condition Testing

Simulate various network conditions:

```typescript
// Simulate slow 3G
await context.newCDPSession(page).then(client => {
  client.send('Network.emulateNetworkConditions', {
    offline: false,
    downloadThroughput: 50 * 1024 / 8,
    uploadThroughput: 50 * 1024 / 8,
    latency: 400
  });
});
```

## Test Organization

### Test Categories

Tests are organized with tags for selective execution:

- `@api` - API integration tests
- `@visual` - Visual regression tests
- `@performance` - Performance tests
- `@accessibility` - Accessibility tests

### Running Specific Test Types

```bash
# Run all tests
npm test

# Run specific test category
npm run test:api
npm run test:visual
npm run test:perf
npm run test:a11y

# Run with grep pattern
npx playwright test --grep @performance
```

## CI/CD Integration

The GitHub Actions workflow has been enhanced with:

1. **Parallel Test Execution** - Tests run across multiple browsers simultaneously
2. **Selective Test Runs** - Manual workflow dispatch with test type selection
3. **Dedicated Test Jobs** - Separate jobs for API, visual, performance, and accessibility tests
4. **Enhanced Reporting** - Comprehensive test summaries and artifact uploads

### Workflow Features

```yaml
workflow_dispatch:
  inputs:
    test_type:
      description: 'Test type to run'
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

### 1. Use Page Objects

Always use page objects for element interactions:

```typescript
// Good
const powerValue = await homePage.getCurrentPowerValue();

// Avoid
const powerValue = await page.locator('#current-power').textContent();
```

### 2. Mock External Dependencies

Mock APIs for reliable tests:

```typescript
beforeEach(async ({ page }) => {
  await apiMocker.mock({
    url: /\/api\/stats/,
    response: mockResponses.powerStats.success
  });
});
```

### 3. Handle Flaky Tests

Use retry logic for unreliable operations:

```typescript
await errorHandler.retry(async () => {
  await page.click('.flaky-button');
}, { maxAttempts: 3 });
```

### 4. Visual Testing Masks

Mask dynamic content in visual tests:

```typescript
await visualTester.compareFullPage('homepage', {
  mask: ['.timestamp', '#current-power', '.loading-spinner']
});
```

### 5. Performance Budgets

Set and enforce performance budgets:

```typescript
const PERFORMANCE_BUDGETS = {
  lcp: 2500,      // 2.5s
  fid: 100,       // 100ms
  cls: 0.1,       // 0.1
  totalSize: 5 * 1024 * 1024  // 5MB
};
```

## Debugging

### Enable Debug Mode

```bash
# Run with Playwright inspector
npm run test:debug

# Run in headed mode
npm run test:headed

# Enable verbose logging
DEBUG=pw:* npm test
```

### Capture Error States

Error handler automatically captures:
- Full page screenshots
- Console errors
- Network failures
- Page HTML

### View Test Reports

```bash
# Open HTML report
npm run test:report

# Reports location
playwright-report/index.html
test-results/
```

## Configuration

### Environment Variables

Create `.env` file based on `.env.example`:

```env
BASE_URL=https://linknode.com
VISUAL_TESTING_ENABLED=true
PERF_LCP_BUDGET=2500
A11Y_STANDARD=WCAG2AA
```

### Playwright Config

Key configuration in `playwright.config.ts`:

```typescript
{
  use: {
    baseURL: process.env.BASE_URL || 'https://linknode.com',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure'
  }
}
```

## Maintenance

### Update Visual Baselines

```bash
# Update all screenshots
npm run update-snapshots

# Update specific test
npx playwright test visual-regression.spec.ts --update-snapshots
```

### Monitor Performance Trends

Track performance metrics over time:
1. Review performance test results in CI
2. Check for degradation in Core Web Vitals
3. Investigate increases in resource size
4. Monitor API response times

### Accessibility Compliance

Regular accessibility audits:
1. Run `npm run test:a11y` locally
2. Review axe-core violations
3. Check new features for a11y compliance
4. Test with screen readers periodically

## Troubleshooting

### Common Issues

1. **Flaky Tests**
   - Use `errorHandler.retry()` for unreliable operations
   - Increase timeouts for slow operations
   - Add explicit waits for dynamic content

2. **Visual Test Failures**
   - Check for unmasked dynamic content
   - Verify font loading completion
   - Disable animations in tests

3. **API Mock Issues**
   - Ensure mock is registered before navigation
   - Check URL patterns match actual requests
   - Verify CORS headers in mock responses

4. **Performance Test Failures**
   - Run tests in isolation to avoid interference
   - Check for background processes
   - Verify network conditions are stable

## Future Enhancements

### Phase 3 Considerations

1. **Advanced User Flows**
   - Multi-step user journeys
   - State persistence testing
   - Session management

2. **Load Testing Integration**
   - Concurrent user simulation
   - API load testing
   - Performance under load

3. **Security Testing**
   - XSS vulnerability checks
   - CSRF protection validation
   - Security header verification

4. **Mobile App Testing**
   - Native app automation
   - Cross-platform testing
   - Device farm integration

## Resources

- [Playwright Documentation](https://playwright.dev)
- [Axe-core Rules](https://dequeuniversity.com/rules/axe/)
- [Web.dev Performance](https://web.dev/performance/)
- [WCAG Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)

## Support

For questions or issues:
1. Check test logs in `test-results/`
2. Review CI/CD artifacts
3. Enable debug mode for detailed information
4. Consult Playwright documentation