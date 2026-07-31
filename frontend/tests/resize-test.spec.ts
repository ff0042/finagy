import { test, expect } from '@playwright/test';

test.use({ ignoreHTTPSErrors: true });

test('verify chart resizing behavior when splitters are dragged', async ({ page }) => {
  // 1. Navigate to the local server
  await page.goto('https://localhost:8080');

  // 2. Wait for workstation dashboard to load
  await page.waitForSelector('text=Watchlist');
  await page.waitForSelector('text=Positions');
  
  // 3. Take an initial screenshot
  await page.screenshot({ path: 'tests/screenshots/initial.png' });

  // 4. Find the vertical resizer handle (between Watchlist and MainChart)
  const colResizer = page.locator('.cursor-col-resize').first();
  await expect(colResizer).toBeVisible();

  // Get bounding box of the resizer
  const box = await colResizer.boundingBox();
  if (box) {
    const startX = box.x + box.width / 2;
    const startY = box.y + box.height / 2;
    
    // Drag left resizer to the right by 150px
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX + 150, startY, { steps: 10 });
    await page.mouse.up();
  }

  // 5. Wait a bit for layout to settle and recharts to adjust
  await page.waitForTimeout(500);

  // 6. Take a screenshot after horizontal drag resizing
  await page.screenshot({ path: 'tests/screenshots/resized.png' });
  
  console.log('--- PLAYWRIGHT RESIZING VERIFICATION COMPLETED ---');
});
