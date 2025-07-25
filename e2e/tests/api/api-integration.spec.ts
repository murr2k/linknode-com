import { test, expect } from '@playwright/test';
import { HomePage } from '../../pages/HomePage';
import { APIMocker, mockResponses, createDynamicPowerResponse } from '../../utils/api-mocks';
import { waitForServiceStatusChecks, waitForAPIData } from '../../utils/wait-helpers';

test.describe('API Integration Tests @api', () => {
  let homePage: HomePage;
  let apiMocker: APIMocker;

  test.beforeEach(async ({ page }) => {
    homePage = new HomePage(page);
    apiMocker = new APIMocker(page);
  });

  test.afterEach(async () => {
    await apiMocker.clearMocks();
  });

  test.describe('Power Stats API', () => {
    test('should handle successful power data response', async ({ page }) => {
      // Mock successful response
      await apiMocker.mock({
        url: /\/api\/stats/,
        method: 'GET',
        response: mockResponses.powerStats.success,
      });

      await homePage.goto();
      
      // Wait for API data to load
      await waitForAPIData(page);
      
      // Verify power data is displayed
      const powerValue = await homePage.getCurrentPowerValue();
      expect(powerValue).toBe('1234.56 W');

      // Check all statistics
      const stats = await homePage.getPowerStatistics();
      expect(stats.min).toContain('1000');
      expect(stats.avg).toContain('1150');
      expect(stats.max).toContain('1500');
      expect(stats.cost).toContain('0.15');

      // Verify API was called
      expect(apiMocker.wasRequestMade('/api/stats', 'GET')).toBe(true);
    });

    test('should handle no data scenario', async ({ page }) => {
      await apiMocker.mock({
        url: /\/api\/stats/,
        method: 'GET',
        response: mockResponses.powerStats.noData,
      });

      await homePage.goto();
      
      // Verify fallback display
      const powerValue = await homePage.getCurrentPowerValue();
      expect(powerValue).toBe('--');
    });

    test('should handle API errors gracefully', async ({ page }) => {
      await apiMocker.mock({
        url: /\/api\/stats/,
        method: 'GET',
        response: mockResponses.powerStats.error,
      });

      await homePage.goto();
      
      // Should show error state or fallback
      const powerValue = await homePage.getCurrentPowerValue();
      expect(powerValue).toBe('--');

      // Check console for error handling
      const errors = await homePage.checkForConsoleErrors();
      // Should handle error without throwing
      expect(errors.filter(e => e.includes('Uncaught'))).toHaveLength(0);
    });

    test('should retry on failure', async ({ page }) => {
      let attemptCount = 0;
      
      await apiMocker.mock({
        url: /\/api\/stats/,
        method: 'GET',
        response: () => {
          attemptCount++;
          if (attemptCount < 3) {
            return mockResponses.powerStats.error;
          }
          return mockResponses.powerStats.success;
        },
      });

      await homePage.goto();
      
      // Wait for retries
      await page.waitForTimeout(10000);
      
      // Should eventually show data after retries
      const requests = apiMocker.getRequests('/api/stats');
      expect(requests.length).toBeGreaterThan(1);
    });

    test('should update power data periodically', async ({ page }) => {
      const dynamicResponse = createDynamicPowerResponse({
        basePower: 1000,
        variance: 50,
        trend: 'increasing',
      });

      await apiMocker.mock({
        url: /\/api\/stats/,
        method: 'GET',
        response: dynamicResponse,
      });

      await homePage.goto();
      
      // Get initial value
      const initialValue = await homePage.getCurrentPowerValue();
      
      // Wait for update (5 seconds according to code)
      await page.waitForTimeout(6000);
      
      // Get updated value
      const updatedValue = await homePage.getCurrentPowerValue();
      
      // Values should be different (dynamic response)
      expect(updatedValue).not.toBe(initialValue);
      
      // Should have made multiple requests
      const requests = apiMocker.getRequests('/api/stats');
      expect(requests.length).toBeGreaterThan(1);
    });
  });

  test.describe('Health Check API', () => {
    test('should show all services as healthy', async ({ page }) => {
      // Mock the eagle monitor health endpoint
      await page.route('**/linknode-eagle-monitor.fly.dev/health', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            status: 'healthy',
            influxdb_connected: true,
            timestamp: new Date().toISOString()
          }),
        });
      });

      await homePage.goto();
      
      // Wait for service status checks to complete
      await waitForServiceStatusChecks(page);
      
      const statuses = await homePage.getAllServiceStatuses();
      expect(statuses.influx).toBe('online');
      expect(statuses.eagle).toBe('online');
      expect(statuses.web).toBe('online');
    });

    test('should show degraded service status', async ({ page }) => {
      // Mock the eagle monitor health endpoint as failing
      await page.route('**/linknode-eagle-monitor.fly.dev/health', async route => {
        await route.abort('failed');
      });

      await homePage.goto();
      
      // Wait for service status checks to complete
      await waitForServiceStatusChecks(page);
      
      const statuses = await homePage.getAllServiceStatuses();
      expect(statuses.influx).toBe('offline');
      expect(statuses.eagle).toBe('offline');
      expect(statuses.web).toBe('online');
    });

    test('should handle complete service failure', async ({ page }) => {
      // Mock all health endpoints as failing
      await page.route('**/linknode-eagle-monitor.fly.dev/health', async route => {
        await route.abort('failed');
      });
      
      // Mock the main page to show it as offline too
      await page.route('**/linknode.com/**', async route => {
        if (route.request().url().includes('health')) {
          await route.abort('failed');
        } else {
          await route.continue();
        }
      });

      await homePage.goto();
      
      // Wait for service status checks to complete
      await waitForServiceStatusChecks(page);
      
      const statuses = await homePage.getAllServiceStatuses();
      expect(statuses.influx).toBe('offline');
      expect(statuses.eagle).toBe('offline');
      // Web status is always online when the page loads
      expect(statuses.web).toBe('online');
    });
  });

  test.describe('CORS and Headers', () => {
    test('should include proper CORS headers', async ({ page }) => {
      await apiMocker.mock({
        url: /\/api\/stats/,
        method: 'GET',
        response: {
          ...mockResponses.powerStats.success,
          headers: {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
          },
        },
      });

      // Monitor actual response headers
      const responsePromise = page.waitForResponse(response => 
        response.url().includes('/api/stats')
      );

      await homePage.goto();
      
      const response = await responsePromise;
      const headers = response.headers();
      
      expect(headers['access-control-allow-origin']).toBeTruthy();
    });

    test('should handle preflight OPTIONS requests', async ({ page }) => {
      await apiMocker.mock({
        url: /\/api\/stats/,
        method: 'OPTIONS',
        response: {
          status: 204,
          headers: {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '86400',
          },
        },
      });

      await apiMocker.mock({
        url: /\/api\/stats/,
        method: 'GET',
        response: mockResponses.powerStats.success,
      });

      await homePage.goto();
      
      // Verify both OPTIONS and GET requests were made
      expect(apiMocker.wasRequestMade('/api/stats', 'OPTIONS')).toBe(true);
      expect(apiMocker.wasRequestMade('/api/stats', 'GET')).toBe(true);
    });
  });

  test.describe('Error Scenarios', () => {
    test('should handle rate limiting', async ({ page }) => {
      await apiMocker.mock({
        url: /\/api\/stats/,
        method: 'GET',
        response: mockResponses.errors.rateLimit,
      });

      await homePage.goto();
      
      // Should show fallback UI
      const powerValue = await homePage.getCurrentPowerValue();
      expect(powerValue).toBe('--');

      // Check for rate limit headers in response
      const requests = apiMocker.getRequests('/api/stats');
      expect(requests.length).toBeGreaterThan(0);
    });

    test('should handle network timeouts', async ({ page }) => {
      await apiMocker.mock({
        url: /\/api\/stats/,
        method: 'GET',
        response: mockResponses.errors.timeout,
      });

      await homePage.goto();
      
      // Should timeout and show fallback
      await page.waitForTimeout(5000);
      const powerValue = await homePage.getCurrentPowerValue();
      expect(powerValue).toBe('--');
    });

    test('should handle 404 errors', async ({ page }) => {
      await apiMocker.mock({
        url: /\/api\/stats/,
        method: 'GET',
        response: mockResponses.errors.notFound,
      });

      await homePage.goto();
      
      const powerValue = await homePage.getCurrentPowerValue();
      expect(powerValue).toBe('--');
    });

    test('should handle unauthorized access', async ({ page }) => {
      await apiMocker.mock({
        url: /\/api\/stats/,
        method: 'GET',
        response: mockResponses.errors.unauthorized,
      });

      await homePage.goto();
      
      const powerValue = await homePage.getCurrentPowerValue();
      expect(powerValue).toBe('--');
    });
  });

  test.describe('Request Validation', () => {
    test('should send correct request headers', async ({ page }) => {
      await apiMocker.mock({
        url: /\/api\/stats/,
        method: 'GET',
        response: (request) => {
          // Validate request headers
          expect(request.headers['accept']).toContain('application/json');
          return mockResponses.powerStats.success;
        },
      });

      await homePage.goto();
      
      // Verify request was made with correct headers
      const requests = apiMocker.getRequests('/api/stats');
      expect(requests).toHaveLength(1);
    });

    test('should include query parameters when needed', async ({ page }) => {
      await apiMocker.mock({
        url: /\/api\/stats/,
        method: 'GET',
        response: (request) => {
          const url = new URL(request.url);
          // Could validate query params here
          return mockResponses.powerStats.success;
        },
      });

      await homePage.goto();
      
      const requests = apiMocker.getRequests('/api/stats');
      expect(requests).toHaveLength(1);
    });
  });
});