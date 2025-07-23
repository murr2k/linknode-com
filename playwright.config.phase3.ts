import { defineConfig, devices } from '@playwright/test';
import * as dotenv from 'dotenv';
import * as path from 'path';

/**
 * Phase 3 Configuration for Advanced Visual and Performance Tests
 */
dotenv.config({ path: path.resolve(__dirname, '.env') });

export default defineConfig({
  testDir: './e2e/tests',
  testMatch: ['**/*@phase3*.spec.ts', '**/visual-advanced.spec.ts', '**/performance-advanced.spec.ts'],
  
  /* Run tests in files in parallel */
  fullyParallel: false, // Sequential for performance tests
  
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  
  /* Minimal retries for visual tests */
  retries: process.env.CI ? 1 : 0,
  
  /* Single worker for accurate performance measurements */
  workers: 1,
  
  /* Advanced reporters */
  reporter: [
    ['./e2e/reporters/phase3-reporter.ts'],
    ['html', { outputFolder: 'test-results/phase3-html' }],
    ['list'],
    ['json', { outputFile: 'test-results/phase3-results.json' }],
    process.env.CI ? ['github'] : null,
  ].filter(Boolean) as any,
  
  /* Shared settings for all the projects below */
  use: {
    /* Base URL to use in actions like `await page.goto('/')`. */
    baseURL: process.env.BASE_URL || 'https://linknode.com',

    /* Always collect trace for analysis */
    trace: 'on',

    /* Always take screenshots for visual comparison */
    screenshot: 'on',

    /* Record video for all tests */
    video: 'on',

    /* Extended timeouts for performance tests */
    actionTimeout: 30000,
    navigationTimeout: 60000,

    /* Accept downloads */
    acceptDownloads: true,

    /* Ignore HTTPS errors */
    ignoreHTTPSErrors: true,

    /* Locale and timezone */
    locale: 'en-US',
    timezoneId: 'America/New_York',

    /* Viewport size for consistency */
    viewport: { width: 1920, height: 1080 },

    /* Device scale factor */
    deviceScaleFactor: 1,

    /* Color scheme */
    colorScheme: 'dark',

    /* Reduced motion for consistent animations */
    reducedMotion: 'reduce',

    /* Performance testing options - removed for cross-browser compatibility */

    /* Context options for performance */
    contextOptions: {
      // Enable CDP for advanced metrics
      recordHar: {
        path: 'test-results/har/recording.har',
        mode: 'full',
        content: 'attach',
      },
    },
  },

  /* Configure projects for comprehensive browser testing */
  projects: [
    // Desktop browsers at different resolutions
    {
      name: 'chromium-1080p',
      use: { 
        ...devices['Desktop Chrome'],
        viewport: { width: 1920, height: 1080 },
      },
    },
    {
      name: 'chromium-1440p',
      use: { 
        ...devices['Desktop Chrome'],
        viewport: { width: 2560, height: 1440 },
      },
    },
    {
      name: 'chromium-4k',
      use: { 
        ...devices['Desktop Chrome'],
        viewport: { width: 3840, height: 2160 },
      },
    },
    
    // Firefox variations
    {
      name: 'firefox-1080p',
      use: { 
        ...devices['Desktop Firefox'],
        viewport: { width: 1920, height: 1080 },
      },
    },
    
    // Safari/WebKit
    {
      name: 'webkit-1080p',
      use: { 
        ...devices['Desktop Safari'],
        viewport: { width: 1920, height: 1080 },
      },
    },
    
    // Mobile devices
    {
      name: 'pixel-5',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'iphone-12',
      use: { ...devices['iPhone 12'] },
    },
    {
      name: 'iphone-12-landscape',
      use: { 
        ...devices['iPhone 12 landscape'],
      },
    },
    {
      name: 'ipad-pro',
      use: { ...devices['iPad Pro'] },
    },
    
    // Performance-specific configurations
    {
      name: 'performance-chrome',
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: {
          args: [
            '--enable-precise-memory-info',
            '--enable-gpu-benchmarking',
            '--enable-thread-composting',
            '--disable-dev-shm-usage',
            '--no-sandbox',
          ],
        },
      },
    },
    
    // Accessibility testing configuration
    {
      name: 'accessibility-chrome',
      use: {
        ...devices['Desktop Chrome'],
        // Force high contrast mode
        colorScheme: 'dark',
        forcedColors: 'active',
      },
    },
  ],

  /* Global timeout for Phase 3 tests */
  timeout: 120000, // 2 minutes per test

  /* Extended expect timeout for visual comparisons */
  expect: {
    timeout: 30000,
    toHaveScreenshot: {
      // Visual comparison options
      threshold: 0.2, // 20% threshold
      maxDiffPixels: 100,
      animations: 'disabled',
      caret: 'hide',
      scale: 'css',
    },
  },

  /* Output directory for Phase 3 artifacts */
  outputDir: 'test-results/phase3/',

  /* Global setup for Phase 3 */
  globalSetup: require.resolve('./e2e/setup/phase3-setup.ts'),

  /* Global teardown */
  globalTeardown: require.resolve('./e2e/setup/phase3-teardown.ts'),
});