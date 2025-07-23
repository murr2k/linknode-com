import { Reporter, TestCase, TestResult, Suite } from '@playwright/test/reporter';
import { TestReporter, getWebVitalStatus } from '../utils/test-reporter';
import * as fs from 'fs';
import * as path from 'path';

export default class Phase3Reporter implements Reporter {
  private testReporter: TestReporter;
  private performanceData: Map<string, any> = new Map();
  private visualData: Map<string, any> = new Map();
  private accessibilityData: Map<string, any> = new Map();
  private coverageData: Map<string, any> = new Map();

  constructor() {
    this.testReporter = new TestReporter();
  }

  onBegin(config: any, suite: Suite) {
    console.log(`Starting test run with ${suite.allTests().length} tests`);
  }

  onTestBegin(test: TestCase, result: TestResult) {
    console.log(`Running: ${test.title}`);
  }

  onTestEnd(test: TestCase, result: TestResult) {
    // Extract performance data from test annotations
    const perfAnnotation = result.annotations.find(a => a.type === 'performance');
    if (perfAnnotation && perfAnnotation.description) {
      try {
        const perfData = JSON.parse(perfAnnotation.description);
        this.performanceData.set(test.title, perfData);
      } catch (e) {
        console.error('Failed to parse performance data:', e);
      }
    }

    // Extract visual test data
    const visualAnnotation = result.annotations.find(a => a.type === 'visual');
    if (visualAnnotation && visualAnnotation.description) {
      try {
        const visualData = JSON.parse(visualAnnotation.description);
        this.visualData.set(test.title, visualData);
      } catch (e) {
        console.error('Failed to parse visual data:', e);
      }
    }

    // Extract accessibility data
    const a11yAnnotation = result.annotations.find(a => a.type === 'accessibility');
    if (a11yAnnotation && a11yAnnotation.description) {
      try {
        const a11yData = JSON.parse(a11yAnnotation.description);
        this.accessibilityData.set(test.title, a11yData);
      } catch (e) {
        console.error('Failed to parse accessibility data:', e);
      }
    }

    // Extract coverage data
    const coverageAnnotation = result.annotations.find(a => a.type === 'coverage');
    if (coverageAnnotation && coverageAnnotation.description) {
      try {
        const coverageData = JSON.parse(coverageAnnotation.description);
        this.coverageData.set(test.title, coverageData);
      } catch (e) {
        console.error('Failed to parse coverage data:', e);
      }
    }

    // Process attachments (screenshots, traces, etc.)
    result.attachments.forEach(attachment => {
      if (attachment.name === 'performance-metrics' && attachment.body) {
        try {
          const metrics = JSON.parse(attachment.body.toString());
          this.processPerformanceMetrics(metrics);
        } catch (e) {
          console.error('Failed to process performance metrics:', e);
        }
      }
    });
  }

  onEnd(result: any) {
    // Add test results
    this.testReporter.addTestResults(result.results);

    // Aggregate performance data
    this.aggregatePerformanceData();

    // Aggregate visual data
    this.aggregateVisualData();

    // Aggregate accessibility data
    this.aggregateAccessibilityData();

    // Aggregate coverage data
    this.aggregateCoverageData();

    // Save reports
    this.testReporter.saveReports();

    // Print summary
    this.printSummary();
  }

  private processPerformanceMetrics(metrics: any) {
    // Process Core Web Vitals
    if (metrics.lcp !== undefined) {
      const status = getWebVitalStatus('lcp', metrics.lcp);
      this.testReporter.addPerformanceMetrics({
        lcp: { value: metrics.lcp, status }
      });
    }

    if (metrics.fid !== undefined) {
      const status = getWebVitalStatus('fid', metrics.fid);
      this.testReporter.addPerformanceMetrics({
        fid: { value: metrics.fid, status }
      });
    }

    if (metrics.cls !== undefined) {
      const status = getWebVitalStatus('cls', metrics.cls);
      this.testReporter.addPerformanceMetrics({
        cls: { value: metrics.cls, status }
      });
    }

    if (metrics.fcp !== undefined) {
      const status = getWebVitalStatus('fcp', metrics.fcp);
      this.testReporter.addPerformanceMetrics({
        fcp: { value: metrics.fcp, status }
      });
    }

    if (metrics.ttfb !== undefined) {
      const status = getWebVitalStatus('ttfb', metrics.ttfb);
      this.testReporter.addPerformanceMetrics({
        ttfb: { value: metrics.ttfb, status }
      });
    }

    if (metrics.timeToInteractive !== undefined) {
      const status = metrics.timeToInteractive < 3800 ? 'good' : 
                    metrics.timeToInteractive < 7300 ? 'needs improvement' : 'poor';
      this.testReporter.addPerformanceMetrics({
        tti: { value: metrics.timeToInteractive, status }
      });
    }
  }

