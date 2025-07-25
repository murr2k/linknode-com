const https = require('https');

// Test different Grafana endpoints
const endpoints = [
  '/api/health',
  '/api/dashboards/uid/power-monitoring',
  '/api/datasources',
  '/api/org',
  '/api/frontend/settings'
];

async function testEndpoint(path) {
  return new Promise((resolve) => {
    https.get(`https://linknode-grafana.fly.dev${path}`, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          console.log(`✓ ${path}:`, JSON.stringify(json, null, 2).substring(0, 100) + '...');
        } catch (e) {
          console.log(`✗ ${path}: Not JSON - ${data.substring(0, 100)}...`);
        }
        resolve();
      });
    }).on('error', (e) => {
      console.log(`✗ ${path}: Error - ${e.message}`);
      resolve();
    });
  });
}

(async () => {
  console.log('Testing Grafana API endpoints...\n');
  
  for (const endpoint of endpoints) {
    await testEndpoint(endpoint);
  }
  
  console.log('\nNow testing dashboard render endpoint...');
  await testEndpoint('/render/d/power-monitoring/eagle-energy-monitor');
  
  // Check panel 3 data specifically
  console.log('\nChecking panel 3 configuration...');
  https.get('https://linknode-grafana.fly.dev/api/dashboards/uid/power-monitoring', (res) => {
    let data = '';
    res.on('data', chunk => data += chunk);
    res.on('end', () => {
      const dashboard = JSON.parse(data);
      const panel3 = dashboard.dashboard.panels.find(p => p.id === 3);
      console.log('Panel 3 config:', JSON.stringify(panel3, null, 2));
    });
  });
})();