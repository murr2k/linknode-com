import { TestResult, TestCase, TestSuite } from '@playwright/test/reporter';
import * as fs from 'fs';
import * as path from 'path';

export interface TestReport {
  summary: {
    total: number;
    passed: number;
    failed: number;
    skipped: number;
    duration: number;
    startTime: Date;
    endTime: Date;
  };
  suites: TestSuiteReport[];
  performance: PerformanceReport;
  visual: VisualReport;
  accessibility: AccessibilityReport;
  coverage: CoverageReport;
}

export interface TestSuiteReport {
  name: string;
  tests: TestCaseReport[];
  duration: number;
  status: 'passed' | 'failed' | 'skipped';
}

export interface TestCaseReport {
  name: string;
  status: 'passed' | 'failed' | 'skipped';
  duration: number;
  error?: string;
  annotations: string[];
  attachments: Array<{
    name: string;
    contentType: string;
    path?: string;
  }>;
}

export interface PerformanceReport {
  metrics: {
    lcp: { value: number; status: string };
    fid: { value: number; status: string };
    cls: { value: number; status: string };
    ttfb: { value: number; status: string };
    fcp: { value: number; status: string };
    tti: { value: number; status: string };
  };
  resourceBreakdown: Record<string, {
    count: number;
    size: number;
    duration: number;
  }>;
  budgetViolations: string[];
}

export interface VisualReport {
  totalComparisons: number;
  differences: Array<{
    name: string;
    diffPixels: number;
    diffPercentage: number;
  }>;
  viewportCoverage: string[];
  browserCoverage: string[];
}

export interface AccessibilityReport {
  violations: Array<{
    rule: string;
    severity: 'minor' | 'moderate' | 'serious' | 'critical';
    elements: number;
    description: string;
  }>;
  wcagLevel: 'A' | 'AA' | 'AAA';
  score: number;
}

export interface CoverageReport {
  js: {
    total: number;
    covered: number;
    percentage: number;
  };
  css: {
    total: number;
    covered: number;
    percentage: number;
  };
}

export class TestReporter {
  private outputDir: string;
  private report: TestReport;

  constructor(outputDir: string = './test-results/reports') {
    this.outputDir = outputDir;
    this.report = this.initializeReport();
    
    // Ensure output directory exists
    if (!fs.existsSync(this.outputDir)) {
      fs.mkdirSync(this.outputDir, { recursive: true });
    }
  }

  private initializeReport(): TestReport {
    return {
      summary: {
        total: 0,
        passed: 0,
        failed: 0,
        skipped: 0,
        duration: 0,
        startTime: new Date(),
        endTime: new Date()
      },
      suites: [],
      performance: {
        metrics: {
          lcp: { value: 0, status: 'unknown' },
          fid: { value: 0, status: 'unknown' },
          cls: { value: 0, status: 'unknown' },
          ttfb: { value: 0, status: 'unknown' },
          fcp: { value: 0, status: 'unknown' },
          tti: { value: 0, status: 'unknown' }
        },
        resourceBreakdown: {},
        budgetViolations: []
      },
      visual: {
        totalComparisons: 0,
        differences: [],
        viewportCoverage: [],
        browserCoverage: []
      },
      accessibility: {
        violations: [],
        wcagLevel: 'AA',
        score: 100
      },
      coverage: {
        js: { total: 0, covered: 0, percentage: 0 },
        css: { total: 0, covered: 0, percentage: 0 }
      }
    };
  }

  /**
   * Add test results to the report
   */
  addTestResults(results: TestResult[]) {
    results.forEach(result => {
      this.report.summary.total++;
      
      switch (result.status) {
        case 'passed':
          this.report.summary.passed++;
          break;
        case 'failed':
          this.report.summary.failed++;
          break;
        case 'skipped':
          this.report.summary.skipped++;
          break;
      }
      
      this.report.summary.duration += result.duration;
    });
  }

  /**
   * Add performance metrics
   */
  addPerformanceMetrics(metrics: Partial<PerformanceReport['metrics']>) {
    Object.assign(this.report.performance.metrics, metrics);
  }

