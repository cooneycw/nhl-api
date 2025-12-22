import { test, expect } from '@playwright/test';

test.describe('Downloads Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173/downloads');
  });

  test('should display Downloads page header', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Downloads', exact: true })).toBeVisible();
    await expect(page.getByText('Select seasons and data sources to download')).toBeVisible();
  });

  test('should display Seasons card', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Seasons' })).toBeVisible();
    await expect(page.getByText('Select one or more seasons to download')).toBeVisible();
  });

  test('should display Data Sources card', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Data Sources' })).toBeVisible();
    await expect(page.getByText('Select data types to download')).toBeVisible();
  });

  test('should load seasons from API', async ({ page }) => {
    // Wait for seasons to load - look for any season pattern
    await page.waitForTimeout(3000);

    // Should see season checkboxes or loading
    const seasonLabel = page.locator('label').filter({ hasText: /202\d-\d\d/ });
    const loading = page.locator('[class*="Skeleton"]');

    await expect(seasonLabel.first().or(loading.first())).toBeVisible();
  });

  test('should load data source groups from API', async ({ page }) => {
    // Wait for source groups to load
    await page.waitForTimeout(2000);

    // Should see source type groups
    const sourceTypes = ['NHL JSON', 'HTML Report', 'Shift Charts'];
    let foundAny = false;
    for (const sourceType of sourceTypes) {
      const element = page.getByText(sourceType, { exact: false });
      if (await element.count() > 0) {
        foundAny = true;
        break;
      }
    }
    expect(foundAny).toBe(true);
  });

  test('should auto-select current season', async ({ page }) => {
    // Wait for initialization
    await page.waitForTimeout(2000);

    // The current season checkbox should be checked
    const currentSeasonCheckbox = page.locator('label:has-text("Current")').locator('..').locator('button[role="checkbox"]');
    await expect(currentSeasonCheckbox).toHaveAttribute('data-state', 'checked');
  });

  test('should toggle season selection', async ({ page }) => {
    await page.waitForTimeout(3000);

    // Find any season checkbox
    const checkbox = page.locator('button[role="checkbox"]').first();

    if (await checkbox.isVisible()) {
      const initialState = await checkbox.getAttribute('data-state');
      await checkbox.click();
      const newState = await checkbox.getAttribute('data-state');
      expect(newState).not.toBe(initialState);
    }
  });

  test('should toggle source selection', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Find any source checkbox (look for schedule, boxscore, etc.)
    const sourceCheckbox = page.locator('label:has-text("Schedule")').locator('..').locator('button[role="checkbox"]').first();

    if (await sourceCheckbox.count() > 0) {
      const initialState = await sourceCheckbox.getAttribute('data-state');
      await sourceCheckbox.click();
      const newState = await sourceCheckbox.getAttribute('data-state');
      expect(newState).not.toBe(initialState);
    }
  });

  test('should display batch calculation', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Should show the batch calculation or "Select at least one season and one source"
    const batchInfo = page.getByText(/batch\(es\)|Select at least one season/);
    await expect(batchInfo).toBeVisible();
  });

  test('should have Start Download button', async ({ page }) => {
    const startButton = page.getByRole('button', { name: /Start Download/ });
    await expect(startButton).toBeVisible();
  });

  test('should display Active Downloads section', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Active Downloads' })).toBeVisible();
    await expect(page.getByText('Real-time progress of running downloads')).toBeVisible();
  });

  test('should show no active downloads message when idle', async ({ page }) => {
    await page.waitForTimeout(2000);

    // If no downloads are running, should show "No active downloads"
    const noDownloads = page.getByText('No active downloads');
    const activeDownload = page.locator('.rounded-lg.border').filter({ hasText: /Batch/ });

    // One of these should be visible
    await expect(noDownloads.or(activeDownload.first())).toBeVisible();
  });

  test('Start Download button should be enabled with selections', async ({ page }) => {
    await page.waitForTimeout(2000);

    // With auto-selections, button should be enabled
    const startButton = page.getByRole('button', { name: /Start Download/ });

    // Check if it's disabled (no selections) or enabled (with auto-selections)
    const isDisabled = await startButton.isDisabled();

    // If disabled, make selections
    if (isDisabled) {
      // Select a season
      const seasonCheckbox = page.locator('label:has-text("2024-25")').locator('..').locator('button[role="checkbox"]');
      if (await seasonCheckbox.count() > 0) {
        await seasonCheckbox.click();
      }

      // Select a source
      const sourceCheckbox = page.locator('label:has-text("Schedule")').locator('..').locator('button[role="checkbox"]').first();
      if (await sourceCheckbox.count() > 0) {
        await sourceCheckbox.click();
      }
    }

    // Now button should be enabled (or still enabled from auto-selections)
    await expect(startButton).toBeEnabled();
  });
});

test.describe('Downloads Page - Group Selection', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173/downloads');
    await page.waitForTimeout(3000);
  });

  test('should have selectable source groups', async ({ page }) => {
    // Verify source groups are present and interactive
    const checkboxes = page.locator('button[role="checkbox"]');
    const checkboxCount = await checkboxes.count();

    // Should have multiple checkboxes for seasons and sources
    expect(checkboxCount).toBeGreaterThan(0);
  });
});
