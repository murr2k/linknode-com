import { Page, expect } from '@playwright/test';

export abstract class BasePage {
  protected page: Page;
  protected url: string;

  constructor(page: Page) {
    this.page = page;
    this.url = '/';
  }

  /**
   * Navigate to the page
   */
  async goto(options?: { waitUntil?: 'load' | 'domcontentloaded' | 'networkidle' }) {
    await this.page.goto(this.url, options);
  }

  /**
   * Wait for page to be fully loaded
   */
  async waitForPageLoad() {
    await this.page.waitForLoadState('networkidle');
    await this.page.waitForLoadState('domcontentloaded');
  }

  /**
   * Take a screenshot for visual regression testing
   */
  async takeScreenshot(name: string, options?: { fullPage?: boolean; clip?: any }) {
    return await this.page.screenshot({
      path: `test-results/screenshots/${name}.png`,
      fullPage: options?.fullPage ?? false,
      clip: options?.clip,
    });
  }

  /**
   * Check if element is visible
   */
  async isElementVisible(selector: string): Promise<boolean> {
    try {
      const element = this.page.locator(selector);
      await element.waitFor({ state: 'visible', timeout: 5000 });
      return await element.isVisible();
    } catch {
      return false;
    }
  }

  /**
   * Get element text content
   */
  async getTextContent(selector: string): Promise<string> {
    const element = this.page.locator(selector);
    return (await element.textContent()) || '';
  }

  /**
   * Wait for API response
   */
  async waitForAPIResponse(urlPattern: string | RegExp, timeout: number = 30000) {
    return this.page.waitForResponse(
      response => {
        const url = response.url();
        return typeof urlPattern === 'string' 
          ? url.includes(urlPattern)
          : urlPattern.test(url);
      },
      { timeout }
    );
  }

  /**
   * Mock API response
   */
  async mockAPIResponse(urlPattern: string | RegExp, response: any) {
    await this.page.route(urlPattern, async route => {
      await route.fulfill({
        status: response.status || 200,
        contentType: response.contentType || 'application/json',
        body: JSON.stringify(response.body || {}),
        headers: response.headers || {},
      });
    });
  }

  /**
   * Intercept and log network requests
   */
  async interceptNetworkRequests(urlPattern?: string | RegExp) {
    const requests: Array<{ url: string; method: string; headers: any }> = [];
    
    this.page.on('request', request => {
      const url = request.url();
      if (!urlPattern || (typeof urlPattern === 'string' ? url.includes(urlPattern) : urlPattern.test(url))) {
        requests.push({
          url: request.url(),
          method: request.method(),
          headers: request.headers(),
        });
      }
    });

    return requests;
  }

  /**
   * Get performance metrics
   */
  async getPerformanceMetrics() {
    return await this.page.evaluate(() => {
      const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
      const paint = performance.getEntriesByType('paint');
      
      return {
        // Navigation timing
        navigationStart: navigation.startTime,
        domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
        loadComplete: navigation.loadEventEnd - navigation.loadEventStart,
        
        // Resource timing
        totalDuration: navigation.duration,
        dnsLookup: navigation.domainLookupEnd - navigation.domainLookupStart,
        tcpConnection: navigation.connectEnd - navigation.connectStart,
        serverResponse: navigation.responseEnd - navigation.requestStart,
        
        // Paint timing
        firstPaint: paint.find(p => p.name === 'first-paint')?.startTime || 0,
        firstContentfulPaint: paint.find(p => p.name === 'first-contentful-paint')?.startTime || 0,
        
        // Memory (if available)
        memory: (performance as any).memory ? {
          usedJSHeapSize: (performance as any).memory.usedJSHeapSize,
          totalJSHeapSize: (performance as any).memory.totalJSHeapSize,
          jsHeapSizeLimit: (performance as any).memory.jsHeapSizeLimit,
        } : null,
      };
    });
  }

  /**
   * Check accessibility
   */
  async checkAccessibility(options?: { includedImpacts?: string[] }) {
    const violations = await this.page.evaluate(async (opts) => {
      // This would use axe-core if injected
      // For now, we'll do basic checks
      const issues: any[] = [];
      
      // Check for alt text on images
      const images = document.querySelectorAll('img');
      images.forEach(img => {
        if (!img.alt) {
          issues.push({
            type: 'missing-alt-text',
            element: img.outerHTML,
            impact: 'serious',
          });
        }
      });
      
      // Check for form labels
      const inputs = document.querySelectorAll('input, select, textarea');
      inputs.forEach(input => {
        const id = input.id;
        if (id && !document.querySelector(`label[for="${id}"]`)) {
          issues.push({
            type: 'missing-label',
            element: input.outerHTML,
            impact: 'serious',
          });
        }
      });
      
      // Check heading structure
      const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
      let lastLevel = 0;
      headings.forEach(heading => {
        const level = parseInt(heading.tagName.substring(1));
        if (level - lastLevel > 1) {
          issues.push({
            type: 'heading-order',
            element: heading.outerHTML,
            impact: 'moderate',
          });
        }
        lastLevel = level;
      });
      
      return issues;
    }, options);
    
    return violations;
  }

  /**
   * Simulate network conditions
   */
  async simulateNetworkCondition(condition: 'slow-3g' | '3g' | '4g' | 'offline') {
    const conditions = {
      'slow-3g': {
        offline: false,
        downloadThroughput: 50 * 1024 / 8,
        uploadThroughput: 50 * 1024 / 8,
        latency: 400,
      },
      '3g': {
        offline: false,
        downloadThroughput: 1.5 * 1024 * 1024 / 8,
        uploadThroughput: 750 * 1024 / 8,
        latency: 100,
      },
      '4g': {
        offline: false,
        downloadThroughput: 4 * 1024 * 1024 / 8,
        uploadThroughput: 3 * 1024 * 1024 / 8,
        latency: 50,
      },
      'offline': {
        offline: true,
        downloadThroughput: 0,
        uploadThroughput: 0,
        latency: 0,
      },
    };

    const context = this.page.context();
    await context.route('**/*', route => route.continue());
    
    // Note: Playwright doesn't have built-in network throttling like CDP
    // This would need CDP protocol for true network simulation
    if (condition === 'offline') {
      await context.setOffline(true);
    }
  }
}