import { Page, TestInfo, errors } from '@playwright/test';

export interface RetryOptions {
  maxAttempts?: number;
  delay?: number;
  backoff?: boolean;
  timeout?: number;
  onRetry?: (attempt: number, error: Error) => void;
}

export interface ErrorContext {
  page: Page;
  testInfo: TestInfo;
  screenshot?: boolean;
  trace?: boolean;
  consoleErrors?: boolean;
}

export class ErrorHandler {
  private context: ErrorContext;
  private consoleErrors: Array<{ type: string; text: string; timestamp: Date }> = [];
  private networkErrors: Array<{ url: string; error: string; timestamp: Date }> = [];

  constructor(context: ErrorContext) {
    this.context = context;
    this.setupErrorMonitoring();
  }

  /**
   * Set up error monitoring
   */
  private setupErrorMonitoring() {
    // Monitor console errors
    this.context.page.on('console', msg => {
      if (msg.type() === 'error') {
        this.consoleErrors.push({
          type: msg.type(),
          text: msg.text(),
          timestamp: new Date(),
        });
      }
    });

    // Monitor page crashes
    this.context.page.on('crash', () => {
      this.captureErrorState('Page crashed');
    });

    // Monitor network failures
    this.context.page.on('requestfailed', request => {
      this.networkErrors.push({
        url: request.url(),
        error: request.failure()?.errorText || 'Unknown error',
        timestamp: new Date(),
      });
    });
  }

