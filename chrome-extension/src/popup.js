import * as pdfjsLib from 'pdfjs-dist';
import { PDFDocument } from 'pdf-lib';

// Worker must be a separate file (MV3 CSP restriction)
pdfjsLib.GlobalWorkerOptions.workerSrc = chrome.runtime.getURL('pdf.worker.min.js');

const QUALITY = {
  low:    { dpi: 72,  jpeg: 0.50 },
  medium: { dpi: 150, jpeg: 0.72 },
  high:   { dpi: 300, jpeg: 0.88 },
};

// ── State ──────────────────────────────────────────────────────────────────────

let currentFile    = null;
let selectedQuality = 'medium';

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

// ── Drop zone ──────────────────────────────────────────────────────────────────

dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file?.type === 'application/pdf') setFile(file);
});
dropZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) setFile(fileInput.files[0]);
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
  if (n < 1024)             return n + ' B';
  if (n < 1024 * 1024)      return (n / 1024).toFixed(1) + ' KB';
  return (n / (1024 * 1024)).toFixed(1) + ' MB';
}

function setProgress(page, total) {
  const pct = Math.round((page / total) * 100);
  progressBar.style.width = pct + '%';
  progressText.textContent = `Page ${page} of ${total}…`;
}

// ── Core compression ───────────────────────────────────────────────────────────

async function compress() {
  if (!currentFile) return;

  compressBtn.disabled  = true;
  progressWrap.hidden   = false;
  resultEl.hidden       = true;
  upsellEl.hidden       = true;
  progressBar.style.width = '0%';
  progressText.textContent = 'Loading PDF…';

  try {
    const cfg     = QUALITY[selectedQuality];
    const scale   = cfg.dpi / 96; // 96 px/in = default screen resolution

    const inputBuf = await currentFile.arrayBuffer();
    const pdfDoc   = await pdfjsLib.getDocument({ data: inputBuf }).promise;
    const numPages = pdfDoc.numPages;
    const outDoc   = await PDFDocument.create();

    const canvas = document.createElement('canvas');
    const ctx    = canvas.getContext('2d');

    for (let i = 1; i <= numPages; i++) {
      setProgress(i, numPages);

      const page     = await pdfDoc.getPage(i);
      const viewport = page.getViewport({ scale });

      canvas.width  = viewport.width;
      canvas.height = viewport.height;

      await page.render({ canvasContext: ctx, viewport }).promise;

      // Convert to JPEG bytes via Blob (avoids toDataURL memory spike)
      const blob      = await canvasToJpegBlob(canvas, cfg.jpeg);
      const jpegBytes = new Uint8Array(await blob.arrayBuffer());

      const img     = await outDoc.embedJpg(jpegBytes);
      const outPage = outDoc.addPage([viewport.width, viewport.height]);
      outPage.drawImage(img, { x: 0, y: 0, width: viewport.width, height: viewport.height });
    }

    const compressed = await outDoc.save();
    showResult(compressed);

  } catch (err) {
    progressText.textContent = '✗ ' + err.message;
    console.error(err);
  } finally {
    compressBtn.disabled = false;
    progressWrap.hidden  = true;
  }
}

function canvasToJpegBlob(canvas, quality) {
  return new Promise((resolve, reject) => {
    canvas.toBlob(b => b ? resolve(b) : reject(new Error('Canvas toBlob failed')), 'image/jpeg', quality);
  });
}

function showResult(compressed) {
  const before = currentFile.size;
  const after  = compressed.byteLength;
  const ratio  = (1 - after / before) * 100;

  document.getElementById('result-before').textContent = fmtBytes(before);
  document.getElementById('result-after').textContent  = fmtBytes(after);

  const ratioEl = document.getElementById('result-ratio');
  ratioEl.textContent  = (ratio >= 0 ? '-' : '+') + Math.abs(ratio).toFixed(1) + '%';
  ratioEl.className    = 'stat-value ratio ' + (ratio >= 0 ? 'good' : 'bad');

  const outName = currentFile.name.replace(/\.pdf$/i, '') + '_kompakt.pdf';
  const url     = URL.createObjectURL(new Blob([compressed], { type: 'application/pdf' }));

  document.getElementById('download-btn').onclick = () => {
    const a = document.createElement('a');
    a.href = url; a.download = outName; a.click();
  };

  resultEl.hidden = false;

  document.getElementById('upsell-ratio').textContent = Math.max(0, ratio).toFixed(0);
  upsellEl.hidden = false;
}
