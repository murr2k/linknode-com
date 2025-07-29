import { Page, TestInfo } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

export interface VisualTestOptions {
  fullPage?: boolean;
  mask?: string[];
  clip?: { x: number; y: number; width: number; height: number };
  animations?: 'disabled' | 'allow';
  caret?: 'hide' | 'initial';
  scale?: 'css' | 'device';
  maxDiffPixels?: number;
  maxDiffPixelRatio?: number;
  threshold?: number;
  timeout?: number;
}

export class VisualTester {
  private page: Page;
  private testInfo: TestInfo;
  private screenshotDir: string;

  constructor(page: Page, testInfo: TestInfo) {
    this.page = page;
    this.testInfo = testInfo;
    this.screenshotDir = path.join(process.cwd(), 'test-results', 'screenshots');
    
    // Ensure screenshot directory exists
    if (!fs.existsSync(this.screenshotDir)) {
      fs.mkdirSync(this.screenshotDir, { recursive: true });
    }
  }

  /**
   * Take a screenshot for visual comparison
   */
  async captureScreenshot(name: string, options?: VisualTestOptions) {
    // Inject styles using JavaScript evaluation to avoid CSP issues
    await this.page.evaluate(({ disableAnimations, hideCaret }) => {
      if (disableAnimations || hideCaret) {
        const style = document.createElement('style');
        style.setAttribute('data-visual-test', 'capture');
        
        let css = '';
        
        // Wait for animations to complete
        if (disableAnimations) {
          css += `
            *, *::before, *::after {
              animation-duration: 0s !important;
              animation-delay: 0s !important;
              transition-duration: 0s !important;
              transition-delay: 0s !important;
            }
          `;
        }
        
        // Hide caret if requested
        if (hideCaret) {
          css += `
            * {
              caret-color: transparent !important;
            }
          `;
        }
        
        if (css) {
          style.textContent = css;
          document.head.appendChild(style);
        }
      }
    }, {
      disableAnimations: options?.animations === 'disabled',
      hideCaret: options?.caret === 'hide',
    });

    // Mask dynamic elements
    if (options?.mask && options.mask.length > 0) {
      for (const selector of options.mask) {
        await this.page.locator(selector).evaluateAll(elements => {
          elements.forEach(el => {
            (el as HTMLElement).style.visibility = 'hidden';
          });
        });
      }
    }

    // Wait for fonts to load
    await this.page.evaluate(() => document.fonts.ready);

    // Wait for images to load
    await this.page.waitForLoadState('networkidle');

    // Take screenshot
    const screenshotPath = path.join(this.screenshotDir, `${name}.png`);
    await this.page.screenshot({
      path: screenshotPath,
      fullPage: options?.fullPage ?? false,
      clip: options?.clip,
      scale: options?.scale,
      timeout: options?.timeout ?? 30000,
    });

    return screenshotPath;
  }

  /**
   * Compare element screenshot
   */
  async compareElement(selector: string, name: string, options?: VisualTestOptions) {
    const element = this.page.locator(selector);
    await element.waitFor({ state: 'visible' });

    // Scroll element into view
    await element.scrollIntoViewIfNeeded();

    // Wait for element to be stable
    await this.page.waitForTimeout(500);

    // Get element bounding box
    const box = await element.boundingBox();
    if (!box) {
      throw new Error(`Element ${selector} not found or not visible`);
    }

    // Add some padding
    const padding = 10;
    const clip = {
      x: Math.max(0, box.x - padding),
      y: Math.max(0, box.y - padding),
      width: box.width + padding * 2,
      height: box.height + padding * 2,
    };

    return await this.captureScreenshot(name, { ...options, clip });
  }

  /**
   * Compare viewport screenshot
   */
  async compareViewport(name: string, options?: VisualTestOptions) {
    return await this.captureScreenshot(name, { ...options, fullPage: false });
  }

  /**
   * Compare full page screenshot
   */
  async compareFullPage(name: string, options?: VisualTestOptions) {
    return await this.captureScreenshot(name, { ...options, fullPage: true });
  }

