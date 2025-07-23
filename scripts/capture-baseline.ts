import { chromium, Browser, Page } from 'playwright';
import * as fs from 'fs';
import * as path from 'path';

interface BaselineData {
  timestamp: string;
  version: string;
  features: Record<string, any>;
  performance: Record<string, any>;
  visual: Record<string, string>;
  api: Record<string, any>;
  metadata: Record<string, any>;
}

class BaselineCapture {
  private browser: Browser | null = null;
  private page: Page | null = null;
  private baselineDir: string;
  private baselineData: BaselineData;

  constructor() {
    this.baselineDir = path.join(process.cwd(), 'test-baselines');
    this.baselineData = {
      timestamp: new Date().toISOString(),
      version: '1.0.0',
      features: {},
      performance: {},
      visual: {},
      api: {},
      metadata: {}
    };
  }

  async initialize() {
    // Create baseline directory
    if (!fs.existsSync(this.baselineDir)) {
      fs.mkdirSync(this.baselineDir, { recursive: true });
    }

    // Create subdirectories
    const subdirs = ['visual', 'performance', 'api', 'reports'];
    subdirs.forEach(dir => {
      const dirPath = path.join(this.baselineDir, dir);
      if (!fs.existsSync(dirPath)) {
        fs.mkdirSync(dirPath, { recursive: true });
      }
    });

    // Launch browser
    this.browser = await chromium.launch({
      headless: true,
      args: ['--enable-precise-memory-info']
    });

    this.page = await this.browser.newPage({
      viewport: { width: 1920, height: 1080 }
    });

    console.log('✅ Baseline capture initialized');
  }

