import { test, expect } from '@playwright/test';
import { PerformanceCollector } from '../../utils/performance-metrics';
import { HomePage } from '../../pages/HomePage';

test.describe('Advanced Performance Tests @performance @phase3', () => {
  let performanceCollector: PerformanceCollector;
  let homePage: HomePage;

  test.beforeEach(async ({ page }) => {
    performanceCollector = new PerformanceCollector(page);
    homePage = new HomePage(page);
    await performanceCollector.initialize();
  });

  test.describe('Performance Profiling', () => {
    test('should profile initial page load performance', async ({ page }) => {
      // Clear cache and cookies
      await page.context().clearCookies();
      
      // Start profiling
      await page.coverage.startJSCoverage();
      await page.coverage.startCSSCoverage();
      
      // Navigate with performance timing
      await homePage.goto();
      
      // Collect metrics
      const metrics = await performanceCollector.collect();
      const jsReport = await page.coverage.stopJSCoverage();
      const cssReport = await page.coverage.stopCSSCoverage();
      
      // Generate performance report
      const report = performanceCollector.generateReport(metrics);
      console.log(report);
      
      // Calculate coverage
      const jsCoverage = jsReport.reduce((acc, entry) => {
        const total = entry.text.length;
        const used = entry.ranges.reduce((sum, range) => sum + (range.end - range.start), 0);
        return acc + (used / total);
      }, 0) / jsReport.length * 100;
      
      const cssCoverage = cssReport.reduce((acc, entry) => {
        const total = entry.text.length;
        const used = entry.ranges.reduce((sum, range) => sum + (range.end - range.start), 0);
        return acc + (used / total);
      }, 0) / cssReport.length * 100;
      
      console.log(`JS Coverage: ${jsCoverage.toFixed(2)}%`);
      console.log(`CSS Coverage: ${cssCoverage.toFixed(2)}%`);
      
      // Performance assertions
      expect(metrics.lcp).toBeLessThan(2500); // Good LCP
      expect(metrics.fid).toBeLessThan(100); // Good FID
      expect(metrics.cls).toBeLessThan(0.1); // Good CLS
    });

    test('should profile runtime performance', async ({ page }) => {
      await homePage.goto();
      
      // Start runtime profiling
      const client = await page.context().newCDPSession(page);
      await client.send('Profiler.enable');
      await client.send('Profiler.start');
      
      // Perform interactions
      await page.waitForTimeout(2000); // Let the page run
      
      // Simulate user interactions
      await page.hover('.power-widget');
      await page.click('.metric:first-child');
      
      // Stop profiling
      const profile = await client.send('Profiler.stop');
      
      // Analyze profile
      if (profile.profile) {
        const totalTime = profile.profile.endTime - profile.profile.startTime;
        console.log(`Total profiling time: ${totalTime}μs`);
        
        // Find expensive functions
        const nodes = profile.profile.nodes || [];
        const expensive = nodes
          .filter(node => node.hitCount && node.hitCount > 10)
          .sort((a, b) => (b.hitCount || 0) - (a.hitCount || 0))
          .slice(0, 5);
        
        console.log('Top 5 most called functions:');
        expensive.forEach(node => {
          console.log(`- ${node.callFrame.functionName || 'anonymous'}: ${node.hitCount} calls`);
        });
      }
    });
  });

  test.describe('Resource Loading Performance', () => {
    test('should optimize resource loading', async ({ page }) => {
      const resources: Array<{
        url: string;
        type: string;
        size: number;
        duration: number;
        priority: string;
      }> = [];
      
      // Monitor resource loading
      page.on('response', async response => {
        const request = response.request();
        const timing = response.timing();
        
        if (timing) {
          resources.push({
            url: response.url(),
            type: request.resourceType(),
            size: parseInt(response.headers()['content-length'] || '0'),
            duration: timing.responseEnd - timing.requestStart,
            priority: request.headers()['priority'] || 'normal'
          });
        }
      });
      
      await homePage.goto();
      await page.waitForLoadState('networkidle');
      
      // Analyze resources
      const breakdown = await performanceCollector.getResourceBreakdown();
      console.log('Resource breakdown:', breakdown);
      
      // Check for optimization opportunities
      const largeResources = resources.filter(r => r.size > 100 * 1024); // > 100KB
      const slowResources = resources.filter(r => r.duration > 1000); // > 1s
      
      console.log(`Large resources (>100KB): ${largeResources.length}`);
      console.log(`Slow resources (>1s): ${slowResources.length}`);
      
      // Check compression
      const uncompressedResources = resources.filter(r => {
        return ['script', 'stylesheet', 'document'].includes(r.type) && 
               !r.url.includes('.min.');
      });
      
      expect(uncompressedResources.length).toBe(0);
      
      // Check resource priorities
      const criticalResources = resources.filter(r => 
        r.type === 'stylesheet' || 
        (r.type === 'script' && r.url.includes('critical'))
      );
      
      criticalResources.forEach(resource => {
        console.log(`Critical resource ${resource.url} priority: ${resource.priority}`);
      });
    });

    test('should implement efficient caching', async ({ page }) => {
      // First visit
      await homePage.goto();
      const firstVisitMetrics = await performanceCollector.collect();
      
      // Second visit (should use cache)
      await page.reload();
      const secondVisitMetrics = await performanceCollector.collect();
      
      // Compare metrics
      console.log('First visit total requests:', firstVisitMetrics.totalRequests);
      console.log('Second visit cached requests:', secondVisitMetrics.cachedRequests);
      
      // Cache ratio should be high on second visit
      const cacheRatio = secondVisitMetrics.cachedRequests / secondVisitMetrics.totalRequests;
      expect(cacheRatio).toBeGreaterThan(0.5); // At least 50% cached
      
      // Load time should be faster
      expect(secondVisitMetrics.loadComplete).toBeLessThan(firstVisitMetrics.loadComplete);
    });
  });

  test.describe('Performance Budget Enforcement', () => {
    test('should meet performance budgets', async ({ page }) => {
      await homePage.goto();
      const metrics = await performanceCollector.collect();
      
      // Define performance budgets
      const budget = {
        // Core Web Vitals
        lcp: 2500,              // 2.5s
        fid: 100,               // 100ms
        cls: 0.1,               // 0.1
        
        // Loading metrics
        firstContentfulPaint: 1800,  // 1.8s
        timeToInteractive: 3800,      // 3.8s
        totalBlockingTime: 300,       // 300ms
        
        // Resource metrics
        totalSize: 2 * 1024 * 1024,   // 2MB
        totalRequests: 50,            // 50 requests
        
        // Memory
        jsHeapUsed: 50 * 1024 * 1024  // 50MB
      };
      
      const budgetCheck = performanceCollector.checkPerformanceBudget(metrics, budget);
      
      if (!budgetCheck.passed) {
        console.log('Performance budget violations:');
        budgetCheck.failures.forEach(failure => console.log(`- ${failure}`));
      }
      
      expect(budgetCheck.passed).toBe(true);
    });

    test('should maintain performance under load', async ({ page }) => {
      await homePage.goto();
      
      const initialMetrics = await performanceCollector.collect();
      
      // Simulate heavy usage
      for (let i = 0; i < 10; i++) {
        // Trigger API calls
        await page.evaluate(() => {
          // Force refresh of power data
          if (typeof (window as any).updatePowerData === 'function') {
            (window as any).updatePowerData();
          }
        });
        
        await page.waitForTimeout(100);
      }
      
      // Collect metrics after load
      const loadedMetrics = await performanceCollector.collect();
      
      // Memory should not increase significantly
      const memoryIncrease = loadedMetrics.jsHeapUsed - initialMetrics.jsHeapUsed;
      const memoryIncreasePercent = (memoryIncrease / initialMetrics.jsHeapUsed) * 100;
      
      console.log(`Memory increase: ${(memoryIncrease / 1024 / 1024).toFixed(2)}MB (${memoryIncreasePercent.toFixed(2)}%)`);
      
      expect(memoryIncreasePercent).toBeLessThan(50); // Less than 50% increase
    });
  });

  test.describe('Animation Performance', () => {
    test('should maintain 60fps during animations', async ({ page }) => {
      await homePage.goto();
      
      // Start monitoring frames
      const client = await page.context().newCDPSession(page);
      await client.send('Overlay.setShowFPSCounter', { show: true });
      
      let frameCount = 0;
      let droppedFrames = 0;
      
      // Monitor animation frames
      await page.evaluateOnNewDocument(() => {
        let lastTime = performance.now();
        const targetFrameTime = 1000 / 60; // 16.67ms for 60fps
        
        (window as any).frameMetrics = {
          count: 0,
          dropped: 0,
          times: []
        };
        
        const measureFrame = () => {
          const currentTime = performance.now();
          const deltaTime = currentTime - lastTime;
          
          (window as any).frameMetrics.count++;
          (window as any).frameMetrics.times.push(deltaTime);
          
          if (deltaTime > targetFrameTime * 1.5) { // 50% tolerance
            (window as any).frameMetrics.dropped++;
          }
          
          lastTime = currentTime;
          requestAnimationFrame(measureFrame);
        };
        
        requestAnimationFrame(measureFrame);
      });
      
      // Trigger animations
      await page.hover('.power-widget');
      await page.hover('.api-status-widget');
      
      // Scroll to trigger any scroll animations
      await page.evaluate(() => {
        window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
      });
      
      await page.waitForTimeout(2000); // Let animations run
      
      // Collect frame metrics
      const frameMetrics = await page.evaluate(() => (window as any).frameMetrics);
      
      console.log(`Total frames: ${frameMetrics.count}`);
      console.log(`Dropped frames: ${frameMetrics.dropped}`);
      
      const avgFrameTime = frameMetrics.times.reduce((a: number, b: number) => a + b, 0) / frameMetrics.times.length;
      console.log(`Average frame time: ${avgFrameTime.toFixed(2)}ms`);
      
      const droppedFramePercent = (frameMetrics.dropped / frameMetrics.count) * 100;
      expect(droppedFramePercent).toBeLessThan(5); // Less than 5% dropped frames
    });

    test('should optimize CSS animations', async ({ page }) => {
      await homePage.goto();
      
      // Check for hardware-accelerated properties
      const animationCheck = await page.evaluate(() => {
        const results: Record<string, any> = {
          willChange: [],
          transforms: [],
          nonOptimized: []
        };
        
        document.querySelectorAll('*').forEach(el => {
          const styles = window.getComputedStyle(el);
          
          // Check will-change
          if (styles.willChange !== 'auto') {
            results.willChange.push({
              element: el.className || el.tagName,
              value: styles.willChange
            });
          }
          
          // Check transforms
          if (styles.transform !== 'none') {
            results.transforms.push({
              element: el.className || el.tagName,
              value: styles.transform
            });
          }
          
          // Check for non-optimized animations
          if (styles.animation !== 'none') {
            const animationName = styles.animationName;
            // This is a simplified check - in reality, we'd parse keyframes
            if (animationName && !animationName.includes('transform') && !animationName.includes('opacity')) {
              results.nonOptimized.push({
                element: el.className || el.tagName,
                animation: animationName
              });
            }
          }
        });
        
        return results;
      });
      
      console.log('Animation optimization check:', animationCheck);
      
      // Warn about non-optimized animations
      if (animationCheck.nonOptimized.length > 0) {
        console.warn('Non-optimized animations found:', animationCheck.nonOptimized);
      }
    });
  });

  test.describe('Memory Performance', () => {
    test('should not have memory leaks', async ({ page }) => {
      await homePage.goto();
      
      // Take initial heap snapshot
      const client = await page.context().newCDPSession(page);
      await client.send('HeapProfiler.enable');
      
      const initialHeap = await page.evaluate(() => {
        if ((performance as any).memory) {
          return (performance as any).memory.usedJSHeapSize;
        }
        return 0;
      });
      
      // Perform actions that might cause leaks
      for (let i = 0; i < 5; i++) {
        // Navigate away and back
        await page.goto('about:blank');
        await homePage.goto();
        
        // Force garbage collection if available
        await page.evaluate(() => {
          if ((window as any).gc) {
            (window as any).gc();
          }
        });
      }
      
      // Take final measurement
      const finalHeap = await page.evaluate(() => {
        if ((performance as any).memory) {
          return (performance as any).memory.usedJSHeapSize;
        }
        return 0;
      });
      
      const heapGrowth = finalHeap - initialHeap;
      const growthPercent = (heapGrowth / initialHeap) * 100;
      
      console.log(`Heap growth: ${(heapGrowth / 1024 / 1024).toFixed(2)}MB (${growthPercent.toFixed(2)}%)`);
      
      // Should not grow more than 20%
      expect(growthPercent).toBeLessThan(20);
    });

    test('should efficiently handle DOM updates', async ({ page }) => {
      await homePage.goto();
      
      // Monitor DOM mutations
      const mutationCount = await page.evaluate(() => {
        let count = 0;
        const observer = new MutationObserver((mutations) => {
          count += mutations.length;
        });
        
        observer.observe(document.body, {
          childList: true,
          subtree: true,
          attributes: true,
          characterData: true
        });
        
        // Store observer reference
        (window as any).mutationObserver = observer;
        (window as any).getMutationCount = () => count;
        
        return count;
      });
      
      // Wait for updates
      await page.waitForTimeout(5000);
      
      // Get final count
      const finalCount = await page.evaluate(() => (window as any).getMutationCount());
      
      console.log(`DOM mutations in 5 seconds: ${finalCount}`);
      
      // Disconnect observer
      await page.evaluate(() => {
        (window as any).mutationObserver.disconnect();
      });
      
      // Should not have excessive DOM thrashing
      expect(finalCount).toBeLessThan(1000); // Reasonable threshold
    });
  });

  test.describe('Network Performance', () => {
    test('should optimize API calls', async ({ page }) => {
      const apiCalls: Array<{
        url: string;
        method: string;
        duration: number;
        status: number;
      }> = [];
      
      page.on('response', async response => {
        const request = response.request();
        const timing = response.timing();
        
        if (request.url().includes('/api/') && timing) {
          apiCalls.push({
            url: request.url(),
            method: request.method(),
            duration: timing.responseEnd - timing.requestStart,
            status: response.status()
          });
        }
      });
      
      await homePage.goto();
      await page.waitForTimeout(3000); // Let API calls complete
      
      // Analyze API performance
      console.log(`Total API calls: ${apiCalls.length}`);
      
      const slowAPIs = apiCalls.filter(call => call.duration > 500);
      if (slowAPIs.length > 0) {
        console.log('Slow API calls (>500ms):');
        slowAPIs.forEach(call => {
          console.log(`- ${call.method} ${call.url}: ${call.duration}ms`);
        });
      }
      
      // Check for duplicate calls
      const urlCounts = apiCalls.reduce((acc, call) => {
        acc[call.url] = (acc[call.url] || 0) + 1;
        return acc;
      }, {} as Record<string, number>);
      
      const duplicates = Object.entries(urlCounts).filter(([_, count]) => count > 1);
      if (duplicates.length > 0) {
        console.log('Duplicate API calls:');
        duplicates.forEach(([url, count]) => {
          console.log(`- ${url}: ${count} times`);
        });
      }
      
      // All API calls should be successful
      const failedCalls = apiCalls.filter(call => call.status >= 400);
      expect(failedCalls).toHaveLength(0);
    });

    test('should handle slow network gracefully', async ({ page }) => {
      // Simulate slow 3G
      await page.context().route('**/*', route => {
        setTimeout(() => route.continue(), 100); // Add 100ms delay
      });
      
      await page.route('**/*', route => route.continue(), {
        times: 1000 // Apply to many requests
      });
      
      const startTime = Date.now();
      await homePage.goto();
      const loadTime = Date.now() - startTime;
      
      console.log(`Page load time on slow network: ${loadTime}ms`);
      
      // Should still load within reasonable time
      expect(loadTime).toBeLessThan(10000); // 10 seconds
      
      // Check that critical content is visible
      await expect(homePage.mainHeading).toBeVisible();
      await expect(homePage.powerWidget).toBeVisible();
    });
  });
});