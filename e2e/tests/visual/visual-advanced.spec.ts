import { test, expect } from '@playwright/test';
import { VisualTester, viewports, commonMasks } from '../../utils/visual-testing';
import { HomePage } from '../../pages/HomePage';

test.describe('Advanced Visual Regression Tests @visual @phase3', () => {
  let visualTester: VisualTester;
  let homePage: HomePage;

  test.beforeEach(async ({ page }, testInfo) => {
    visualTester = new VisualTester(page, testInfo);
    homePage = new HomePage(page);
    await homePage.goto();
    await visualTester.preparePage();
  });

  test.describe('Multi-Viewport Visual Tests', () => {
    test('should maintain consistent layout across all viewport sizes', async ({ page }) => {
      const viewportSizes = [
        viewports.mobile.small,
        viewports.mobile.medium,
        viewports.mobile.large,
        viewports.tablet.portrait,
        viewports.tablet.landscape,
        viewports.desktop.small,
        viewports.desktop.medium,
        viewports.desktop.large,
        viewports.desktop.xlarge
      ];

      const results = await visualTester.compareResponsiveLayouts('homepage', viewportSizes);
      
      // Verify screenshots were taken
      expect(Object.keys(results)).toHaveLength(viewportSizes.length);
    });

    test('should handle orientation changes correctly', async ({ page }) => {
      // Test portrait to landscape transitions
      const orientations = [
        { width: 414, height: 896, label: 'mobile-portrait' },
        { width: 896, height: 414, label: 'mobile-landscape' },
        { width: 768, height: 1024, label: 'tablet-portrait' },
        { width: 1024, height: 768, label: 'tablet-landscape' }
      ];

      for (const orientation of orientations) {
        await page.setViewportSize(orientation);
        await page.waitForTimeout(300);
        
        // Check that no horizontal scroll appears
        const hasHorizontalScroll = await page.evaluate(() => {
          return document.documentElement.scrollWidth > document.documentElement.clientWidth;
        });
        expect(hasHorizontalScroll).toBe(false);
        
        // Take screenshot
        await visualTester.compareViewport(`orientation-${orientation.label}`);
      }
    });
  });

  test.describe('Component State Visual Tests', () => {
    test('should capture all power widget states', async ({ page }) => {
      const powerWidgetStates = [
        {
          action: async () => {
            // Normal state (default)
          },
          label: 'normal'
        },
        {
          action: async () => {
            // Simulate updating state
            await page.evaluate(() => {
              const indicator = document.querySelector('#power-update-indicator');
              if (indicator) {
                indicator.classList.add('pulse');
              }
            });
          },
          label: 'updating'
        },
        {
          action: async () => {
            // Simulate error state
            await page.evaluate(() => {
              document.querySelectorAll('.metric-value').forEach(el => {
                el.textContent = '--';
              });
            });
          },
          label: 'error'
        }
      ];

      await visualTester.compareElementStates('.power-widget', 'power-widget', powerWidgetStates);
    });

    test('should capture API status widget states', async ({ page }) => {
      const statusStates = [
        {
          action: async () => {
            // All services online
            await page.evaluate(() => {
              ['influx', 'eagle', 'web'].forEach(service => {
                const el = document.querySelector(`#${service}-status`);
                if (el) {
                  el.className = 'status-indicator online';
                }
              });
            });
          },
          label: 'all-online'
        },
        {
          action: async () => {
            // Mixed status
            await page.evaluate(() => {
              document.querySelector('#influx-status')?.classList.add('offline');
            });
          },
          label: 'mixed-status'
        },
        {
          action: async () => {
            // All offline
            await page.evaluate(() => {
              ['influx', 'eagle', 'web'].forEach(service => {
                const el = document.querySelector(`#${service}-status`);
                if (el) {
                  el.className = 'status-indicator offline';
                }
              });
            });
          },
          label: 'all-offline'
        }
      ];

      await visualTester.compareElementStates('.api-status-widget', 'api-status', statusStates);
    });
  });

  test.describe('Dynamic Content Visual Tests', () => {
    test('should handle dynamic content masking correctly', async ({ page }) => {
      // Mask all dynamic content
      const masks = [
        ...commonMasks.dynamic,
        '#current-power',
        '#power-min',
        '#power-avg',
        '#power-max',
        '#power-cost',
        '#app-version',
        '#build-date',
        '#commit-sha',
        '.grafana-preview iframe'
      ];

      await visualTester.compareFullPage('homepage-masked', {
        mask: masks,
        animations: 'disabled'
      });
    });

    test('should capture loading states', async ({ page }) => {
      // Reload and capture loading states
      await page.reload();
      
      // Capture initial loading state
      await visualTester.compareViewport('loading-initial');
      
      // Wait for partial load
      await page.waitForTimeout(500);
      await visualTester.compareViewport('loading-partial');
      
      // Wait for full load
      await page.waitForLoadState('networkidle');
      await visualTester.compareViewport('loading-complete');
    });
  });

  test.describe('Cross-Browser Visual Consistency', () => {
    test('should render consistently across browsers', async ({ page, browserName }) => {
      // Take browser-specific screenshots
      await visualTester.compareFullPage(`browser-${browserName}`, {
        fullPage: true,
        animations: 'disabled',
        mask: commonMasks.dynamic
      });
      
      // Check specific rendering issues
      const renderingChecks = await page.evaluate(() => {
        const checks: Record<string, boolean> = {};
        
        // Check font rendering
        const computedFont = window.getComputedStyle(document.body).fontFamily;
        checks.fontLoaded = computedFont.includes('Inter') || computedFont.includes('system-ui');
        
        // Check flexbox rendering
        const flexElements = document.querySelectorAll('[style*="display: flex"], [style*="display:flex"]');
        checks.flexboxWorking = flexElements.length > 0;
        
        // Check grid rendering
        const gridElements = document.querySelectorAll('[style*="display: grid"], [style*="display:grid"]');
        checks.gridWorking = gridElements.length > 0;
        
        // Check backdrop filters
        const backdropElements = document.querySelectorAll('[style*="backdrop-filter"]');
        checks.backdropFilters = backdropElements.length > 0;
        
        return checks;
      });
      
      console.log(`Browser ${browserName} rendering checks:`, renderingChecks);
    });
  });

  test.describe('Theme and Color Scheme Tests', () => {
    test('should handle system color scheme preferences', async ({ page }) => {
      // Test light mode preference
      await page.emulateMedia({ colorScheme: 'light' });
      await page.waitForTimeout(300);
      await visualTester.compareFullPage('color-scheme-light');
      
      // Test dark mode preference
      await page.emulateMedia({ colorScheme: 'dark' });
      await page.waitForTimeout(300);
      await visualTester.compareFullPage('color-scheme-dark');
      
      // Test high contrast mode
      await page.emulateMedia({ forcedColors: 'active' });
      await page.waitForTimeout(300);
      await visualTester.compareFullPage('high-contrast-mode');
    });

    test('should maintain readability with different color schemes', async ({ page }) => {
      const colorSchemes = ['light', 'dark', 'no-preference'] as const;
      
      for (const scheme of colorSchemes) {
        await page.emulateMedia({ colorScheme: scheme });
        
        // Check contrast ratios
        const contrastCheck = await page.evaluate(() => {
          const getContrastRatio = (rgb1: number[], rgb2: number[]) => {
            const getLuminance = (rgb: number[]) => {
              const [r, g, b] = rgb.map(val => {
                val = val / 255;
                return val <= 0.03928 ? val / 12.92 : Math.pow((val + 0.055) / 1.055, 2.4);
              });
              return 0.2126 * r + 0.7152 * g + 0.0722 * b;
            };
            
            const l1 = getLuminance(rgb1);
            const l2 = getLuminance(rgb2);
            return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
          };
          
          // Check text contrast
          const body = document.body;
          const bgColor = window.getComputedStyle(body).backgroundColor;
          const textColor = window.getComputedStyle(body).color;
          
          // Parse RGB values (simplified)
          const parseRGB = (color: string) => {
            const match = color.match(/\d+/g);
            return match ? match.slice(0, 3).map(Number) : [0, 0, 0];
          };
          
          const bgRGB = parseRGB(bgColor);
          const textRGB = parseRGB(textColor);
          
          return {
            ratio: getContrastRatio(bgRGB, textRGB),
            bgColor,
            textColor
          };
        });
        
        console.log(`Color scheme ${scheme} contrast:`, contrastCheck);
        expect(contrastCheck.ratio).toBeGreaterThan(4.5); // WCAG AA standard
      }
    });
  });

  test.describe('Print Media Visual Tests', () => {
    test('should render correctly for print media', async ({ page }) => {
      // Emulate print media
      await page.emulateMedia({ media: 'print' });
      await page.waitForTimeout(500);
      
      // Check print styles are applied
      const printStylesApplied = await page.evaluate(() => {
        const styles = window.getComputedStyle(document.body);
        return {
          background: styles.backgroundColor,
          color: styles.color,
          // Check if unnecessary elements are hidden
          navigationHidden: window.getComputedStyle(
            document.querySelector('nav') || document.createElement('div')
          ).display === 'none'
        };
      });
      
      console.log('Print styles:', printStylesApplied);
      
      // Take print preview screenshot
      await visualTester.compareFullPage('print-preview', {
        fullPage: true
      });
    });
  });

  test.describe('Animation and Transition Tests', () => {
    test('should capture animations at different stages', async ({ page }) => {
      // Find all animated elements
      const animatedElements = await page.evaluate(() => {
        const elements: string[] = [];
        document.querySelectorAll('*').forEach(el => {
          const styles = window.getComputedStyle(el);
          if (styles.animation !== 'none' || styles.transition !== 'none') {
            if (el.className) {
              elements.push(`.${el.className.split(' ')[0]}`);
            }
          }
        });
        return [...new Set(elements)];
      });
      
      console.log('Animated elements found:', animatedElements);
      
      // Capture animation states
      await visualTester.compareViewport('animations-enabled');
      
      // Disable animations and compare
      await visualTester.preparePage({ disableAnimations: true });
      await visualTester.compareViewport('animations-disabled');
    });
  });

  test.describe('Edge Case Visual Tests', () => {
    test('should handle extremely long content gracefully', async ({ page }) => {
      // Inject long content
      await page.evaluate(() => {
        const powerValue = document.querySelector('#current-power');
        if (powerValue) {
          powerValue.textContent = '999999999.99';
        }
        
        const version = document.querySelector('#app-version');
        if (version) {
          version.textContent = 'v1.0.999-development-build-extremely-long-version-string';
        }
      });
      
      await visualTester.compareElement('.metrics', 'edge-case-long-content');
    });

    test('should handle missing images gracefully', async ({ page }) => {
      // Break image sources
      await page.evaluate(() => {
        document.querySelectorAll('img').forEach(img => {
          img.src = '/non-existent-image.png';
        });
      });
      
      await page.waitForTimeout(500);
      await visualTester.compareFullPage('edge-case-broken-images');
    });

    test('should handle RTL text direction', async ({ page }) => {
      // Set RTL direction
      await page.evaluate(() => {
        document.documentElement.dir = 'rtl';
        document.documentElement.lang = 'ar';
      });
      
      await page.waitForTimeout(300);
      await visualTester.compareFullPage('edge-case-rtl');
    });
  });

  test.describe('Focus State Visual Tests', () => {
    test('should show clear focus indicators', async ({ page }) => {
      // Tab through interactive elements
      const focusableElements = await page.evaluate(() => {
        const elements = document.querySelectorAll(
          'a, button, input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        return elements.length;
      });
      
      console.log(`Found ${focusableElements} focusable elements`);
      
      // Focus first element
      await page.keyboard.press('Tab');
      await visualTester.compareViewport('focus-state-first');
      
      // Focus additional elements
      for (let i = 0; i < Math.min(3, focusableElements - 1); i++) {
        await page.keyboard.press('Tab');
        await page.waitForTimeout(100);
        await visualTester.compareViewport(`focus-state-${i + 2}`);
      }
    });
  });
});