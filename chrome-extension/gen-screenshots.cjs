/**
 * Generates per-locale screenshots for Chrome Web Store.
 * Outputs: screenshots/locales/{locale}/shot1.html + shot2.html + shot1.png + shot2.png
 *
 * Usage: node gen-screenshots.cjs
 */

const fs   = require('fs');
const path = require('path');
const { chromium } = require('@playwright/test');

const LOCALES_DIR  = path.join(__dirname, 'src/_locales');
const OUT_DIR      = path.join(__dirname, 'screenshots/locales');

fs.mkdirSync(OUT_DIR, { recursive: true });

// ── Load all locale data ───────────────────────────────────────────────────────

const locales = fs.readdirSync(LOCALES_DIR);

function msg(messages, key) {
  return messages[key]?.message || key;
}

// ── HTML template (self-contained, 1280×800) ──────────────────────────────────

const CSS = `
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  width: 1280px; height: 800px; overflow: hidden;
  background: #070b10;
  font-family: 'SF Mono', ui-monospace, 'Cascadia Mono', 'Consolas', monospace;
  display: flex; align-items: center; justify-content: center;
  position: relative;
}
body::before {
  content: '';
  position: absolute;
  width: 500px; height: 500px;
  background: radial-gradient(circle, rgba(57,208,216,0.07) 0%, transparent 70%);
  top: 50%; left: 50%; transform: translate(-50%, -50%);
  pointer-events: none;
}
.tagline {
  position: absolute;
  left: 96px; top: 50%; transform: translateY(-50%);
  display: flex; flex-direction: column; gap: 16px;
  max-width: 320px;
}
.tag-eyebrow { font-size: 11px; letter-spacing: 2px; text-transform: uppercase; color: #39d0d8; opacity: 0.8; }
.tag-headline { font-size: 34px; font-weight: 800; line-height: 1.2; color: #e6edf3; }
.tag-headline span { color: #39d0d8; }
.tag-sub { font-size: 13px; color: #7d8590; line-height: 1.7; }
.stat-showcase { display: flex; flex-direction: column; gap: 10px; margin-top: 4px; }
.stat-row { display: flex; align-items: baseline; gap: 10px; }
.stat-num { font-size: 28px; font-weight: 800; color: #3fb950; }
.stat-label { font-size: 12px; color: #7d8590; }

.browser {
  position: absolute; right: 80px; top: 50%; transform: translateY(-50%);
  background: #161b22; border: 1px solid #30363d; border-radius: 14px;
  box-shadow: 0 32px 80px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,255,255,0.04);
  overflow: hidden; width: 390px;
}
.browser-chrome {
  background: #0d1117; border-bottom: 1px solid #21262d;
  padding: 10px 14px; display: flex; align-items: center; gap: 8px;
}
.dots { display: flex; gap: 6px; }
.dot { width: 10px; height: 10px; border-radius: 50%; }
.dot-r { background: #ff5f57; } .dot-y { background: #ffbd2e; } .dot-g { background: #28c840; }
.url-bar {
  flex: 1; background: #161b22; border: 1px solid #30363d; border-radius: 6px;
  padding: 3px 10px; font-size: 10px; color: #7d8590; text-align: center; margin: 0 8px;
}

.popup {
  --bg: #0d1117; --bg2: #161b22; --bg3: #21262d;
  --border: #30363d; --border2: #3d444d;
  --text: #e6edf3; --muted: #7d8590;
  --cyan: #39d0d8; --cyan-dim: rgba(57,208,216,0.10);
  --green: #3fb950; --yellow: #d29922; --radius: 8px;
  background: var(--bg);
  padding: 14px 14px 16px;
  display: flex; flex-direction: column; gap: 10px;
}
.p-header { display: flex; align-items: center; justify-content: space-between; }
.p-logo { display: flex; align-items: center; gap: 7px; font-size: 13px; font-weight: 700; color: var(--cyan); }
.p-badge { font-size: 10px; background: var(--bg3); border: 1px solid var(--border); color: var(--muted); padding: 1px 7px; border-radius: 20px; }
.p-drop {
  border: 1.5px solid var(--border2); border-radius: var(--radius);
  padding: 20px 16px; text-align: center;
  display: flex; flex-direction: column; align-items: center; gap: 4px;
}
.p-drop.has-file { border-color: var(--cyan); background: var(--cyan-dim); }
.p-drop-icon { font-size: 22px; margin-bottom: 2px; }
.p-drop-label { font-size: 12px; font-weight: 600; color: var(--text); }
.p-drop-label.file { color: var(--cyan); }
.p-drop-hint { font-size: 11px; color: var(--muted); }
.p-section-label { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: -4px; }
.p-quality-row { display: flex; gap: 6px; }
.p-q-btn { flex: 1; background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius); color: var(--muted); padding: 8px 4px; display: flex; flex-direction: column; align-items: center; gap: 3px; }
.p-q-btn.active { border-color: var(--cyan); background: var(--cyan-dim); color: var(--cyan); }
.p-q-key { font-size: 12px; font-weight: 700; }
.p-q-desc { font-size: 10px; color: var(--muted); }
.p-q-btn.active .p-q-desc { color: var(--cyan); opacity: 0.75; }
.p-compress-btn { background: var(--cyan); color: #000; border: none; border-radius: var(--radius); padding: 10px 12px; font-size: 12px; font-weight: 700; width: 100%; }
.p-compress-btn.disabled { opacity: 0.45; cursor: default; }
.p-result { background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
.p-result-stats { display: flex; align-items: center; padding: 12px 14px; gap: 4px; }
.p-stat { display: flex; flex-direction: column; align-items: center; gap: 2px; flex: 1; }
.p-stat-label { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
.p-stat-value { font-size: 14px; font-weight: 700; color: var(--text); }
.p-stat-ratio { font-size: 14px; font-weight: 700; color: var(--green); }
.p-stat-arrow { color: var(--muted); font-size: 14px; padding: 0 4px; margin-top: 14px; }
.p-dl-btn { display: block; width: 100%; background: var(--bg3); border: none; border-top: 1px solid var(--border); color: var(--text); padding: 9px 12px; font-size: 12px; font-weight: 600; text-align: center; }
.p-upsell { border: 1px solid rgba(210,153,34,0.4); border-radius: var(--radius); background: rgba(210,153,34,0.06); padding: 11px 12px; display: flex; flex-direction: column; gap: 7px; }
.p-upsell-row { display: flex; align-items: flex-start; gap: 7px; }
.p-upsell-text { font-size: 11px; color: #7d8590; line-height: 1.6; }
.p-upsell-text strong { color: var(--text); }
.p-upsell-link { font-size: 11px; font-weight: 700; color: var(--cyan); text-decoration: none; }
`;

