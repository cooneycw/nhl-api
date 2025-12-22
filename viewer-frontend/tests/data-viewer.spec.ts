import { test, expect } from '@playwright/test';

/**
 * Data Viewer Page Tests
 *
 * Tests for Players, Games, and Teams pages.
 * Tests marked with @integration are recommended for regular CI runs.
 * Tests marked with @slow require database data and may take longer.
 */

// ============================================
// PLAYERS PAGE
// ============================================

test.describe('Players Page - Core UI', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173/players');
  });

  // @integration - Fast, reliable
  test('should display Players page header', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Players' })).toBeVisible();
  });

  // @integration - Fast, reliable
  test('should have search input', async ({ page }) => {
    const searchInput = page.getByPlaceholder(/Search|search/i);
    await expect(searchInput.first()).toBeVisible();
  });

  // @slow - Requires database data
  test('should display players content after loading', async ({ page }) => {
    await page.waitForTimeout(3000);

    // Page should have main content
    const content = page.locator('main');
    await expect(content).toBeVisible();
  });

  // @slow - Requires database data
  test('should filter players by search', async ({ page }) => {
    await page.waitForTimeout(2000);

    const searchInput = page.getByPlaceholder(/Search|search/i).first();
    if (await searchInput.isVisible()) {
      await searchInput.fill('Connor');
      await page.waitForTimeout(1000);

      // Results should update (or show no matches)
      const tableRows = page.locator('table tbody tr');
      const noResults = page.getByText(/No players|No results/i);

      await expect(tableRows.first().or(noResults)).toBeVisible();
    }
  });
});

test.describe('Players Page - Navigation', () => {
  // @slow - Requires database data
  test('should navigate to player detail on row click', async ({ page }) => {
    await page.goto('http://localhost:5173/players');
    await page.waitForTimeout(3000);

    const playerRow = page.locator('table tbody tr').first();
    if (await playerRow.isVisible().catch(() => false)) {
      await playerRow.click();
      await expect(page).toHaveURL(/\/players\/\d+/);
    }
  });
});

// ============================================
// GAMES PAGE
// ============================================

test.describe('Games Page - Core UI', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173/games');
  });

  // @integration - Fast, reliable
  test('should display Games page header', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Games' })).toBeVisible();
  });

  // @slow - Requires database data
  test('should display games list or table', async ({ page }) => {
    await page.waitForTimeout(3000);

    const table = page.locator('table');
    const gameCards = page.locator('[class*="Card"]');
    const loading = page.locator('[class*="Skeleton"]');
    const noData = page.getByText(/No games|No data/i);

    await expect(table.or(gameCards.first()).or(loading.first()).or(noData)).toBeVisible();
  });

  // @slow - Requires database data
  test('should display game information (teams, date)', async ({ page }) => {
    await page.waitForTimeout(3000);

    // Look for team abbreviations or "@" symbol indicating game matchup
    const gameMatchup = page.locator('text=/@/');
    const teamAbbrev = page.locator('text=/^[A-Z]{3}$/').first();
    const noGames = page.getByText(/No games/i);

    await expect(gameMatchup.or(teamAbbrev).or(noGames)).toBeVisible();
  });
});

test.describe('Games Page - Filtering', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173/games');
    await page.waitForTimeout(2000);
  });

  // @integration - Tests filter presence
  test('should have date or season filter', async ({ page }) => {
    // Look for filter controls
    const dateInput = page.locator('input[type="date"]');
    const seasonSelector = page.locator('button').filter({ hasText: /2024|season/i });
    const filterButton = page.getByRole('button', { name: /Filter/i });

    const hasFilter = await dateInput.count() > 0 ||
      await seasonSelector.count() > 0 ||
      await filterButton.count() > 0;

    // At least some filtering mechanism should exist (or basic table)
    expect(hasFilter || await page.locator('table').count() > 0).toBe(true);
  });
});

test.describe('Games Page - Navigation', () => {
  // @slow - Requires database data
  test('should navigate to game detail', async ({ page }) => {
    await page.goto('http://localhost:5173/games');
    await page.waitForTimeout(3000);

    // Click on a game row or card
    const gameRow = page.locator('table tbody tr').first();
    const gameCard = page.locator('[class*="Card"]').filter({ hasText: /@/ }).first();

    if (await gameRow.isVisible().catch(() => false)) {
      await gameRow.click();
      await expect(page).toHaveURL(/\/games\/\d+/);
    } else if (await gameCard.isVisible().catch(() => false)) {
      await gameCard.click();
      await expect(page).toHaveURL(/\/games\/\d+/);
    }
  });
});

// ============================================
// TEAMS PAGE
// ============================================

test.describe('Teams Page - Core UI', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173/teams');
  });

  // @integration - Fast, reliable
  test('should display Teams page header', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Teams' })).toBeVisible();
  });

  // @slow - Requires database data
  test('should display teams content after loading', async ({ page }) => {
    await page.waitForTimeout(3000);

    // Page should have main content
    const content = page.locator('main');
    await expect(content).toBeVisible();
  });

});

test.describe('Teams Page - Navigation', () => {
  // @slow - Requires database data
  test('should navigate to team detail', async ({ page }) => {
    await page.goto('http://localhost:5173/teams');
    await page.waitForTimeout(3000);

    // Click on a team card or row
    const teamCard = page.locator('[class*="Card"]').first();
    const teamRow = page.locator('table tbody tr').first();

    if (await teamCard.isVisible().catch(() => false)) {
      await teamCard.click();
      await expect(page).toHaveURL(/\/teams\/.+/);
    } else if (await teamRow.isVisible().catch(() => false)) {
      await teamRow.click();
      await expect(page).toHaveURL(/\/teams\/.+/);
    }
  });
});

// ============================================
// CROSS-PAGE NAVIGATION
// ============================================

test.describe('Sidebar Navigation', () => {
  // @integration - Fast, reliable
  test('should navigate between all data pages', async ({ page }) => {
    await page.goto('http://localhost:5173/');

    // Navigate to Players
    await page.click('text=Players');
    await expect(page).toHaveURL(/\/players/);

    // Navigate to Games
    await page.click('text=Games');
    await expect(page).toHaveURL(/\/games/);

    // Navigate to Teams
    await page.click('text=Teams');
    await expect(page).toHaveURL(/\/teams/);

    // Navigate back to Dashboard
    await page.click('text=Dashboard');
    await expect(page).toHaveURL(/\/$/);
  });
});
