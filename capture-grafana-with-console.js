const { chromium } = require('playwright');

(async () => {
  console.log('Starting Grafana capture with console logging...');
  
  const browser = await chromium.launch({
    headless: true
  });
  
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    ignoreHTTPSErrors: true
  });
  
  const page = await context.newPage();
  
  // Log console messages
  page.on('console', msg => {
    console.log('Browser console:', msg.type(), msg.text());
  });
  
  // Log page errors
  page.on('pageerror', err => {
    console.log('Page error:', err.message);
  });
  
  // Log failed requests
  page.on('requestfailed', request => {
    console.log('Request failed:', request.url(), request.failure().errorText);
  });
  
  console.log('Navigating to Grafana...');
  await page.goto('https://linknode-grafana.fly.dev/d/power-monitoring/eagle-energy-monitor', {
    waitUntil: 'domcontentloaded',
    timeout: 30000
  });
  
  // Check page content
  const pageContent = await page.content();
  if (pageContent.includes('Grafana has failed to load')) {
    console.log('ERROR: Grafana loading error screen detected');
    
    // Check if app.js is loading
    const appJsUrls = await page.evaluate(() => {
      const scripts = Array.from(document.querySelectorAll('script[src*="app"]'));
      return scripts.map(s => ({
        src: s.src,
        loaded: s.loaded !== false
      }));
    });
    console.log('App.js scripts:', appJsUrls);
  }
  
  // Wait and take screenshot
  await page.waitForTimeout(10000);
  
  await page.screenshot({ 
    path: 'test-results/grafana-console-capture.png',
    fullPage: true 
  });
  
  console.log('Screenshot saved');
  
  await browser.close();
})();