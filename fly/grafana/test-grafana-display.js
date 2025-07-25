const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  console.log('Navigating to Grafana dashboard...');
  await page.goto('https://linknode-grafana.fly.dev/d/power-monitoring/eagle-energy-monitor?orgId=1&refresh=5s', {
    waitUntil: 'networkidle',
    timeout: 60000
  });
  
  console.log('Waiting for dashboard to load...');
  
  try {
    // Wait for the dashboard panels to be visible
    await page.waitForSelector('.dashboard-container', { timeout: 30000 });
    console.log('Dashboard container found');
    
    // Wait a bit more for data to load
    await page.waitForTimeout(5000);
    
    // Take screenshot
    await page.screenshot({ 
      path: 'test-results/grafana-meter-display.png',
      fullPage: true 
    });
    console.log('Screenshot saved to test-results/grafana-meter-display.png');
    
    // Try to find the meter reading
    const meterText = await page.evaluate(() => {
      const panels = document.querySelectorAll('.panel-content');
      for (const panel of panels) {
        const title = panel.querySelector('.panel-title');
        if (title && title.textContent.includes('Utility Meter Reading')) {
          const value = panel.querySelector('.grafana-stat-panel__value, [data-testid="data-testid Panel value"]');
          return value ? value.textContent : 'Value element not found';
        }
      }
      return 'Meter panel not found';
    });
    
    console.log('Meter reading display:', meterText);
    
  } catch (error) {
    console.error('Error:', error.message);
    await page.screenshot({ 
      path: 'test-results/grafana-error-state.png',
      fullPage: true 
    });
  }
  
  await browser.close();
})();