function browserChrome() {
  return `
  <div class="browser-chrome">
    <div class="dots"><div class="dot dot-r"></div><div class="dot dot-y"></div><div class="dot dot-g"></div></div>
    <div class="url-bar">chrome-extension://pdf-kompakt</div>
  </div>`;
}

function popupHeader(m) {
  return `
    <div class="p-header">
      <div class="p-logo">
        <svg width="15" height="15" viewBox="0 0 16 16" fill="none">
          <rect x="2" y="1" width="10" height="13" rx="1.5" fill="#21262d" stroke="#39d0d8" stroke-width="1.2"/>
          <path d="M9 1.5V5h3.5" stroke="#39d0d8" stroke-width="1" stroke-linecap="round"/>
          <line x1="4.5" y1="7.5" x2="9.5" y2="7.5" stroke="#39d0d8" stroke-width="1" stroke-linecap="round"/>
          <line x1="4.5" y1="9.5" x2="9.5" y2="9.5" stroke="#39d0d8" stroke-width="1" stroke-linecap="round"/>
          <line x1="4.5" y1="11.5" x2="7.5" y2="11.5" stroke="#39d0d8" stroke-width="1" stroke-linecap="round"/>
        </svg>
        pdf-kompakt
      </div>
      <span class="p-badge">${msg(m, 'badge')}</span>
    </div>`;
}

function qualityRow(m) {
  return `
    <div class="p-section-label">${msg(m, 'labelCompression')}</div>
    <div class="p-quality-row">
      <div class="p-q-btn"><span class="p-q-key">${msg(m, 'qualityLow')}</span><span class="p-q-desc">${msg(m, 'qualityLowDesc')}</span></div>
      <div class="p-q-btn active"><span class="p-q-key">${msg(m, 'qualityMedium')}</span><span class="p-q-desc">${msg(m, 'qualityMediumDesc')}</span></div>
      <div class="p-q-btn"><span class="p-q-key">${msg(m, 'qualityHigh')}</span><span class="p-q-desc">${msg(m, 'qualityHighDesc')}</span></div>
    </div>`;
}

// ── Shot 1: initial / drop zone ────────────────────────────────────────────────

