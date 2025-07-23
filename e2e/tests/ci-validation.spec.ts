import { test, expect } from '@playwright/test';

test.describe('CI Validation Tests', () => {
  test('should validate test configuration', async () => {
    // This test validates that the test suite is properly configured
    // It doesn't require a browser and can run in CI without browser installation
    
    // Verify test data is accessible
    const { testData } = await import('../fixtures/test-data');
    expect(testData).toBeDefined();
    expect(testData.pageContent.title).toContain('Linknode Energy Monitor');
    
    // Verify test helpers are accessible
    const { testHelpers } = await import('../utils/test-helpers');
    expect(testHelpers).toBeDefined();
    expect(typeof testHelpers.waitForPageLoad).toBe('function');
    
    // Verify expected configuration
    expect(testData.apiEndpoints.stats).toBe('https://linknode-eagle-monitor.fly.dev/api/stats');
    expect(testData.apiEndpoints.health).toBe('https://linknode-eagle-monitor.fly.dev/health');
    
    // Verify timeout configuration
    expect(testData.timeouts.pageLoad).toBe(30000);
    expect(testData.timeouts.apiResponse).toBe(15000);
    expect(testData.timeouts.elementVisible).toBe(10000);
  });
  
  test('should have proper test structure', async () => {
    // Validate that all expected test files exist
    const fs = await import('fs');
    const path = await import('path');
    
    const testFiles = [
      'homepage.smoke.spec.ts',
      'power-monitoring.smoke.spec.ts',
      'ci-validation.spec.ts'
    ];
    
    const testsDir = path.join(process.cwd(), 'e2e', 'tests');
    
    for (const file of testFiles) {
      const filePath = path.join(testsDir, file);
      const exists = fs.existsSync(filePath);
      expect(exists, `Test file ${file} should exist`).toBe(true);
    }
  });
});