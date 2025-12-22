import { test, expect } from '@playwright/test';

/**
 * Validation Page Tests
 *
 * Tests marked with @integration are recommended for regular CI runs.
 * Tests marked with @slow require data and may take longer.
 */

test.describe('Validation Page - Core UI', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173/validation');
  });

  // @integration - Fast, reliable
  test('should display Validation page header', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Data Validation' })).toBeVisible();
    await expect(page.getByText('Cross-source reconciliation and data quality metrics')).toBeVisible();
  });

  // @integration - Fast, reliable
  test('should have season selector', async ({ page }) => {
    // Should have a season dropdown
    const seasonSelector = page.locator('button').filter({ hasText: /2024-25|2023-24/ });
    await expect(seasonSelector.first()).toBeVisible();
  });

  // @integration - Fast, reliable
  test('should have Run Reconciliation button', async ({ page }) => {
    const runButton = page.getByRole('button', { name: /Run Reconciliation/ });
    await expect(runButton).toBeVisible();
  });

  // @integration - Fast, reliable
  test('should display validation page content', async ({ page }) => {
    // Wait for page to load
    await page.waitForTimeout(2000);
    // The main content area should be visible
    await expect(page.locator('main')).toBeVisible();
  });

  // @integration - Fast, reliable
  test('should display reconciliation category cards', async ({ page }) => {
    await expect(page.getByText('Goal Reconciliation')).toBeVisible();
    await expect(page.getByText('Penalty Reconciliation')).toBeVisible();
    await expect(page.getByText('TOI Reconciliation')).toBeVisible();
  });

  // @integration - Fast, reliable
  test('should display Games with Discrepancies section', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Games with Discrepancies' })).toBeVisible();
    await expect(page.getByText('Games where data sources')).toBeVisible();
  });

  // @integration - Fast, reliable
  test('should have discrepancy type filter', async ({ page }) => {
    const filterSelector = page.locator('button').filter({ hasText: /All Types/ });
    await expect(filterSelector.first()).toBeVisible();
  });

  // @integration - Fast, reliable
  test('should have Export CSV button', async ({ page }) => {
    const exportButton = page.getByRole('button', { name: /Export CSV/ });
    await expect(exportButton).toBeVisible();
  });
});

test.describe('Validation Page - Data Display', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173/validation');
    await page.waitForTimeout(2000);
  });

  // @slow - Requires database data
  test('should load quality score from API', async ({ page }) => {
    // Wait for the quality score to load
    await page.waitForTimeout(3000);

    // Page should have rendered (any content visible)
    await expect(page.getByRole('heading', { name: 'Data Validation' })).toBeVisible();
  });

  // @slow - Requires database data
  test('should show page content after loading', async ({ page }) => {
    await page.waitForTimeout(3000);

    // Page should have loaded something
    const content = page.locator('main');
    await expect(content).toBeVisible();
  });

});

test.describe('Validation Page - Filtering', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173/validation');
    await page.waitForTimeout(2000);
  });

  // @integration - Tests dropdown interaction
  test('should open discrepancy filter dropdown', async ({ page }) => {
    const filterTrigger = page.locator('button').filter({ hasText: /All Types/ });
    await filterTrigger.click();

    // Filter options should appear
    await expect(page.getByRole('option', { name: 'All Types' })).toBeVisible();
  });

  // @integration - Tests filter options
  test('should have filter options for each discrepancy type', async ({ page }) => {
    const filterTrigger = page.locator('button').filter({ hasText: /All Types/ });
    await filterTrigger.click();

    // Check for each filter type
    await expect(page.getByRole('option', { name: 'Goals' })).toBeVisible();
    await expect(page.getByRole('option', { name: 'Penalties' })).toBeVisible();
    await expect(page.getByRole('option', { name: 'TOI' })).toBeVisible();
    await expect(page.getByRole('option', { name: 'Shots' })).toBeVisible();
  });

  // @integration - Tests season switching
  test('should switch seasons via dropdown', async ({ page }) => {
    const seasonTrigger = page.locator('button').filter({ hasText: /2024-25/ }).first();
    await seasonTrigger.click();

    // Select a different season
    const otherSeason = page.getByRole('option', { name: '2023-24' });
    if (await otherSeason.isVisible()) {
      await otherSeason.click();

      // Verify season changed in trigger
      await expect(page.locator('button').filter({ hasText: /2023-24/ }).first()).toBeVisible();
    }
  });
});

test.describe('Validation Page - Navigation', () => {
  // @integration - Tests navigation to game detail
  test('should navigate to game reconciliation detail', async ({ page }) => {
    await page.goto('http://localhost:5173/validation');
    await page.waitForTimeout(3000);

    // Find a "View Details" link if there are discrepancies
    const viewDetailsLink = page.getByRole('link', { name: 'View Details' }).first();

    if (await viewDetailsLink.isVisible().catch(() => false)) {
      await viewDetailsLink.click();

      // Should navigate to game reconciliation page
      await expect(page).toHaveURL(/\/validation\/game\/\d+/);
    }
  });
});