function shot1Html(m, locale) {
  const taglines = {
    en:    { eyebrow: 'Free · Private · Offline', headline: 'Compress PDFs<br>in your <span>browser</span>', sub: 'No upload, no account, no limits.\nFiles never leave your device.' },
    de:    { eyebrow: 'Kostenlos · Privat · Offline', headline: 'PDFs direkt im<br><span>Browser</span> komprimieren', sub: 'Kein Upload, kein Konto. Dateien verlassen nie Ihr Gerät.' },
    zh_CN: { eyebrow: '免费 · 私密 · 离线可用', headline: '在<span>浏览器</span>中<br>压缩PDF文件', sub: '无需上传，无需账号。文件始终留在您的设备上。' },
    es:    { eyebrow: 'Gratis · Privado · Sin conexión', headline: 'Comprime PDFs<br>en tu <span>navegador</span>', sub: 'Sin subidas, sin cuentas. Tus archivos nunca salen de tu dispositivo.' },
    pt_BR: { eyebrow: 'Grátis · Privado · Offline', headline: 'Comprima PDFs<br>no seu <span>navegador</span>', sub: 'Sem upload, sem conta. Seus arquivos ficam no seu dispositivo.' },
    fr:    { eyebrow: 'Gratuit · Privé · Hors ligne', headline: 'Compressez vos PDFs<br>dans le <span>navigateur</span>', sub: 'Sans upload, sans compte. Vos fichiers restent sur votre appareil.' },
    ru:    { eyebrow: 'Бесплатно · Приватно · Офлайн', headline: 'Сжимайте PDF<br>прямо в <span>браузере</span>', sub: 'Без загрузки на сервер. Файлы остаются на вашем устройстве.' },
    ja:    { eyebrow: '無料・プライベート・オフライン', headline: '<span>ブラウザ</span>で<br>PDFを圧縮', sub: 'アップロード不要、アカウント不要。ファイルはデバイスに留まります。' },
  };
  const t = taglines[locale] || taglines.en;

  return `<!DOCTYPE html>
<html lang="${locale.replace('_', '-')}">
<head>
<meta charset="UTF-8">
<style>${CSS}</style>
</head>
<body>

<div class="tagline">
  <div class="tag-eyebrow">${t.eyebrow}</div>
  <div class="tag-headline">${t.headline}</div>
  <div class="tag-sub">${t.sub.replace(/\n/g, '<br>')}</div>
</div>

<div class="browser">
  ${browserChrome()}
  <div class="popup">
    ${popupHeader(m)}
    <div class="p-drop">
      <div class="p-drop-icon">📄</div>
      <div class="p-drop-label">${msg(m, 'dropTitle')}</div>
      <div class="p-drop-hint">${msg(m, 'dropHint')}</div>
    </div>
    ${qualityRow(m)}
    <button class="p-compress-btn disabled">${msg(m, 'btnCompress')}</button>
  </div>
</div>

</body>
</html>`;
}

// ── Shot 2: result + upsell ────────────────────────────────────────────────────

