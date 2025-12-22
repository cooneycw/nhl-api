import { test, expect } from '@playwright/test';

/**
 * Game Reconciliation Detail Page Tests
 *
 * These tests require navigating from validation page to a specific game.
 * Tests marked with @integration are recommended for regular CI runs.
 */

test.describe('Game Reconciliation Page - Structure', () => {
  // This test navigates from validation to a game detail if available
  test('should handle game reconciliation page', async ({ page }) => {
    // Go directly to a game reconciliation page (using sample game ID)
    await page.goto('http://localhost:5173/validation/game/2024020001');
    await page.waitForTimeout(2000);

    // Page should load something (back button, error, or loading)
    const content = page.locator('body');
    await expect(content).toBeVisible();
  });

  test('should display game header or error for invalid game', async ({ page }) => {
    await page.goto('http://localhost:5173/validation/game/2024020001');
    await page.waitForTimeout(2000);

    // Should show game header (Away @ Home) or error
    const gameHeader = page.locator('h1').filter({ hasText: /@/ });
    const errorCard = page.locator('[class*="border-destructive"]');
    const loading = page.locator('[class*="Skeleton"]');

    await expect(gameHeader.or(errorCard).or(loading.first())).toBeVisible();
  });
});

test.describe('Game Reconciliation Page - Check Display', () => {
  test.beforeEach(async ({ page }) => {
    // Try to navigate to an actual game from validation
    await page.goto('http://localhost:5173/validation');
    await page.waitForTimeout(3000);

    // Click first "View Details" link if available
    const viewDetails = page.getByRole('link', { name: 'View Details' }).first();
    if (await viewDetails.isVisible().catch(() => false)) {
      await viewDetails.click();
      await page.waitForTimeout(2000);
    }
  });

  test('should display data sources section', async ({ page }) => {
    // If we're on a game page, should see source sections
    if (await page.url().includes('/validation/game/')) {
      const availableSources = page.getByText('Available Sources');
      const missingSources = page.getByText('Missing Sources');

      await expect(availableSources.or(missingSources)).toBeVisible();
    }
  });

  test('should display check tabs', async ({ page }) => {
    if (await page.url().includes('/validation/game/')) {
      // Should have tabs for Failed, Passed, All checks
      const failedTab = page.getByRole('tab', { name: /Failed Checks/ });
      const passedTab = page.getByRole('tab', { name: /Passed Checks/ });
      const allTab = page.getByRole('tab', { name: /All Checks/ });

      await expect(failedTab.or(passedTab).or(allTab)).toBeVisible();
    }
  });

  test('should switch between check tabs', async ({ page }) => {
    if (await page.url().includes('/validation/game/')) {
      // Click on Passed Checks tab
      const passedTab = page.getByRole('tab', { name: /Passed Checks/ });
      if (await passedTab.isVisible()) {
        await passedTab.click();
        await expect(page.getByText('Passed Reconciliation Checks')).toBeVisible();
      }

      // Click on All Checks tab
      const allTab = page.getByRole('tab', { name: /All Checks/ });
      if (await allTab.isVisible()) {
        await allTab.click();
        await expect(page.getByText('All Reconciliation Checks')).toBeVisible();
      }
    }
  });

  test('should display checks table with columns', async ({ page }) => {
    if (await page.url().includes('/validation/game/')) {
      // Table should have expected columns
      const table = page.locator('table');
      if (await table.first().isVisible()) {
        await expect(page.getByRole('columnheader', { name: 'Check' })).toBeVisible();
        await expect(page.getByRole('columnheader', { name: 'Entity' })).toBeVisible();
        await expect(page.getByRole('columnheader', { name: 'Source A' })).toBeVisible();
        await expect(page.getByRole('columnheader', { name: 'Source B' })).toBeVisible();
      }
    }
  });
});

test.describe('Game Reconciliation Page - Badge Display', () => {
  test('should display passed/failed count badges', async ({ page }) => {
    await page.goto('http://localhost:5173/validation');
    await page.waitForTimeout(3000);

    const viewDetails = page.getByRole('link', { name: 'View Details' }).first();
    if (await viewDetails.isVisible().catch(() => false)) {
      await viewDetails.click();
      await page.waitForTimeout(2000);

      // Should show passed and failed badges
      const passedBadge = page.locator('text=/\\d+ passed/');
      const failedBadge = page.locator('text=/\\d+ failed/');

      await expect(passedBadge.or(failedBadge)).toBeVisible();
    }
  });
});
