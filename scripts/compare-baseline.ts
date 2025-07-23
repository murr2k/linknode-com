import { chromium } from 'playwright';
import * as fs from 'fs';
import * as path from 'path';
import { BaselineCapture } from './capture-baseline';

interface ComparisonResult {
  category: string;
  item: string;
  status: 'pass' | 'fail' | 'warning';
  baseline: any;
  current: any;
  difference?: string;
}

class BaselineComparison {
  private results: ComparisonResult[] = [];
  private baselineData: any;

  constructor() {
    const baselinePath = path.join(process.cwd(), 'test-baselines', 'baseline.json');
    if (!fs.existsSync(baselinePath)) {
      throw new Error('No baseline found. Run capture-baseline.ts first.');
    }
    this.baselineData = JSON.parse(fs.readFileSync(baselinePath, 'utf-8'));
  }

  async run() {
    console.log('🔍 Starting baseline comparison...\n');

    // Capture current state
    const capture = new BaselineCapture();
    const currentData = await capture.run();

    // Compare results
    this.compareFeatures(currentData);
    this.comparePerformance(currentData);
    this.compareAPIs(currentData);

    // Generate report
    this.generateReport();

    return this.results;
  }

  private compareFeatures(currentData: any) {
    console.log('📋 Comparing features...');

    // Compare page structure
    const baselineStructure = this.baselineData.features.pageStructure;
    const currentStructure = currentData.features.pageStructure;

    Object.keys(baselineStructure).forEach(key => {
      const baseline = baselineStructure[key];
      const current = currentStructure[key];
      
      this.results.push({
        category: 'Page Structure',
        item: key,
        status: baseline === current ? 'pass' : 'fail',
        baseline,
        current,
        difference: baseline !== current ? `Expected ${baseline}, got ${current}` : undefined
      });
    });

    // Compare functionality
    const baselineFunctionality = this.baselineData.features.functionality;
    const currentFunctionality = currentData.features.functionality;

    Object.keys(baselineFunctionality).forEach(section => {
      Object.keys(baselineFunctionality[section]).forEach(feature => {
        const baseline = baselineFunctionality[section][feature];
        const current = currentFunctionality[section]?.[feature];
        
        this.results.push({
          category: `Functionality - ${section}`,
          item: feature,
          status: baseline === current ? 'pass' : 'fail',
          baseline,
          current,
          difference: baseline !== current ? `Feature availability changed` : undefined
        });
      });
    });
  }

  private comparePerformance(currentData: any) {
    console.log('⚡ Comparing performance metrics...');

    const baselinePerf = this.baselineData.performance;
    const currentPerf = currentData.performance;
    const tolerance = 1.2; // 20% tolerance

    // Navigation timing
    if (baselinePerf.navigation && currentPerf.navigation) {
      Object.keys(baselinePerf.navigation).forEach(metric => {
        const baseline = baselinePerf.navigation[metric];
        const current = currentPerf.navigation[metric];
        const ratio = current / baseline;
        
        this.results.push({
          category: 'Navigation Timing',
          item: metric,
          status: ratio <= tolerance ? 'pass' : ratio <= 1.5 ? 'warning' : 'fail',
          baseline: `${baseline}ms`,
          current: `${current}ms`,
          difference: `${((ratio - 1) * 100).toFixed(1)}% change`
        });
      });
    }

    // Paint timing
    if (baselinePerf.paint && currentPerf.paint) {
      Object.keys(baselinePerf.paint).forEach(metric => {
        const baseline = baselinePerf.paint[metric];
        const current = currentPerf.paint[metric];
        const ratio = current / baseline;
        
        this.results.push({
          category: 'Paint Timing',
          item: metric,
          status: ratio <= tolerance ? 'pass' : ratio <= 1.5 ? 'warning' : 'fail',
          baseline: `${baseline}ms`,
          current: `${current}ms`,
          difference: `${((ratio - 1) * 100).toFixed(1)}% change`
        });
      });
    }

    // Resource metrics
    if (baselinePerf.resources && currentPerf.resources) {
      const baselineSize = baselinePerf.resources.totalSize;
      const currentSize = currentPerf.resources.totalSize;
      const sizeRatio = currentSize / baselineSize;
      
      this.results.push({
        category: 'Resources',
        item: 'Total Size',
        status: sizeRatio <= 1.1 ? 'pass' : sizeRatio <= 1.2 ? 'warning' : 'fail',
        baseline: `${(baselineSize / 1024 / 1024).toFixed(2)}MB`,
        current: `${(currentSize / 1024 / 1024).toFixed(2)}MB`,
        difference: `${((sizeRatio - 1) * 100).toFixed(1)}% change`
      });

      const baselineCount = baselinePerf.resources.total;
      const currentCount = currentPerf.resources.total;
      
      this.results.push({
        category: 'Resources',
        item: 'Request Count',
        status: currentCount <= baselineCount * 1.1 ? 'pass' : 'warning',
        baseline: baselineCount,
        current: currentCount,
        difference: `${currentCount - baselineCount} requests`
      });
    }
  }

