import { Page, CDPSession } from '@playwright/test';

export interface PerformanceMetrics {
  // Navigation timing
  navigationStart: number;
  domContentLoaded: number;
  loadComplete: number;
  firstPaint: number;
  firstContentfulPaint: number;
  largestContentfulPaint: number;
  
  // Resource timing
  totalDuration: number;
  dnsLookup: number;
  tcpConnection: number;
  tlsNegotiation: number;
  serverResponse: number;
  domInteractive: number;
  domComplete: number;
  
  // Core Web Vitals
  lcp: number; // Largest Contentful Paint
  fid: number; // First Input Delay
  cls: number; // Cumulative Layout Shift
  
  // Custom metrics
  timeToInteractive: number;
  totalBlockingTime: number;
  
  // Memory metrics
  jsHeapUsed: number;
  jsHeapTotal: number;
  
  // Network metrics
  totalRequests: number;
  totalSize: number;
  cachedRequests: number;
  failedRequests: number;
}

export class PerformanceCollector {
  private page: Page;
  private cdp: CDPSession | null = null;
  private networkRequests: Array<{
    url: string;
    method: string;
    status: number;
    size: number;
    duration: number;
    cached: boolean;
  }> = [];

  constructor(page: Page) {
    this.page = page;
  }

  /**
   * Initialize performance monitoring
   */
  async initialize() {
    // Set up network monitoring
    this.page.on('response', async response => {
      const request = response.request();
      
      this.networkRequests.push({
        url: response.url(),
        method: request.method(),
        status: response.status(),
        size: response.headers()['content-length'] ? 
          parseInt(response.headers()['content-length']) : 0,
        duration: 0, // timing() was removed in newer Playwright versions
        cached: response.fromCache(),
      });
    });

    // Enable CDP for advanced metrics
    try {
      this.cdp = await this.page.context().newCDPSession(this.page);
      await this.cdp.send('Performance.enable');
      await this.cdp.send('Runtime.enable');
    } catch (e) {
      console.log('CDP not available, using fallback metrics');
    }
  }

  /**
   * Collect all performance metrics
   */
  async collect(): Promise<PerformanceMetrics> {
    // Get navigation timing
    const navigationTiming = await this.getNavigationTiming();
    
    // Get paint timing
    const paintTiming = await this.getPaintTiming();
    
    // Get Core Web Vitals
    const webVitals = await this.getCoreWebVitals();
    
    // Get memory usage
    const memory = await this.getMemoryUsage();
    
    // Get network stats
    const networkStats = this.getNetworkStats();
    
    return {
      // Navigation timing
      navigationStart: navigationTiming.navigationStart,
      domContentLoaded: navigationTiming.domContentLoaded,
      loadComplete: navigationTiming.loadComplete,
      firstPaint: paintTiming.firstPaint,
      firstContentfulPaint: paintTiming.firstContentfulPaint,
      largestContentfulPaint: webVitals.lcp,
      
      // Resource timing
      totalDuration: navigationTiming.totalDuration,
      dnsLookup: navigationTiming.dnsLookup,
      tcpConnection: navigationTiming.tcpConnection,
      tlsNegotiation: navigationTiming.tlsNegotiation,
      serverResponse: navigationTiming.serverResponse,
      domInteractive: navigationTiming.domInteractive,
      domComplete: navigationTiming.domComplete,
      
      // Core Web Vitals
      lcp: webVitals.lcp,
      fid: webVitals.fid,
      cls: webVitals.cls,
      
      // Custom metrics
      timeToInteractive: await this.getTimeToInteractive(),
      totalBlockingTime: await this.getTotalBlockingTime(),
      
      // Memory metrics
      jsHeapUsed: memory.used,
      jsHeapTotal: memory.total,
      
      // Network metrics
      totalRequests: networkStats.totalRequests,
      totalSize: networkStats.totalSize,
      cachedRequests: networkStats.cachedRequests,
      failedRequests: networkStats.failedRequests,
    };
  }

