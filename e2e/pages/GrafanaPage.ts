import { Page, Locator, Frame } from '@playwright/test';
import { BasePage } from './BasePage';

export class GrafanaPage extends BasePage {
  readonly grafanaFrame: Locator;
  
  constructor(page: Page) {
    super(page);
    this.url = '/';
    this.grafanaFrame = page.locator('.grafana-preview iframe');
  }

  /**
   * Get Grafana iframe frame context
   */
  async getGrafanaFrame(): Promise<Frame | null> {
    await this.grafanaFrame.waitFor({ state: 'visible' });
    const frameElement = await this.grafanaFrame.elementHandle();
    return frameElement ? await frameElement.contentFrame() : null;
  }

  /**
   * Wait for Grafana dashboard to fully load
   */
  async waitForDashboardLoad() {
    const frame = await this.getGrafanaFrame();
    if (!frame) throw new Error('Grafana frame not found');

    // Wait for Grafana-specific elements
    await frame.waitForSelector('.dashboard-container', { timeout: 30000 });
    await frame.waitForLoadState('networkidle');
  }

  /**
   * Get dashboard panels
   */
  async getDashboardPanels(): Promise<Array<{ title: string; id: string }>> {
    const frame = await this.getGrafanaFrame();
    if (!frame) return [];

    return await frame.evaluate(() => {
      const panels: Array<{ title: string; id: string }> = [];
      const panelElements = document.querySelectorAll('.panel-container');
      
      panelElements.forEach(panel => {
        const titleElement = panel.querySelector('.panel-title');
        const title = titleElement?.textContent?.trim() || '';
        const id = panel.getAttribute('data-panel-id') || '';
        
        if (title) {
          panels.push({ title, id });
        }
      });
      
      return panels;
    });
  }

  /**
   * Check if dashboard has data
   */
  async dashboardHasData(): Promise<boolean> {
    const frame = await this.getGrafanaFrame();
    if (!frame) return false;

    return await frame.evaluate(() => {
      const noDataElements = document.querySelectorAll('.panel-info-content');
      const hasNoData = Array.from(noDataElements).some(
        el => el.textContent?.toLowerCase().includes('no data')
      );
      return !hasNoData;
    });
  }

  /**
   * Get time range selector value
   */
  async getTimeRange(): Promise<string> {
    const frame = await this.getGrafanaFrame();
    if (!frame) return '';

    return await frame.evaluate(() => {
      const timePickerButton = document.querySelector('.time-picker-button-label');
      return timePickerButton?.textContent?.trim() || '';
    });
  }

  /**
   * Change time range
   */
  async setTimeRange(range: 'Last 5 minutes' | 'Last 15 minutes' | 'Last 30 minutes' | 'Last 1 hour' | 'Last 6 hours' | 'Last 24 hours') {
    const frame = await this.getGrafanaFrame();
    if (!frame) throw new Error('Grafana frame not found');

    // Click time picker
    await frame.click('.time-picker-button-label');
    
    // Wait for dropdown
    await frame.waitForSelector('.time-picker-popover', { state: 'visible' });
    
    // Click the desired range
    await frame.click(`text="${range}"`);
    
    // Wait for update
    await frame.waitForLoadState('networkidle');
  }

  /**
   * Refresh dashboard
   */
  async refreshDashboard() {
    const frame = await this.getGrafanaFrame();
    if (!frame) throw new Error('Grafana frame not found');

    // Click refresh button
    const refreshButton = frame.locator('[aria-label="Refresh dashboard"]');
    if (await refreshButton.count() > 0) {
      await refreshButton.click();
      await frame.waitForLoadState('networkidle');
    }
  }

  /**
   * Get panel data by title
   */
  async getPanelData(panelTitle: string): Promise<any> {
    const frame = await this.getGrafanaFrame();
    if (!frame) return null;

    return await frame.evaluate((title) => {
      // Find panel by title
      const panels = document.querySelectorAll('.panel-container');
      let targetPanel: Element | null = null;
      
      panels.forEach(panel => {
        const titleElement = panel.querySelector('.panel-title');
        if (titleElement?.textContent?.trim() === title) {
          targetPanel = panel;
        }
      });
      
      if (!targetPanel) return null;
      
      // Extract data from the panel
      const data: any = {
        title: title,
        hasData: !targetPanel.querySelector('.panel-info-content')?.textContent?.includes('No data'),
        values: [],
      };
      
      // Try to extract numeric values
      const valueElements = targetPanel.querySelectorAll('.graph-legend-value');
      valueElements.forEach(el => {
        const text = el.textContent?.trim();
        if (text) {
          data.values.push(text);
        }
      });
      
      // Check for single stat panels
      const singleStat = targetPanel.querySelector('.singlestat-panel-value');
      if (singleStat) {
        data.mainValue = singleStat.textContent?.trim();
      }
      
      return data;
    }, panelTitle);
  }

  /**
   * Take screenshot of specific panel
   */
  async takePanelScreenshot(panelTitle: string, filename: string) {
    const frame = await this.getGrafanaFrame();
    if (!frame) throw new Error('Grafana frame not found');

    // Find panel element
    const panel = await frame.evaluate((title) => {
      const panels = document.querySelectorAll('.panel-container');
      let targetPanel: Element | null = null;
      
      panels.forEach(panel => {
        const titleElement = panel.querySelector('.panel-title');
        if (titleElement?.textContent?.trim() === title) {
          targetPanel = panel;
        }
      });
      
      if (targetPanel) {
        const rect = targetPanel.getBoundingClientRect();
        return {
          x: rect.x,
          y: rect.y,
          width: rect.width,
          height: rect.height,
        };
      }
      
      return null;
    }, panelTitle);

    if (panel) {
      await frame.screenshot({
        path: `test-results/screenshots/${filename}.png`,
        clip: panel,
      });
    }
  }

  /**
   * Check if dashboard is responsive
   */
  async checkResponsiveLayout(viewport: { width: number; height: number }) {
    await this.page.setViewportSize(viewport);
    await this.page.waitForTimeout(1000); // Allow time for responsive adjustments

    const frame = await this.getGrafanaFrame();
    if (!frame) return false;

    return await frame.evaluate(() => {
      const panels = document.querySelectorAll('.panel-container');
      let isResponsive = true;
      
      panels.forEach(panel => {
        const rect = panel.getBoundingClientRect();
        // Check if panels are visible and not overlapping viewport
        if (rect.width <= 0 || rect.height <= 0 || rect.right > window.innerWidth) {
          isResponsive = false;
        }
      });
      
      return isResponsive;
    });
  }

  /**
   * Export dashboard data
   */
  async exportDashboardData(): Promise<any> {
    const frame = await this.getGrafanaFrame();
    if (!frame) return null;

    // Click dashboard settings if available
    const settingsButton = frame.locator('[aria-label="Dashboard settings"]');
    if (await settingsButton.count() > 0) {
      await settingsButton.click();
      
      // Look for export option
      const exportButton = frame.locator('text="Export"');
      if (await exportButton.count() > 0) {
        await exportButton.click();
        
        // Get JSON export
        const jsonExport = await frame.locator('.json-formatter-row').textContent();
        return jsonExport ? JSON.parse(jsonExport) : null;
      }
    }
    
    return null;
  }
}