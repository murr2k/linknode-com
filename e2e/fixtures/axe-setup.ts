import { test as base } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

export const test = base.extend<{
  makeAxeBuilder: () => AxeBuilder;
}>({
  makeAxeBuilder: async ({ page }, use) => {
    const makeAxeBuilder = () => new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .exclude('.grafana-preview iframe') // Exclude cross-origin iframe
      .exclude('[aria-hidden="true"]'); // Exclude hidden elements
    
    await use(makeAxeBuilder);
  },
});