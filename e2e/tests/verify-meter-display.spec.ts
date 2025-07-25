import { test, expect } from '@playwright/test';

test.describe('Verify Utility Meter Display', () => {
  test('check meter reading display format', async ({ page }) => {
    console.log('Navigating to linknode.com...');
    
    // Go to the main page
    await page.goto('https://linknode.com');
    
    // Wait for the page to load
    await page.waitForLoadState('networkidle');
    
    // Take a screenshot for analysis
    await page.screenshot({ 
      path: 'test-results/linknode-current-state.png',
      fullPage: true 
    });
    
    // Wait for Grafana iframe to load
    const grafanaFrame = page.frameLocator('iframe.grafana-preview');
    await page.waitForTimeout(5000); // Give Grafana time to load
    
    // Try to find text containing meter reading
    const pageText = await page.evaluate(() => document.body.innerText);
    console.log('\n=== Page Text Analysis ===');
    
    // Look for patterns like "87 k", "87k", "86733", etc.
    const patterns = [
      /\d+\s*k\b/gi,           // Numbers followed by 'k'
      /\d+\s*kWh/gi,           // Numbers with kWh
      /\d{5,}/g,               // 5+ digit numbers
      /utility.*\d+/gi,        // Utility followed by numbers
      /meter.*\d+/gi           // Meter followed by numbers
    ];
    
    patterns.forEach((pattern, index) => {
      const matches = pageText.match(pattern);
      if (matches) {
        console.log(`Pattern ${index + 1} matches:`, matches);
      }
    });
    
    // Try to access Grafana directly for better inspection
    console.log('\n=== Direct Grafana Access ===');
    await page.goto('https://linknode-grafana.fly.dev/d/power-monitoring/eagle-energy-monitor?orgId=1&refresh=5s');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);
    
    // Take Grafana screenshot
    await page.screenshot({ 
      path: 'test-results/grafana-direct-access.png',
      fullPage: true 
    });
    
    // Look for the utility meter panel
    const meterPanel = page.locator('div:has-text("Utility Meter Reading")').first();
    if (await meterPanel.isVisible()) {
      console.log('Found Utility Meter Reading panel');
      
      // Get the parent panel to find the value
      const panelParent = meterPanel.locator('..');
      const valueElement = panelParent.locator('.grafana-stat-panel__value, [data-testid="stat-panel-value"], .css-1jcwk6r, .css-8tk2dk');
      
      if (await valueElement.count() > 0) {
        const value = await valueElement.first().textContent();
        console.log('Current display value:', value);
        
        // Check if it matches our expected format
        if (value?.includes('k')) {
          console.log('❌ Issue: Value is abbreviated with "k"');
        }
        if (!value?.includes('kWh')) {
          console.log('❌ Issue: Missing "kWh" unit');
        }
        if (!value?.includes('86733')) {
          console.log('❌ Issue: Not showing full meter reading');
        }
      }
    }
    
    // Get all text from Grafana
    const grafanaText = await page.evaluate(() => document.body.innerText);
    console.log('\n=== Searching for meter values ===');
    
    // Look for our expected value
    if (grafanaText.includes('86733')) {
      console.log('✅ Found full meter reading 86733');
    } else if (grafanaText.includes('87 k')) {
      console.log('❌ Found abbreviated "87 k"');
    } else if (grafanaText.includes('87k')) {
      console.log('❌ Found abbreviated "87k"');
    } else if (grafanaText.includes('87')) {
      console.log('❌ Found truncated "87"');
    }
  });
});