  private aggregatePerformanceData() {
    // Collect all performance metrics
    const allMetrics: any[] = [];
    this.performanceData.forEach(data => {
      if (data.metrics) {
        allMetrics.push(data.metrics);
      }
    });

    // Calculate averages for Core Web Vitals
    if (allMetrics.length > 0) {
      const avgLcp = allMetrics.reduce((sum, m) => sum + (m.lcp || 0), 0) / allMetrics.length;
      const avgFid = allMetrics.reduce((sum, m) => sum + (m.fid || 0), 0) / allMetrics.length;
      const avgCls = allMetrics.reduce((sum, m) => sum + (m.cls || 0), 0) / allMetrics.length;
      
      this.testReporter.addPerformanceMetrics({
        lcp: { value: Math.round(avgLcp), status: getWebVitalStatus('lcp', avgLcp) },
        fid: { value: Math.round(avgFid), status: getWebVitalStatus('fid', avgFid) },
        cls: { value: parseFloat(avgCls.toFixed(3)), status: getWebVitalStatus('cls', avgCls) }
      });
    }

    // Collect budget violations
    const violations: string[] = [];
    this.performanceData.forEach((data, testName) => {
      if (data.budgetViolations && data.budgetViolations.length > 0) {
        violations.push(...data.budgetViolations.map((v: string) => `${testName}: ${v}`));
      }
    });
    
    if (violations.length > 0) {
      this.testReporter.addPerformanceMetrics({
        budgetViolations: violations
      } as any);
    }
  }

  private aggregateVisualData() {
    let totalComparisons = 0;
    const differences: any[] = [];
    const viewports = new Set<string>();
    const browsers = new Set<string>();

    this.visualData.forEach((data, testName) => {
      if (data.comparisons) {
        totalComparisons += data.comparisons;
      }

      if (data.differences && data.differences.length > 0) {
        differences.push(...data.differences);
      }

      if (data.viewport) {
        viewports.add(data.viewport);
      }

      if (data.browser) {
        browsers.add(data.browser);
      }
    });

    this.testReporter.addVisualResults({
      totalComparisons,
      differences,
      viewportCoverage: Array.from(viewports),
      browserCoverage: Array.from(browsers)
    });
  }

  private aggregateAccessibilityData() {
    const allViolations: any[] = [];
    let totalScore = 0;
    let scoreCount = 0;

    this.accessibilityData.forEach(data => {
      if (data.violations) {
        allViolations.push(...data.violations);
      }

      if (data.score !== undefined) {
        totalScore += data.score;
        scoreCount++;
      }
    });

    // Group violations by rule
    const violationMap = new Map<string, any>();
    allViolations.forEach(violation => {
      const existing = violationMap.get(violation.rule) || {
        rule: violation.rule,
        severity: violation.severity,
        elements: 0,
        description: violation.description
      };
      existing.elements += violation.elements || 1;
      violationMap.set(violation.rule, existing);
    });

    this.testReporter.addAccessibilityResults({
      violations: Array.from(violationMap.values()),
      score: scoreCount > 0 ? Math.round(totalScore / scoreCount) : 100
    });
  }

  private aggregateCoverageData() {
    let totalJsLines = 0;
    let coveredJsLines = 0;
    let totalCssRules = 0;
    let coveredCssRules = 0;

    this.coverageData.forEach(data => {
      if (data.js) {
        totalJsLines += data.js.total || 0;
        coveredJsLines += data.js.covered || 0;
      }

      if (data.css) {
        totalCssRules += data.css.total || 0;
        coveredCssRules += data.css.covered || 0;
      }
    });

    this.testReporter.addCoverageResults({
      js: {
        total: totalJsLines,
        covered: coveredJsLines,
        percentage: totalJsLines > 0 ? (coveredJsLines / totalJsLines) * 100 : 0
      },
      css: {
        total: totalCssRules,
        covered: coveredCssRules,
        percentage: totalCssRules > 0 ? (coveredCssRules / totalCssRules) * 100 : 0
      }
    });
  }

  private printSummary() {
    console.log('\n' + '='.repeat(80));
    console.log('E2E TEST SUMMARY - PHASE 3');
    console.log('='.repeat(80));
    
    // Performance summary
    console.log('\n📊 Performance Metrics:');
    console.log('  Core Web Vitals status aggregated across all tests');
    
    // Visual testing summary
    console.log('\n👁️  Visual Testing:');
    console.log(`  Total comparisons: ${this.visualData.size}`);
    
    // Accessibility summary
    console.log('\n♿ Accessibility:');
    console.log(`  Tests with violations: ${Array.from(this.accessibilityData.values()).filter(d => d.violations && d.violations.length > 0).length}`);
    
    // Coverage summary
    console.log('\n📈 Code Coverage:');
    console.log('  Coverage data collected for JS and CSS');
    
    console.log('\n📄 Reports generated in: ./test-results/reports/');
    console.log('='.repeat(80) + '\n');
  }
}

// Helper function to attach performance data to test
export function attachPerformanceData(test: any, data: any) {
  test.info().annotations.push({
    type: 'performance',
    description: JSON.stringify(data)
  });
}

// Helper function to attach visual data to test
export function attachVisualData(test: any, data: any) {
  test.info().annotations.push({
    type: 'visual',
    description: JSON.stringify(data)
  });
}

// Helper function to attach accessibility data to test
export function attachAccessibilityData(test: any, data: any) {
  test.info().annotations.push({
    type: 'accessibility',
    description: JSON.stringify(data)
  });
}

// Helper function to attach coverage data to test
export function attachCoverageData(test: any, data: any) {
  test.info().annotations.push({
    type: 'coverage',
    description: JSON.stringify(data)
  });
}