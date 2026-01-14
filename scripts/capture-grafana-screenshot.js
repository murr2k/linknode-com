const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  console.log('Navigating to Grafana dashboard...');
  await page.goto('https://linknode-grafana.fly.dev/d/power-monitoring/eagle-energy-monitor?orgId=1&refresh=5s');
  
  // Wait for dashboard to load
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(5000); // Extra wait for data
  
  // Take screenshot
  const screenshotPath = 'grafana-dashboard-verification.png';
  await page.screenshot({ 
    path: screenshotPath,
    fullPage: true 
  });
  
  console.log(`Screenshot saved to: ${screenshotPath}`);
  
  // Check page content for units
  const content = await page.content();
  
  console.log('\nChecking for unit displays:');
  if (content.includes('GWh')) {
    console.log('❌ Found GWh (this should not appear anymore)');
  } else {
    console.log('✅ No GWh units found');
  }
  
  if (content.includes('kWh')) {
    console.log('✅ Found kWh units');
  }
  
  if (content.includes(' W')) {
    console.log('✅ Found W (watts) units');
  }
  
  await browser.close();
})();