  /**
   * Retry a function with exponential backoff
   */
  async retry<T>(
    fn: () => Promise<T>,
    options: RetryOptions = {}
  ): Promise<T> {
    const {
      maxAttempts = 3,
      delay = 1000,
      backoff = true,
      timeout = 30000,
      onRetry,
    } = options;

    let lastError: Error;
    
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        // Add timeout wrapper
        const result = await Promise.race([
          fn(),
          new Promise<never>((_, reject) => 
            setTimeout(() => reject(new Error('Timeout')), timeout)
          ),
        ]);
        
        return result;
      } catch (error) {
        lastError = error as Error;
        
        if (attempt < maxAttempts) {
          const waitTime = backoff ? delay * Math.pow(2, attempt - 1) : delay;
          
          if (onRetry) {
            onRetry(attempt, lastError);
          }
          
          console.log(`Retry attempt ${attempt}/${maxAttempts} after ${waitTime}ms. Error: ${lastError.message}`);
          
          await new Promise(resolve => setTimeout(resolve, waitTime));
        }
      }
    }
    
    // All attempts failed
    await this.captureErrorState(`All ${maxAttempts} attempts failed: ${lastError!.message}`);
    throw lastError!;
  }

  /**
   * Safe navigation with retry
   */
  async safeGoto(url: string, options?: any): Promise<void> {
    await this.retry(
      async () => {
        try {
          await this.context.page.goto(url, {
            waitUntil: 'domcontentloaded',
            timeout: 30000,
            ...options,
          });
        } catch (error) {
          if (error instanceof errors.TimeoutError) {
            // Try with reduced wait condition
            await this.context.page.goto(url, {
              waitUntil: 'commit',
              timeout: 60000,
              ...options,
            });
          } else {
            throw error;
          }
        }
      },
      {
        maxAttempts: 3,
        delay: 2000,
        onRetry: (attempt) => {
          console.log(`Navigation retry ${attempt} for ${url}`);
        },
      }
    );
  }

  /**
   * Safe element interaction with retry
   */
  async safeClick(selector: string, options?: any): Promise<void> {
    await this.retry(
      async () => {
        const element = this.context.page.locator(selector);
        await element.waitFor({ state: 'visible', timeout: 10000 });
        await element.click(options);
      },
      {
        maxAttempts: 3,
        delay: 1000,
        onRetry: (attempt) => {
          console.log(`Click retry ${attempt} for ${selector}`);
        },
      }
    );
  }

  /**
   * Safe text input with retry
   */
  async safeFill(selector: string, value: string, options?: any): Promise<void> {
    await this.retry(
      async () => {
        const element = this.context.page.locator(selector);
        await element.waitFor({ state: 'visible', timeout: 10000 });
        await element.fill(value, options);
      },
      {
        maxAttempts: 3,
        delay: 1000,
      }
    );
  }

  /**
   * Wait for element with custom error handling
   */
  async waitForElement(
    selector: string,
    options: { timeout?: number; state?: 'attached' | 'detached' | 'visible' | 'hidden' } = {}
  ): Promise<boolean> {
    try {
      await this.context.page.locator(selector).waitFor({
        timeout: options.timeout || 30000,
        state: options.state || 'visible',
      });
      return true;
    } catch (error) {
      if (error instanceof errors.TimeoutError) {
        await this.captureErrorState(`Element not found: ${selector}`);
        return false;
      }
      throw error;
    }
  }

  /**
   * Capture error state for debugging
   */
  async captureErrorState(errorMessage: string) {
    console.error(`Error: ${errorMessage}`);
    
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    
    try {
      // Take screenshot if enabled
      if (this.context.screenshot !== false) {
        const screenshotPath = `test-results/errors/error-${timestamp}.png`;
        await this.context.page.screenshot({
          path: screenshotPath,
          fullPage: true,
        });
        console.log(`Screenshot saved: ${screenshotPath}`);
      }
      
      // Save page HTML
      const html = await this.context.page.content();
      const fs = require('fs');
      const htmlPath = `test-results/errors/error-${timestamp}.html`;
      fs.writeFileSync(htmlPath, html);
      console.log(`HTML saved: ${htmlPath}`);
      
      // Log console errors
      if (this.consoleErrors.length > 0) {
        console.log('Console errors:', this.consoleErrors);
      }
      
      // Log network errors
      if (this.networkErrors.length > 0) {
        console.log('Network errors:', this.networkErrors);
      }
      
      // Attach to test report
      if (this.context.testInfo) {
        await this.context.testInfo.attach('error-screenshot', {
          body: await this.context.page.screenshot({ fullPage: true }),
          contentType: 'image/png',
        });
        
        await this.context.testInfo.attach('error-details', {
          body: JSON.stringify({
            error: errorMessage,
            url: this.context.page.url(),
            consoleErrors: this.consoleErrors,
            networkErrors: this.networkErrors,
            timestamp: new Date().toISOString(),
          }, null, 2),
          contentType: 'application/json',
        });
      }
    } catch (captureError) {
      console.error('Failed to capture error state:', captureError);
    }
  }

  /**
   * Get all errors
   */
  getErrors() {
    return {
      console: [...this.consoleErrors],
      network: [...this.networkErrors],
    };
  }

  /**
   * Clear error logs
   */
  clearErrors() {
    this.consoleErrors = [];
    this.networkErrors = [];
  }

  /**
   * Handle specific error types
   */
  async handleError(error: Error): Promise<void> {
    if (error instanceof errors.TimeoutError) {
      console.log('Timeout error detected, capturing page state...');
      await this.captureErrorState(`Timeout: ${error.message}`);
    } else if (error.message.includes('net::ERR_')) {
      console.log('Network error detected:', error.message);
      await this.captureErrorState(`Network error: ${error.message}`);
    } else if (error.message.includes('Target closed')) {
      console.log('Page closed unexpectedly');
      await this.captureErrorState('Page closed unexpectedly');
    } else {
      await this.captureErrorState(`Unknown error: ${error.message}`);
    }
  }

  /**
   * Graceful degradation for flaky elements
   */
  async tryMultipleSelectors(selectors: string[], action: (selector: string) => Promise<void>): Promise<boolean> {
    for (const selector of selectors) {
      try {
        const exists = await this.context.page.locator(selector).count() > 0;
        if (exists) {
          await action(selector);
          return true;
        }
      } catch (error) {
        console.log(`Selector ${selector} failed, trying next...`);
      }
    }
    return false;
  }

  /**
   * Wait for network idle with timeout
   */
  async waitForNetworkIdle(options: { timeout?: number; maxInflightRequests?: number } = {}): Promise<void> {
    const { timeout = 30000, maxInflightRequests = 0 } = options;
    
    try {
      await this.context.page.waitForLoadState('networkidle', { timeout });
    } catch (error) {
      console.log('Network idle timeout, checking if page is usable...');
      
      // Check if critical elements are loaded
      const criticalElements = ['body', 'main', '[role="main"]'];
      const loaded = await this.tryMultipleSelectors(
        criticalElements,
        async (selector) => {
          await this.context.page.locator(selector).waitFor({ state: 'visible', timeout: 5000 });
        }
      );
      
      if (!loaded) {
        throw new Error('Page failed to load critical elements');
      }
    }
  }

  /**
   * Smart wait for element
   */
  async smartWait(selector: string, options: { 
    timeout?: number; 
    fallbackSelectors?: string[];
    waitForStable?: boolean;
  } = {}): Promise<string | null> {
    const { timeout = 30000, fallbackSelectors = [], waitForStable = true } = options;
    
    // Try primary selector
    try {
      const element = this.context.page.locator(selector);
      await element.waitFor({ state: 'visible', timeout });
      
      if (waitForStable) {
        // Wait for element to be stable (not moving)
        await element.evaluate(el => {
          return new Promise<void>(resolve => {
            let lastPosition = el.getBoundingClientRect();
            const checkStable = () => {
              const currentPosition = el.getBoundingClientRect();
              if (
                lastPosition.top === currentPosition.top &&
                lastPosition.left === currentPosition.left
              ) {
                resolve();
              } else {
                lastPosition = currentPosition;
                setTimeout(checkStable, 100);
              }
            };
            checkStable();
          });
        });
      }
      
      return selector;
    } catch (error) {
      // Try fallback selectors
      for (const fallback of fallbackSelectors) {
        try {
          await this.context.page.locator(fallback).waitFor({ state: 'visible', timeout: 5000 });
          return fallback;
        } catch {
          continue;
        }
      }
      
      return null;
    }
  }
}

// Decorator for automatic retry
export function withRetry(options: RetryOptions = {}) {
  return function (target: any, propertyKey: string, descriptor: PropertyDescriptor) {
    const originalMethod = descriptor.value;
    
    descriptor.value = async function (...args: any[]) {
      const errorHandler = new ErrorHandler({
        page: this.page,
        testInfo: this.testInfo,
      });
      
      return await errorHandler.retry(
        () => originalMethod.apply(this, args),
        options
      );
    };
    
    return descriptor;
  };
}