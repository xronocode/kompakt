import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const localesDir = join(__dirname, '../../src/_locales');

const REQUIRED_KEYS = [
  'appName', 'appDescription', 'badge',
  'dropTitle', 'dropHint',
  'labelCompression',
  'qualityLow', 'qualityLowDesc',
  'qualityMedium', 'qualityMediumDesc',
  'qualityHigh', 'qualityHighDesc',
  'btnCompress', 'preparing', 'progressPage',
  'statBefore', 'statAfter', 'statSaved',
  'btnDownload',
  'upsellBody', 'upsellLink',
  'errFileTooLarge', 'errNoPages', 'errPasswordProtected',
  'donateLink',
];

const PLACEHOLDER_KEYS = {
  progressPage: ['page', 'total'],
  upsellBody:   ['ratio'],
};

const locales = readdirSync(localesDir);

describe('i18n locale files', () => {
  it('at least 8 locales exist', () => {
    expect(locales.length).toBeGreaterThanOrEqual(8);
  });

  for (const locale of locales) {
    const filePath = join(localesDir, locale, 'messages.json');
    const messages = JSON.parse(readFileSync(filePath, 'utf8'));

    describe(`locale: ${locale}`, () => {
      it('has all required keys', () => {
        for (const key of REQUIRED_KEYS) {
          expect(messages, `missing key "${key}" in ${locale}`).toHaveProperty(key);
        }
      });

      it('has no extra unknown keys', () => {
        for (const key of Object.keys(messages)) {
          expect(REQUIRED_KEYS, `unexpected key "${key}" in ${locale}`).toContain(key);
        }
      });

      it('all messages are non-empty strings', () => {
        for (const key of REQUIRED_KEYS) {
          const entry = messages[key];
          expect(typeof entry.message, `key "${key}" in ${locale}`).toBe('string');
          expect(entry.message.trim().length, `key "${key}" in ${locale} is empty`).toBeGreaterThan(0);
        }
      });

      it('placeholder keys are defined for parametric messages', () => {
        for (const [key, expectedPlaceholders] of Object.entries(PLACEHOLDER_KEYS)) {
          const entry = messages[key];
          expect(entry.placeholders, `"${key}" in ${locale} missing placeholders`).toBeDefined();
          for (const ph of expectedPlaceholders) {
            expect(
              entry.placeholders,
              `"${key}" in ${locale} missing placeholder "${ph}"`
            ).toHaveProperty(ph);
          }
        }
      });

      it('progressPage message contains $PAGE$ and $TOTAL$', () => {
        const msg = messages.progressPage.message;
        expect(msg).toContain('$PAGE$');
        expect(msg).toContain('$TOTAL$');
      });

      it('upsellBody message contains $RATIO$', () => {
        const msg = messages.upsellBody.message;
        expect(msg).toContain('$RATIO$');
      });
    });
  }

  it('all locales have identical key sets', () => {
    const keysets = locales.map(locale => {
      const filePath = join(localesDir, locale, 'messages.json');
      const messages = JSON.parse(readFileSync(filePath, 'utf8'));
      return Object.keys(messages).sort().join(',');
    });
    const first = keysets[0];
    for (let i = 1; i < keysets.length; i++) {
      expect(keysets[i], `locale "${locales[i]}" key set differs from "${locales[0]}"`).toBe(first);
    }
  });
});