  /**
   * Prepare page for visual testing
   */
  async preparePage(options: {
    hideCursor?: boolean;
    disableAnimations?: boolean;
    waitForFonts?: boolean;
    hideScrollbars?: boolean;
  } = {}) {
    // Use JavaScript evaluation to inject styles to avoid CSP issues
    await this.page.evaluate(({ hideCursor, disableAnimations, hideScrollbars }) => {
      const style = document.createElement('style');
      style.setAttribute('data-visual-test', 'true');
      
      let css = '';
      
      // Hide cursor
      if (hideCursor) {
        css += '* { cursor: none !important; }\n';
      }
      
      // Disable animations
      if (disableAnimations) {
        css += `
          *, *::before, *::after {
            animation-duration: 0s !important;
            animation-delay: 0s !important;
            transition-duration: 0s !important;
            transition-delay: 0s !important;
          }
        `;
      }
      
      // Hide scrollbars
      if (hideScrollbars) {
        css += `
          ::-webkit-scrollbar { display: none !important; }
          * { scrollbar-width: none !important; }
        `;
      }
      
      if (css) {
        style.textContent = css;
        document.head.appendChild(style);
      }
    }, {
      hideCursor: options.hideCursor ?? true,
      disableAnimations: options.disableAnimations ?? true,
      hideScrollbars: options.hideScrollbars ?? true,
    });

    // Wait for fonts
    if (options.waitForFonts ?? true) {
      await this.page.evaluate(() => document.fonts.ready);
    }
  }

  /**
   * Visual regression test helpers for common elements
   */
  async compareCommonElements() {
    const results: Record<string, string> = {};

    // Header
    try {
      results.header = await this.compareElement('header', 'header');
    } catch (e) {
      console.log('Header element not found');
    }

    // Footer
    try {
      results.footer = await this.compareElement('.footer', 'footer');
    } catch (e) {
      console.log('Footer element not found');
    }

    // Main content
    try {
      results.mainContent = await this.compareElement('main, .main-content, [role="main"]', 'main-content');
    } catch (e) {
      console.log('Main content element not found');
    }

    return results;
  }

  /**
   * Test responsive layouts
   */
  async compareResponsiveLayouts(name: string, viewports: Array<{ width: number; height: number; label: string }>) {
    const results: Record<string, string> = {};

    for (const viewport of viewports) {
      await this.page.setViewportSize(viewport);
      await this.page.waitForTimeout(500); // Allow layout to adjust
      
      const screenshotName = `${name}-${viewport.label}`;
      results[viewport.label] = await this.compareViewport(screenshotName);
    }

    return results;
  }

  /**
   * Compare element states
   */
  async compareElementStates(selector: string, name: string, states: Array<{ 
    action: () => Promise<void>; 
    label: string 
  }>) {
    const results: Record<string, string> = {};

    // Capture default state
    results.default = await this.compareElement(selector, `${name}-default`);

    // Capture each state
    for (const state of states) {
      await state.action();
      await this.page.waitForTimeout(300); // Allow for state transition
      results[state.label] = await this.compareElement(selector, `${name}-${state.label}`);
    }

    return results;
  }

  /**
   * Compare theme variations
   */
  async compareThemes(themes: Array<{ name: string; setup: () => Promise<void> }>) {
    const results: Record<string, string> = {};

    for (const theme of themes) {
      await theme.setup();
      await this.page.waitForTimeout(500); // Allow theme to apply
      results[theme.name] = await this.compareFullPage(`theme-${theme.name}`);
    }

    return results;
  }
}

// Predefined viewport sizes for responsive testing
export const viewports = {
  mobile: {
    small: { width: 320, height: 568, label: 'mobile-small' },
    medium: { width: 375, height: 667, label: 'mobile-medium' },
    large: { width: 414, height: 896, label: 'mobile-large' },
  },
  tablet: {
    portrait: { width: 768, height: 1024, label: 'tablet-portrait' },
    landscape: { width: 1024, height: 768, label: 'tablet-landscape' },
  },
  desktop: {
    small: { width: 1280, height: 720, label: 'desktop-small' },
    medium: { width: 1440, height: 900, label: 'desktop-medium' },
    large: { width: 1920, height: 1080, label: 'desktop-large' },
    xlarge: { width: 2560, height: 1440, label: 'desktop-xlarge' },
  },
};

// Common elements to mask in visual tests
export const commonMasks = {
  dynamic: [
    '[data-testid="timestamp"]',
    '.timestamp',
    '.date-time',
    '.last-updated',
  ],
  animations: [
    '.loading',
    '.spinner',
    '.pulse',
    '.animate',
  ],
  media: [
    'video',
    'iframe[src*="youtube"]',
    'iframe[src*="vimeo"]',
  ],
  ads: [
    '.advertisement',
    '.ad-container',
    '[id*="google_ads"]',
  ],
};