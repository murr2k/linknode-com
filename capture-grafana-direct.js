const { chromium } = require('playwright');

(async () => {
  console.log('Starting direct Grafana capture...');
  
  // Launch browser without any test framework
  const browser = await chromium.launch({
    headless: true,
    args: ['--disable-web-security', '--disable-features=IsolateOrigins,site-per-process']
  });
  
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    ignoreHTTPSErrors: true
  });
  
  const page = await context.newPage();
  
  console.log('Navigating to Grafana dashboard...');
  
  // First check if Grafana is healthy
  const healthResponse = await page.goto('https://linknode-grafana.fly.dev/api/health');
  const healthData = await healthResponse.json();
  console.log('Grafana health:', healthData);
  
  // Now navigate to dashboard
  await page.goto('https://linknode-grafana.fly.dev/d/power-monitoring/eagle-energy-monitor?orgId=1&refresh=5s', {
    waitUntil: 'domcontentloaded',
    timeout: 30000
  });
  
  // Wait for Grafana to initialize
  console.log('Waiting for Grafana to load...');
  try {
    await page.waitForSelector('.dashboard-container', { timeout: 15000 });
  } catch (e) {
    console.log('Dashboard container not found, waiting for panels...');
    await page.waitForSelector('[data-panel-id]', { timeout: 15000 }).catch(() => {
      console.log('No panels found either');
    });
  }
  
  // Additional wait for rendering
  await page.waitForTimeout(5000);
  
  // Take screenshot
  const screenshotPath = 'test-results/grafana-direct-capture.png';
  await page.screenshot({ 
    path: screenshotPath,
    fullPage: true 
  });
  
  console.log(`Screenshot saved to: ${screenshotPath}`);
  
  // Also capture the panel data
  try {
    const panelData = await page.evaluate(() => {
      const panels = document.querySelectorAll('[data-panel-id]');
      const results = [];
      panels.forEach(panel => {
        const id = panel.getAttribute('data-panel-id');
        const title = panel.querySelector('.panel-title')?.textContent || '';
        const value = panel.querySelector('.singlestat-panel-value')?.textContent || 
                      panel.querySelector('[data-testid="data-testid Panel value"]')?.textContent ||
                      panel.querySelector('.panel-value')?.textContent || '';
        results.push({ id, title, value });
      });
      return results;
    });
    
    console.log('Panel data:', JSON.stringify(panelData, null, 2));
  } catch (e) {
    console.log('Could not extract panel data:', e.message);
  }
  
  await browser.close();
  console.log('Done!');
})();