  /**
   * Get navigation timing metrics
   */
  private async getNavigationTiming() {
    return await this.page.evaluate(() => {
      const nav = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
      
      return {
        navigationStart: nav.startTime,
        domContentLoaded: nav.domContentLoadedEventEnd - nav.domContentLoadedEventStart,
        loadComplete: nav.loadEventEnd - nav.loadEventStart,
        totalDuration: nav.duration,
        dnsLookup: nav.domainLookupEnd - nav.domainLookupStart,
        tcpConnection: nav.connectEnd - nav.connectStart,
        tlsNegotiation: nav.secureConnectionStart > 0 ? 
          nav.connectEnd - nav.secureConnectionStart : 0,
        serverResponse: nav.responseEnd - nav.requestStart,
        domInteractive: nav.domInteractive - nav.responseEnd,
        domComplete: nav.domComplete - nav.domInteractive,
      };
    });
  }

  /**
   * Get paint timing metrics
   */
  private async getPaintTiming() {
    return await this.page.evaluate(() => {
      const paintEntries = performance.getEntriesByType('paint');
      const firstPaint = paintEntries.find(entry => entry.name === 'first-paint');
      const firstContentfulPaint = paintEntries.find(entry => entry.name === 'first-contentful-paint');
      
      return {
        firstPaint: firstPaint?.startTime || 0,
        firstContentfulPaint: firstContentfulPaint?.startTime || 0,
      };
    });
  }

  /**
   * Get Core Web Vitals
   */
  private async getCoreWebVitals() {
    return await this.page.evaluate(() => {
      return new Promise<{ lcp: number; fid: number; cls: number }>((resolve) => {
        let lcp = 0;
        let fid = 0;
        let cls = 0;
        
        // Observe LCP
        new PerformanceObserver((entryList) => {
          const entries = entryList.getEntries();
          const lastEntry = entries[entries.length - 1];
          lcp = lastEntry.startTime;
        }).observe({ entryTypes: ['largest-contentful-paint'] });
        
        // Observe FID
        new PerformanceObserver((entryList) => {
          const entries = entryList.getEntries();
          if (entries.length > 0) {
            fid = entries[0].processingStart - entries[0].startTime;
          }
        }).observe({ entryTypes: ['first-input'] });
        
        // Observe CLS
        let clsValue = 0;
        new PerformanceObserver((entryList) => {
          for (const entry of entryList.getEntries()) {
            if (!(entry as any).hadRecentInput) {
              clsValue += (entry as any).value;
            }
          }
          cls = clsValue;
        }).observe({ entryTypes: ['layout-shift'] });
        
        // Wait a bit for metrics to be collected
        setTimeout(() => {
          resolve({ lcp, fid, cls });
        }, 5000);
      });
    });
  }

  /**
   * Get memory usage
   */
  private async getMemoryUsage() {
    if (this.cdp) {
      try {
        const result = await this.cdp.send('Runtime.evaluate', {
          expression: 'performance.memory',
          returnByValue: true,
        });
        
        if (result.result.value) {
          return {
            used: result.result.value.usedJSHeapSize,
            total: result.result.value.totalJSHeapSize,
          };
        }
      } catch (e) {
        console.log('Failed to get memory metrics via CDP');
      }
    }
    
    // Fallback
    return await this.page.evaluate(() => {
      if ((performance as any).memory) {
        return {
          used: (performance as any).memory.usedJSHeapSize,
          total: (performance as any).memory.totalJSHeapSize,
        };
      }
      return { used: 0, total: 0 };
    });
  }

  /**
   * Get Time to Interactive
   */
  private async getTimeToInteractive(): Promise<number> {
    return await this.page.evaluate(() => {
      return new Promise<number>((resolve) => {
        // Simple TTI approximation
        const checkInteractive = () => {
          const longtasks = performance.getEntriesByType('longtask');
          const lastLongtask = longtasks[longtasks.length - 1];
          
          if (!lastLongtask || Date.now() - lastLongtask.startTime > 5000) {
            resolve(performance.now());
          } else {
            setTimeout(checkInteractive, 100);
          }
        };
        
        if (document.readyState === 'complete') {
          checkInteractive();
        } else {
          window.addEventListener('load', () => {
            setTimeout(checkInteractive, 100);
          });
        }
      });
    });
  }

