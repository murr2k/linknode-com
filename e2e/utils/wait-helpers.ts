import { Page } from '@playwright/test';

/**
 * Wait for service status checks to complete
 */
export async function waitForServiceStatusChecks(page: Page, timeout = 10000) {
  // Wait for all status elements to lose the 'connecting' class
  await page.waitForFunction(
    () => {
      const statusElements = document.querySelectorAll('[id$="-status"]');
      return Array.from(statusElements).every(el => !el.classList.contains('connecting'));
    },
    { timeout }
  );
  
  // Additional wait to ensure status text is updated
  await page.waitForFunction(
    () => {
      const statusTexts = document.querySelectorAll('[id$="-status-text"]');
      return Array.from(statusTexts).every(el => 
        el.textContent !== 'Checking...' && el.textContent !== ''
      );
    },
    { timeout: 5000 }
  );
}

/**
 * Wait for power data to be loaded
 */
export async function waitForPowerData(page: Page, timeout = 10000) {
  await page.waitForFunction(
    () => {
      const powerElement = document.getElementById('current-power');
      return powerElement && powerElement.textContent !== 'Loading...' && powerElement.textContent !== '';
    },
    { timeout }
  );
}

/**
 * Wait for all API data to be loaded
 */
export async function waitForAPIData(page: Page) {
  await Promise.all([
    waitForServiceStatusChecks(page),
    waitForPowerData(page)
  ]);
}