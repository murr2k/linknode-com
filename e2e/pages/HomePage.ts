import { Page, Locator } from '@playwright/test';
import { BasePage } from './BasePage';

export class HomePage extends BasePage {
  // Locators
  readonly header: Locator;
  readonly mainHeading: Locator;
  readonly subtitle: Locator;
  readonly metricsSection: Locator;
  readonly liveMetricsSection: Locator;
  readonly powerWidget: Locator;
  readonly apiStatusWidget: Locator;
  readonly grafanaPreview: Locator;
  readonly footer: Locator;

  // Power monitoring elements
  readonly currentPower: Locator;
  readonly powerMin: Locator;
  readonly powerAvg: Locator;
  readonly powerMax: Locator;
  readonly powerCost: Locator;
  readonly powerUpdateIndicator: Locator;

  // API status elements
  readonly influxStatus: Locator;
  readonly eagleStatus: Locator;
  readonly webStatus: Locator;

  // Grafana elements
  readonly grafanaIframe: Locator;

  constructor(page: Page) {
    super(page);
    this.url = '/';

    // Initialize locators
    this.header = page.locator('header');
    this.mainHeading = page.locator('h1').first();
    this.subtitle = page.locator('.subtitle');
    this.metricsSection = page.locator('.metrics');
    this.liveMetricsSection = page.locator('.live-metrics-section');
    this.powerWidget = page.locator('.power-widget');
    this.apiStatusWidget = page.locator('.api-status-widget');
    this.grafanaPreview = page.locator('.grafana-preview');
    this.footer = page.locator('.footer');

    // Power monitoring locators
    this.currentPower = page.locator('#current-power');
    this.powerMin = page.locator('#power-min');
    this.powerAvg = page.locator('#power-avg');
    this.powerMax = page.locator('#power-max');
    this.powerCost = page.locator('#power-cost');
    this.powerUpdateIndicator = page.locator('#power-update-indicator');

    // API status locators
    this.influxStatus = page.locator('#influx-status');
    this.eagleStatus = page.locator('#eagle-status');
    this.webStatus = page.locator('#web-status');

    // Grafana locators
    this.grafanaIframe = page.locator('.grafana-preview iframe');
  }

  /**
   * Get current power value
   */
  async getCurrentPowerValue(): Promise<string> {
    await this.currentPower.waitFor({ state: 'visible' });
    return (await this.currentPower.textContent()) || '--';
  }

  /**
   * Get all power statistics
   */
  async getPowerStatistics() {
    return {
      current: await this.getCurrentPowerValue(),
      min: await this.powerMin.textContent() || '--',
      avg: await this.powerAvg.textContent() || '--',
      max: await this.powerMax.textContent() || '--',
      cost: await this.powerCost.textContent() || '--',
    };
  }

  /**
   * Check if power data is updating
   */
  async isPowerDataUpdating(): Promise<boolean> {
    const classes = await this.powerUpdateIndicator.getAttribute('class') || '';
    return classes.includes('pulse') || classes.includes('updating');
  }

  /**
   * Get service status
   */
  async getServiceStatus(service: 'influx' | 'eagle' | 'web'): Promise<'online' | 'offline' | 'unknown'> {
    const statusMap = {
      influx: this.influxStatus,
      eagle: this.eagleStatus,
      web: this.webStatus,
    };

    const statusElement = statusMap[service];
    const classes = await statusElement.getAttribute('class') || '';
    
    if (classes.includes('online') || classes.includes('success')) return 'online';
    if (classes.includes('offline') || classes.includes('error')) return 'offline';
    return 'unknown';
  }

  /**
   * Get all service statuses
   */
  async getAllServiceStatuses() {
    return {
      influx: await this.getServiceStatus('influx'),
      eagle: await this.getServiceStatus('eagle'),
      web: await this.getServiceStatus('web'),
    };
  }

  /**
   * Wait for Grafana dashboard to load
   */
  async waitForGrafanaDashboard() {
    await this.grafanaIframe.waitFor({ state: 'visible' });
    
    // Wait for iframe to have content
    await this.page.waitForFunction(
      () => {
        const iframe = document.querySelector('.grafana-preview iframe') as HTMLIFrameElement;
        return iframe && iframe.contentDocument && iframe.contentDocument.readyState === 'complete';
      },
      { timeout: 30000 }
    );
  }

  /**
   * Get Grafana dashboard URL
   */
  async getGrafanaDashboardUrl(): Promise<string | null> {
    return await this.grafanaIframe.getAttribute('src');
  }

  /**
   * Get all metric values
   */
  async getAllMetrics() {
    const metrics: Record<string, string> = {};
    const metricElements = await this.page.locator('.metric').all();
    
    for (const metric of metricElements) {
      const label = await metric.locator('.metric-label').textContent() || '';
      const value = await metric.locator('.metric-value').textContent() || '';
      metrics[label.toLowerCase().replace(/\s+/g, '_')] = value;
    }
    
    return metrics;
  }

  /**
   * Check if page has console errors
   */
  async checkForConsoleErrors(): Promise<string[]> {
    const errors: string[] = [];
    
    this.page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });
    
    // Wait a bit to catch any delayed errors
    await this.page.waitForTimeout(2000);
    
    return errors;
  }

  /**
   * Get page meta tags for SEO validation
   */
  async getMetaTags() {
    return {
      title: await this.page.title(),
      description: await this.page.getAttribute('meta[name="description"]', 'content'),
      keywords: await this.page.getAttribute('meta[name="keywords"]', 'content'),
      canonical: await this.page.getAttribute('link[rel="canonical"]', 'href'),
      ogTitle: await this.page.getAttribute('meta[property="og:title"]', 'content'),
      ogDescription: await this.page.getAttribute('meta[property="og:description"]', 'content'),
      ogImage: await this.page.getAttribute('meta[property="og:image"]', 'content'),
      viewport: await this.page.getAttribute('meta[name="viewport"]', 'content'),
    };
  }

  /**
   * Mock power API responses
   */
  async mockPowerData(data: {
    current_power?: number;
    min_power?: number;
    avg_power?: number;
    max_power?: number;
    cost?: number;
  }) {
    await this.mockAPIResponse(/\/api\/stats/, {
      status: 200,
      body: {
        current_power: data.current_power ?? 1234.56,
        min_power: data.min_power ?? 1000.00,
        avg_power: data.avg_power ?? 1150.25,
        max_power: data.max_power ?? 1500.00,
        cost: data.cost ?? 0.15,
        timestamp: new Date().toISOString(),
      },
    });
  }

  /**
   * Mock service health API
   */
  async mockServiceHealth(services: {
    influx?: boolean;
    eagle?: boolean;
    web?: boolean;
  }) {
    await this.mockAPIResponse(/\/health/, {
      status: 200,
      body: {
        status: 'ok',
        services: {
          influxdb: services.influx ?? true,
          eagle_monitor: services.eagle ?? true,
          web_interface: services.web ?? true,
        },
        timestamp: new Date().toISOString(),
      },
    });
  }
}