  /**
   * Get Total Blocking Time
   */
  private async getTotalBlockingTime(): Promise<number> {
    return await this.page.evaluate(() => {
      let totalBlockingTime = 0;
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.duration > 50) {
            totalBlockingTime += entry.duration - 50;
          }
        }
      });
      
      observer.observe({ entryTypes: ['longtask'] });
      
      return new Promise<number>((resolve) => {
        setTimeout(() => {
          observer.disconnect();
          resolve(totalBlockingTime);
        }, 5000);
      });
    });
  }

  /**
   * Get network statistics
   */
  private getNetworkStats() {
    const failed = this.networkRequests.filter(r => r.status >= 400).length;
    const cached = this.networkRequests.filter(r => r.cached).length;
    const totalSize = this.networkRequests.reduce((sum, r) => sum + r.size, 0);
    
    return {
      totalRequests: this.networkRequests.length,
      failedRequests: failed,
      cachedRequests: cached,
      totalSize: totalSize,
    };
  }

  /**
   * Get resource breakdown by type
   */
  async getResourceBreakdown() {
    return await this.page.evaluate(() => {
      const resources = performance.getEntriesByType('resource') as PerformanceResourceTiming[];
      const breakdown: Record<string, { count: number; size: number; duration: number }> = {};
      
      resources.forEach(resource => {
        const type = resource.initiatorType || 'other';
        if (!breakdown[type]) {
          breakdown[type] = { count: 0, size: 0, duration: 0 };
        }
        
        breakdown[type].count++;
        breakdown[type].size += resource.transferSize || 0;
        breakdown[type].duration += resource.duration;
      });
      
      return breakdown;
    });
  }

  /**
   * Generate performance report
   */
  generateReport(metrics: PerformanceMetrics): string {
    const report = `
Performance Report
==================

Navigation Timing:
- DOM Content Loaded: ${metrics.domContentLoaded.toFixed(2)}ms
- Page Load Complete: ${metrics.loadComplete.toFixed(2)}ms
- Total Duration: ${metrics.totalDuration.toFixed(2)}ms

Paint Timing:
- First Paint: ${metrics.firstPaint.toFixed(2)}ms
- First Contentful Paint: ${metrics.firstContentfulPaint.toFixed(2)}ms
- Largest Contentful Paint: ${metrics.largestContentfulPaint.toFixed(2)}ms

Core Web Vitals:
- LCP: ${metrics.lcp.toFixed(2)}ms ${metrics.lcp < 2500 ? '✅' : metrics.lcp < 4000 ? '⚠️' : '❌'}
- FID: ${metrics.fid.toFixed(2)}ms ${metrics.fid < 100 ? '✅' : metrics.fid < 300 ? '⚠️' : '❌'}
- CLS: ${metrics.cls.toFixed(3)} ${metrics.cls < 0.1 ? '✅' : metrics.cls < 0.25 ? '⚠️' : '❌'}

Network Performance:
- Total Requests: ${metrics.totalRequests}
- Failed Requests: ${metrics.failedRequests}
- Cached Requests: ${metrics.cachedRequests}
- Total Size: ${(metrics.totalSize / 1024 / 1024).toFixed(2)}MB

Memory Usage:
- JS Heap Used: ${(metrics.jsHeapUsed / 1024 / 1024).toFixed(2)}MB
- JS Heap Total: ${(metrics.jsHeapTotal / 1024 / 1024).toFixed(2)}MB

Other Metrics:
- Time to Interactive: ${metrics.timeToInteractive.toFixed(2)}ms
- Total Blocking Time: ${metrics.totalBlockingTime.toFixed(2)}ms
`;
    
    return report;
  }

  /**
   * Check if metrics meet performance budget
   */
  checkPerformanceBudget(metrics: PerformanceMetrics, budget: Partial<PerformanceMetrics>): {
    passed: boolean;
    failures: string[];
  } {
    const failures: string[] = [];
    
    Object.entries(budget).forEach(([key, threshold]) => {
      const actual = metrics[key as keyof PerformanceMetrics];
      if (typeof actual === 'number' && typeof threshold === 'number' && actual > threshold) {
        failures.push(`${key}: ${actual.toFixed(2)} > ${threshold} (budget)`);
      }
    });
    
    return {
      passed: failures.length === 0,
      failures,
    };
  }
}