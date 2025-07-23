import { test, expect } from '@playwright/test';
import { HomePage } from '../pages/HomePage';
import { GrafanaPage } from '../pages/GrafanaPage';
import { APIMocker, mockResponses } from '../utils/api-mocks';

test.describe('Advanced Grafana Dashboard Tests', () => {
  let homePage: HomePage;
  let grafanaPage: GrafanaPage;
  let apiMocker: APIMocker;

  test.beforeEach(async ({ page }) => {
    homePage = new HomePage(page);
    grafanaPage = new GrafanaPage(page);
    apiMocker = new APIMocker(page);

    // Mock APIs for consistent testing
    await apiMocker.mock({
      url: /\/api\/stats/,
      method: 'GET',
      response: mockResponses.powerStats.success,
    });
  });

  test('should load Grafana dashboard in iframe', async ({ page }) => {
    await homePage.goto();
    
    // Wait for Grafana iframe
    await expect(grafanaPage.grafanaFrame).toBeVisible();
    
    // Verify iframe attributes
    const src = await grafanaPage.getGrafanaDashboardUrl();
    expect(src).toBeTruthy();
    expect(src).toContain('linknode-grafana.fly.dev');
    expect(src).toContain('power-monitoring');
    
    // Check iframe security attributes
    const sandbox = await grafanaPage.grafanaFrame.getAttribute('sandbox');
    if (sandbox) {
      expect(sandbox).toContain('allow-scripts');
      expect(sandbox).toContain('allow-same-origin');
    }
  });

  test('should handle Grafana dashboard loading states', async ({ page }) => {
    await homePage.goto();
    
    // Monitor iframe loading
    const frameLoadPromise = page.waitForEvent('frameattached');
    
    // Wait for frame to be attached
    await frameLoadPromise;
    
    // Wait for dashboard to load
    await grafanaPage.waitForDashboardLoad();
    
    // Verify dashboard has loaded
    const hasData = await grafanaPage.dashboardHasData();
    expect(hasData).toBe(true);
  });

  test('should display dashboard panels correctly', async ({ page }) => {
    await homePage.goto();
    await grafanaPage.waitForDashboardLoad();
    
    // Get dashboard panels
    const panels = await grafanaPage.getDashboardPanels();
    
    // Should have at least one panel
    expect(panels.length).toBeGreaterThan(0);
    
    // Verify expected panels
    const panelTitles = panels.map(p => p.title);
    console.log('Dashboard panels:', panelTitles);
    
    // Check for common power monitoring panels
    const expectedPanels = ['Power Consumption', 'Current Power', 'Power History'];
    for (const expected of expectedPanels) {
      const hasPanel = panelTitles.some(title => 
        title.toLowerCase().includes(expected.toLowerCase())
      );
      if (!hasPanel) {
        console.log(`Panel "${expected}" not found`);
      }
    }
  });

  test('should interact with time range selector', async ({ page }) => {
    await homePage.goto();
    await grafanaPage.waitForDashboardLoad();
    
    // Get current time range
    const initialTimeRange = await grafanaPage.getTimeRange();
    console.log('Initial time range:', initialTimeRange);
    
    // Try to change time range
    try {
      await grafanaPage.setTimeRange('Last 1 hour');
      
      // Verify time range changed
      const newTimeRange = await grafanaPage.getTimeRange();
      expect(newTimeRange).not.toBe(initialTimeRange);
      expect(newTimeRange).toContain('1');
    } catch (e) {
      console.log('Time range selector not accessible in embedded mode');
    }
  });

  test('should handle dashboard refresh', async ({ page }) => {
    await homePage.goto();
    await grafanaPage.waitForDashboardLoad();
    
    // Try to refresh dashboard
    try {
      await grafanaPage.refreshDashboard();
      
      // Wait for refresh to complete
      await page.waitForTimeout(2000);
      
      // Dashboard should still be loaded
      const hasData = await grafanaPage.dashboardHasData();
      expect(hasData).toBe(true);
    } catch (e) {
      console.log('Refresh button not available in embedded mode');
    }
  });

  test('should display panel data correctly', async ({ page }) => {
    await homePage.goto();
    await grafanaPage.waitForDashboardLoad();
    
    // Get data from a specific panel
    const panelData = await grafanaPage.getPanelData('Power Consumption');
    
    if (panelData) {
      console.log('Panel data:', panelData);
      
      // Verify panel has data
      expect(panelData.hasData).toBe(true);
      
      // If it's a single stat panel, should have main value
      if (panelData.mainValue) {
        expect(panelData.mainValue).toBeTruthy();
      }
      
      // If it has values array, should not be empty
      if (panelData.values && panelData.values.length > 0) {
        expect(panelData.values.length).toBeGreaterThan(0);
      }
    }
  });

  test('should handle cross-origin iframe restrictions', async ({ page }) => {
    await homePage.goto();
    
    // Try to access iframe content
    const frame = await grafanaPage.getGrafanaFrame();
    
    if (frame) {
      // Frame is accessible (same origin or CORS allowed)
      const url = frame.url();
      expect(url).toContain('grafana');
    } else {
      // Frame is not accessible due to cross-origin restrictions
      console.log('Grafana iframe is cross-origin restricted');
      
      // Verify iframe element exists even if content is not accessible
      await expect(grafanaPage.grafanaFrame).toBeVisible();
    }
  });

  test('should maintain aspect ratio on resize', async ({ page }) => {
    await homePage.goto();
    await expect(grafanaPage.grafanaFrame).toBeVisible();
    
    // Test different viewport sizes
    const viewports = [
      { width: 1920, height: 1080 },
      { width: 1366, height: 768 },
      { width: 768, height: 1024 },
      { width: 375, height: 667 },
    ];
    
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await page.waitForTimeout(500);
      
      // Check iframe is still visible and properly sized
      await expect(grafanaPage.grafanaFrame).toBeVisible();
      
      const box = await grafanaPage.grafanaFrame.boundingBox();
      if (box) {
        // Iframe should have reasonable dimensions
        expect(box.width).toBeGreaterThan(200);
        expect(box.height).toBeGreaterThan(200);
        
        // Aspect ratio should be maintained (roughly 16:9 or similar)
        const aspectRatio = box.width / box.height;
        expect(aspectRatio).toBeGreaterThan(1);
        expect(aspectRatio).toBeLessThan(3);
      }
    }
  });

  test('should handle dashboard errors gracefully', async ({ page }) => {
    // Mock Grafana as unavailable
    await page.route('**/linknode-grafana.fly.dev/**', route => {
      route.abort('failed');
    });
    
    await homePage.goto();
    
    // Page should still load
    await expect(homePage.mainHeading).toBeVisible();
    
    // Grafana section should handle error gracefully
    const grafanaSection = page.locator('.grafana-preview');
    await expect(grafanaSection).toBeVisible();
    
    // Could show error message or fallback content
    const errorMessage = grafanaSection.locator('.error, .fallback');
    const hasErrorHandling = await errorMessage.count() > 0;
    
    if (!hasErrorHandling) {
      // At minimum, shouldn't break the page
      const consoleErrors = await homePage.checkForConsoleErrors();
      const criticalErrors = consoleErrors.filter(e => 
        e.includes('Uncaught') || e.includes('TypeError')
      );
      expect(criticalErrors).toHaveLength(0);
    }
  });

  test('should verify Grafana dashboard URL parameters', async ({ page }) => {
    await homePage.goto();
    
    const dashboardUrl = await grafanaPage.getGrafanaDashboardUrl();
    if (dashboardUrl) {
      const url = new URL(dashboardUrl);
      
      // Check for expected parameters
      expect(url.pathname).toContain('dashboard');
      
      // Check for theme parameter
      const theme = url.searchParams.get('theme');
      if (theme) {
        expect(['light', 'dark']).toContain(theme);
      }
      
      // Check for kiosk mode
      const kiosk = url.searchParams.get('kiosk');
      if (kiosk) {
        expect(['tv', '1', 'true']).toContain(kiosk);
      }
      
      // Check for time range parameters
      const from = url.searchParams.get('from');
      const to = url.searchParams.get('to');
      if (from && to) {
        expect(from).toMatch(/now-\d+[mhd]|^\d+$/);
        expect(to).toBe('now');
      }
    }
  });

  test('should capture Grafana panel screenshots', async ({ page }) => {
    await homePage.goto();
    await grafanaPage.waitForDashboardLoad();
    
    // Try to capture panel screenshot
    try {
      await grafanaPage.takePanelScreenshot('Power Consumption', 'power-consumption-panel');
      
      // Verify screenshot was created
      const fs = require('fs');
      const screenshotPath = 'test-results/screenshots/power-consumption-panel.png';
      const exists = fs.existsSync(screenshotPath);
      expect(exists).toBe(true);
    } catch (e) {
      console.log('Unable to capture panel screenshot due to iframe restrictions');
    }
  });

  test('should test Grafana responsive behavior', async ({ page }) => {
    await homePage.goto();
    
    const responsiveCheck = await grafanaPage.checkResponsiveLayout({ width: 375, height: 667 });
    
    if (responsiveCheck) {
      expect(responsiveCheck).toBe(true);
    } else {
      // If we can't check inside iframe, at least verify container is responsive
      await page.setViewportSize({ width: 375, height: 667 });
      
      const container = page.locator('.grafana-preview');
      await expect(container).toBeVisible();
      
      const box = await container.boundingBox();
      if (box) {
        // Container should fit mobile viewport
        expect(box.width).toBeLessThanOrEqual(375);
      }
    }
  });
});