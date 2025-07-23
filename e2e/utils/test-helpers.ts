import { Page, expect } from '@playwright/test';

export const testHelpers = {
  /**
   * Wait for the page to be fully loaded
   */
  async waitForPageLoad(page: Page) {
    await page.waitForLoadState('networkidle');
    await page.waitForLoadState('domcontentloaded');
  },

  /**
   * Check if an element is visible and stable
   */
  async isElementVisible(page: Page, selector: string): Promise<boolean> {
    try {
      const element = page.locator(selector);
      await element.waitFor({ state: 'visible', timeout: 5000 });
      return await element.isVisible();
    } catch {
      return false;
    }
  },

  /**
   * Get text content safely
   */
  async getTextContent(page: Page, selector: string): Promise<string> {
    const element = page.locator(selector);
    return (await element.textContent()) || '';
  },

  /**
   * Wait for API response
   */
  async waitForAPIResponse(page: Page, urlPattern: string | RegExp) {
    return page.waitForResponse(
      response => {
        const url = response.url();
        return typeof urlPattern === 'string' 
          ? url.includes(urlPattern)
          : urlPattern.test(url);
      },
      { timeout: 30000 }
    );
  },

  /**
   * Verify meta tags for SEO
   */
  async verifyMetaTags(page: Page) {
    const metaTags = {
      description: await page.getAttribute('meta[name="description"]', 'content'),
      keywords: await page.getAttribute('meta[name="keywords"]', 'content'),
      ogTitle: await page.getAttribute('meta[property="og:title"]', 'content'),
      ogDescription: await page.getAttribute('meta[property="og:description"]', 'content'),
    };
    
    // Verify meta tags exist and have content
    for (const [key, value] of Object.entries(metaTags)) {
      expect(value, `Meta tag ${key} should have content`).toBeTruthy();
    }
    
    return metaTags;
  }
};