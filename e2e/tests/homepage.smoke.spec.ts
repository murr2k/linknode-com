import { test, expect } from '@playwright/test';
import { testData } from '../fixtures/test-data';
import { testHelpers } from '../utils/test-helpers';

test.describe('Linknode Homepage - Smoke Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the homepage
    await page.goto('/', { waitUntil: 'domcontentloaded' });
  });

  test('should load the homepage successfully', async ({ page }) => {
    // Wait for page to be fully loaded
    await testHelpers.waitForPageLoad(page);
    
    // Verify the page loads without errors
    const response = page.context().pages()[0];
    expect(response).toBeTruthy();
    
    // Check that no console errors occurred
    const consoleErrors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    
    // Give it a moment to catch any errors
    await page.waitForTimeout(1000);
    expect(consoleErrors).toHaveLength(0);
  });

  test('should have correct page title', async ({ page }) => {
    // Verify the page title
    await expect(page).toHaveTitle(testData.pageContent.title);
  });

  test('should display main heading', async ({ page }) => {
    // Check for main heading
    const heading = page.locator('h1').first();
    await expect(heading).toBeVisible();
    await expect(heading).toContainText(testData.pageContent.heading);
  });

  test('should display subtitle', async ({ page }) => {
    // Check for subtitle
    const subtitle = page.locator('.subtitle');
    await expect(subtitle).toBeVisible();
    await expect(subtitle).toContainText(testData.pageContent.subtitle);
  });

  test('should have all key page sections visible', async ({ page }) => {
    // Wait for page to stabilize
    await testHelpers.waitForPageLoad(page);
    
    // Check for key sections
    const sections = [
      { name: 'Header', selector: testData.expectedElements.header },
      { name: 'Metrics Section', selector: testData.expectedElements.metricsSection },
      { name: 'Live Metrics Section', selector: testData.expectedElements.liveMetricsSection },
      { name: 'Power Widget', selector: testData.expectedElements.powerWidget },
      { name: 'API Status Widget', selector: testData.expectedElements.apiStatusWidget },
      { name: 'Grafana Preview', selector: testData.expectedElements.grafanaPreview },
      { name: 'Footer', selector: testData.expectedElements.footer },
    ];

    for (const section of sections) {
      const element = page.locator(section.selector);
      await expect(element, `${section.name} should be visible`).toBeVisible();
    }
  });

  test('should display service status indicators', async ({ page }) => {
    // Wait for status indicators to load
    await page.waitForSelector('.api-status-item', { timeout: testData.timeouts.elementVisible });
    
    // Check each service status indicator
    for (const service of testData.services) {
      const statusDot = page.locator(service.selector);
      await expect(statusDot, `${service.name} status indicator should be visible`).toBeVisible();
    }
  });

  test('should have proper SEO meta tags', async ({ page }) => {
    // Verify meta tags
    await testHelpers.verifyMetaTags(page);
    
    // Check canonical URL
    const canonical = await page.getAttribute('link[rel="canonical"]', 'href');
    expect(canonical).toBe('https://linknode.com/');
  });

  test('should display metrics values', async ({ page }) => {
    // Wait for metrics to be visible
    await page.waitForSelector('.metric', { timeout: testData.timeouts.elementVisible });
    
    // Check that metrics are displayed
    const metrics = page.locator('.metric');
    const count = await metrics.count();
    expect(count).toBeGreaterThan(0);
    
    // Verify each metric has a value and label
    for (let i = 0; i < count; i++) {
      const metric = metrics.nth(i);
      const value = metric.locator('.metric-value');
      const label = metric.locator('.metric-label');
      
      await expect(value).toBeVisible();
      await expect(label).toBeVisible();
    }
  });

  test('should have responsive viewport meta tag', async ({ page }) => {
    // Check viewport meta tag
    const viewport = await page.getAttribute('meta[name="viewport"]', 'content');
    expect(viewport).toContain('width=device-width');
    expect(viewport).toContain('initial-scale=1.0');
  });

  test('should have working navigation structure', async ({ page }) => {
    // Verify the page has proper structure
    const body = page.locator('body');
    await expect(body).toBeVisible();
    
    // Check for container
    const container = page.locator('.container');
    await expect(container).toBeVisible();
    
    // Verify grid layout exists
    const grid = page.locator('.grid');
    await expect(grid).toBeVisible();
    
    // Check that cards are present
    const cards = page.locator('.card');
    const cardCount = await cards.count();
    expect(cardCount).toBeGreaterThan(0);
  });
});