  private compareAPIs(currentData: any) {
    console.log('🔌 Comparing API endpoints...');

    const baselineAPIs = this.baselineData.api;
    const currentAPIs = currentData.api;

    // Check critical endpoints
    const criticalEndpoints = ['/api/stats', '/health', '/build-info.json'];
    
    criticalEndpoints.forEach(endpoint => {
      const baseline = baselineAPIs[endpoint];
      const current = currentAPIs[endpoint];
      
      if (baseline && current) {
        this.results.push({
          category: 'API Endpoints',
          item: endpoint,
          status: baseline.status === current.status ? 'pass' : 'fail',
          baseline: `Status ${baseline.status}`,
          current: `Status ${current.status}`,
          difference: baseline.status !== current.status ? 'Status code changed' : undefined
        });
      }
    });
  }

  private generateReport() {
    console.log('\n📊 Generating comparison report...\n');

    const passed = this.results.filter(r => r.status === 'pass').length;
    const warnings = this.results.filter(r => r.status === 'warning').length;
    const failed = this.results.filter(r => r.status === 'fail').length;
    const total = this.results.length;

    // Console output
    console.log('=== BASELINE COMPARISON RESULTS ===');
    console.log(`Total Checks: ${total}`);
    console.log(`✅ Passed: ${passed} (${((passed/total)*100).toFixed(1)}%)`);
    console.log(`⚠️  Warnings: ${warnings} (${((warnings/total)*100).toFixed(1)}%)`);
    console.log(`❌ Failed: ${failed} (${((failed/total)*100).toFixed(1)}%)`);
    console.log('===================================\n');

    // Show failures
    if (failed > 0) {
      console.log('❌ FAILURES:');
      this.results.filter(r => r.status === 'fail').forEach(result => {
        console.log(`  - ${result.category} > ${result.item}: ${result.difference}`);
      });
      console.log('');
    }

    // Show warnings
    if (warnings > 0) {
      console.log('⚠️  WARNINGS:');
      this.results.filter(r => r.status === 'warning').forEach(result => {
        console.log(`  - ${result.category} > ${result.item}: ${result.difference}`);
      });
      console.log('');
    }

    // Save detailed report
    const reportPath = path.join(process.cwd(), 'test-baselines', 'comparison-report.json');
    const report = {
      timestamp: new Date().toISOString(),
      summary: { total, passed, warnings, failed },
      baselineDate: this.baselineData.timestamp,
      results: this.results
    };
    
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
    console.log(`📄 Detailed report saved to: ${reportPath}`);

    // Generate markdown report
    const markdown = this.generateMarkdownReport(report);
    const mdPath = path.join(process.cwd(), 'test-baselines', 'COMPARISON_REPORT.md');
    fs.writeFileSync(mdPath, markdown);
    console.log(`📄 Markdown report saved to: ${mdPath}`);

    // Exit with error if failures
    if (failed > 0) {
      console.log('\n❌ Regression detected! Please review the failures above.');
      process.exit(1);
    }
  }

  private generateMarkdownReport(report: any): string {
    return `# Baseline Comparison Report

Generated: ${new Date().toLocaleString()}
Baseline Date: ${new Date(report.baselineDate).toLocaleString()}

## Summary
- **Total Checks**: ${report.summary.total}
- **✅ Passed**: ${report.summary.passed} (${((report.summary.passed/report.summary.total)*100).toFixed(1)}%)
- **⚠️  Warnings**: ${report.summary.warnings} (${((report.summary.warnings/report.summary.total)*100).toFixed(1)}%)
- **❌ Failed**: ${report.summary.failed} (${((report.summary.failed/report.summary.total)*100).toFixed(1)}%)

${report.summary.failed > 0 ? `
## ❌ Failures
${report.results.filter((r: any) => r.status === 'fail').map((r: any) => 
  `- **${r.category} > ${r.item}**: ${r.difference}
  - Baseline: ${r.baseline}
  - Current: ${r.current}`
).join('\n\n')}
` : ''}

${report.summary.warnings > 0 ? `
## ⚠️  Warnings
${report.results.filter((r: any) => r.status === 'warning').map((r: any) => 
  `- **${r.category} > ${r.item}**: ${r.difference}
  - Baseline: ${r.baseline}
  - Current: ${r.current}`
).join('\n\n')}
` : ''}

## Detailed Results

### Page Structure
${report.results.filter((r: any) => r.category === 'Page Structure').map((r: any) => 
  `- ${r.status === 'pass' ? '✅' : '❌'} ${r.item}`
).join('\n')}

### Functionality
${report.results.filter((r: any) => r.category.startsWith('Functionality')).map((r: any) => 
  `- ${r.status === 'pass' ? '✅' : '❌'} ${r.category} > ${r.item}`
).join('\n')}

### Performance
${report.results.filter((r: any) => r.category.includes('Timing') || r.category === 'Resources').map((r: any) => 
  `- ${r.status === 'pass' ? '✅' : r.status === 'warning' ? '⚠️' : '❌'} ${r.category} > ${r.item}: ${r.current} (${r.difference || 'no change'})`
).join('\n')}

### API Endpoints
${report.results.filter((r: any) => r.category === 'API Endpoints').map((r: any) => 
  `- ${r.status === 'pass' ? '✅' : '❌'} ${r.item}: ${r.current}`
).join('\n')}

## Recommendations
${report.summary.failed > 0 ? '- Review and fix failing checks before deployment' : ''}
${report.summary.warnings > 0 ? '- Monitor warning items for potential issues' : ''}
${report.summary.failed === 0 && report.summary.warnings === 0 ? '- All checks passed! Safe to deploy.' : ''}
`;
  }
}

// Run if called directly
if (require.main === module) {
  const comparison = new BaselineComparison();
  comparison.run().catch(console.error);
}

export { BaselineComparison };