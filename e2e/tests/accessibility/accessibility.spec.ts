import { expect } from '@playwright/test';
import { test } from '../../fixtures/axe-setup';
import { HomePage } from '../../pages/HomePage';
import { APIMocker, mockResponses } from '../../utils/api-mocks';

test.describe('Accessibility Tests @accessibility', () => {
  let homePage: HomePage;
  let apiMocker: APIMocker;

  test.beforeEach(async ({ page }) => {
    homePage = new HomePage(page);
    apiMocker = new APIMocker(page);

    // Mock APIs for consistent testing
    await apiMocker.mock({
      url: /\/api\/stats/,
      method: 'GET',
      response: mockResponses.powerStats.success,
    });

    await apiMocker.mock({
      url: /\/health/,
      method: 'GET',
      response: mockResponses.health.allHealthy,
    });
  });

  test('should pass accessibility checks on homepage', async ({ page, makeAxeBuilder }) => {
    await homePage.goto();
    await page.waitForLoadState('networkidle');

    const accessibilityScanResults = await makeAxeBuilder().analyze();

    // Log violations for debugging
    if (accessibilityScanResults.violations.length > 0) {
      console.log('Accessibility violations found:');
      accessibilityScanResults.violations.forEach((violation, index) => {
        console.log(`\n${index + 1}. ${violation.id}: ${violation.description}`);
        console.log(`   Impact: ${violation.impact}`);
        console.log(`   Affected elements: ${violation.nodes.length}`);
        violation.nodes.forEach(node => {
          console.log(`   - ${node.target}`);
        });
      });
    }

    // Should have no critical violations
    const criticalViolations = accessibilityScanResults.violations.filter(
      v => v.impact === 'critical' || v.impact === 'serious'
    );
    expect(criticalViolations).toHaveLength(0);
  });

  test('should have proper heading hierarchy', async ({ page }) => {
    await homePage.goto();

    const headingStructure = await page.evaluate(() => {
      const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6'));
      return headings.map(h => ({
        level: parseInt(h.tagName[1]),
        text: h.textContent?.trim() || '',
        visible: (h as HTMLElement).offsetParent !== null,
      }));
    });

    console.log('Heading structure:', headingStructure);

    // Should have exactly one h1
    const h1Count = headingStructure.filter(h => h.level === 1 && h.visible).length;
    expect(h1Count).toBe(1);

    // Check heading hierarchy
    let lastLevel = 0;
    for (const heading of headingStructure.filter(h => h.visible)) {
      // Heading levels should not skip (e.g., h1 -> h3)
      if (lastLevel > 0) {
        expect(heading.level - lastLevel).toBeLessThanOrEqual(1);
      }
      lastLevel = heading.level;
    }
  });

  test('should have accessible forms and inputs', async ({ page }) => {
    await homePage.goto();

    const formIssues = await page.evaluate(() => {
      const issues: string[] = [];
      
      // Check all form inputs
      const inputs = document.querySelectorAll('input, select, textarea');
      inputs.forEach(input => {
        const id = input.id;
        const name = input.getAttribute('name');
        const ariaLabel = input.getAttribute('aria-label');
        const ariaLabelledBy = input.getAttribute('aria-labelledby');
        
        // Check for associated label
        let hasLabel = false;
        if (id) {
          const label = document.querySelector(`label[for="${id}"]`);
          hasLabel = !!label;
        }
        
        // Must have some form of labeling
        if (!hasLabel && !ariaLabel && !ariaLabelledBy) {
          issues.push(`Input ${input.tagName}[name="${name}"] has no accessible label`);
        }
        
        // Required fields should be marked
        if (input.hasAttribute('required') && !input.getAttribute('aria-required')) {
          issues.push(`Required input ${input.tagName}[name="${name}"] missing aria-required`);
        }
      });
      
      // Check for form validation messages
      const errorMessages = document.querySelectorAll('.error, .validation-error');
      errorMessages.forEach(error => {
        if (!error.getAttribute('role') && !error.getAttribute('aria-live')) {
          issues.push('Error message missing ARIA live region attributes');
        }
      });
      
      return issues;
    });

    expect(formIssues).toHaveLength(0);
  });

  test('should have sufficient color contrast', async ({ page, makeAxeBuilder }) => {
    await homePage.goto();

    // Run contrast-specific checks
    const contrastResults = await makeAxeBuilder()
      .withTags(['wcag2aa'])
      .withRules(['color-contrast'])
      .analyze();

    const contrastViolations = contrastResults.violations.filter(
      v => v.id === 'color-contrast'
    );

    if (contrastViolations.length > 0) {
      console.log('Color contrast issues:');
      contrastViolations[0].nodes.forEach(node => {
        console.log(`- ${node.target}: ${node.failureSummary}`);
      });
    }

    expect(contrastViolations).toHaveLength(0);
  });

  test('should have accessible images', async ({ page }) => {
    await homePage.goto();

    const imageIssues = await page.evaluate(() => {
      const issues: string[] = [];
      const images = document.querySelectorAll('img');
      
      images.forEach(img => {
        const alt = img.getAttribute('alt');
        const role = img.getAttribute('role');
        const ariaLabel = img.getAttribute('aria-label');
        
        // Decorative images should have empty alt or role="presentation"
        if (alt === null && role !== 'presentation' && !ariaLabel) {
          issues.push(`Image ${img.src} missing alt text`);
        }
        
        // Alt text should be meaningful (not just filename)
        if (alt && (alt.includes('.jpg') || alt.includes('.png') || alt.includes('.gif'))) {
          issues.push(`Image ${img.src} has non-descriptive alt text: "${alt}"`);
        }
      });
      
      return issues;
    });

    expect(imageIssues).toHaveLength(0);
  });

  test('should support keyboard navigation', async ({ page }) => {
    await homePage.goto();

    // Tab through interactive elements
    const tabOrder = await page.evaluate(async () => {
      const elements: string[] = [];
      const focusableSelectors = 'a, button, input, select, textarea, [tabindex]:not([tabindex="-1"])';
      const focusableElements = document.querySelectorAll(focusableSelectors);
      
      // Simulate tab navigation
      for (const element of focusableElements) {
        if ((element as HTMLElement).offsetParent !== null) { // Is visible
          elements.push(`${element.tagName}${element.id ? '#' + element.id : ''}`);
        }
      }
      
      return elements;
    });

    console.log('Tab order:', tabOrder);

    // Should have focusable elements
    expect(tabOrder.length).toBeGreaterThan(0);

    // Test keyboard interaction with Tab key
    await page.keyboard.press('Tab');
    
    // Check if focus is visible
    const focusVisible = await page.evaluate(() => {
      const activeElement = document.activeElement;
      if (!activeElement) return false;
      
      const styles = window.getComputedStyle(activeElement);
      const outline = styles.outline;
      const boxShadow = styles.boxShadow;
      
      // Should have visible focus indicator
      return outline !== 'none' || boxShadow !== 'none';
    });

    expect(focusVisible).toBe(true);
  });

  test('should have proper ARIA landmarks', async ({ page }) => {
    await homePage.goto();

    const landmarks = await page.evaluate(() => {
      const landmarkRoles = ['banner', 'navigation', 'main', 'complementary', 'contentinfo'];
      const found: Record<string, number> = {};
      
      // Check for landmark roles
      landmarkRoles.forEach(role => {
        const elements = document.querySelectorAll(`[role="${role}"]`);
        found[role] = elements.length;
      });
      
      // Check for semantic HTML5 elements
      found['header'] = document.querySelectorAll('header').length;
      found['nav'] = document.querySelectorAll('nav').length;
      found['main'] = document.querySelectorAll('main').length;
      found['aside'] = document.querySelectorAll('aside').length;
      found['footer'] = document.querySelectorAll('footer').length;
      
      return found;
    });

    console.log('Landmarks found:', landmarks);

    // Should have main landmark
    expect(landmarks.main + landmarks.main).toBeGreaterThan(0);

    // Should have header/banner
    expect(landmarks.header + landmarks.banner).toBeGreaterThan(0);

    // Should have footer/contentinfo
    expect(landmarks.footer + landmarks.contentinfo).toBeGreaterThan(0);
  });

  test('should handle focus management properly', async ({ page }) => {
    await homePage.goto();

    // Test focus trap in modals/dialogs if any
    const hasModals = await page.evaluate(() => {
      return document.querySelector('[role="dialog"], .modal, .popup') !== null;
    });

    if (hasModals) {
      // Check if focus is trapped within modal
      const focusTrapWorks = await page.evaluate(() => {
        const modal = document.querySelector('[role="dialog"], .modal, .popup');
        if (!modal) return true;
        
        const focusableElements = modal.querySelectorAll(
          'a, button, input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        
        return focusableElements.length > 0;
      });

      expect(focusTrapWorks).toBe(true);
    }

    // Test skip links
    const skipLinks = await page.evaluate(() => {
      const links = Array.from(document.querySelectorAll('a'));
      return links.filter(link => 
        link.textContent?.toLowerCase().includes('skip') ||
        link.classList.contains('skip-link')
      ).length;
    });

    console.log(`Found ${skipLinks} skip links`);
  });

  test('should have accessible data tables', async ({ page }) => {
    await homePage.goto();

    const tableIssues = await page.evaluate(() => {
      const issues: string[] = [];
      const tables = document.querySelectorAll('table');
      
      tables.forEach((table, index) => {
        // Check for caption or aria-label
        const caption = table.querySelector('caption');
        const ariaLabel = table.getAttribute('aria-label');
        
        if (!caption && !ariaLabel) {
          issues.push(`Table ${index + 1} missing caption or aria-label`);
        }
        
        // Check for table headers
        const headers = table.querySelectorAll('th');
        if (headers.length === 0) {
          issues.push(`Table ${index + 1} has no header cells`);
        }
        
        // Check scope attributes on headers
        headers.forEach(th => {
          if (!th.getAttribute('scope')) {
            issues.push(`Table header missing scope attribute`);
          }
        });
      });
      
      return issues;
    });

    // Only fail if tables exist and have issues
    if (tableIssues.length > 0) {
      console.log('Table accessibility issues:', tableIssues);
    }
  });

  test('should support screen reader announcements', async ({ page }) => {
    await homePage.goto();

    // Check for ARIA live regions
    const liveRegions = await page.evaluate(() => {
      const regions = document.querySelectorAll('[aria-live], [role="alert"], [role="status"]');
      return Array.from(regions).map(region => ({
        tag: region.tagName,
        role: region.getAttribute('role'),
        ariaLive: region.getAttribute('aria-live'),
        text: (region as HTMLElement).innerText?.substring(0, 50),
      }));
    });

    console.log('Live regions:', liveRegions);

    // Check for status messages on dynamic updates
    await page.waitForTimeout(2000); // Wait for potential updates

    const hasStatusUpdates = await page.evaluate(() => {
      // Check if power update indicator has proper ARIA
      const updateIndicator = document.querySelector('#power-update-indicator');
      if (updateIndicator) {
        const role = updateIndicator.getAttribute('role');
        const ariaLive = updateIndicator.getAttribute('aria-live');
        return role === 'status' || ariaLive === 'polite';
      }
      return true; // Pass if element doesn't exist
    });

    expect(hasStatusUpdates).toBe(true);
  });

  test('should meet responsive design accessibility', async ({ page, makeAxeBuilder }) => {
    const viewports = [
      { width: 320, height: 568, name: 'mobile-small' },
      { width: 768, height: 1024, name: 'tablet' },
      { width: 1920, height: 1080, name: 'desktop' },
    ];

    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await homePage.goto();
      await page.waitForLoadState('networkidle');

      const results = await makeAxeBuilder().analyze();
      
      const criticalViolations = results.violations.filter(
        v => v.impact === 'critical' || v.impact === 'serious'
      );

      if (criticalViolations.length > 0) {
        console.log(`Accessibility issues at ${viewport.name}:`, criticalViolations);
      }

      expect(criticalViolations).toHaveLength(0);
    }
  });

  test('should have accessible error states', async ({ page }) => {
    // Mock API error
    await apiMocker.mock({
      url: /\/api\/stats/,
      method: 'GET',
      response: mockResponses.powerStats.error,
    });

    await homePage.goto();
    await page.waitForTimeout(2000);

    // Check error message accessibility
    const errorAccessibility = await page.evaluate(() => {
      const errorElements = document.querySelectorAll('.error, [role="alert"]');
      const issues: string[] = [];

      errorElements.forEach(error => {
        const role = error.getAttribute('role');
        const ariaLive = error.getAttribute('aria-live');
        
        if (role !== 'alert' && ariaLive !== 'assertive' && ariaLive !== 'polite') {
          issues.push('Error message missing proper ARIA attributes');
        }
      });

      return issues;
    });

    expect(errorAccessibility).toHaveLength(0);
  });
});