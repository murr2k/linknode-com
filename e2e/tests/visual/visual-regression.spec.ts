import { test, expect } from '@playwright/test';
import { HomePage } from '../../pages/HomePage';
import { GrafanaPage } from '../../pages/GrafanaPage';
import { VisualTester, viewports, commonMasks } from '../../utils/visual-testing';
import { APIMocker, mockResponses } from '../../utils/api-mocks';

test.describe('Visual Regression Tests @visual', () => {
  let homePage: HomePage;
  let visualTester: VisualTester;
  let apiMocker: APIMocker;

  test.beforeEach(async ({ page }, testInfo) => {
    homePage = new HomePage(page);
    visualTester = new VisualTester(page, testInfo);
    apiMocker = new APIMocker(page);

    // Mock APIs for consistent visual tests
    await apiMocker.mock({
      url: /\/api\/stats/,
      method: 'GET',
      response: mockResponses.powerStats.success,
    });

    await apiMocker.mock({
      url: /\/health/,
      method: 'GET',
      response: mockResponses.health.allHealthy,
    });
  });

  test.describe('Homepage Visual Tests', () => {
    test('should match homepage full page screenshot', async ({ page }) => {
      await homePage.goto();
      await visualTester.preparePage();

      // Wait for all content to load
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      // Take full page screenshot
      const screenshot = await visualTester.compareFullPage('homepage-full', {
        mask: [
          ...commonMasks.dynamic,
          '#current-power', // Dynamic power value
          '.metric-value', // All metric values
          '#power-update-indicator', // Update indicator
        ],
      });

      expect(screenshot).toBeTruthy();
    });

    test('should match header component', async ({ page }) => {
      await homePage.goto();
      await visualTester.preparePage();

      const screenshot = await visualTester.compareElement('header', 'header-component');
      expect(screenshot).toBeTruthy();
    });

    test('should match power widget component', async ({ page }) => {
      await homePage.goto();
      await visualTester.preparePage();

      const screenshot = await visualTester.compareElement('.power-widget', 'power-widget', {
        mask: ['#current-power', '.metric-value'],
      });
      expect(screenshot).toBeTruthy();
    });

    test('should match API status widget', async ({ page }) => {
      await homePage.goto();
      await visualTester.preparePage();

      const screenshot = await visualTester.compareElement('.api-status-widget', 'api-status-widget');
      expect(screenshot).toBeTruthy();
    });

    test('should match metrics section', async ({ page }) => {
      await homePage.goto();
      await visualTester.preparePage();

      const screenshot = await visualTester.compareElement('.metrics', 'metrics-section', {
        mask: ['.metric-value'],
      });
      expect(screenshot).toBeTruthy();
    });
  });

  test.describe('Responsive Layout Tests', () => {
    test('should match mobile layouts', async ({ page }) => {
      await homePage.goto();
      await visualTester.preparePage();

      const screenshots = await visualTester.compareResponsiveLayouts('homepage', [
        viewports.mobile.small,
        viewports.mobile.medium,
        viewports.mobile.large,
      ]);

      Object.keys(screenshots).forEach(viewport => {
        expect(screenshots[viewport]).toBeTruthy();
      });
    });

    test('should match tablet layouts', async ({ page }) => {
      await homePage.goto();
      await visualTester.preparePage();

      const screenshots = await visualTester.compareResponsiveLayouts('homepage', [
        viewports.tablet.portrait,
        viewports.tablet.landscape,
      ]);

      Object.keys(screenshots).forEach(viewport => {
        expect(screenshots[viewport]).toBeTruthy();
      });
    });

    test('should match desktop layouts', async ({ page }) => {
      await homePage.goto();
      await visualTester.preparePage();

      const screenshots = await visualTester.compareResponsiveLayouts('homepage', [
        viewports.desktop.small,
        viewports.desktop.medium,
        viewports.desktop.large,
      ]);

      Object.keys(screenshots).forEach(viewport => {
        expect(screenshots[viewport]).toBeTruthy();
      });
    });
  });

  test.describe('Component State Tests', () => {
    test('should match service status states', async ({ page }) => {
      await homePage.goto();
      await visualTester.preparePage();

      // Test different service states
      const states = [
        {
          label: 'all-online',
          setup: async () => {
            await apiMocker.mock({
              url: /\/health/,
              method: 'GET',
              response: mockResponses.health.allHealthy,
            });
          },
        },
        {
          label: 'partial-failure',
          setup: async () => {
            await apiMocker.mock({
              url: /\/health/,
              method: 'GET',
              response: mockResponses.health.partial,
            });
          },
        },
        {
          label: 'all-offline',
          setup: async () => {
            await apiMocker.mock({
              url: /\/health/,
              method: 'GET',
              response: mockResponses.health.allDown,
            });
          },
        },
      ];

      for (const state of states) {
        await state.setup();
        await page.reload();
        await visualTester.preparePage();
        await page.waitForTimeout(2000);

        const screenshot = await visualTester.compareElement(
          '.api-status-widget',
          `api-status-${state.label}`
        );
        expect(screenshot).toBeTruthy();
      }
    });

    test('should match loading states', async ({ page }) => {
      // Mock slow response
      await apiMocker.mock({
        url: /\/api\/stats/,
        method: 'GET',
        response: {
          ...mockResponses.powerStats.success,
          delay: 3000,
        },
      });

      await homePage.goto();
      await visualTester.preparePage();

      // Capture loading state immediately
      const loadingScreenshot = await visualTester.compareElement(
        '.power-widget',
        'power-widget-loading'
      );
      expect(loadingScreenshot).toBeTruthy();

      // Wait for data to load
      await page.waitForTimeout(4000);

      // Capture loaded state
      const loadedScreenshot = await visualTester.compareElement(
        '.power-widget',
        'power-widget-loaded',
        { mask: ['#current-power', '.metric-value'] }
      );
      expect(loadedScreenshot).toBeTruthy();
    });

    test('should match error states', async ({ page }) => {
      await apiMocker.mock({
        url: /\/api\/stats/,
        method: 'GET',
        response: mockResponses.powerStats.error,
      });

      await homePage.goto();
      await visualTester.preparePage();
      await page.waitForTimeout(2000);

      const screenshot = await visualTester.compareElement(
        '.power-widget',
        'power-widget-error'
      );
      expect(screenshot).toBeTruthy();
    });
  });

  test.describe('Grafana Dashboard Visual Tests', () => {
    test('should match Grafana dashboard preview', async ({ page }) => {
      const grafanaPage = new GrafanaPage(page);
      
      await homePage.goto();
      await visualTester.preparePage();

      // Wait for Grafana to load
      await page.waitForTimeout(5000);

      const screenshot = await visualTester.compareElement(
        '.grafana-preview',
        'grafana-preview',
        {
          mask: [
            '.grafana-preview iframe', // Mask entire iframe content as it's dynamic
          ],
        }
      );
      expect(screenshot).toBeTruthy();
    });
  });

  test.describe('Dark Mode Tests', () => {
    test('should match dark mode appearance', async ({ page }) => {
      await homePage.goto();
      
      // Apply dark mode styles
      await page.addStyleTag({
        content: `
          :root {
            --background: #121212;
            --foreground: #ffffff;
            --card-background: #1e1e1e;
            --border-color: #333333;
          }
          body {
            background-color: var(--background);
            color: var(--foreground);
          }
          .card {
            background-color: var(--card-background);
            border-color: var(--border-color);
          }
        `,
      });

      await visualTester.preparePage();
      await page.waitForTimeout(1000);

      const screenshot = await visualTester.compareFullPage('homepage-dark-mode', {
        mask: [...commonMasks.dynamic, '#current-power', '.metric-value'],
      });
      expect(screenshot).toBeTruthy();
    });
  });

  test.describe('Cross-browser Visual Tests', () => {
    test('should have consistent appearance across browsers', async ({ page, browserName }) => {
      await homePage.goto();
      await visualTester.preparePage();

      const screenshot = await visualTester.compareViewport(
        `homepage-${browserName}`,
        {
          mask: [...commonMasks.dynamic, '#current-power', '.metric-value'],
        }
      );
      expect(screenshot).toBeTruthy();
    });
  });

  test.describe('Print Layout Tests', () => {
    test('should match print layout', async ({ page }) => {
      await homePage.goto();
      
      // Emulate print media
      await page.emulateMedia({ media: 'print' });
      await visualTester.preparePage();

      const screenshot = await visualTester.compareFullPage('homepage-print', {
        mask: [...commonMasks.dynamic, '#current-power', '.metric-value'],
      });
      expect(screenshot).toBeTruthy();
    });
  });
});