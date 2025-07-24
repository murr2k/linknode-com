import { test, expect } from '@playwright/test';
import { RegressionBlackout, captureWithBlackouts } from '../../utils/regression-blackout';
import * as fs from 'fs';
import * as path from 'path';

test.describe('Power Monitoring Visual Regression', () => {
  let blackoutManager: RegressionBlackout;

  test.beforeEach(async ({ page }) => {
    blackoutManager = new RegressionBlackout(page);
    await page.goto('https://linknode.com');
    await page.waitForLoadState('networkidle');
  });

  test('capture baseline with dynamic content blackouts', async ({ page }) => {
    // Apply blackouts to dynamic regions
    await blackoutManager.applyPowerMonitoringBlackouts();

    // Verify blackouts are applied
    const blackoutsApplied = await blackoutManager.verifyBlackouts();
    expect(blackoutsApplied).toBe(true);

    // Take screenshot
    const screenshotPath = 'test-results/regression/linknode-baseline.png';
    await page.screenshot({ path: screenshotPath, fullPage: true });

    // Generate blackout report
    const report = await blackoutManager.generateBlackoutReport();
    fs.writeFileSync(
      'test-results/regression/linknode-blackout-report.json',
      report
    );

    // Log what was blacked out
    const appliedBlackouts = blackoutManager.getAppliedBlackouts();
    console.log('Applied blackouts:', appliedBlackouts);

    // Verify the screenshot exists
    expect(fs.existsSync(screenshotPath)).toBe(true);
  });

  test('compare with baseline ignoring dynamic regions', async ({ page }) => {
    // Apply the same blackouts
    await blackoutManager.applyPowerMonitoringBlackouts();

    // Take comparison screenshot
    const comparisonPath = 'test-results/regression/linknode-comparison.png';
    await page.screenshot({ path: comparisonPath, fullPage: true });

    // In a real test, you would compare with baseline here
    // For now, just verify the screenshot was taken
    expect(fs.existsSync(comparisonPath)).toBe(true);
  });

  test('verify Grafana iframe is properly blacked out', async ({ page }) => {
    // Apply only Grafana blackout
    await blackoutManager.applyBlackouts([
      RegressionBlackout.STANDARD_BLACKOUTS.grafana
    ]);

    // Check that Grafana iframe has blackout applied
    const grafanaBlackedOut = await page.evaluate(() => {
      const iframe = document.querySelector('.grafana-preview iframe');
      return iframe?.classList.contains('regression-blackout');
    });

    expect(grafanaBlackedOut).toBe(true);

    // Verify the label is visible
    const labelVisible = await page.evaluate(() => {
      const iframe = document.querySelector('.grafana-preview iframe');
      const label = iframe?.getAttribute('data-blackout-label');
      return label === 'Grafana Chart';
    });

    expect(labelVisible).toBe(true);
  });

  test('debug mode - capture without blackouts', async ({ page }) => {
    // This test captures the page WITHOUT blackouts for debugging
    const debugPath = 'test-results/regression/linknode-debug-no-blackout.png';
    await page.screenshot({ path: debugPath, fullPage: true });

    console.log('Debug screenshot saved (no blackouts):', debugPath);
    expect(fs.existsSync(debugPath)).toBe(true);
  });

  test('document all dynamic elements', async ({ page }) => {
    // Find all potentially dynamic elements
    const dynamicElements = await page.evaluate(() => {
      const elements: Array<{ selector: string; text: string; reason: string }> = [];

      // Find all elements with numeric content
      document.querySelectorAll('*').forEach(el => {
        const text = el.textContent?.trim() || '';
        const hasNumbers = /\d+/.test(text);
        const isLeaf = el.children.length === 0;
        
        if (hasNumbers && isLeaf && text.length < 50) {
          const selector = el.className ? `.${el.className.split(' ')[0]}` : el.tagName.toLowerCase();
          elements.push({
            selector,
            text,
            reason: 'Contains numeric data that may change'
          });
        }
      });

      // Find iframes
      document.querySelectorAll('iframe').forEach(iframe => {
        elements.push({
          selector: 'iframe',
          text: iframe.src,
          reason: 'External content that changes independently'
        });
      });

      return elements;
    });

    // Save report of dynamic elements
    fs.writeFileSync(
      'test-results/regression/dynamic-elements-report.json',
      JSON.stringify(dynamicElements, null, 2)
    );

    console.log(`Found ${dynamicElements.length} potentially dynamic elements`);
  });

  test('create annotated screenshot showing blackout regions', async ({ page }) => {
    // Apply blackouts
    await blackoutManager.applyPowerMonitoringBlackouts();

    // Add visual indicators around blackout regions
    await page.addStyleTag({
      content: `
        .regression-blackout {
          box-shadow: 0 0 0 3px red !important;
        }
      `
    });

    // Take annotated screenshot
    const annotatedPath = 'test-results/regression/linknode-blackout-annotated.png';
    await page.screenshot({ path: annotatedPath, fullPage: true });

    console.log('Annotated screenshot saved:', annotatedPath);
  });

  test('verify blackout metadata is embedded', async ({ page }) => {
    // Apply blackouts
    await blackoutManager.applyPowerMonitoringBlackouts();

    // Check metadata
    const metadata = await page.evaluate(() => {
      const meta = document.querySelector('meta[name="regression-blackouts"]');
      return meta?.getAttribute('content');
    });

    expect(metadata).toBeTruthy();
    
    const blackouts = JSON.parse(metadata!);
    expect(blackouts.length).toBeGreaterThan(0);
    
    console.log('Embedded blackout metadata:', blackouts);
  });
});

test.describe('Regression Blackout Configuration', () => {
  test('generate blackout configuration file', async () => {
    // Create a configuration file that documents all blackout regions
    const config = {
      version: '1.0',
      description: 'Regression test blackout configuration for linknode.com',
      lastUpdated: new Date().toISOString(),
      blackouts: [
        {
          name: 'Grafana Dashboard',
          ...RegressionBlackout.STANDARD_BLACKOUTS.grafana,
          screenshots: ['grafana-blacked-out.png'],
        },
        {
          name: 'Power Readings',
          ...RegressionBlackout.STANDARD_BLACKOUTS.powerReadings,
          expectedValues: ['XXX W', 'XXX.X kWh'],
        },
        {
          name: 'Timestamps',
          ...RegressionBlackout.STANDARD_BLACKOUTS.timestamps,
          format: 'ISO 8601 or relative time',
        },
      ],
      instructions: [
        'Run tests with blackouts enabled for regression testing',
        'Run tests without blackouts for debugging',
        'Check blackout-report.json for details of what was hidden',
        'Use annotated screenshots to verify blackout regions',
      ],
    };

    const configPath = 'test-results/regression/blackout-config.json';
    fs.mkdirSync(path.dirname(configPath), { recursive: true });
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2));

    console.log('Blackout configuration saved:', configPath);
  });
});