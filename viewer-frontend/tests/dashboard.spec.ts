import { test, expect } from '@playwright/test';

test.describe('Dashboard Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173/');
  });

  test('should display Dashboard title', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  });

  test('API Status card should show healthy status', async ({ page }) => {
    // Wait for API data to load
    await page.waitForSelector('text=API Status');

    // Check the API Status card shows "healthy"
    const apiStatusCard = page.locator('text=API Status').locator('..').locator('..');
    await expect(apiStatusCard).toContainText(/healthy/i);
  });

  test('Database card should show connected status', async ({ page }) => {
    await page.waitForSelector('text=Database');

    const databaseCard = page.locator('text=Database').locator('..').locator('..');
    await expect(databaseCard).toContainText(/Connected/i);
  });

  test('Last Update card should display timestamp', async ({ page }) => {
    await page.waitForSelector('text=Last Update');

    // Should show a time value (HH:MM:SS format)
    const lastUpdateCard = page.locator('text=Last Update').locator('..').locator('..');
    await expect(lastUpdateCard).toBeVisible();
    // Check for time pattern like "6:01:09 AM" or similar
    await expect(lastUpdateCard.locator('div.text-lg')).not.toHaveText('-');
  });

  test('Environment card should show Development badge', async ({ page }) => {
    await page.waitForSelector('text=Environment');

    const envCard = page.locator('text=Environment').locator('..').locator('..');
    await expect(envCard).toContainText('Development');
  });

  test('Active Downloads section should be present', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Active Downloads' })).toBeVisible();
    await expect(page.getByText('Coming soon (#167)')).toBeVisible();
  });

  test('Source Health grid should be visible', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Source Health' })).toBeVisible();

    // Wait for source cards to load (should see at least one source)
    await page.waitForSelector('[class*="grid"] [class*="border"]', { timeout: 10000 });
  });

  test('Source Health grid should display source cards', async ({ page }) => {
    // Wait for data to load
    await page.waitForTimeout(2000);

    // Check for expected source names
    const sourceNames = [
      'schedule', 'boxscore', 'roster', 'shift_chart'
    ];

    // At least one should be visible
    let foundAny = false;
    for (const name of sourceNames) {
      const element = page.getByText(name, { exact: false });
      if (await element.count() > 0) {
        foundAny = true;
        break;
      }
    }

    // If no specific sources found, check for "No sources" message or source type badges
    if (!foundAny) {
      const noSourcesMsg = page.getByText('No sources configured');
      const badges = page.locator('[class*="Badge"]').filter({ hasText: /NHL JSON|HTML Report|DailyFaceoff/i });
      expect(await noSourcesMsg.count() + await badges.count()).toBeGreaterThan(0);
    }
  });

  test('Recent Failures section should be present', async ({ page }) => {
    // Wait for heading to appear
    await expect(page.getByRole('heading', { name: /Recent Failures/i })).toBeVisible();

    // Should show either "No failures" or a table
    const noFailures = page.getByText('No failures - all downloads successful!');
    const failureTable = page.locator('table');

    // One of these should be visible
    await expect(noFailures.or(failureTable)).toBeVisible();
  });
});

test.describe('Navigation', () => {
  test('should navigate to Downloads page', async ({ page }) => {
    await page.goto('http://localhost:5173/');
    await page.click('text=Downloads');
    await expect(page).toHaveURL(/\/downloads/);
    await expect(page.getByRole('heading', { name: 'Downloads' })).toBeVisible();
  });

  test('should navigate to Players page', async ({ page }) => {
    await page.goto('http://localhost:5173/');
    await page.click('text=Players');
    await expect(page).toHaveURL(/\/players/);
    await expect(page.getByRole('heading', { name: 'Players' })).toBeVisible();
  });

  test('should navigate to Games page', async ({ page }) => {
    await page.goto('http://localhost:5173/');
    await page.click('text=Games');
    await expect(page).toHaveURL(/\/games/);
    await expect(page.getByRole('heading', { name: 'Games' })).toBeVisible();
  });

  test('should navigate to Teams page', async ({ page }) => {
    await page.goto('http://localhost:5173/');
    await page.click('text=Teams');
    await expect(page).toHaveURL(/\/teams/);
    await expect(page.getByRole('heading', { name: 'Teams' })).toBeVisible();
  });

  test('should navigate to Validation page', async ({ page }) => {
    await page.goto('http://localhost:5173/');
    await page.click('text=Validation');
    await expect(page).toHaveURL(/\/validation/);
    await expect(page.getByRole('heading', { name: 'Validation' })).toBeVisible();
  });
});
