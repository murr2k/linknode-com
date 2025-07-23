import { test, expect } from '@playwright/test';
import { HomePage } from '../pages/HomePage';

test.describe('Cross-Origin Resource and CORS Tests', () => {
  let homePage: HomePage;

  test.beforeEach(async ({ page }) => {
    homePage = new HomePage(page);
  });

  test('should handle CORS headers for API requests', async ({ page }) => {
    const apiResponses: Array<{
      url: string;
      headers: Record<string, string>;
      status: number;
    }> = [];

    // Monitor API responses
    page.on('response', response => {
      const url = response.url();
      if (url.includes('linknode-eagle-monitor.fly.dev') || url.includes('/api/')) {
        apiResponses.push({
          url,
          headers: response.headers(),
          status: response.status(),
        });
      }
    });

    await homePage.goto();
    await page.waitForTimeout(3000);

    // Check CORS headers on API responses
    for (const response of apiResponses) {
      console.log(`Checking CORS for ${response.url}`);
      
      // Should have CORS headers
      const corsHeaders = {
        'access-control-allow-origin': response.headers['access-control-allow-origin'],
        'access-control-allow-methods': response.headers['access-control-allow-methods'],
        'access-control-allow-headers': response.headers['access-control-allow-headers'],
      };

      // At least origin should be set
      if (response.status < 400) {
        expect(corsHeaders['access-control-allow-origin']).toBeTruthy();
        
        // Should allow linknode.com or use wildcard
        const allowedOrigin = corsHeaders['access-control-allow-origin'];
        expect(
          allowedOrigin === '*' || 
          allowedOrigin === 'https://linknode.com' ||
          allowedOrigin?.includes('linknode')
        ).toBe(true);
      }
    }
  });

  test('should load cross-origin Grafana iframe', async ({ page }) => {
    await homePage.goto();

    // Check Grafana iframe
    const grafanaIframe = homePage.grafanaIframe;
    await expect(grafanaIframe).toBeVisible();

    // Get iframe attributes
    const src = await grafanaIframe.getAttribute('src');
    expect(src).toBeTruthy();
    
    // Should be different origin
    const pageUrl = new URL(page.url());
    const iframeUrl = new URL(src!);
    expect(iframeUrl.origin).not.toBe(pageUrl.origin);

    // Check security attributes
    const sandbox = await grafanaIframe.getAttribute('sandbox');
    const allowAttribute = await grafanaIframe.getAttribute('allow');
    
    // Should have appropriate permissions
    if (sandbox) {
      expect(sandbox).toContain('allow-scripts');
      expect(sandbox).toContain('allow-same-origin');
    }
  });

  test('should handle mixed content properly', async ({ page }) => {
    const mixedContentIssues: string[] = [];

    // Listen for mixed content warnings
    page.on('console', msg => {
      if (msg.text().includes('Mixed Content') || msg.text().includes('was loaded over HTTPS')) {
        mixedContentIssues.push(msg.text());
      }
    });

    await homePage.goto();
    await page.waitForTimeout(3000);

    // Should not have mixed content issues
    expect(mixedContentIssues).toHaveLength(0);

    // All resources should be HTTPS
    const resources = await page.evaluate(() => {
      const results = {
        images: Array.from(document.images).map(img => img.src),
        scripts: Array.from(document.scripts).map(script => script.src),
        links: Array.from(document.querySelectorAll('link[href]')).map(link => 
          (link as HTMLLinkElement).href
        ),
        iframes: Array.from(document.querySelectorAll('iframe')).map(iframe => 
          (iframe as HTMLIFrameElement).src
        ),
      };
      return results;
    });

    // Check all resources use HTTPS
    const allResources = [
      ...resources.images,
      ...resources.scripts,
      ...resources.links,
      ...resources.iframes,
    ].filter(url => url && !url.startsWith('data:') && !url.startsWith('blob:'));

    for (const resource of allResources) {
      if (resource.startsWith('http://')) {
        console.warn(`Insecure resource found: ${resource}`);
      }
      expect(resource.startsWith('https://') || resource.startsWith('//')).toBe(true);
    }
  });

  test('should validate CSP headers', async ({ page }) => {
    const response = await page.goto('/');
    const headers = response?.headers() || {};

    // Check for Content Security Policy
    const csp = headers['content-security-policy'] || headers['x-content-security-policy'];
    
    if (csp) {
      console.log('CSP Header:', csp);
      
      // Should have basic CSP directives
      expect(csp).toContain('default-src');
      
      // Should allow necessary cross-origin resources
      if (csp.includes('frame-src')) {
        expect(csp).toContain('linknode-grafana.fly.dev');
      }
      
      // Should not be too permissive
      expect(csp).not.toContain("default-src * 'unsafe-inline' 'unsafe-eval'");
    } else {
      console.log('No CSP header found - consider adding one for security');
    }
  });

  test('should handle cross-origin API failures gracefully', async ({ page }) => {
    // Block cross-origin API requests
    await page.route('**/linknode-eagle-monitor.fly.dev/**', route => {
      route.abort('failed');
    });

    await homePage.goto();
    await page.waitForTimeout(3000);

    // Page should still be functional
    await expect(homePage.mainHeading).toBeVisible();
    await expect(homePage.powerWidget).toBeVisible();

    // Should show fallback state for API data
    const powerValue = await homePage.getCurrentPowerValue();
    expect(powerValue).toBe('--');

    // Should handle errors without breaking
    const consoleErrors = await homePage.checkForConsoleErrors();
    const criticalErrors = consoleErrors.filter(e => 
      e.includes('Uncaught') || e.includes('TypeError')
    );
    expect(criticalErrors).toHaveLength(0);
  });

  test('should validate CORS preflight requests', async ({ page }) => {
    const preflightRequests: Array<{
      url: string;
      headers: Record<string, string>;
    }> = [];

    // Monitor OPTIONS requests
    page.on('request', request => {
      if (request.method() === 'OPTIONS') {
        preflightRequests.push({
          url: request.url(),
          headers: request.headers(),
        });
      }
    });

    page.on('response', response => {
      if (response.request().method() === 'OPTIONS') {
        const headers = response.headers();
        console.log(`Preflight response for ${response.url()}:`, {
          'access-control-allow-origin': headers['access-control-allow-origin'],
          'access-control-allow-methods': headers['access-control-allow-methods'],
          'access-control-allow-headers': headers['access-control-allow-headers'],
          'access-control-max-age': headers['access-control-max-age'],
        });
      }
    });

    await homePage.goto();
    await page.waitForTimeout(3000);

    // Log preflight requests if any
    if (preflightRequests.length > 0) {
      console.log('Preflight requests detected:', preflightRequests);
    }
  });

  test('should handle cross-origin font loading', async ({ page }) => {
    await homePage.goto();

    // Check for cross-origin fonts
    const fontSources = await page.evaluate(() => {
      const fonts: string[] = [];
      
      // Check stylesheets for @font-face
      for (const sheet of document.styleSheets) {
        try {
          const rules = sheet.cssRules || sheet.rules;
          for (const rule of rules) {
            if (rule instanceof CSSFontFaceRule) {
              const src = rule.style.getPropertyValue('src');
              if (src) {
                fonts.push(src);
              }
            }
          }
        } catch (e) {
          // Cross-origin stylesheet, can't read rules
          console.log('Cross-origin stylesheet detected');
        }
      }
      
      return fonts;
    });

    // Fonts should load properly
    if (fontSources.length > 0) {
      console.log('Font sources found:', fontSources);
      
      // Monitor font loading
      const fontLoadErrors = await page.evaluate(() => {
        return new Promise<string[]>((resolve) => {
          const errors: string[] = [];
          
          document.fonts.ready.then(() => {
            document.fonts.forEach(font => {
              if (font.status === 'error') {
                errors.push(`Font loading error: ${font.family}`);
              }
            });
            resolve(errors);
          });
          
          // Timeout after 5 seconds
          setTimeout(() => resolve(errors), 5000);
        });
      });
      
      expect(fontLoadErrors).toHaveLength(0);
    }
  });

  test('should validate X-Frame-Options for iframe embedding', async ({ page }) => {
    // Check if the main page can be embedded
    const response = await page.goto('/');
    const headers = response?.headers() || {};
    
    const xFrameOptions = headers['x-frame-options'];
    const csp = headers['content-security-policy'];
    
    console.log('X-Frame-Options:', xFrameOptions);
    
    // If X-Frame-Options is set, it should allow embedding from same origin at least
    if (xFrameOptions) {
      expect(['SAMEORIGIN', 'ALLOW-FROM https://linknode.com']).toContain(xFrameOptions);
      expect(xFrameOptions).not.toBe('DENY');
    }
    
    // Check frame-ancestors in CSP
    if (csp && csp.includes('frame-ancestors')) {
      expect(csp).not.toContain("frame-ancestors 'none'");
    }
  });

  test('should handle cross-origin WebSocket connections', async ({ page }) => {
    const wsConnections: Array<{ url: string; readyState: number }> = [];
    
    // Monitor WebSocket connections
    await page.evaluateOnNewDocument(() => {
      const originalWebSocket = window.WebSocket;
      window.WebSocket = new Proxy(originalWebSocket, {
        construct(target, args) {
          const ws = new target(...args);
          
          // Log connection
          (window as any).wsConnections = (window as any).wsConnections || [];
          (window as any).wsConnections.push({
            url: args[0],
            readyState: ws.readyState,
          });
          
          return ws;
        },
      });
    });
    
    await homePage.goto();
    await page.waitForTimeout(3000);
    
    // Get WebSocket connections if any
    const connections = await page.evaluate(() => (window as any).wsConnections || []);
    
    if (connections.length > 0) {
      console.log('WebSocket connections:', connections);
      
      // Verify WebSocket URLs use secure protocol
      for (const conn of connections) {
        expect(conn.url.startsWith('wss://') || conn.url.startsWith('/')).toBe(true);
      }
    }
  });

  test('should validate cross-origin cookie handling', async ({ page, context }) => {
    // Get cookies after page load
    await homePage.goto();
    const cookies = await context.cookies();
    
    // Check cookie attributes for cross-origin scenarios
    for (const cookie of cookies) {
      console.log(`Cookie ${cookie.name}:`, {
        domain: cookie.domain,
        sameSite: cookie.sameSite,
        secure: cookie.secure,
      });
      
      // Cross-origin cookies should have appropriate SameSite attribute
      if (cookie.domain && !cookie.domain.includes('linknode.com')) {
        expect(cookie.sameSite).toBe('None');
        expect(cookie.secure).toBe(true);
      }
    }
  });

  test('should handle referrer policy correctly', async ({ page }) => {
    const response = await page.goto('/');
    const headers = response?.headers() || {};
    
    const referrerPolicy = headers['referrer-policy'];
    console.log('Referrer-Policy:', referrerPolicy);
    
    // Check meta tag as fallback
    const metaReferrer = await page.getAttribute('meta[name="referrer"]', 'content');
    console.log('Meta referrer:', metaReferrer);
    
    const policy = referrerPolicy || metaReferrer;
    
    if (policy) {
      // Should have a reasonable referrer policy
      const acceptablePolicies = [
        'strict-origin-when-cross-origin',
        'strict-origin',
        'same-origin',
        'no-referrer-when-downgrade',
      ];
      
      expect(acceptablePolicies).toContain(policy);
    }
  });
});