import { test, expect } from '@playwright/test';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const POPUP_URL = `file://${join(__dirname, '../../dist/popup.html')}`;

// Inject a minimal chrome stub before popup.js runs so chrome.runtime.getURL
// and chrome.i18n.getMessage don't throw in the file:// context.
async function gotoPopup(page) {
  await page.addInitScript(() => {
    window.chrome = {
      runtime: { getURL: (path) => path },
      i18n:    { getMessage: (key) => key },
    };
  });
  await page.goto(POPUP_URL);
}

test.describe('popup — initial state', () => {
  test.beforeEach(async ({ page }) => {
    await gotoPopup(page);
  });

  test('header contains logo and badge', async ({ page }) => {
    await expect(page.locator('.logo span')).toBeVisible();
    await expect(page.locator('.badge')).toBeVisible();
  });

  test('drop zone is visible', async ({ page }) => {
    await expect(page.locator('#drop-zone')).toBeVisible();
  });

  test('compress button is disabled initially', async ({ page }) => {
    await expect(page.locator('#compress-btn')).toBeDisabled();
  });

  test('result section is hidden initially', async ({ page }) => {
    await expect(page.locator('#result')).toBeHidden();
  });

  test('upsell section is hidden initially', async ({ page }) => {
    await expect(page.locator('#upsell')).toBeHidden();
  });

  test('progress section is hidden initially', async ({ page }) => {
    await expect(page.locator('#progress')).toBeHidden();
  });

  test('medium quality button is active by default', async ({ page }) => {
    const mediumBtn = page.locator('.quality-btn[data-quality="medium"]');
    await expect(mediumBtn).toHaveClass(/active/);
  });

  test('low and high quality buttons are not active', async ({ page }) => {
    await expect(page.locator('.quality-btn[data-quality="low"]')).not.toHaveClass(/active/);
    await expect(page.locator('.quality-btn[data-quality="high"]')).not.toHaveClass(/active/);
  });

  test('three quality buttons are rendered', async ({ page }) => {
    await expect(page.locator('.quality-btn')).toHaveCount(3);
  });
});

test.describe('popup — quality selection', () => {
  test.beforeEach(async ({ page }) => {
    await gotoPopup(page);
  });

  test('clicking low sets it active and deactivates medium', async ({ page }) => {
    await page.locator('.quality-btn[data-quality="low"]').click();
    await expect(page.locator('.quality-btn[data-quality="low"]')).toHaveClass(/active/);
    await expect(page.locator('.quality-btn[data-quality="medium"]')).not.toHaveClass(/active/);
  });

  test('clicking high sets it active', async ({ page }) => {
    await page.locator('.quality-btn[data-quality="high"]').click();
    await expect(page.locator('.quality-btn[data-quality="high"]')).toHaveClass(/active/);
    await expect(page.locator('.quality-btn[data-quality="medium"]')).not.toHaveClass(/active/);
  });

  test('only one quality button is active at a time', async ({ page }) => {
    for (const q of ['low', 'medium', 'high']) {
      await page.locator(`.quality-btn[data-quality="${q}"]`).click();
      const activeCount = await page.locator('.quality-btn.active').count();
      expect(activeCount).toBe(1);
    }
  });
});

test.describe('popup — file input', () => {
  test.beforeEach(async ({ page }) => {
    await gotoPopup(page);
  });

  test('file input accepts only pdf', async ({ page }) => {
    const accept = await page.locator('#file-input').getAttribute('accept');
    expect(accept).toContain('.pdf');
    expect(accept).toContain('application/pdf');
  });

  test('file input is hidden', async ({ page }) => {
    await expect(page.locator('#file-input')).toBeHidden();
  });

  test('clicking drop zone triggers file input click', async ({ page }) => {
    // Track whether file input received a click via in-page listener
    await page.evaluate(() => {
      window.__fileInputClicked = false;
      document.getElementById('file-input').addEventListener('click', () => {
        window.__fileInputClicked = true;
      });
    });
    await page.locator('#drop-zone').click();
    await page.waitForTimeout(200);
    const clicked = await page.evaluate(() => window.__fileInputClicked);
    expect(clicked).toBe(true);
  });
});

test.describe('popup — i18n data attributes', () => {
  test.beforeEach(async ({ page }) => {
    await gotoPopup(page);
  });

  const expectedI18nKeys = [
    'badge', 'dropTitle', 'dropHint', 'labelCompression',
    'qualityLow', 'qualityLowDesc', 'qualityMedium', 'qualityMediumDesc',
    'qualityHigh', 'qualityHighDesc', 'btnCompress',
    'statBefore', 'statAfter', 'statSaved', 'btnDownload',
  ];

  for (const key of expectedI18nKeys) {
    test(`element with data-i18n="${key}" exists`, async ({ page }) => {
      await expect(page.locator(`[data-i18n="${key}"]`)).toHaveCount(1);
    });
  }

  test('no element has empty data-i18n attribute', async ({ page }) => {
    const elements = await page.locator('[data-i18n]').all();
    for (const el of elements) {
      const val = await el.getAttribute('data-i18n');
      expect(val?.trim().length).toBeGreaterThan(0);
    }
  });
});

test.describe('popup — drag-over state', () => {
  test.beforeEach(async ({ page }) => {
    await gotoPopup(page);
  });

  test('drop zone gets drag-over class on dragover and loses it on dragleave', async ({ page }) => {
    const dropZone = page.locator('#drop-zone');

    // Use evaluate to dispatch events that require DataTransfer
    await page.evaluate(() => {
      const el = document.getElementById('drop-zone');
      el.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true }));
    });
    await expect(dropZone).toHaveClass(/drag-over/);

    await page.evaluate(() => {
      const el = document.getElementById('drop-zone');
      el.dispatchEvent(new DragEvent('dragleave', { bubbles: true }));
    });
    await expect(dropZone).not.toHaveClass(/drag-over/);
  });
});

test.describe('popup — result and download button', () => {
  test.beforeEach(async ({ page }) => {
    await gotoPopup(page);
  });

  test('download button exists inside result section', async ({ page }) => {
    await expect(page.locator('#download-btn')).toHaveCount(1);
  });

  test('result stats elements exist', async ({ page }) => {
    await expect(page.locator('#result-before')).toHaveCount(1);
    await expect(page.locator('#result-after')).toHaveCount(1);
    await expect(page.locator('#result-ratio')).toHaveCount(1);
  });
});

test.describe('popup — upsell section structure', () => {
  test.beforeEach(async ({ page }) => {
    await gotoPopup(page);
  });

  test('upsell body element exists and is empty by default', async ({ page }) => {
    const body = page.locator('#upsell-body');
    await expect(body).toHaveCount(1);
    const text = await body.textContent();
    expect(text?.trim()).toBe('');
  });

  test('upsell link points to GitHub releases', async ({ page }) => {
    const href = await page.locator('#upsell-link').getAttribute('href');
    expect(href).toContain('github.com');
    expect(href).toContain('releases');
  });

  test('upsell link opens in new tab', async ({ page }) => {
    const target = await page.locator('#upsell-link').getAttribute('target');
    expect(target).toBe('_blank');
  });
});
