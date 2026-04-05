import * as pdfjsLib from 'pdfjs-dist';
import { PDFDocument } from 'pdf-lib';

pdfjsLib.GlobalWorkerOptions.workerSrc = chrome.runtime.getURL('pdf.worker.min.js');

const QUALITY = {
  low:    { dpi: 72,  jpeg: 0.50 },
  medium: { dpi: 150, jpeg: 0.72 },
  high:   { dpi: 300, jpeg: 0.88 },
};

const MAX_FILE_BYTES = 52_428_800; // 50 MB

// ── i18n ───────────────────────────────────────────────────────────────────────

function t(key, ...subs) {
  return chrome?.i18n?.getMessage(key, subs) || key;
}

function applyI18n() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const msg = t(el.dataset.i18n);
    if (msg && msg !== el.dataset.i18n) el.textContent = msg;
  });
}

// ── State ──────────────────────────────────────────────────────────────────────

let currentFile     = null;
let selectedQuality = 'medium';
let isCompressing   = false;
let lastBlobUrl     = null;

// ── DOM refs ───────────────────────────────────────────────────────────────────

const dropZone     = document.getElementById('drop-zone');
const fileInput    = document.getElementById('file-input');
const qualityBtns  = document.querySelectorAll('.quality-btn');
const compressBtn  = document.getElementById('compress-btn');
const progressWrap = document.getElementById('progress');
const progressBar  = document.getElementById('progress-bar');
const progressText = document.getElementById('progress-text');
const resultEl     = document.getElementById('result');
const upsellEl     = document.getElementById('upsell');

// ── Init ───────────────────────────────────────────────────────────────────────

applyI18n();

// ── Drop zone ──────────────────────────────────────────────────────────────────

dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  if (isCompressing) return;   // ignore drops during compression
  const file = e.dataTransfer.files[0];
  if (file?.type === 'application/pdf') setFile(file);
});
dropZone.addEventListener('click', () => { if (!isCompressing) fileInput.click(); });
fileInput.addEventListener('change', () => {
  if (fileInput.files[0] && !isCompressing) setFile(fileInput.files[0]);
});

// ── Quality ────────────────────────────────────────────────────────────────────

qualityBtns.forEach(btn => btn.addEventListener('click', () => {
  qualityBtns.forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  selectedQuality = btn.dataset.quality;
}));

// ── Compress ───────────────────────────────────────────────────────────────────

compressBtn.addEventListener('click', compress);

// ── Helpers ────────────────────────────────────────────────────────────────────

function setFile(file) {
  if (file.size > MAX_FILE_BYTES) {
    alert(t('errFileTooLarge'));
    return;
  }
  currentFile = file;
  const name = file.name.length > 34 ? file.name.slice(0, 31) + '…' : file.name;
  dropZone.querySelector('.drop-label').textContent = name;
  dropZone.querySelector('.drop-hint').textContent  = fmtBytes(file.size);
  dropZone.classList.add('has-file');
  compressBtn.disabled = false;
  resultEl.hidden  = true;
  upsellEl.hidden  = true;
}

function fmtBytes(n) {
  if (n < 1024)    return n + ' B';
  if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
  return (n / 1048576).toFixed(1) + ' MB';
}

function setProgress(page, total) {
  progressBar.style.width  = Math.round((page / total) * 100) + '%';
  progressText.textContent = t('progressPage', String(page), String(total));
}

function setLocked(locked) {
  isCompressing        = locked;
  compressBtn.disabled = locked;
  dropZone.style.pointerEvents = locked ? 'none' : '';
  fileInput.disabled   = locked;
}

// ── Core compression ───────────────────────────────────────────────────────────

async function compress() {
  if (!currentFile || isCompressing) return;

  setLocked(true);
  progressWrap.hidden     = false;
  resultEl.hidden         = true;
  upsellEl.hidden         = true;
  progressBar.style.width = '0%';
  progressText.textContent = t('preparing');

  try {
    const cfg    = QUALITY[selectedQuality];
    const scale  = cfg.dpi / 96;

    const inputBuf = await currentFile.arrayBuffer();
    const pdfDoc   = await pdfjsLib.getDocument({ data: inputBuf }).promise;
    const numPages = pdfDoc.numPages;

    if (numPages === 0) throw new Error(t('errNoPages'));

    const outDoc = await PDFDocument.create();
    const canvas = document.createElement('canvas');
    const ctx    = canvas.getContext('2d');

    for (let i = 1; i <= numPages; i++) {
      setProgress(i, numPages);

      const page     = await pdfDoc.getPage(i);
      const viewport = page.getViewport({ scale });

      canvas.width  = viewport.width;
      canvas.height = viewport.height;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      await page.render({ canvasContext: ctx, viewport }).promise;

      const blob      = await canvasToJpegBlob(canvas, cfg.jpeg);
      const jpegBytes = new Uint8Array(await blob.arrayBuffer());

      const img     = await outDoc.embedJpg(jpegBytes);
      const outPage = outDoc.addPage([viewport.width, viewport.height]);
      outPage.drawImage(img, { x: 0, y: 0, width: viewport.width, height: viewport.height });
    }

    showResult(await outDoc.save());

  } catch (err) {
    const msg = err?.name === 'PasswordException'
      ? t('errPasswordProtected')
      : '✗ ' + err.message;
    progressText.textContent = msg;
    console.error(err);
  } finally {
    setLocked(false);
    progressWrap.hidden = true;
  }
}

function canvasToJpegBlob(canvas, quality) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Canvas toBlob timed out')), 30_000);
    canvas.toBlob(b => {
      clearTimeout(timer);
      b ? resolve(b) : reject(new Error('Canvas toBlob failed'));
    }, 'image/jpeg', quality);
  });
}

function showResult(compressed) {
  const before = currentFile.size;
  const after  = compressed.byteLength;
  const ratio  = (1 - after / before) * 100;

  document.getElementById('result-before').textContent = fmtBytes(before);
  document.getElementById('result-after').textContent  = fmtBytes(after);

  const ratioEl     = document.getElementById('result-ratio');
  ratioEl.textContent = (ratio >= 0 ? '-' : '+') + Math.abs(ratio).toFixed(1) + '%';
  ratioEl.className   = 'stat-value ratio ' + (ratio >= 0 ? 'good' : 'bad');

  // Revoke previous blob URL to avoid memory leak
  if (lastBlobUrl) URL.revokeObjectURL(lastBlobUrl);
  lastBlobUrl = URL.createObjectURL(new Blob([compressed], { type: 'application/pdf' }));
  const outName = currentFile.name.replace(/\.pdf$/i, '') + '_kompakt.pdf';

  document.getElementById('download-btn').onclick = () => {
    const a = document.createElement('a');
    a.href = lastBlobUrl; a.download = outName; a.click();
  };

  resultEl.hidden = false;

  // Upsell — use innerHTML so the i18n string can bold the ratio
  const ratioStr = `<strong>${Math.max(0, ratio).toFixed(0)}</strong>`;
  document.getElementById('upsell-body').innerHTML =
    t('upsellBody', ratioStr);
  document.getElementById('upsell-link').textContent = t('upsellLink');
  upsellEl.hidden = false;
}
