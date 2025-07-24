import { Page } from '@playwright/test';

export interface BlackoutRegion {
  selector?: string;
  label: string;
  reason: string;
  type: 'dynamic-data' | 'timestamp' | 'animation' | 'external-content';
}

export class RegressionBlackout {
  private page: Page;
  private appliedBlackouts: BlackoutRegion[] = [];

  constructor(page: Page) {
    this.page = page;
  }

  /**
   * Apply blackouts to dynamic regions before taking screenshots
   */
  async applyBlackouts(regions: BlackoutRegion[]) {
    // Inject CSS for blackout styling
    await this.page.addStyleTag({
      content: `
        .regression-blackout {
          position: relative !important;
          background: #1a1a1a !important;
          color: transparent !important;
          overflow: hidden !important;
        }
        
        .regression-blackout * {
          visibility: hidden !important;
        }
        
        .regression-blackout::after {
          content: attr(data-blackout-label) !important;
          position: absolute !important;
          top: 50% !important;
          left: 50% !important;
          transform: translate(-50%, -50%) !important;
          color: #666 !important;
          font-size: 14px !important;
          font-family: monospace !important;
          text-align: center !important;
          visibility: visible !important;
          pointer-events: none !important;
          white-space: nowrap !important;
          background: #1a1a1a !important;
          padding: 4px 8px !important;
          border: 1px dashed #444 !important;
          border-radius: 4px !important;
        }
        
        /* Special handling for iframes */
        iframe.regression-blackout {
          opacity: 1 !important;
        }
        
        iframe.regression-blackout::after {
          z-index: 999999 !important;
        }
      `,
    });

    // Apply blackouts to each region
    for (const region of regions) {
      if (region.selector) {
        await this.blackoutElement(region);
        this.appliedBlackouts.push(region);
      }
    }

    // Add metadata comment to page
    await this.page.evaluate((blackouts) => {
      const meta = document.createElement('meta');
      meta.name = 'regression-blackouts';
      meta.content = JSON.stringify(blackouts);
      document.head.appendChild(meta);
    }, this.appliedBlackouts);
  }

  /**
   * Blackout a specific element
   */
  private async blackoutElement(region: BlackoutRegion) {
    await this.page.evaluate(({ selector, label, reason }) => {
      const elements = document.querySelectorAll(selector!);
      elements.forEach((el, index) => {
        el.classList.add('regression-blackout');
        el.setAttribute('data-blackout-label', `${label}${elements.length > 1 ? ` (${index + 1})` : ''}`);
        el.setAttribute('data-blackout-reason', reason);
        el.setAttribute('data-testid', 'regression-blackout');
      });
    }, region);
  }

  /**
   * Remove all blackouts (useful for debugging)
   */
  async removeBlackouts() {
    await this.page.evaluate(() => {
      const elements = document.querySelectorAll('.regression-blackout');
      elements.forEach(el => {
        el.classList.remove('regression-blackout');
        el.removeAttribute('data-blackout-label');
        el.removeAttribute('data-blackout-reason');
      });
    });
    this.appliedBlackouts = [];
  }

  /**
   * Get list of applied blackouts
   */
  getAppliedBlackouts(): BlackoutRegion[] {
    return [...this.appliedBlackouts];
  }

  /**
   * Standard blackout configurations
   */
  static readonly STANDARD_BLACKOUTS = {
    grafana: {
      selector: '.grafana-preview iframe, iframe[src*="grafana"]',
      label: 'Grafana Chart',
      reason: 'Dynamic time-series data changes constantly',
      type: 'dynamic-data' as const,
    },
    timestamps: {
      selector: '[data-testid="timestamp"], .timestamp, .last-updated, time',
      label: 'Timestamp',
      reason: 'Timestamps change on every page load',
      type: 'timestamp' as const,
    },
    powerReadings: {
      selector: '[data-testid="power-value"], .power-reading, .watt-value',
      label: 'Power Reading',
      reason: 'Real-time power values fluctuate',
      type: 'dynamic-data' as const,
    },
    animations: {
      selector: '.pulse, .animate, .loading, .spinner',
      label: 'Animation',
      reason: 'Animated elements cause pixel differences',
      type: 'animation' as const,
    },
    externalContent: {
      selector: 'iframe[src*="youtube"], iframe[src*="vimeo"], .ad-container',
      label: 'External Content',
      reason: 'External content is not under our control',
      type: 'external-content' as const,
    },
  };

  /**
   * Apply standard blackouts for power monitoring page
   */
  async applyPowerMonitoringBlackouts() {
    await this.applyBlackouts([
      RegressionBlackout.STANDARD_BLACKOUTS.grafana,
      RegressionBlackout.STANDARD_BLACKOUTS.powerReadings,
      RegressionBlackout.STANDARD_BLACKOUTS.timestamps,
    ]);
  }

  /**
   * Create a blackout report for documentation
   */
  async generateBlackoutReport(): Promise<string> {
    const report = {
      timestamp: new Date().toISOString(),
      url: this.page.url(),
      blackouts: this.appliedBlackouts,
      screenshot: await this.page.screenshot({ encoding: 'base64' }),
    };

    return JSON.stringify(report, null, 2);
  }

  /**
   * Verify blackouts are working correctly
   */
  async verifyBlackouts(): Promise<boolean> {
    const result = await this.page.evaluate(() => {
      const blackouts = document.querySelectorAll('.regression-blackout');
      return {
        count: blackouts.length,
        allHaveLabels: Array.from(blackouts).every(el => 
          el.getAttribute('data-blackout-label')
        ),
        allHaveReasons: Array.from(blackouts).every(el => 
          el.getAttribute('data-blackout-reason')
        ),
      };
    });

    return result.count > 0 && result.allHaveLabels && result.allHaveReasons;
  }
}

/**
 * Helper function to create a visual regression test with blackouts
 */
export async function captureWithBlackouts(
  page: Page,
  blackouts: BlackoutRegion[],
  screenshotName: string
): Promise<{ path: string; blackouts: BlackoutRegion[] }> {
  const blackoutManager = new RegressionBlackout(page);
  await blackoutManager.applyBlackouts(blackouts);
  
  const path = `test-results/regression/${screenshotName}`;
  await page.screenshot({ path, fullPage: true });
  
  return {
    path,
    blackouts: blackoutManager.getAppliedBlackouts(),
  };
}