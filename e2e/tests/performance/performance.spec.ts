import { test, expect } from '@playwright/test';
import { HomePage } from '../../pages/HomePage';
import { PerformanceCollector } from '../../utils/performance-metrics';
import { APIMocker, mockResponses } from '../../utils/api-mocks';

test.describe('Performance Tests @performance', () => {
  let homePage: HomePage;
  let performanceCollector: PerformanceCollector;
  let apiMocker: APIMocker;

  // Performance budgets
  const PERFORMANCE_BUDGETS = {
    lcp: 2500, // 2.5s for good LCP
    fid: 100, // 100ms for good FID
    cls: 0.1, // 0.1 for good CLS
    firstContentfulPaint: 1800, // 1.8s
    domContentLoaded: 3000, // 3s
    totalRequests: 50, // Max 50 requests
    totalSize: 5 * 1024 * 1024, // 5MB max
    jsHeapUsed: 50 * 1024 * 1024, // 50MB max
  };

  test.beforeEach(async ({ page }) => {
    homePage = new HomePage(page);
    performanceCollector = new PerformanceCollector(page);
    apiMocker = new APIMocker(page);
    
    await performanceCollector.initialize();
  });

  test('should meet performance budget for initial page load', async ({ page }) => {
    // Start performance measurement
    await page.goto('/', { waitUntil: 'networkidle' });
    
    // Wait for page to stabilize
    await page.waitForTimeout(5000);
    
    // Collect metrics
    const metrics = await performanceCollector.collect();
    
    // Generate report
    const report = performanceCollector.generateReport(metrics);
    console.log(report);
    
    // Check performance budget
    const budgetCheck = performanceCollector.checkPerformanceBudget(metrics, PERFORMANCE_BUDGETS);
    
    if (!budgetCheck.passed) {
      console.log('Performance budget failures:', budgetCheck.failures);
    }
    
    // Assert Core Web Vitals
    expect(metrics.lcp, 'LCP should be under 2.5s').toBeLessThan(2500);
    expect(metrics.cls, 'CLS should be under 0.1').toBeLessThan(0.1);
    
    // Assert other key metrics
    expect(metrics.firstContentfulPaint, 'FCP should be under 1.8s').toBeLessThan(1800);
    expect(metrics.totalRequests, 'Total requests should be under 50').toBeLessThan(50);
  });

  test('should maintain performance with API data loading', async ({ page }) => {
    // Mock API responses with realistic delays
    await apiMocker.mock({
      url: /\/api\/stats/,
      method: 'GET',
      response: {
        ...mockResponses.powerStats.success,
        delay: 500, // Simulate API latency
      },
    });

    await apiMocker.mock({
      url: /\/health/,
      method: 'GET',
      response: {
        ...mockResponses.health.allHealthy,
        delay: 300,
      },
    });

    await page.goto('/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(5000);
    
    const metrics = await performanceCollector.collect();
    
    // API calls shouldn't significantly impact Core Web Vitals
    expect(metrics.lcp).toBeLessThan(3000);
    expect(metrics.cls).toBeLessThan(0.15);
  });

  test('should handle slow network conditions gracefully', async ({ page }) => {
    // Simulate slow 3G
    const client = await page.context().newCDPSession(page);
    await client.send('Network.enable');
    await client.send('Network.emulateNetworkConditions', {
      offline: false,
      downloadThroughput: 50 * 1024 / 8, // 50kb/s
      uploadThroughput: 50 * 1024 / 8,
      latency: 400,
    });

    await page.goto('/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(10000);
    
    const metrics = await performanceCollector.collect();
    
    // Even on slow network, CLS should remain low
    expect(metrics.cls).toBeLessThan(0.25);
    
    // Total blocking time should be reasonable
    expect(metrics.totalBlockingTime).toBeLessThan(1000);
  });

  test('should optimize resource loading', async ({ page }) => {
    await page.goto('/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);
    
    const metrics = await performanceCollector.collect();
    const resourceBreakdown = await performanceCollector.getResourceBreakdown();
    
    console.log('Resource Breakdown:', resourceBreakdown);
    
    // Check resource optimization
    expect(metrics.cachedRequests / metrics.totalRequests).toBeGreaterThan(0.2); // At least 20% cached
    
    // Check for reasonable resource counts by type
    if (resourceBreakdown.script) {
      expect(resourceBreakdown.script.count).toBeLessThan(20);
    }
    if (resourceBreakdown.css) {
      expect(resourceBreakdown.css.count).toBeLessThan(10);
    }
    if (resourceBreakdown.image) {
      expect(resourceBreakdown.image.count).toBeLessThan(30);
    }
  });

  test('should have minimal layout shifts', async ({ page }) => {
    await page.goto('/');
    
    // Monitor layout shifts during page lifecycle
    const layoutShifts = await page.evaluate(() => {
      const shifts: number[] = [];
      
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (!(entry as any).hadRecentInput) {
            shifts.push((entry as any).value);
          }
        }
      }).observe({ entryTypes: ['layout-shift'] });
      
      return new Promise<number[]>((resolve) => {
        // Monitor for 5 seconds
        setTimeout(() => resolve(shifts), 5000);
      });
    });
    
    // Total CLS should be low
    const totalCLS = layoutShifts.reduce((sum, shift) => sum + shift, 0);
    expect(totalCLS).toBeLessThan(0.1);
    
    // No single shift should be too large
    layoutShifts.forEach(shift => {
      expect(shift).toBeLessThan(0.05);
    });
  });

  test('should load critical resources efficiently', async ({ page }) => {
    const criticalResources: string[] = [];
    
    page.on('response', response => {
      const url = response.url();
      const timing = response.timing();
      
      // Track critical resources (main document, CSS, critical JS)
      if (
        url.includes('.css') ||
        url.includes('main.js') ||
        response.request().resourceType() === 'document'
      ) {
        criticalResources.push(url);
      }
    });
    
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    
    const metrics = await performanceCollector.collect();
    
    // Critical resources should load quickly
    expect(metrics.domContentLoaded).toBeLessThan(2000);
    
    // Should have reasonable number of critical resources
    expect(criticalResources.length).toBeLessThan(10);
  });

  test('should maintain performance during interactions', async ({ page }) => {
    await page.goto('/', { waitUntil: 'networkidle' });
    
    // Measure performance during user interactions
    const interactionMetrics = await page.evaluate(async () => {
      const metrics = {
        clickResponseTime: 0,
        renderingTime: 0,
      };
      
      // Measure click response time
      const button = document.querySelector('.refresh-button, button');
      if (button) {
        const startTime = performance.now();
        button.dispatchEvent(new Event('click'));
        await new Promise(resolve => setTimeout(resolve, 100));
        metrics.clickResponseTime = performance.now() - startTime;
      }
      
      // Measure rendering performance
      const startRender = performance.now();
      for (let i = 0; i < 10; i++) {
        document.body.style.transform = `translateX(${i}px)`;
        await new Promise(resolve => requestAnimationFrame(resolve));
      }
      metrics.renderingTime = (performance.now() - startRender) / 10;
      
      return metrics;
    });
    
    // Interactions should be responsive
    expect(interactionMetrics.clickResponseTime).toBeLessThan(100);
    expect(interactionMetrics.renderingTime).toBeLessThan(16.67); // 60fps
  });

  test('should not have memory leaks', async ({ page }) => {
    await page.goto('/', { waitUntil: 'networkidle' });
    
    // Get initial memory usage
    const initialMetrics = await performanceCollector.collect();
    const initialMemory = initialMetrics.jsHeapUsed;
    
    // Perform actions that could cause memory leaks
    for (let i = 0; i < 5; i++) {
      await page.reload({ waitUntil: 'networkidle' });
      await page.waitForTimeout(2000);
    }
    
    // Force garbage collection if possible
    await page.evaluate(() => {
      if ((window as any).gc) {
        (window as any).gc();
      }
    });
    
    await page.waitForTimeout(2000);
    
    // Get final memory usage
    const finalMetrics = await performanceCollector.collect();
    const finalMemory = finalMetrics.jsHeapUsed;
    
    // Memory growth should be reasonable (less than 50% increase)
    const memoryGrowth = (finalMemory - initialMemory) / initialMemory;
    expect(memoryGrowth).toBeLessThan(0.5);
  });

  test('should optimize API calls', async ({ page }) => {
    let apiCallCount = 0;
    
    await apiMocker.mock({
      url: /\/api\/stats/,
      method: 'GET',
      response: () => {
        apiCallCount++;
        return mockResponses.powerStats.success;
      },
    });
    
    await page.goto('/', { waitUntil: 'networkidle' });
    
    // Wait for potential API polling
    await page.waitForTimeout(15000);
    
    // API calls should be reasonable (not too frequent)
    expect(apiCallCount).toBeLessThan(5); // Max 5 calls in 15 seconds
    expect(apiCallCount).toBeGreaterThan(1); // At least initial call + 1 update
  });

  test('should provide performance hints', async ({ page }) => {
    await page.goto('/', { waitUntil: 'networkidle' });
    
    // Check for performance best practices
    const performanceHints = await page.evaluate(() => {
      const hints = {
        hasLazyLoadingImages: false,
        hasPreconnectHints: false,
        hasCriticalCSS: false,
        hasServiceWorker: false,
      };
      
      // Check for lazy loading
      const images = document.querySelectorAll('img[loading="lazy"]');
      hints.hasLazyLoadingImages = images.length > 0;
      
      // Check for preconnect hints
      const preconnects = document.querySelectorAll('link[rel="preconnect"]');
      hints.hasPreconnectHints = preconnects.length > 0;
      
      // Check for critical CSS
      const criticalStyles = document.querySelector('style[data-critical]');
      hints.hasCriticalCSS = !!criticalStyles;
      
      // Check for service worker
      hints.hasServiceWorker = 'serviceWorker' in navigator && navigator.serviceWorker.controller !== null;
      
      return hints;
    });
    
    console.log('Performance Hints:', performanceHints);
    
    // These are recommendations, not hard requirements
    if (!performanceHints.hasLazyLoadingImages) {
      console.log('Consider implementing lazy loading for images');
    }
    if (!performanceHints.hasPreconnectHints) {
      console.log('Consider adding preconnect hints for third-party domains');
    }
  });
});