  /**
   * Add visual test results
   */
  addVisualResults(results: Partial<VisualReport>) {
    Object.assign(this.report.visual, results);
  }

  /**
   * Add accessibility results
   */
  addAccessibilityResults(results: Partial<AccessibilityReport>) {
    Object.assign(this.report.accessibility, results);
  }

  /**
   * Add coverage results
   */
  addCoverageResults(results: Partial<CoverageReport>) {
    Object.assign(this.report.coverage, results);
  }

  /**
   * Generate HTML report
   */
  generateHTMLReport(): string {
    const html = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>E2E Test Report - ${new Date().toLocaleDateString()}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0a;
            color: #e0e0e0;
            line-height: 1.6;
            padding: 2rem;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1, h2, h3 { margin-bottom: 1rem; }
        h1 { 
            font-size: 2.5rem; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 2rem;
        }
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 3rem;
        }
        .summary-card {
            background: rgba(255, 255, 255, 0.05);
            padding: 1.5rem;
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .summary-card h3 { font-size: 0.875rem; opacity: 0.7; }
        .summary-card .value { font-size: 2rem; font-weight: bold; }
        .passed { color: #4ade80; }
        .failed { color: #f87171; }
        .skipped { color: #fbbf24; }
        .section {
            background: rgba(255, 255, 255, 0.03);
            padding: 2rem;
            border-radius: 16px;
            margin-bottom: 2rem;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }
        .metric {
            text-align: center;
            padding: 1rem;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 8px;
        }
        .metric .label { font-size: 0.875rem; opacity: 0.7; }
        .metric .value { font-size: 1.5rem; font-weight: bold; margin: 0.5rem 0; }
        .metric .status { font-size: 0.75rem; }
        .good { color: #4ade80; }
        .warning { color: #fbbf24; }
        .bad { color: #f87171; }
        .chart {
            height: 200px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            display: flex;
            align-items: flex-end;
            padding: 1rem;
            gap: 0.5rem;
            margin-top: 1rem;
        }
        .bar {
            flex: 1;
            background: #667eea;
            border-radius: 4px 4px 0 0;
            position: relative;
        }
        .bar::after {
            content: attr(data-label);
            position: absolute;
            bottom: -1.5rem;
            left: 50%;
            transform: translateX(-50%);
            font-size: 0.75rem;
            opacity: 0.7;
        }
        table {
            width: 100%;
            margin-top: 1rem;
            border-collapse: collapse;
        }
        th, td {
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        th { opacity: 0.7; font-weight: normal; }
        .severity-critical { color: #dc2626; }
        .severity-serious { color: #f87171; }
        .severity-moderate { color: #fbbf24; }
        .severity-minor { color: #60a5fa; }
        .footer {
            margin-top: 3rem;
            padding-top: 2rem;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            text-align: center;
            opacity: 0.7;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>E2E Test Report</h1>
        
        <div class="summary">
            <div class="summary-card">
                <h3>Total Tests</h3>
                <div class="value">${this.report.summary.total}</div>
            </div>
            <div class="summary-card">
                <h3>Passed</h3>
                <div class="value passed">${this.report.summary.passed}</div>
            </div>
            <div class="summary-card">
                <h3>Failed</h3>
                <div class="value failed">${this.report.summary.failed}</div>
            </div>
            <div class="summary-card">
                <h3>Skipped</h3>
                <div class="value skipped">${this.report.summary.skipped}</div>
            </div>
            <div class="summary-card">
                <h3>Duration</h3>
                <div class="value">${(this.report.summary.duration / 1000).toFixed(1)}s</div>
            </div>
            <div class="summary-card">
                <h3>Success Rate</h3>
                <div class="value">${((this.report.summary.passed / this.report.summary.total) * 100).toFixed(1)}%</div>
            </div>
        </div>

        <div class="section">
            <h2>Performance Metrics</h2>
            <div class="metrics-grid">
                ${Object.entries(this.report.performance.metrics).map(([key, metric]) => `
                    <div class="metric">
                        <div class="label">${key.toUpperCase()}</div>
                        <div class="value">${metric.value}${key === 'cls' ? '' : 'ms'}</div>
                        <div class="status ${metric.status}">${metric.status}</div>
                    </div>
                `).join('')}
            </div>
            ${this.report.performance.budgetViolations.length > 0 ? `
                <h3 style="margin-top: 2rem;">Budget Violations</h3>
                <ul>
                    ${this.report.performance.budgetViolations.map(v => `<li>${v}</li>`).join('')}
                </ul>
            ` : ''}
        </div>

        <div class="section">
            <h2>Visual Testing</h2>
            <p>Total Comparisons: ${this.report.visual.totalComparisons}</p>
            <p>Viewports Tested: ${this.report.visual.viewportCoverage.join(', ')}</p>
            <p>Browsers Tested: ${this.report.visual.browserCoverage.join(', ')}</p>
            ${this.report.visual.differences.length > 0 ? `
                <h3>Visual Differences</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Test</th>
                            <th>Diff Pixels</th>
                            <th>Diff %</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${this.report.visual.differences.map(d => `
                            <tr>
                                <td>${d.name}</td>
                                <td>${d.diffPixels}</td>
                                <td>${d.diffPercentage.toFixed(2)}%</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            ` : '<p>No visual differences detected!</p>'}
        </div>

        <div class="section">
            <h2>Accessibility</h2>
            <p>WCAG Level: ${this.report.accessibility.wcagLevel}</p>
            <p>Score: ${this.report.accessibility.score}/100</p>
            ${this.report.accessibility.violations.length > 0 ? `
                <h3>Violations</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Rule</th>
                            <th>Severity</th>
                            <th>Elements</th>
                            <th>Description</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${this.report.accessibility.violations.map(v => `
                            <tr>
                                <td>${v.rule}</td>
                                <td class="severity-${v.severity}">${v.severity}</td>
                                <td>${v.elements}</td>
                                <td>${v.description}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            ` : '<p>No accessibility violations found!</p>'}
        </div>

        <div class="section">
            <h2>Code Coverage</h2>
            <div class="metrics-grid">
                <div class="metric">
                    <div class="label">JavaScript</div>
                    <div class="value">${this.report.coverage.js.percentage.toFixed(1)}%</div>
                    <div class="status">${this.report.coverage.js.covered}/${this.report.coverage.js.total} lines</div>
                </div>
                <div class="metric">
                    <div class="label">CSS</div>
                    <div class="value">${this.report.coverage.css.percentage.toFixed(1)}%</div>
                    <div class="status">${this.report.coverage.css.covered}/${this.report.coverage.css.total} rules</div>
                </div>
            </div>
        </div>

        <div class="footer">
            <p>Generated on ${new Date().toLocaleString()}</p>
            <p>Linknode E2E Test Suite - Phase 3</p>
        </div>
    </div>
</body>
</html>
`;
    return html;
  }

  /**
   * Generate JSON report
   */
  generateJSONReport(): string {
    return JSON.stringify(this.report, null, 2);
  }

  /**
   * Generate Markdown report
   */
  generateMarkdownReport(): string {
    const md = `# E2E Test Report
Generated: ${new Date().toLocaleString()}

## Summary
- **Total Tests**: ${this.report.summary.total}
- **Passed**: ${this.report.summary.passed} ✅
- **Failed**: ${this.report.summary.failed} ❌
- **Skipped**: ${this.report.summary.skipped} ⏭️
- **Duration**: ${(this.report.summary.duration / 1000).toFixed(1)}s
- **Success Rate**: ${((this.report.summary.passed / this.report.summary.total) * 100).toFixed(1)}%

## Performance Metrics
| Metric | Value | Status |
|--------|-------|--------|
${Object.entries(this.report.performance.metrics).map(([key, metric]) => 
  `| ${key.toUpperCase()} | ${metric.value}${key === 'cls' ? '' : 'ms'} | ${metric.status} |`
).join('\n')}

${this.report.performance.budgetViolations.length > 0 ? `
### Budget Violations
${this.report.performance.budgetViolations.map(v => `- ${v}`).join('\n')}
` : ''}

## Visual Testing
- **Total Comparisons**: ${this.report.visual.totalComparisons}
- **Viewports**: ${this.report.visual.viewportCoverage.join(', ')}
- **Browsers**: ${this.report.visual.browserCoverage.join(', ')}

${this.report.visual.differences.length > 0 ? `
### Visual Differences
| Test | Diff Pixels | Diff % |
|------|-------------|--------|
${this.report.visual.differences.map(d => 
  `| ${d.name} | ${d.diffPixels} | ${d.diffPercentage.toFixed(2)}% |`
).join('\n')}
` : 'No visual differences detected! ✅'}

## Accessibility
- **WCAG Level**: ${this.report.accessibility.wcagLevel}
- **Score**: ${this.report.accessibility.score}/100

${this.report.accessibility.violations.length > 0 ? `
### Violations
| Rule | Severity | Elements | Description |
|------|----------|----------|-------------|
${this.report.accessibility.violations.map(v => 
  `| ${v.rule} | ${v.severity} | ${v.elements} | ${v.description} |`
).join('\n')}
` : 'No accessibility violations found! ♿'}

## Code Coverage
- **JavaScript**: ${this.report.coverage.js.percentage.toFixed(1)}% (${this.report.coverage.js.covered}/${this.report.coverage.js.total} lines)
- **CSS**: ${this.report.coverage.css.percentage.toFixed(1)}% (${this.report.coverage.css.covered}/${this.report.coverage.css.total} rules)
`;
    return md;
  }

  /**
   * Save reports to files
   */
  saveReports() {
    // Save HTML report
    const htmlPath = path.join(this.outputDir, `report-${Date.now()}.html`);
    fs.writeFileSync(htmlPath, this.generateHTMLReport());
    console.log(`HTML report saved to: ${htmlPath}`);
    
    // Save JSON report
    const jsonPath = path.join(this.outputDir, `report-${Date.now()}.json`);
    fs.writeFileSync(jsonPath, this.generateJSONReport());
    console.log(`JSON report saved to: ${jsonPath}`);
    
    // Save Markdown report
    const mdPath = path.join(this.outputDir, `report-${Date.now()}.md`);
    fs.writeFileSync(mdPath, this.generateMarkdownReport());
    console.log(`Markdown report saved to: ${mdPath}`);
    
    // Save latest symlinks
    const latestHtml = path.join(this.outputDir, 'latest.html');
    const latestJson = path.join(this.outputDir, 'latest.json');
    const latestMd = path.join(this.outputDir, 'latest.md');
    
    if (fs.existsSync(latestHtml)) fs.unlinkSync(latestHtml);
    if (fs.existsSync(latestJson)) fs.unlinkSync(latestJson);
    if (fs.existsSync(latestMd)) fs.unlinkSync(latestMd);
    
    fs.symlinkSync(path.basename(htmlPath), latestHtml);
    fs.symlinkSync(path.basename(jsonPath), latestJson);
    fs.symlinkSync(path.basename(mdPath), latestMd);
  }
}

// Helper function to get Web Vitals status
export function getWebVitalStatus(metric: string, value: number): string {
  const thresholds: Record<string, { good: number; needsImprovement: number }> = {
    lcp: { good: 2500, needsImprovement: 4000 },
    fid: { good: 100, needsImprovement: 300 },
    cls: { good: 0.1, needsImprovement: 0.25 },
    fcp: { good: 1800, needsImprovement: 3000 },
    ttfb: { good: 800, needsImprovement: 1800 }
  };
  
  const threshold = thresholds[metric];
  if (!threshold) return 'unknown';
  
  if (value <= threshold.good) return 'good';
  if (value <= threshold.needsImprovement) return 'needs improvement';
  return 'poor';
}