function shot2Html(m, locale) {
  const taglines = {
    en:    { eyebrow: 'Result', headline: '11.2 MB<br>→ <span>1.4 MB</span>', sub: 'Typical desktop savings with Ghostscript.\nBrowser mode already saves 5–40%.' },
    de:    { eyebrow: 'Ergebnis', headline: '11,2 MB<br>→ <span>1,4 MB</span>', sub: 'Typische Einsparung mit Ghostscript.\nBrowsermodus spart bereits 5–40 %.' },
    zh_CN: { eyebrow: '压缩结果', headline: '11.2 MB<br>→ <span>1.4 MB</span>', sub: 'Ghostscript典型压缩效果。\n浏览器模式也可节省5–40%。' },
    es:    { eyebrow: 'Resultado', headline: '11,2 MB<br>→ <span>1,4 MB</span>', sub: 'Ahorro típico con Ghostscript.\nEl modo navegador ya ahorra un 5–40 %.' },
    pt_BR: { eyebrow: 'Resultado', headline: '11,2 MB<br>→ <span>1,4 MB</span>', sub: 'Economia típica com Ghostscript.\nModo navegador já economiza 5–40%.' },
    fr:    { eyebrow: 'Résultat', headline: '11,2 Mo<br>→ <span>1,4 Mo</span>', sub: 'Économies typiques avec Ghostscript.\nLe mode navigateur économise déjà 5–40 %.' },
    ru:    { eyebrow: 'Результат', headline: '11,2 МБ<br>→ <span>1,4 МБ</span>', sub: 'Типичное сжатие через Ghostscript.\nБраузерный режим уже даёт 5–40 %.' },
    ja:    { eyebrow: '圧縮結果', headline: '11.2 MB<br>→ <span>1.4 MB</span>', sub: 'Ghostscriptの典型的な圧縮効果。\nブラウザモードでも5〜40%削減できます。' },
  };
  const statNums = { en: ['87%', '9.8 MB'], de: ['87 %', '9,8 MB'], zh_CN: ['87%', '9.8 MB'], es: ['87 %', '9,8 MB'], pt_BR: ['87%', '9,8 MB'], fr: ['87 %', '9,8 Mo'], ru: ['87 %', '9,8 МБ'], ja: ['87%', '9.8 MB'] };
  const statLabels = { en: ['smaller file', 'freed up'], de: ['kleinere Datei', 'gespart'], zh_CN: ['文件更小', '已释放'], es: ['archivo menor', 'liberado'], pt_BR: ['arquivo menor', 'liberado'], fr: ['fichier plus petit', 'libéré'], ru: ['меньше файл', 'освобождено'], ja: ['ファイル縮小', '解放済み'] };
  const upsellBody = msg(m, 'upsellBody').replace('$RATIO$', '22');

  const t = taglines[locale] || taglines.en;
  const [pct, freed] = statNums[locale] || statNums.en;
  const [smaller, freedLabel] = statLabels[locale] || statLabels.en;

  return `<!DOCTYPE html>
<html lang="${locale.replace('_', '-')}">
<head>
<meta charset="UTF-8">
<style>${CSS}
body::before { background: radial-gradient(circle, rgba(63,185,80,0.08) 0%, transparent 70%); }
</style>
</head>
<body>

<div class="tagline">
  <div class="tag-eyebrow">${t.eyebrow}</div>
  <div class="tag-headline">${t.headline}</div>
  <div class="tag-sub">${t.sub.replace(/\n/g, '<br>')}</div>
  <div class="stat-showcase">
    <div class="stat-row"><span class="stat-num">${pct}</span><span class="stat-label">${smaller}</span></div>
    <div class="stat-row"><span class="stat-num">${freed}</span><span class="stat-label">${freedLabel}</span></div>
  </div>
</div>

<div class="browser">
  ${browserChrome()}
  <div class="popup">
    ${popupHeader(m)}
    <div class="p-drop has-file">
      <div class="p-drop-label file">📄 annual_report_2024.pdf</div>
      <div class="p-drop-hint">11.2 MB</div>
    </div>
    ${qualityRow(m)}
    <button class="p-compress-btn">${msg(m, 'btnCompress')}</button>
    <div class="p-result">
      <div class="p-result-stats">
        <div class="p-stat"><span class="p-stat-label">${msg(m, 'statBefore')}</span><span class="p-stat-value">11.2 MB</span></div>
        <div class="p-stat-arrow">→</div>
        <div class="p-stat"><span class="p-stat-label">${msg(m, 'statAfter')}</span><span class="p-stat-value">1.4 MB</span></div>
        <div class="p-stat"><span class="p-stat-label">${msg(m, 'statSaved')}</span><span class="p-stat-ratio">-87.5%</span></div>
      </div>
      <div class="p-dl-btn">⬇ ${msg(m, 'btnDownload')}</div>
    </div>
    <div class="p-upsell">
      <div class="p-upsell-row">
        <span>⚡</span>
        <div class="p-upsell-text">${upsellBody.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')}</div>
      </div>
      <a class="p-upsell-link" href="#">${msg(m, 'upsellLink')}</a>
    </div>
  </div>
</div>

</body>
</html>`;
}

// ── Generate HTML files ────────────────────────────────────────────────────────

const generated = [];

for (const locale of locales) {
  const messagesPath = path.join(LOCALES_DIR, locale, 'messages.json');
  const messages = JSON.parse(fs.readFileSync(messagesPath, 'utf8'));

  const outDir = path.join(OUT_DIR, locale);
  fs.mkdirSync(outDir, { recursive: true });

  const s1Path = path.join(outDir, 'shot1.html');
  const s2Path = path.join(outDir, 'shot2.html');
  fs.writeFileSync(s1Path, shot1Html(messages, locale), 'utf8');
  fs.writeFileSync(s2Path, shot2Html(messages, locale), 'utf8');
  generated.push({ locale, s1Path, s2Path });
  console.log(`  ✓ ${locale}`);
}

// ── Render PNGs via Playwright ─────────────────────────────────────────────────

async function renderPngs() {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1280, height: 800 });

  for (const { locale, s1Path, s2Path } of generated) {
    const outDir = path.join(OUT_DIR, locale);

    await page.goto(`file://${s1Path}`);
    await page.screenshot({ path: path.join(outDir, 'shot1.png'), fullPage: false });

    await page.goto(`file://${s2Path}`);
    await page.screenshot({ path: path.join(outDir, 'shot2.png'), fullPage: false });

    console.log(`  📸 ${locale}/shot1.png + shot2.png`);
  }

  await browser.close();
}

renderPngs().then(() => {
  console.log(`\n✓ Screenshots written to screenshots/locales/`);
}).catch(err => {
  console.error(err);
  process.exit(1);
});
