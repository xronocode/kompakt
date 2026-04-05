const esbuild = require('esbuild');
const fs = require('fs');
const path = require('path');

const watch = process.argv.includes('--watch');
const outdir = 'dist';

fs.mkdirSync(outdir, { recursive: true });
fs.mkdirSync(path.join(outdir, 'icons'), { recursive: true });

// Copy static files
const statics = [
  ['src/popup.html', `${outdir}/popup.html`],
  ['src/style.css',  `${outdir}/style.css`],
  ['manifest.json',  `${outdir}/manifest.json`],
];
for (const [src, dst] of statics) fs.copyFileSync(src, dst);

// Copy pdf.js worker (pre-built, avoid bundling issues)
const workerSrc = require.resolve('pdfjs-dist/build/pdf.worker.min.mjs');
fs.copyFileSync(workerSrc, path.join(outdir, 'pdf.worker.min.js'));

// Copy icons if they exist
const iconSizes = [16, 48, 128];
for (const size of iconSizes) {
  const src = `src/icons/icon${size}.png`;
  if (fs.existsSync(src)) fs.copyFileSync(src, `${outdir}/icons/icon${size}.png`);
}

const ctx = esbuild.buildSync({
  entryPoints: ['src/popup.js'],
  bundle: true,
  outfile: `${outdir}/popup.js`,
  format: 'iife',
  minify: !watch,
  target: 'chrome100',
  define: { 'process.env.NODE_ENV': '"production"' },
  logLevel: 'info',
});

console.log(`\n✓ Built → ${outdir}/`);
