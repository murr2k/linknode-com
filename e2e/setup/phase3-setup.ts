import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

async function globalSetup(config: FullConfig) {
  console.log('🚀 Phase 3 E2E Tests - Global Setup');
  
  // Create necessary directories
  const directories = [
    'test-results/phase3',
    'test-results/phase3/screenshots',
    'test-results/phase3/videos',
    'test-results/phase3/traces',
    'test-results/phase3/har',
    'test-results/reports',
    'test-results/visual-baselines',
  ];
  
  directories.forEach(dir => {
    const fullPath = path.join(process.cwd(), dir);
    if (!fs.existsSync(fullPath)) {
      fs.mkdirSync(fullPath, { recursive: true });
      console.log(`✅ Created directory: ${dir}`);
    }
  });
  
  // Set up environment variables for Phase 3
  process.env.PHASE3_TESTING = 'true';
  process.env.VISUAL_TESTING = 'true';
  process.env.PERFORMANCE_TESTING = 'true';
  process.env.COVERAGE_TESTING = 'true';
  
  // Log test configuration
  console.log('\n📋 Test Configuration:');
  console.log(`  Base URL: ${config.projects[0].use?.baseURL}`);
  console.log(`  Workers: ${config.workers}`);
  console.log(`  Projects: ${config.projects.length}`);
  console.log(`  Timeout: ${config.timeout}ms`);
  
  // Create baseline images directory if needed
  const baselineDir = path.join(process.cwd(), 'test-results/visual-baselines');
  if (!fs.existsSync(baselineDir)) {
    console.log('\n📸 First run detected - visual baselines will be created');
  }
  
  // Clean up old test results (optional)
  if (process.env.CLEAN_RESULTS === 'true') {
    console.log('\n🧹 Cleaning old test results...');
    const resultsDir = path.join(process.cwd(), 'test-results/phase3');
    if (fs.existsSync(resultsDir)) {
      fs.rmSync(resultsDir, { recursive: true, force: true });
      fs.mkdirSync(resultsDir, { recursive: true });
    }
  }
  
  // Performance monitoring setup
  console.log('\n⚡ Performance monitoring enabled');
  console.log('  - Core Web Vitals tracking');
  console.log('  - Memory profiling');
  console.log('  - Network analysis');
  console.log('  - Coverage collection');
  
  // Visual testing setup
  console.log('\n👁️  Visual testing enabled');
  console.log('  - Multi-viewport testing');
  console.log('  - Cross-browser rendering');
  console.log('  - Animation testing');
  console.log('  - Theme testing');
  
  // Return storage state if needed
  return {};
}

export default globalSetup;