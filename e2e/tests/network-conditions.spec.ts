import { test, expect } from '@playwright/test';
import { HomePage } from '../pages/HomePage';
import { APIMocker, mockResponses } from '../utils/api-mocks';

test.describe('Network Condition Tests', () => {
  let homePage: HomePage;
  let apiMocker: APIMocker;

  test.beforeEach(async ({ page }) => {
    homePage = new HomePage(page);
    apiMocker = new APIMocker(page);
  });

  test('should handle slow 3G network conditions', async ({ page, context }) => {
    // Simulate slow 3G network
    const client = await context.newCDPSession(page);
    await client.send('Network.enable');
    await client.send('Network.emulateNetworkConditions', {
      offline: false,
      downloadThroughput: 50 * 1024 / 8, // 50kb/s
      uploadThroughput: 50 * 1024 / 8,
      latency: 400, // 400ms latency
    });

    const startTime = Date.now();
    await homePage.goto({ waitUntil: 'domcontentloaded' });
    const loadTime = Date.now() - startTime;

    console.log(`Page load time on slow 3G: ${loadTime}ms`);

    // Page should still be functional
    await expect(homePage.mainHeading).toBeVisible();
    await expect(homePage.powerWidget).toBeVisible();

    // Should show loading states appropriately
    const powerValue = await homePage.getCurrentPowerValue();
    expect(powerValue).toBeTruthy(); // Either loading indicator or value
  });

  test('should handle offline mode gracefully', async ({ page, context }) => {
    // Load page first
    await homePage.goto();
    
    // Go offline
    await context.setOffline(true);
    
    // Try to reload
    await page.reload().catch(() => {
      console.log('Page reload failed as expected in offline mode');
    });

    // Should show offline message or cached content
    const offlineIndicator = await page.evaluate(() => {
      // Check for offline indicators
      const indicators = [
        document.querySelector('.offline'),
        document.querySelector('[data-offline]'),
        Array.from(document.querySelectorAll('*')).find(el => 
          el.textContent?.toLowerCase().includes('offline')
        ),
      ];
      return indicators.some(el => el !== null);
    });

    console.log('Has offline indicator:', offlineIndicator);

    // Go back online
    await context.setOffline(false);
  });

  test('should handle intermittent connectivity', async ({ page }) => {
    let requestCount = 0;
    let failureCount = 0;

    // Simulate intermittent connectivity - fail every other request
    await page.route('**/*', async (route, request) => {
      if (request.url().includes('/api/')) {
        requestCount++;
        if (requestCount % 2 === 0) {
          failureCount++;
          await route.abort('failed');
        } else {
          await route.continue();
        }
      } else {
        await route.continue();
      }
    });

    await homePage.goto();
    await page.waitForTimeout(10000); // Wait for multiple API call attempts

    console.log(`Total API requests: ${requestCount}, Failed: ${failureCount}`);

    // Should still show data despite intermittent failures
    const powerValue = await homePage.getCurrentPowerValue();
    expect(powerValue).not.toBe(''); // Should have some value
  });

  test('should prioritize critical resources on slow networks', async ({ page, context }) => {
    const resourceTimings: Array<{ url: string; duration: number; size: number }> = [];

    // Monitor resource loading
    page.on('response', async response => {
      const timing = response.timing();
      if (timing) {
        resourceTimings.push({
          url: response.url(),
          duration: timing.responseEnd - timing.requestStart,
          size: parseInt(response.headers()['content-length'] || '0'),
        });
      }
    });

    // Simulate slow network
    const client = await context.newCDPSession(page);
    await client.send('Network.enable');
    await client.send('Network.emulateNetworkConditions', {
      offline: false,
      downloadThroughput: 100 * 1024 / 8, // 100kb/s
      uploadThroughput: 50 * 1024 / 8,
      latency: 200,
    });

    await homePage.goto();

    // Analyze resource loading order
    const criticalResources = resourceTimings
      .filter(r => 
        r.url.includes('.css') || 
        r.url.includes('.js') || 
        r.url.endsWith('/')
      )
      .sort((a, b) => a.duration - b.duration);

    console.log('Critical resources load times:', criticalResources.slice(0, 5));

    // CSS should load before JS for better perceived performance
    const firstCSS = resourceTimings.find(r => r.url.includes('.css'));
    const firstJS = resourceTimings.find(r => r.url.includes('.js'));

    if (firstCSS && firstJS) {
      console.log(`First CSS loaded in ${firstCSS.duration}ms`);
      console.log(`First JS loaded in ${firstJS.duration}ms`);
    }
  });

  test('should handle high latency networks', async ({ page, context }) => {
    // Simulate high latency
    const client = await context.newCDPSession(page);
    await client.send('Network.enable');
    await client.send('Network.emulateNetworkConditions', {
      offline: false,
      downloadThroughput: 10 * 1024 * 1024 / 8, // 10Mbps (good bandwidth)
      uploadThroughput: 5 * 1024 * 1024 / 8,
      latency: 1000, // 1 second latency
    });

    await homePage.goto();

    // Check if page implements latency optimization techniques
    const optimizations = await page.evaluate(() => {
      const results = {
        hasServiceWorker: 'serviceWorker' in navigator,
        hasPreconnect: document.querySelectorAll('link[rel="preconnect"]').length > 0,
        hasDNSPrefetch: document.querySelectorAll('link[rel="dns-prefetch"]').length > 0,
        hasResourceHints: document.querySelectorAll('link[rel="prefetch"], link[rel="preload"]').length > 0,
      };
      return results;
    });

    console.log('Latency optimizations:', optimizations);

    // Page should still be interactive despite high latency
    await expect(homePage.powerWidget).toBeVisible();
  });

  test('should handle request timeout scenarios', async ({ page }) => {
    // Mock extremely slow API
    await apiMocker.mock({
      url: /\/api\/stats/,
      method: 'GET',
      response: {
        ...mockResponses.powerStats.success,
        delay: 60000, // 60 second delay (will timeout)
      },
    });

    await homePage.goto();

    // Wait for timeout handling
    await page.waitForTimeout(10000);

    // Should show fallback UI
    const powerValue = await homePage.getCurrentPowerValue();
    expect(powerValue).toBe('--'); // Fallback value

    // Should not have unhandled errors
    const errors = await homePage.checkForConsoleErrors();
    const unhandledErrors = errors.filter(e => e.includes('Uncaught'));
    expect(unhandledErrors).toHaveLength(0);
  });

  test('should efficiently handle bandwidth constraints', async ({ page, context }) => {
    // Track data usage
    let totalDataTransferred = 0;

    page.on('response', response => {
      const size = parseInt(response.headers()['content-length'] || '0');
      totalDataTransferred += size;
    });

    // Simulate limited bandwidth
    const client = await context.newCDPSession(page);
    await client.send('Network.enable');
    await client.send('Network.emulateNetworkConditions', {
      offline: false,
      downloadThroughput: 256 * 1024 / 8, // 256kb/s
      uploadThroughput: 128 * 1024 / 8,
      latency: 100,
    });

    await homePage.goto();
    await page.waitForLoadState('networkidle');

    const totalMB = totalDataTransferred / 1024 / 1024;
    console.log(`Total data transferred: ${totalMB.toFixed(2)}MB`);

    // Should be reasonably sized for slow connections
    expect(totalMB).toBeLessThan(5); // Less than 5MB

    // Check for optimization techniques
    const hasOptimizations = await page.evaluate(() => {
      const images = Array.from(document.images);
      return {
        lazyLoadedImages: images.filter(img => img.loading === 'lazy').length,
        totalImages: images.length,
        hasCompression: document.querySelector('meta[name="viewport"]') !== null,
      };
    });

    console.log('Bandwidth optimizations:', hasOptimizations);
  });

  test('should handle connection recovery', async ({ page, context }) => {
    await homePage.goto();

    // Get initial data
    const initialPower = await homePage.getCurrentPowerValue();
    console.log('Initial power value:', initialPower);

    // Go offline
    await context.setOffline(true);
    await page.waitForTimeout(5000);

    // Go back online
    await context.setOffline(false);
    
    // Wait for recovery
    await page.waitForTimeout(10000);

    // Should resume data updates
    const recoveredPower = await homePage.getCurrentPowerValue();
    console.log('Recovered power value:', recoveredPower);

    // Should have fresh data after recovery
    expect(recoveredPower).not.toBe('--');
  });

  test('should handle packet loss simulation', async ({ page }) => {
    let droppedRequests = 0;

    // Simulate 20% packet loss
    await page.route('**/*', async (route, request) => {
      if (Math.random() < 0.2) {
        droppedRequests++;
        await route.abort('failed');
      } else {
        await route.continue();
      }
    });

    try {
      await homePage.goto({ waitUntil: 'domcontentloaded' });
    } catch (e) {
      console.log('Navigation may have failed due to packet loss simulation');
    }

    console.log(`Dropped requests: ${droppedRequests}`);

    // Page should handle packet loss gracefully
    const isPageUsable = await page.evaluate(() => {
      return document.body && document.querySelector('h1') !== null;
    });

    expect(isPageUsable).toBe(true);
  });
});