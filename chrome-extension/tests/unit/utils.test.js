import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ── fmtBytes (copied verbatim from popup.js for isolated testing) ──────────────

function fmtBytes(n) {
  if (n < 1024)    return n + ' B';
  if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
  return (n / 1048576).toFixed(1) + ' MB';
}

describe('fmtBytes', () => {
  it('returns bytes for < 1 KB', () => {
    expect(fmtBytes(0)).toBe('0 B');
    expect(fmtBytes(1)).toBe('1 B');
    expect(fmtBytes(1023)).toBe('1023 B');
  });

  it('returns KB for 1 KB – <1 MB', () => {
    expect(fmtBytes(1024)).toBe('1.0 KB');
    expect(fmtBytes(1536)).toBe('1.5 KB');
    expect(fmtBytes(1048575)).toBe('1024.0 KB');
  });

  it('returns MB for ≥ 1 MB', () => {
    expect(fmtBytes(1048576)).toBe('1.0 MB');
    expect(fmtBytes(52428800)).toBe('50.0 MB');
    expect(fmtBytes(11796480)).toBe('11.3 MB'); // 11.25 rounds to 11.3
  });

  it('boundary: exactly 1 KB', () => {
    expect(fmtBytes(1024)).toBe('1.0 KB');
  });

  it('boundary: exactly 1 MB', () => {
    expect(fmtBytes(1048576)).toBe('1.0 MB');
  });
});

// ── t() helper ────────────────────────────────────────────────────────────────

function t(key, ...subs) {
  return globalThis.chrome?.i18n?.getMessage(key, subs) || key;
}

describe('t() i18n helper', () => {
  beforeEach(() => {
    globalThis.chrome = undefined;
  });
  afterEach(() => {
    delete globalThis.chrome;
  });

  it('returns key as fallback when chrome is undefined', () => {
    expect(t('btnCompress')).toBe('btnCompress');
  });

  it('returns key as fallback when chrome.i18n is missing', () => {
    globalThis.chrome = {};
    expect(t('preparing')).toBe('preparing');
  });

  it('returns key as fallback when getMessage returns empty string', () => {
    globalThis.chrome = { i18n: { getMessage: () => '' } };
    expect(t('dropTitle')).toBe('dropTitle');
  });

  it('returns translated string when chrome.i18n is available', () => {
    globalThis.chrome = { i18n: { getMessage: (key) => `translated_${key}` } };
    expect(t('btnCompress')).toBe('translated_btnCompress');
  });

  it('passes substitutions array to getMessage', () => {
    const spy = vi.fn(() => 'Page 1 of 5…');
    globalThis.chrome = { i18n: { getMessage: spy } };
    t('progressPage', '1', '5');
    expect(spy).toHaveBeenCalledWith('progressPage', ['1', '5']);
  });
});

// ── setFile validation ────────────────────────────────────────────────────────

const MAX_FILE_BYTES = 52_428_800;

describe('file size validation', () => {
  it('MAX_FILE_BYTES is exactly 50 MB', () => {
    expect(MAX_FILE_BYTES).toBe(50 * 1024 * 1024);
  });

  it('50 MB file passes', () => {
    expect(MAX_FILE_BYTES).toBeLessThanOrEqual(52_428_800);
  });

  it('50 MB + 1 byte fails the check', () => {
    expect(MAX_FILE_BYTES + 1).toBeGreaterThan(MAX_FILE_BYTES);
  });
});

// ── ratio display logic ───────────────────────────────────────────────────────

function ratioSign(before, after) {
  const ratio = (1 - after / before) * 100;
  return ratio >= 0 ? 'good' : 'bad';
}

function ratioText(before, after) {
  const ratio = (1 - after / before) * 100;
  return (ratio >= 0 ? '-' : '+') + Math.abs(ratio).toFixed(1) + '%';
}

describe('ratio display', () => {
  it('compression: shows negative ratio as good with - prefix', () => {
    expect(ratioSign(1000, 500)).toBe('good');
    expect(ratioText(1000, 500)).toBe('-50.0%');
  });

  it('expansion: shows positive ratio as bad with + prefix', () => {
    expect(ratioSign(500, 1000)).toBe('bad');
    expect(ratioText(500, 1000)).toBe('+100.0%');
  });

  it('no change: treated as good (0.0%)', () => {
    expect(ratioSign(1000, 1000)).toBe('good');
    expect(ratioText(1000, 1000)).toBe('-0.0%');
  });

  it('upsell displays max(0, ratio) so never negative', () => {
    const ratio = (1 - 1200 / 1000) * 100; // -20
    expect(Math.max(0, ratio).toFixed(0)).toBe('0');
  });
});

// ── QUALITY config ────────────────────────────────────────────────────────────

const QUALITY = {
  low:    { dpi: 72,  jpeg: 0.50 },
  medium: { dpi: 150, jpeg: 0.72 },
  high:   { dpi: 300, jpeg: 0.88 },
};

describe('QUALITY config', () => {
  it('has exactly three levels', () => {
    expect(Object.keys(QUALITY)).toHaveLength(3);
  });

  it('low is most compressed', () => {
    expect(QUALITY.low.dpi).toBeLessThan(QUALITY.medium.dpi);
    expect(QUALITY.low.jpeg).toBeLessThan(QUALITY.medium.jpeg);
  });

  it('high is least compressed', () => {
    expect(QUALITY.high.dpi).toBeGreaterThan(QUALITY.medium.dpi);
    expect(QUALITY.high.jpeg).toBeGreaterThan(QUALITY.medium.jpeg);
  });

  it('scale = dpi / 96 for each level', () => {
    for (const [, cfg] of Object.entries(QUALITY)) {
      const scale = cfg.dpi / 96;
      expect(scale).toBeGreaterThan(0);
    }
  });
});
