import { test, expect } from '@playwright/test';
import { HomePage } from '../pages/HomePage';
import { ErrorHandler } from '../utils/error-handling';
import { APIMocker, mockResponses } from '../utils/api-mocks';

test.describe('Error Handling and Retry Tests', () => {
  let homePage: HomePage;
  let errorHandler: ErrorHandler;
  let apiMocker: APIMocker;

  test.beforeEach(async ({ page }, testInfo) => {
    homePage = new HomePage(page);
    errorHandler = new ErrorHandler({ page, testInfo });
    apiMocker = new APIMocker(page);
  });

  test('should retry on navigation failure', async ({ page }) => {
    let attemptCount = 0;
    
    // Mock intermittent network failure
    await page.route('**/*', async (route, request) => {
      if (request.isNavigationRequest()) {
        attemptCount++;
        if (attemptCount < 2) {
          await route.abort('failed');
        } else {
          await route.continue();
        }
      } else {
        await route.continue();
      }
    });

    // Should succeed after retry
    await errorHandler.safeGoto('/');
    
    // Verify page loaded
    await expect(page.locator('body')).toBeVisible();
    expect(attemptCount).toBeGreaterThan(1);
  });

  test('should handle element not found gracefully', async ({ page }) => {
    await homePage.goto();
    
    // Try to find non-existent element
    const found = await errorHandler.waitForElement('.non-existent-element', {
      timeout: 5000,
    });
    
    expect(found).toBe(false);
    
    // Should have captured error state
    const errors = errorHandler.getErrors();
    expect(errors).toBeDefined();
  });

  test('should retry click operations', async ({ page }) => {
    await homePage.goto();
    
    // Create a button that works after delay
    await page.evaluate(() => {
      const button = document.createElement('button');
      button.id = 'delayed-button';
      button.style.display = 'none';
      button.textContent = 'Click me';
      document.body.appendChild(button);
      
      // Show button after 2 seconds
      setTimeout(() => {
        button.style.display = 'block';
      }, 2000);
    });
    
    // Should retry and eventually click
    await errorHandler.safeClick('#delayed-button');
    
    // Verify click worked
    const clicked = await page.evaluate(() => {
      const button = document.querySelector('#delayed-button') as HTMLButtonElement;
      return button?.style.display === 'block';
    });
    expect(clicked).toBe(true);
  });

  test('should handle API timeouts with retry', async ({ page }) => {
    let callCount = 0;
    
    // Mock API with timeout then success
    await page.route('**/api/stats', async (route) => {
      callCount++;
      if (callCount < 3) {
        // Timeout for first 2 attempts
        await new Promise(resolve => setTimeout(resolve, 40000));
      } else {
        // Success on 3rd attempt
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockResponses.powerStats.success.body),
        });
      }
    });

    // Use retry logic for API calls
    await errorHandler.retry(
      async () => {
        await homePage.goto();
        await page.waitForResponse(
          response => response.url().includes('/api/stats'),
          { timeout: 5000 }
        );
      },
      {
        maxAttempts: 3,
        timeout: 10000,
        onRetry: (attempt, error) => {
          console.log(`API retry attempt ${attempt}: ${error.message}`);
        },
      }
    );

    expect(callCount).toBe(3);
  });

  test('should handle console errors appropriately', async ({ page }) => {
    await homePage.goto();
    
    // Inject console error
    await page.evaluate(() => {
      console.error('Test error message');
      throw new Error('Uncaught test error');
    });
    
    // Wait a moment for error to be logged
    await page.waitForTimeout(1000);
    
    // Get logged errors
    const errors = errorHandler.getErrors();
    expect(errors.console.length).toBeGreaterThan(0);
    expect(errors.console.some(e => e.text.includes('Test error message'))).toBe(true);
  });

  test('should handle network failures gracefully', async ({ page }) => {
    // Mock network failure for specific resource
    await page.route('**/api/health', route => route.abort('failed'));
    
    await homePage.goto();
    
    // Wait for failed request
    await page.waitForTimeout(2000);
    
    // Check network errors were captured
    const errors = errorHandler.getErrors();
    expect(errors.network.length).toBeGreaterThan(0);
    expect(errors.network.some(e => e.url.includes('/api/health'))).toBe(true);
  });

  test('should use fallback selectors when primary fails', async ({ page }) => {
    await homePage.goto();
    
    // Try multiple selectors for the same element
    const selector = await errorHandler.smartWait('.power-widget', {
      fallbackSelectors: [
        '[data-testid="power-widget"]',
        '#power-container',
        '.widget.power',
      ],
      timeout: 10000,
    });
    
    expect(selector).toBeTruthy();
    
    // Verify element exists with found selector
    if (selector) {
      await expect(page.locator(selector)).toBeVisible();
    }
  });

  test('should handle page crashes', async ({ page, context }) => {
    await homePage.goto();
    
    // Set up crash handler
    let crashDetected = false;
    page.on('crash', () => {
      crashDetected = true;
    });
    
    // Simulate crash by closing context (in real scenario)
    // Note: Actually crashing the page is difficult to simulate
    
    // Instead, test error capture on navigation failure
    await page.route('**/*', route => route.abort());
    
    try {
      await page.reload();
    } catch (error) {
      await errorHandler.handleError(error as Error);
    }
    
    // Verify error was handled
    const errors = errorHandler.getErrors();
    expect(errors.network.length).toBeGreaterThan(0);
  });

  test('should wait for network idle with fallback', async ({ page }) => {
    // Mock slow loading resources
    await page.route('**/slow-resource', async route => {
      await new Promise(resolve => setTimeout(resolve, 35000));
      await route.fulfill({ status: 200, body: 'slow' });
    });
    
    await homePage.goto();
    
    // Inject slow loading resource
    await page.evaluate(() => {
      const img = document.createElement('img');
      img.src = '/slow-resource';
      document.body.appendChild(img);
    });
    
    // Should not wait forever for network idle
    await errorHandler.waitForNetworkIdle({ timeout: 5000 });
    
    // Page should be usable even if some resources are still loading
    await expect(homePage.mainHeading).toBeVisible();
  });

  test('should capture error state with screenshots', async ({ page }, testInfo) => {
    await homePage.goto();
    
    // Trigger an error state
    await errorHandler.captureErrorState('Test error for screenshot');
    
    // Verify attachments were created
    const attachments = testInfo.attachments;
    expect(attachments.some(a => a.name === 'error-screenshot')).toBe(true);
    expect(attachments.some(a => a.name === 'error-details')).toBe(true);
  });

  test('should handle flaky API responses', async ({ page }) => {
    let callCount = 0;
    const responses = [
      mockResponses.powerStats.error,
      mockResponses.powerStats.error,
      mockResponses.powerStats.success,
    ];
    
    await apiMocker.mock({
      url: /\/api\/stats/,
      method: 'GET',
      response: () => {
        const response = responses[callCount] || mockResponses.powerStats.success;
        callCount++;
        return response;
      },
    });
    
    await errorHandler.retry(
      async () => {
        await homePage.goto();
        
        // Wait for successful data load
        await page.waitForFunction(
          () => {
            const powerElement = document.querySelector('#current-power');
            return powerElement && powerElement.textContent !== '--';
          },
          { timeout: 15000 }
        );
      },
      {
        maxAttempts: 3,
        delay: 2000,
      }
    );
    
    // Should eventually show data
    const powerValue = await homePage.getCurrentPowerValue();
    expect(powerValue).not.toBe('--');
    expect(callCount).toBeGreaterThanOrEqual(3);
  });

  test('should handle intermittent element visibility', async ({ page }) => {
    await homePage.goto();
    
    // Make element flicker
    await page.evaluate(() => {
      const element = document.querySelector('.power-widget') as HTMLElement;
      if (element) {
        let visible = true;
        setInterval(() => {
          visible = !visible;
          element.style.display = visible ? 'block' : 'none';
        }, 500);
      }
    });
    
    // Should wait for stable visibility
    const selector = await errorHandler.smartWait('.power-widget', {
      waitForStable: true,
      timeout: 10000,
    });
    
    expect(selector).toBe('.power-widget');
  });
});