  async captureWebsiteState() {
    if (!this.page) throw new Error('Page not initialized');

    console.log('📸 Capturing website state...');

    // Navigate to homepage
    await this.page.goto('https://linknode.com', { waitUntil: 'networkidle' });

    // Capture build info
    try {
      const buildInfo = await this.page.evaluate(async () => {
        const response = await fetch('/build-info.json');
        return response.json();
      });
      this.baselineData.metadata.buildInfo = buildInfo;
      console.log('  ✓ Build info captured:', buildInfo);
    } catch (e) {
      console.log('  ⚠ Build info not available');
    }

    // Capture page structure
    const pageStructure = await this.page.evaluate(() => {
      const elements = {
        header: !!document.querySelector('header'),
        mainHeading: document.querySelector('h1')?.textContent,
        metricsSection: !!document.querySelector('.metrics'),
        powerWidget: !!document.querySelector('.power-widget'),
        apiStatusWidget: !!document.querySelector('.api-status-widget'),
        grafanaPreview: !!document.querySelector('.grafana-preview'),
        buildStatus: !!document.querySelector('.build-status'),
        footer: !!document.querySelector('.footer')
      };
      return elements;
    });
    this.baselineData.features.pageStructure = pageStructure;
    console.log('  ✓ Page structure captured');

    // Capture feature availability
    const features = await this.page.evaluate(() => {
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
    this.baselineData.features.functionality = features;
    console.log('  ✓ Feature availability captured');
  }

  async captureVisualBaselines() {
    if (!this.page) throw new Error('Page not initialized');

    console.log('🎨 Capturing visual baselines...');

    const viewports = [
      { width: 1920, height: 1080, name: 'desktop-1080p' },
      { width: 1440, height: 900, name: 'desktop-900p' },
      { width: 768, height: 1024, name: 'tablet-portrait' },
      { width: 375, height: 667, name: 'mobile' }
    ];

    for (const viewport of viewports) {
      await this.page.setViewportSize({ width: viewport.width, height: viewport.height });
      await this.page.waitForTimeout(500); // Allow layout to settle

      const screenshotPath = path.join(this.baselineDir, 'visual', `baseline-${viewport.name}.png`);
      await this.page.screenshot({
        path: screenshotPath,
        fullPage: true
      });
      
      this.baselineData.visual[viewport.name] = screenshotPath;
      console.log(`  ✓ ${viewport.name} screenshot captured`);
    }

    // Reset to default viewport
    await this.page.setViewportSize({ width: 1920, height: 1080 });

    // Capture component states
    const components = [
      { selector: '.power-widget', name: 'power-widget' },
      { selector: '.api-status-widget', name: 'api-status-widget' },
      { selector: '.build-status', name: 'build-status' },
      { selector: '.metrics', name: 'metrics-section' }
    ];

    for (const component of components) {
      try {
        const element = await this.page.$(component.selector);
        if (element) {
          const screenshotPath = path.join(this.baselineDir, 'visual', `component-${component.name}.png`);
          await element.screenshot({ path: screenshotPath });
          this.baselineData.visual[`component-${component.name}`] = screenshotPath;
          console.log(`  ✓ ${component.name} component captured`);
        }
      } catch (e) {
        console.log(`  ⚠ Could not capture ${component.name}`);
      }
    }
  }

  async capturePerformanceBaselines() {
    if (!this.page) throw new Error('Page not initialized');

    console.log('⚡ Capturing performance baselines...');

    // Clear cache and reload for clean metrics
    await this.page.context().clearCookies();
    await this.page.reload({ waitUntil: 'networkidle' });

    // Capture navigation timing
    const navigationTiming = await this.page.evaluate(() => {
      const nav = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
      return {
        domContentLoaded: nav.domContentLoadedEventEnd - nav.domContentLoadedEventStart,
        loadComplete: nav.loadEventEnd - nav.loadEventStart,
        totalDuration: nav.duration,
        dnsLookup: nav.domainLookupEnd - nav.domainLookupStart,
        tcpConnection: nav.connectEnd - nav.connectStart,
        serverResponse: nav.responseEnd - nav.requestStart,
        domInteractive: nav.domInteractive - nav.responseEnd,
        domComplete: nav.domComplete - nav.domInteractive
      };
    });
    this.baselineData.performance.navigation = navigationTiming;
    console.log('  ✓ Navigation timing captured');

    // Capture paint timing
    const paintTiming = await this.page.evaluate(() => {
      const paintEntries = performance.getEntriesByType('paint');
      const fcp = paintEntries.find(entry => entry.name === 'first-contentful-paint');
      const fp = paintEntries.find(entry => entry.name === 'first-paint');
      return {
        firstPaint: fp?.startTime || 0,
        firstContentfulPaint: fcp?.startTime || 0
      };
    });
    this.baselineData.performance.paint = paintTiming;
    console.log('  ✓ Paint timing captured');

    // Capture Core Web Vitals (simplified)
    await this.page.waitForTimeout(3000); // Wait for metrics to stabilize
    
    const webVitals = await this.page.evaluate(() => {
      return {
        lcp: performance.getEntriesByType('largest-contentful-paint')[0]?.startTime || 0,
        cls: 0, // Would need observer for accurate CLS
        fid: 0  // Would need user interaction for FID
      };
    });
    this.baselineData.performance.webVitals = webVitals;
    console.log('  ✓ Web Vitals captured');

    // Capture resource metrics
    const resources = await this.page.evaluate(() => {
      const resources = performance.getEntriesByType('resource') as PerformanceResourceTiming[];
      const breakdown: Record<string, number> = {};
      
      resources.forEach(resource => {
        const type = resource.initiatorType || 'other';
        breakdown[type] = (breakdown[type] || 0) + 1;
      });
      
      return {
        total: resources.length,
        breakdown,
        totalSize: resources.reduce((sum, r) => sum + (r.transferSize || 0), 0)
      };
    });
    this.baselineData.performance.resources = resources;
    console.log('  ✓ Resource metrics captured');
  }

  async captureAPIBaselines() {
    if (!this.page) throw new Error('Page not initialized');

    console.log('🔌 Capturing API baselines...');

    // Monitor API calls
    const apiCalls: any[] = [];
    
    this.page.on('response', async response => {
      const url = response.url();
      if (url.includes('/api/') || url.includes('/health')) {
        apiCalls.push({
          url,
          status: response.status(),
          method: response.request().method(),
          headers: response.headers()
        });
      }
    });

    // Reload to capture API calls
    await this.page.reload({ waitUntil: 'networkidle' });
    await this.page.waitForTimeout(3000); // Wait for API calls

    this.baselineData.api.endpoints = apiCalls;
    console.log(`  ✓ ${apiCalls.length} API endpoints captured`);

    // Test specific endpoints
    const endpoints = [
      '/api/stats',
      '/api/current',
      '/health',
      '/build-info.json'
    ];

    for (const endpoint of endpoints) {
      try {
        const response = await this.page.evaluate(async (url) => {
          const res = await fetch(url);
          return {
            status: res.status,
            contentType: res.headers.get('content-type'),
            ok: res.ok
          };
        }, `https://linknode.com${endpoint}`);
        
        this.baselineData.api[endpoint] = response;
        console.log(`  ✓ ${endpoint}: ${response.status}`);
      } catch (e) {
        console.log(`  ⚠ ${endpoint}: Failed to test`);
      }
    }
  }

  async generateBaselineReport() {
    console.log('📊 Generating baseline report...');

    const report = {
      ...this.baselineData,
      summary: {
        captureDate: new Date().toISOString(),
        features: Object.keys(this.baselineData.features.functionality || {}).length,
        visualSnapshots: Object.keys(this.baselineData.visual).length,
        performanceMetrics: Object.keys(this.baselineData.performance).length,
        apiEndpoints: this.baselineData.api.endpoints?.length || 0
      }
    };

    // Save JSON baseline
    const jsonPath = path.join(this.baselineDir, 'baseline.json');
    fs.writeFileSync(jsonPath, JSON.stringify(report, null, 2));
    console.log(`  ✓ Baseline data saved to ${jsonPath}`);

    // Generate markdown report
    const markdown = this.generateMarkdownReport(report);
    const mdPath = path.join(this.baselineDir, 'BASELINE_REPORT.md');
    fs.writeFileSync(mdPath, markdown);
    console.log(`  ✓ Baseline report saved to ${mdPath}`);

    return report;
  }

  private generateMarkdownReport(data: any): string {
    return `# Regression Testing Baseline Report
Generated: ${new Date().toLocaleString()}

## Summary
- **Capture Date**: ${data.summary.captureDate}
- **Visual Snapshots**: ${data.summary.visualSnapshots}
- **Performance Metrics**: ${data.summary.performanceMetrics}
- **API Endpoints**: ${data.summary.apiEndpoints}

## Build Information
${data.metadata.buildInfo ? `
- **Version**: ${data.metadata.buildInfo.version}
- **Build Date**: ${data.metadata.buildInfo.buildDate}
- **Commit**: ${data.metadata.buildInfo.commit}
- **Environment**: ${data.metadata.buildInfo.environment}
` : 'Build information not available'}

## Feature Availability
### Page Structure
${Object.entries(data.features.pageStructure || {}).map(([key, value]) => 
  `- **${key}**: ${value === true ? '✅ Present' : value || '❌ Not found'}`
).join('\n')}

### Functionality
${Object.entries(data.features.functionality || {}).map(([section, features]: [string, any]) => `
#### ${section}
${Object.entries(features).map(([feature, available]) => 
  `- **${feature}**: ${available ? '✅ Available' : '❌ Not available'}`
).join('\n')}`
).join('\n')}

## Performance Baselines
### Navigation Timing
${Object.entries(data.performance.navigation || {}).map(([metric, value]) => 
  `- **${metric}**: ${value}ms`
).join('\n')}

### Paint Timing
${Object.entries(data.performance.paint || {}).map(([metric, value]) => 
  `- **${metric}**: ${value}ms`
).join('\n')}

### Core Web Vitals
- **LCP**: ${data.performance.webVitals?.lcp || 'N/A'}ms
- **CLS**: ${data.performance.webVitals?.cls || 'N/A'}
- **FID**: ${data.performance.webVitals?.fid || 'N/A'}ms

### Resource Loading
- **Total Resources**: ${data.performance.resources?.total || 0}
- **Total Size**: ${((data.performance.resources?.totalSize || 0) / 1024 / 1024).toFixed(2)}MB

## API Endpoints
${(data.api.endpoints || []).map((endpoint: any) => 
  `- **${endpoint.method} ${endpoint.url}**: ${endpoint.status}`
).join('\n')}

## Visual Baselines
The following visual baselines were captured:
${Object.keys(data.visual || {}).map(name => `- ${name}`).join('\n')}

## Usage
This baseline can be used for:
1. Regression testing after deployments
2. Visual comparison testing
3. Performance degradation detection
4. API contract validation
5. Feature availability verification
`;
  }

  async cleanup() {
    if (this.browser) {
      await this.browser.close();
    }
    console.log('✅ Cleanup complete');
  }

  async run() {
    try {
      await this.initialize();
      await this.captureWebsiteState();
      await this.captureVisualBaselines();
      await this.capturePerformanceBaselines();
      await this.captureAPIBaselines();
      const report = await this.generateBaselineReport();
      
      console.log('\n✨ Baseline capture complete!');
      console.log(`📁 Results saved to: ${this.baselineDir}`);
      
      return report;
    } catch (error) {
      console.error('❌ Error during baseline capture:', error);
      throw error;
    } finally {
      await this.cleanup();
    }
  }
}

// Run if called directly
if (require.main === module) {
  const capture = new BaselineCapture();
  capture.run().catch(console.error);
}

export { BaselineCapture };