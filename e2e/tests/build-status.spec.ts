import { test, expect } from '@playwright/test';
import { HomePage } from '../pages/HomePage';

test.describe('Build Status Display', () => {
  let homePage: HomePage;

  test.beforeEach(async ({ page }) => {
    homePage = new HomePage(page);
    await homePage.goto();
  });

  test('should display build status section', async ({ page }) => {
    // Check that build status section exists
    const buildStatusSection = page.locator('.build-status');
    await expect(buildStatusSection).toBeVisible();
    
    // Check the heading
    await expect(buildStatusSection.locator('h3')).toContainText('Deployment Status');
  });

  test('should display all build metadata fields', async ({ page }) => {
    // Check all status items are present
    const statusItems = page.locator('.status-item');
    await expect(statusItems).toHaveCount(4);
    
    // Check each field label
    await expect(page.locator('.status-label').nth(0)).toContainText('Version:');
    await expect(page.locator('.status-label').nth(1)).toContainText('Build Date:');
    await expect(page.locator('.status-label').nth(2)).toContainText('Commit:');
    await expect(page.locator('.status-label').nth(3)).toContainText('Environment:');
  });

  test('should display version number in correct format', async ({ page }) => {
    const versionElement = page.locator('#app-version');
    await expect(versionElement).toBeVisible();
    
    // Version should match pattern v1.0.X or similar
    const versionText = await versionElement.textContent();
    expect(versionText).toMatch(/^v\d+\.\d+\.\d+$/);
  });

  test('should display build date in ISO format', async ({ page }) => {
    const buildDateElement = page.locator('#build-date');
    await expect(buildDateElement).toBeVisible();
    
    // Date should be in YYYY-MM-DD format
    const dateText = await buildDateElement.textContent();
    expect(dateText).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  test('should display commit SHA (7 characters)', async ({ page }) => {
    const commitElement = page.locator('#commit-sha');
    await expect(commitElement).toBeVisible();
    
    const commitText = await commitElement.textContent();
    // Should be either '-' for dev or 7-character SHA
    expect(commitText).toMatch(/^(-|[a-f0-9]{7})$/);
  });

  test('should display environment as Production', async ({ page }) => {
    const envElement = page.locator('#environment');
    await expect(envElement).toBeVisible();
    await expect(envElement).toContainText('Production');
  });

  test('should load build info from JSON file', async ({ page }) => {
    // Intercept the build-info.json request
    let buildInfoRequested = false;
    
    page.on('request', request => {
      if (request.url().includes('build-info.json')) {
        buildInfoRequested = true;
      }
    });
    
    // Reload page to ensure fresh load
    await page.reload();
    await page.waitForTimeout(1000); // Give time for the fetch
    
    // Verify the request was made
    expect(buildInfoRequested).toBe(true);
  });

  test('should have proper styling for build status elements', async ({ page }) => {
    // Check background color of status items
    const statusItem = page.locator('.status-item').first();
    await expect(statusItem).toHaveCSS('background-color', 'rgba(255, 255, 255, 0.05)');
    
    // Check version color (green)
    const versionElement = page.locator('#app-version');
    await expect(versionElement).toHaveCSS('color', 'rgb(74, 222, 128)');
    
    // Check build date color (blue)
    const buildDateElement = page.locator('#build-date');
    await expect(buildDateElement).toHaveCSS('color', 'rgb(96, 165, 250)');
    
    // Check commit SHA color (pink)
    const commitElement = page.locator('#commit-sha');
    await expect(commitElement).toHaveCSS('color', 'rgb(244, 114, 182)');
    
    // Check environment color (yellow)
    const envElement = page.locator('#environment');
    await expect(envElement).toHaveCSS('color', 'rgb(251, 191, 36)');
  });

  test('should handle missing build-info.json gracefully', async ({ page }) => {
    // Mock a failed request
    await page.route('**/build-info.json', route => {
      route.abort();
    });
    
    // Reload the page
    await page.reload();
    
    // Should still show default values
    await expect(page.locator('#app-version')).toContainText('v1.0.0');
    await expect(page.locator('#build-date')).toContainText('2025-07-23');
    await expect(page.locator('#commit-sha')).toContainText('-');
    await expect(page.locator('#environment')).toContainText('Production');
  });

  test('should be responsive on mobile', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    
    // Check that status grid stacks on mobile
    const statusGrid = page.locator('.status-grid');
    await expect(statusGrid).toBeVisible();
    
    // All items should still be visible
    const statusItems = page.locator('.status-item');
    for (let i = 0; i < 4; i++) {
      await expect(statusItems.nth(i)).toBeVisible();
    }
  });
});