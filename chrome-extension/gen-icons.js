// Generates icons/icon16.png, icon48.png, icon128.png
// Pure Node.js, no deps needed

const zlib = require('zlib');
const fs   = require('fs');
const path = require('path');

fs.mkdirSync(path.join(__dirname, 'src/icons'), { recursive: true });
fs.mkdirSync(path.join(__dirname, 'dist/icons'), { recursive: true });

function uint32BE(n) {
  const b = Buffer.alloc(4);
  b.writeUInt32BE(n >>> 0);
  return b;
}

function crc32(buf) {
  let c = 0xffffffff;
  for (const byte of buf) {
    c ^= byte;
    for (let i = 0; i < 8; i++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
  }
  return (c ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const t = Buffer.from(type, 'ascii');
  const crc = uint32BE(crc32(Buffer.concat([t, data])));
  return Buffer.concat([uint32BE(data.length), t, data, crc]);
}

function makePNG(size, draw) {
  const sig = Buffer.from([137,80,78,71,13,10,26,10]);
  const ihdr = chunk('IHDR', Buffer.concat([
    uint32BE(size), uint32BE(size),
    Buffer.from([8, 2, 0, 0, 0])  // 8bpc RGB
  ]));
  const rows = [];
  for (let y = 0; y < size; y++) {
    rows.push(0); // filter=None
    for (let x = 0; x < size; x++) {
      const [r,g,b] = draw(x, y, size);
      rows.push(r, g, b);
    }
  }
  const idat = chunk('IDAT', zlib.deflateSync(Buffer.from(rows)));
  const iend = chunk('IEND', Buffer.alloc(0));
  return Buffer.concat([sig, ihdr, idat, iend]);
}

// Parse hex color
function hex(h) {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff];
}

const BG   = hex('#0d1117');
const BG2  = hex('#161b22');
const CYAN = hex('#39d0d8');

// Distance from point (px,py) to segment (ax,ay)-(bx,by)
function distToSeg(px, py, ax, ay, bx, by) {
  const dx = bx - ax, dy = by - ay;
  const lenSq = dx*dx + dy*dy;
  if (lenSq === 0) return Math.hypot(px-ax, py-ay);
  const t = Math.max(0, Math.min(1, ((px-ax)*dx + (py-ay)*dy) / lenSq));
  return Math.hypot(px - (ax + t*dx), py - (ay + t*dy));
}

// Rounded square test
function inRoundedRect(px, py, x0, y0, x1, y1, r) {
  if (px < x0 || py < y0 || px > x1 || py > y1) return false;
  const cx = px < x0+r ? x0+r : px > x1-r ? x1-r : px;
  const cy = py < y0+r ? y0+r : py > y1-r ? y1-r : py;
  return Math.hypot(px-cx, py-cy) <= r;
}

// Blend two colors by alpha [0..1]
function blend(a, b, t) {
  return [
    Math.round(a[0]*(1-t) + b[0]*t),
    Math.round(a[1]*(1-t) + b[1]*t),
    Math.round(a[2]*(1-t) + b[2]*t),
  ];
}

function drawIcon(x, y, size) {
  const s  = size;
  const pad = s * 0.07;
  const r   = s * 0.24;
  const x0 = pad, y0 = pad, x1 = s-pad, y1 = s-pad;

  if (!inRoundedRect(x+0.5, y+0.5, x0, y0, x1, y1, r)) return BG;

  // K geometry — defined in normalised [0..1] coords, scaled to size
  const m  = s;
  const sw = s * 0.135;  // stroke half-width

  // Vertical bar: x=0.30, y from 0.18 to 0.82
  const vx = 0.30 * m;
  const vy0 = 0.18 * m, vy1 = 0.82 * m;

  // Upper arm: from (0.38, 0.50) to (0.72, 0.18)
  const mx = 0.38 * m, my = 0.50 * m;
  const ux = 0.72 * m, uy = 0.18 * m;

  // Lower arm: from (0.38, 0.50) to (0.72, 0.82)
  const lx = 0.72 * m, ly = 0.82 * m;

  const px = x + 0.5, py = y + 0.5;

  const d1 = distToSeg(px, py, vx, vy0, vx, vy1);
  const d2 = distToSeg(px, py, mx, my, ux, uy);
  const d3 = distToSeg(px, py, mx, my, lx, ly);

  const d = Math.min(d1, d2, d3);

  // Anti-alias: fade over 1px band around stroke edge
  const alpha = Math.max(0, Math.min(1, (sw - d + 0.5)));
  if (alpha <= 0) return BG2;
  if (alpha >= 1) return CYAN;
  return blend(BG2, CYAN, alpha);
}

for (const size of [16, 48, 128]) {
  const buf = makePNG(size, drawIcon);
  const dst = path.join(__dirname, `src/icons/icon${size}.png`);
  const dst2 = path.join(__dirname, `dist/icons/icon${size}.png`);
  fs.writeFileSync(dst, buf);
  fs.writeFileSync(dst2, buf);
  console.log(`✓ icon${size}.png`);
}
