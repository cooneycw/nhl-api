import { test, expect } from '@playwright/test';

/**
 * Season Selector Tests
 *
 * Tests for the global season dropdown in the header.
 * Tests marked with @integration are fast and reliable.
 * Tests marked with @slow require API data.
 */

// ============================================
// SEASON SELECTOR - CORE UI
// ============================================

test.describe('Season Selector - Core UI', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(2000);
  });

  // @integration
  test('should display season selector in header', async ({ page }) => {
    const seasonButton = page.locator('button').filter({ hasText: /\d{4}-\d{4}/ });
    await expect(seasonButton.first()).toBeVisible();
  });

  // @integration
  test('should show calendar icon', async ({ page }) => {
    // The button contains an SVG calendar icon
    const seasonButton = page.locator('button').filter({ hasText: /\d{4}-\d{4}/ }).first();
    const svg = seasonButton.locator('svg').first();
    await expect(svg).toBeVisible();
  });

  // @slow
  test('should display current season by default', async ({ page }) => {
    const seasonButton = page.locator('button').filter({ hasText: /\d{4}-\d{4}/ }).first();
    // Should show a season label like "2024-2025" or "2025-2026"
    await expect(seasonButton).toContainText(/202\d-202\d/);
  });
});

// ============================================
// SEASON SELECTOR - DROPDOWN INTERACTION
// ============================================

test.describe('Season Selector - Dropdown', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(2000);
  });

  // @integration
  test('should open dropdown on click', async ({ page }) => {
    const seasonButton = page.locator('button').filter({ hasText: /\d{4}-\d{4}/ }).first();
    await seasonButton.click();

    // Dropdown menu should appear with role="menu"
    const menu = page.locator('[role="menu"]');
    await expect(menu).toBeVisible();
  });

  // @slow
  test('should list available seasons', async ({ page }) => {
    const seasonButton = page.locator('button').filter({ hasText: /\d{4}-\d{4}/ }).first();
    await seasonButton.click();

    // Should have menu items for each season
    const menuItems = page.locator('[role="menuitem"]');
    await expect(menuItems.first()).toBeVisible();

    // Should have at least 2 seasons
    const count = await menuItems.count();
    expect(count).toBeGreaterThanOrEqual(2);
  });

  // @slow
  test('should mark current season with indicator', async ({ page }) => {
    const seasonButton = page.locator('button').filter({ hasText: /\d{4}-\d{4}/ }).first();
    await seasonButton.click();

    // One item should have "(current)" text
    const currentItem = page.getByText('(current)');
    await expect(currentItem).toBeVisible();
  });

  // @slow
  test('should select different season on click', async ({ page }) => {
    const seasonButton = page.locator('button').filter({ hasText: /\d{4}-\d{4}/ }).first();
    const initialText = await seasonButton.textContent();

    await seasonButton.click();

    // Click a different season (not the one with "(current)")
    const menuItems = page.locator('[role="menuitem"]');
    const count = await menuItems.count();

    // Find and click a season that's different from current
    for (let i = 0; i < count; i++) {
      const item = menuItems.nth(i);
      const itemText = await item.textContent();
      if (!itemText?.includes('(current)')) {
        await item.click();
        break;
      }
    }

    // Button text should change
    await page.waitForTimeout(500);
    const newText = await seasonButton.textContent();
    expect(newText).not.toBe(initialText);
  });
});

// ============================================
// SEASON SELECTOR - PERSISTENCE
// ============================================

test.describe('Season Selector - Persistence', () => {
  // @slow
  test('should persist selection across page navigation', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(2000);

    // Get current selection
    const seasonButton = page.locator('button').filter({ hasText: /\d{4}-\d{4}/ }).first();
    await seasonButton.click();

    // Select a non-current season
    const menuItems = page.locator('[role="menuitem"]');
    const count = await menuItems.count();
    let selectedSeason = '';

    for (let i = 0; i < count; i++) {
      const item = menuItems.nth(i);
      const itemText = await item.textContent();
      if (!itemText?.includes('(current)')) {
        selectedSeason = itemText?.replace('(current)', '').trim() || '';
        await item.click();
        break;
      }
    }

    // Navigate to Teams page
    await page.click('text=Teams');
    await expect(page).toHaveURL(/\/teams/);
    await page.waitForTimeout(1000);

    // Season should still be selected
    const teamsSeasonButton = page.locator('button').filter({ hasText: /\d{4}-\d{4}/ }).first();
    await expect(teamsSeasonButton).toContainText(selectedSeason.substring(0, 9));
  });

  // @slow
  test('should persist selection after page reload', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(2000);

    // Select a specific season
    const seasonButton = page.locator('button').filter({ hasText: /\d{4}-\d{4}/ }).first();
    await seasonButton.click();

    // Click 2023-2024 specifically
    const season2023 = page.locator('[role="menuitem"]').filter({ hasText: '2023-2024' });
    if (await season2023.isVisible().catch(() => false)) {
      await season2023.click();
      await page.waitForTimeout(500);

      // Reload page
      await page.reload();
      await page.waitForTimeout(2000);

      // Should still show 2023-2024
      const reloadedButton = page.locator('button').filter({ hasText: /\d{4}-\d{4}/ }).first();
      await expect(reloadedButton).toContainText('2023-2024');
    }
  });
});

// ============================================
// SEASON SELECTOR - TEAMS INTEGRATION
// ============================================

test.describe('Season Selector - Teams Page Integration', () => {
  // @slow
  test('should load Teams page with selected season', async ({ page }) => {
    await page.goto('/teams');
    await page.waitForTimeout(3000);

    // Page should display teams
    const teamsHeading = page.getByRole('heading', { name: 'Teams' });
    await expect(teamsHeading).toBeVisible();

    // Season selector should be visible
    const seasonButton = page.locator('button').filter({ hasText: /\d{4}-\d{4}/ }).first();
    await expect(seasonButton).toBeVisible();
  });

  // @slow
  test('Teams page displays division groups', async ({ page }) => {
    await page.goto('/teams');
    await page.waitForTimeout(3000);

    // Should show division headings
    const atlanticDiv = page.getByText('Atlantic');
    const metropolitanDiv = page.getByText('Metropolitan');
    const centralDiv = page.getByText('Central');
    const pacificDiv = page.getByText('Pacific');

    // At least one division should be visible
    const anyDiv = atlanticDiv.or(metropolitanDiv).or(centralDiv).or(pacificDiv);
    await expect(anyDiv.first()).toBeVisible();
  });
});
