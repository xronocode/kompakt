const path = require('path');
const { chromium } = require('@playwright/test');

const SHOTS = [
  { html: 'promo-small.html', out: 'promo-small.png', w: 440,  h: 280 },
  { html: 'promo-large.html', out: 'promo-large.png', w: 1400, h: 560 },
];

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  for (const { html, out, w, h } of SHOTS) {
    await page.setViewportSize({ width: w, height: h });
    await page.goto(`file://${path.join(__dirname, 'screenshots', html)}`);
    await page.waitForTimeout(200); // let fonts settle
    await page.screenshot({
      path: path.join(__dirname, 'screenshots', out),
      fullPage: false,
      type: 'png',
    });
    console.log(`  ✓ ${out}  (${w}×${h})`);
  }

  await browser.close();
  console.log('\n✓ Promo images saved to screenshots/');
})();
