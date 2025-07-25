import { test, expect } from '@playwright/test';

test.describe('Verify Grafana Dashboard Fixes', () => {
  test('capture dashboard screenshot and verify fixes', async ({ page }) => {
    // Navigate to Grafana dashboard
    await page.goto('https://linknode-grafana.fly.dev/d/power-monitoring/eagle-energy-monitor?orgId=1&refresh=5s');
    
    // Wait for dashboard to fully load
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000); // Extra wait for data to populate
    
    // Take a full page screenshot
    await page.screenshot({ 
      path: 'test-results/grafana-dashboard-fixes.png',
      fullPage: true 
    });
    
    // Also capture individual panels for clarity
    const panels = [
      { selector: '[aria-label="Current Power Demand"]', name: 'power-gauge' },
      { selector: '[aria-label="Today\'s Total Energy"]', name: 'energy-total' },
      { selector: '[aria-label="Average Power (1h)"]', name: 'average-power' },
      { selector: '[aria-label="Peak Power (1h)"]', name: 'peak-power' }
    ];
    
    for (const panel of panels) {
      const element = page.locator(panel.selector).first();
      if (await element.isVisible()) {
        await element.screenshot({ 
          path: `test-results/grafana-panel-${panel.name}.png` 
        });
      }
    }
    
    // Check for GWh text (should not be present)
    const pageContent = await page.content();
    expect(pageContent).not.toContain('GWh');
    
    // Log what units we do see
    console.log('Checking for unit displays...');
    
    // Check for expected units
    const expectedUnits = ['W', 'kWh', 'Wh'];
    for (const unit of expectedUnits) {
      if (pageContent.includes(unit)) {
        console.log(`Found unit: ${unit}`);
      }
    }
  });
});