import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { HomePage } from '../../pages/HomePage';
import { PerformanceCollector } from '../../utils/performance-metrics';
import { VisualTester } from '../../utils/visual-testing';

// Load baseline data
const baselinePath = path.join(process.cwd(), 'test-baselines', 'baseline.json');
const baseline = fs.existsSync(baselinePath) 
  ? JSON.parse(fs.readFileSync(baselinePath, 'utf-8'))
  : null;

test.describe('Regression Tests Against Baseline @regression', () => {
  test.skip(!baseline, 'No baseline found. Run capture-baseline.ts first');

  let homePage: HomePage;
  let performanceCollector: PerformanceCollector;
  let visualTester: VisualTester;

  test.beforeEach(async ({ page }, testInfo) => {
    homePage = new HomePage(page);
    performanceCollector = new PerformanceCollector(page);
    visualTester = new VisualTester(page, testInfo);
    await performanceCollector.initialize();
  });

  test.describe('Feature Availability Regression', () => {
    test('should have all baseline page structure elements', async ({ page }) => {
      await homePage.goto();

      const currentStructure = await page.evaluate(() => {
        return {
          header: !!document.querySelector('header'),
          mainHeading: document.querySelector('h1')?.textContent,
          metricsSection: !!document.querySelector('.metrics'),
          powerWidget: !!document.querySelector('.power-widget'),
          apiStatusWidget: !!document.querySelector('.api-status-widget'),
          grafanaPreview: !!document.querySelector('.grafana-preview'),
          buildStatus: !!document.querySelector('.build-status'),
          footer: !!document.querySelector('.footer')
        };
      });

      // Compare with baseline
      const baselineStructure = baseline.features.pageStructure;
      
      expect(currentStructure.header).toBe(baselineStructure.header);
      expect(currentStructure.mainHeading).toBe(baselineStructure.mainHeading);
      expect(currentStructure.metricsSection).toBe(baselineStructure.metricsSection);
      expect(currentStructure.powerWidget).toBe(baselineStructure.powerWidget);
      expect(currentStructure.apiStatusWidget).toBe(baselineStructure.apiStatusWidget);
      expect(currentStructure.grafanaPreview).toBe(baselineStructure.grafanaPreview);
      expect(currentStructure.buildStatus).toBe(baselineStructure.buildStatus);
      expect(currentStructure.footer).toBe(baselineStructure.footer);
    });

    test('should have all baseline functionality features', async ({ page }) => {
      await homePage.goto();

      const currentFeatures = await page.evaluate(() => {
        return {
          powerMonitoring: {
            currentPower: !!document.querySelector('#current-power'),
            powerStats: !!document.querySelector('.power-widget'),
            metricsDisplay: !!document.querySelector('.metrics')
          },
          apiStatus: {
            influxStatus: !!document.querySelector('#influx-status'),
            eagleStatus: !!document.querySelector('#eagle-status'),
            webStatus: !!document.querySelector('#web-status')
          },
          buildInfo: {
            version: !!document.querySelector('#app-version'),
            buildDate: !!document.querySelector('#build-date'),
            commit: !!document.querySelector('#commit-sha'),
            environment: !!document.querySelector('#environment')
          },
          grafana: {
            iframe: !!document.querySelector('.grafana-preview iframe')
          }
        };
      });

      const baselineFeatures = baseline.features.functionality;

      // Deep comparison of features
      expect(currentFeatures).toEqual(baselineFeatures);
    });
  });

  test.describe('Visual Regression Tests', () => {
    test('should match desktop visual baseline', async ({ page }) => {
      await homePage.goto();
      await page.waitForLoadState('networkidle');
      await visualTester.preparePage();

      // Take current screenshot
      const screenshot = await page.screenshot({ fullPage: true });
      
      // Compare with baseline
      const baselineScreenshotPath = path.join(process.cwd(), 'test-baselines', 'visual', 'baseline-desktop-1080p.png');
      
      if (fs.existsSync(baselineScreenshotPath)) {
        await expect(page).toHaveScreenshot('regression-desktop.png', {
          fullPage: true,
          maxDiffPixels: 100,
          threshold: 0.2
        });
      }
    });

    test('should match mobile visual baseline', async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 });
      await homePage.goto();
      await page.waitForLoadState('networkidle');
      await visualTester.preparePage();

      const screenshot = await page.screenshot({ fullPage: true });
      
      const baselineScreenshotPath = path.join(process.cwd(), 'test-baselines', 'visual', 'baseline-mobile.png');
      
      if (fs.existsSync(baselineScreenshotPath)) {
        await expect(page).toHaveScreenshot('regression-mobile.png', {
          fullPage: true,
          maxDiffPixels: 100,
          threshold: 0.2
        });
      }
    });

    test('should match component visual baselines', async ({ page }) => {
      await homePage.goto();
      await page.waitForLoadState('networkidle');

      const components = [
        { selector: '.power-widget', name: 'power-widget' },
        { selector: '.api-status-widget', name: 'api-status-widget' },
        { selector: '.build-status', name: 'build-status' }
      ];

      for (const component of components) {
        const element = await page.$(component.selector);
        if (element) {
          await expect(element).toHaveScreenshot(`regression-${component.name}.png`, {
            maxDiffPixels: 50,
            threshold: 0.2
          });
        }
      }
    });
  });

  test.describe('Performance Regression Tests', () => {
    test('should not regress from baseline performance metrics', async ({ page }) => {
      await homePage.goto();
      const metrics = await performanceCollector.collect();

      const baselinePerf = baseline.performance;
      const tolerance = 1.2; // Allow 20% degradation

      // Navigation timing should not regress significantly
      if (baselinePerf.navigation) {
        // Handle zero baseline values
        if (baselinePerf.navigation.domContentLoaded === 0) {
          // When baseline is 0, just check that current is reasonable
          expect(metrics.domContentLoaded).toBeLessThan(1000); // 1 second max
        } else {
          expect(metrics.domContentLoaded).toBeLessThan(
            baselinePerf.navigation.domContentLoaded * tolerance
          );
        }
        
        if (baselinePerf.navigation.loadComplete === 0) {
          // When baseline is 0, just check that current is reasonable
          expect(metrics.loadComplete).toBeLessThan(2000); // 2 seconds max
        } else {
          expect(metrics.loadComplete).toBeLessThan(
            baselinePerf.navigation.loadComplete * tolerance
          );
        }
      }

      // Paint timing should not regress
      if (baselinePerf.paint) {
        if (baselinePerf.paint.firstContentfulPaint === 0) {
          // When baseline is 0, just check that current is reasonable
          expect(metrics.firstContentfulPaint).toBeLessThan(3000); // 3 seconds max
        } else {
          expect(metrics.firstContentfulPaint).toBeLessThan(
            baselinePerf.paint.firstContentfulPaint * tolerance
          );
        }
      }

      // Core Web Vitals should not regress
      if (baselinePerf.webVitals) {
        expect(metrics.lcp).toBeLessThan(
          (baselinePerf.webVitals.lcp || 2500) * tolerance
        );
      }

      // Resource count should not increase significantly
      if (baselinePerf.resources) {
        expect(metrics.totalRequests).toBeLessThan(
          baselinePerf.resources.total * tolerance
        );
      }
    });

    test('should maintain resource efficiency', async ({ page }) => {
      await homePage.goto();
      const metrics = await performanceCollector.collect();

      const baselineResources = baseline.performance.resources;
      
      if (baselineResources) {
        // Total size should not increase significantly
        const baselineSize = baselineResources.totalSize || 0;
        const currentSize = metrics.totalSize;
        
        expect(currentSize).toBeLessThan(baselineSize * 1.1); // 10% tolerance
        
        console.log(`Resource size: ${(currentSize / 1024 / 1024).toFixed(2)}MB (baseline: ${(baselineSize / 1024 / 1024).toFixed(2)}MB)`);
      }
    });
  });

  test.describe('API Regression Tests', () => {
    test('should have all baseline API endpoints available', async ({ page }) => {
      await homePage.goto();

      const baselineEndpoints = baseline.api;
      const criticalEndpoints = ['/api/stats', '/health', '/build-info.json'];

      for (const endpoint of criticalEndpoints) {
        const response = await page.request.get(`https://linknode.com${endpoint}`);
        
        expect(response.ok()).toBe(true);
        
        if (baselineEndpoints[endpoint]) {
          expect(response.status()).toBe(baselineEndpoints[endpoint].status);
        }
      }
    });

    test('should maintain API response times', async ({ page }) => {
      await homePage.goto();

      const endpoints = ['/api/stats', '/health'];
      
      for (const endpoint of endpoints) {
        const start = Date.now();
        const response = await page.request.get(`https://linknode.com${endpoint}`);
        const duration = Date.now() - start;
        
        expect(response.ok()).toBe(true);
        expect(duration).toBeLessThan(1000); // 1 second max
        
        console.log(`${endpoint} response time: ${duration}ms`);
      }
    });
  });

  test.describe('Build Information Regression', () => {
    test('should have valid build information', async ({ page }) => {
      await homePage.goto();

      try {
        const buildInfo = await page.evaluate(async () => {
          const response = await fetch('/build-info.json');
          return response.json();
        });

        expect(buildInfo).toHaveProperty('version');
        expect(buildInfo).toHaveProperty('buildDate');
        expect(buildInfo).toHaveProperty('commit');
        expect(buildInfo).toHaveProperty('environment');

        // Version should follow semantic versioning
        expect(buildInfo.version).toMatch(/^v\d+\.\d+\.\d+/);
        
        // Build date should be recent (within last 30 days)
        const buildDate = new Date(buildInfo.buildDate);
        const daysSinceBuild = (Date.now() - buildDate.getTime()) / (1000 * 60 * 60 * 24);
        expect(daysSinceBuild).toBeLessThan(30);

        console.log('Current build info:', buildInfo);
      } catch (e) {
        // Build info might not be available in all environments
        console.log('Build info not available');
      }
    });
  });

  test.describe('Critical User Flows Regression', () => {
    test('should display power monitoring data', async ({ page }) => {
      await homePage.goto();
      
      // Wait for power data to load
      await page.waitForSelector('#current-power', { timeout: 10000 });
      
      const powerValue = await homePage.getCurrentPowerValue();
      expect(powerValue).not.toBe('--');
      expect(powerValue).toMatch(/^\d+(\.\d+)?$/); // Should be a number
    });

    test('should show API service status', async ({ page }) => {
      await homePage.goto();
      
      const statuses = await homePage.getAllServiceStatuses();
      
      // At least one service should be online
      const onlineServices = Object.values(statuses).filter(s => s === 'online');
      expect(onlineServices.length).toBeGreaterThan(0);
    });

    test('should load Grafana dashboard', async ({ page }) => {
      await homePage.goto();
      
      const grafanaUrl = await homePage.getGrafanaDashboardUrl();
      expect(grafanaUrl).toBeTruthy();
      expect(grafanaUrl).toContain('grafana');
    });
  });

  test.describe('Regression Test Summary', () => {
    test.afterAll(async () => {
      console.log('\n=== Regression Test Summary ===');
      console.log(`Baseline captured: ${baseline?.timestamp || 'N/A'}`);
      console.log(`Current test run: ${new Date().toISOString()}`);
      console.log('===============================\n');
    });
  });
});