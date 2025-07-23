import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

async function globalTeardown(config: FullConfig) {
  console.log('\n🏁 Phase 3 E2E Tests - Global Teardown');
  
  // Generate test summary
  const resultsPath = path.join(process.cwd(), 'test-results/phase3-results.json');
  if (fs.existsSync(resultsPath)) {
    try {
      const results = JSON.parse(fs.readFileSync(resultsPath, 'utf-8'));
      console.log('\n📊 Test Summary:');
      console.log(`  Total: ${results.stats?.total || 0}`);
      console.log(`  Passed: ${results.stats?.passed || 0}`);
      console.log(`  Failed: ${results.stats?.failed || 0}`);
      console.log(`  Skipped: ${results.stats?.skipped || 0}`);
      console.log(`  Duration: ${results.stats?.duration || 0}ms`);
    } catch (e) {
      console.log('Could not parse test results');
    }
  }
  
  // Archive artifacts if on CI
  if (process.env.CI) {
    console.log('\n📦 Archiving test artifacts...');
    // CI will handle artifact collection
  }
  
  // Performance report location
  console.log('\n📄 Reports generated:');
  console.log('  - HTML: test-results/reports/latest.html');
  console.log('  - JSON: test-results/reports/latest.json');
  console.log('  - Markdown: test-results/reports/latest.md');
  
  // Check for visual differences
  const visualDiffsDir = path.join(process.cwd(), 'test-results/phase3/screenshots');
  if (fs.existsSync(visualDiffsDir)) {
    const files = fs.readdirSync(visualDiffsDir);
    const diffFiles = files.filter(f => f.includes('diff'));
    if (diffFiles.length > 0) {
      console.log(`\n⚠️  Visual differences detected: ${diffFiles.length} files`);
    }
  }
  
  // Cleanup temporary files
  const tempFiles = [
    'test-results/phase3/temp',
    'test-results/phase3/.tmp',
  ];
  
  tempFiles.forEach(file => {
    const fullPath = path.join(process.cwd(), file);
    if (fs.existsSync(fullPath)) {
      fs.rmSync(fullPath, { recursive: true, force: true });
    }
  });
  
  console.log('\n✨ Phase 3 testing complete!\n');
}

export default globalTeardown;