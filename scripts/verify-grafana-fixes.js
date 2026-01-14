const { chromium } = require('playwright');

(async () => {
  console.log('Verifying Grafana dashboard fixes...\n');
  
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();
  
  try {
    console.log('Navigating to Grafana dashboard...');
    await page.goto('https://linknode-grafana.fly.dev/d/power-monitoring/eagle-energy-monitor?orgId=1&refresh=5s', {
      waitUntil: 'networkidle',
      timeout: 30000
    });
    
    // Wait for panels to load
    await page.waitForTimeout(5000);
    
    // Take screenshot
    await page.screenshot({ 
      path: 'grafana-dashboard-verification.png',
      fullPage: true 
    });
    console.log('Screenshot saved to: grafana-dashboard-verification.png');
    
    // Extract text content from the page
    const pageText = await page.evaluate(() => document.body.innerText);
    
    console.log('\n=== VERIFICATION RESULTS ===\n');
    
    // Check for GWh (should NOT be present)
    if (pageText.includes('GWh')) {
      console.log('❌ ISSUE: Found GWh units (these should not appear for normal usage)');
      // Find where GWh appears
      const lines = pageText.split('\n');
      lines.forEach((line, i) => {
        if (line.includes('GWh')) {
          console.log(`   Line ${i}: ${line.trim()}`);
        }
      });
    } else {
      console.log('✅ PASS: No GWh units found (correct)');
    }
    
    // Check for expected units
    console.log('\n--- Unit Display Check ---');
    if (pageText.includes('kWh')) {
      console.log('✅ Found kWh units (correct for energy)');
    }
    
    if (pageText.includes(' W')) {
      console.log('✅ Found W units (correct for power)');
    }
    
    // Try to extract specific values
    console.log('\n--- Value Extraction ---');
    
    // Look for numeric values with units
    const valuePattern = /(\d+(?:\.\d+)?)\s*(W|kWh|MWh|GWh)\b/g;
    const matches = pageText.match(valuePattern);
    
    if (matches) {
      console.log('Found values with units:');
      matches.forEach(match => {
        console.log(`  - ${match}`);
      });
    }
    
    // Check decimal precision
    console.log('\n--- Decimal Precision Check ---');
    const decimalPattern = /(\d+\.\d+)\s*(W|kWh)/g;
    const decimalMatches = pageText.match(decimalPattern);
    
    if (decimalMatches) {
      decimalMatches.forEach(match => {
        const parts = match.match(/(\d+\.(\d+))\s*(W|kWh)/);
        if (parts) {
          const decimals = parts[2].length;
          const unit = parts[3];
          console.log(`  ${match} - ${decimals} decimal places for ${unit}`);
          
          // Verify expected precision
          if (unit === 'W' && decimals > 0) {
            console.log(`    ⚠️  Power (W) has decimals, expected 0`);
          } else if (unit === 'kWh' && decimals !== 2) {
            console.log(`    ⚠️  Energy (kWh) has ${decimals} decimals, expected 2`);
          }
        }
      });
    }
    
  } catch (error) {
    console.error('Error during verification:', error.message);
  } finally {
    await browser.close();
  }
})();