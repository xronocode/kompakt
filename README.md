# pdf-kompakt

> Compress PDFs in your browser — or from the terminal. Free, private, offline.

---

## Two ways to use it

| | [Browser Extension](#-chrome-extension) | [Desktop CLI](#-desktop-app) |
|---|---|---|
| Install | Chrome Web Store or sideload | Binary / Homebrew / Python |
| Compression | 5–40% (canvas re-render) | **50–90%** (Ghostscript) |
| Privacy | 100% local — files never leave device | 100% local |
| OS | Any (Chrome/Chromium) | macOS · Linux · Windows |

---

## 🌐 Chrome Extension

Compress PDFs directly in your browser — no upload, no account, works offline.

### Install from Chrome Web Store

*(submission in progress — use sideload in the meantime)*

### Sideload (manual install)

1. Download **[pdf-kompakt-chrome-extension.zip](https://github.com/xronocode/kompakt/releases/latest/download/pdf-kompakt-chrome-extension.zip)** from Releases
2. Unzip it
3. Open Chrome → `chrome://extensions` → enable **Developer mode**
4. Click **Load unpacked** → select the unzipped folder

### Features

- Drag & drop or click to pick a PDF (up to 50 MB)
- 3 quality levels: low (72 dpi) · medium (150 dpi) · high (300 dpi)
- Shows before / after size and % saved
- Prompts to try the desktop app for heavier compression

### Languages

The extension is fully localised in **8 languages** — Chrome picks the right one automatically based on your browser language:

| Language | Locale |
|----------|--------|
| English | `en` |
| German | `de` |
| Spanish | `es` |
| French | `fr` |
| Japanese | `ja` |
| Portuguese (Brazil) | `pt_BR` |
| Russian | `ru` |
| Chinese (Simplified) | `zh_CN` |

---

## 💻 Desktop App

### Binary (no Python required)

Download the prebuilt binary for your platform from [Releases](https://github.com/xronocode/kompakt/releases/latest) (no Python required):

| Platform | File |
|----------|------|
| macOS    | `pdf-kompakt-macos` |
| Linux    | `pdf-kompakt-linux` |
| Windows  | `pdf-kompakt-windows.exe` |

```bash
# macOS / Linux
chmod +x pdf-kompakt-macos
./pdf-kompakt-macos
```

### Homebrew (macOS / Linux)

```bash
brew tap xronocode/tools
brew install pdf-kompakt
```

### Python (any platform)

Requires Python 3.8+.

```bash
git clone https://github.com/xronocode/kompakt.git
cd kompakt
pip install pypdf          # optional but recommended
python pdf_compress.py
```

For best compression, also install Ghostscript:

```bash
# macOS
brew install ghostscript

# Ubuntu / Debian
sudo apt install ghostscript

# Fedora
sudo dnf install ghostscript
```

---

## Usage

```
pdf-kompakt                              interactive: pick file + quality
pdf-kompakt input.pdf                    pick quality interactively
pdf-kompakt input.pdf -q medium          skip all menus
pdf-kompakt input.pdf -q low -o out.pdf  fully non-interactive
pdf-kompakt --methods                    check dependency status
pdf-kompakt --help
```

### Quality levels

| Flag | DPI | Compression | Best for |
|------|-----|-------------|----------|
| `low` | 72 | maximum | email, messaging, web |
| `medium` ★ | 150 | balanced | most use cases |
| `high` | 300 | minimal | print, archiving |

---

## How it works

Running `pdf-kompakt` opens a 3-step interactive wizard:

1. **Pick a file** — fuzzy search across all PDFs in the current directory, sort by name / date / size
2. **Choose quality** — low / medium / high with live hints
3. **Confirm output name** — sensible default, editable

```
  Step 2 of 3 — Choose compression level     (2/3)
  ────────────────────────────────────────────────────────
▶  Maximum compression  [low]
   Balance  [medium]  ★ recommended
   High quality  [high]
  ────────────────────────────────────────────────────────
  ℹ  72 dpi · heavy lossy · email, messengers, web
  ↑↓ navigate   Enter confirm   q quit

  ✓ Done  (Ghostscript)
  ────────────────────────────────────────────────────────
  Before : 11.2 MB
  After  : 1.4 MB
  Saved  : 87.5%  (9.8 MB freed)
```

---

## Dependencies

| Tool | Role | Install |
|------|------|---------|
| [Ghostscript](https://www.ghostscript.com/) | Primary engine · 50–90% savings | `brew install ghostscript` |
| [pypdf](https://pypdf.readthedocs.io/) | Fallback · 5–30% savings | `pip install pypdf` |

Both are optional — the tool detects what's available and offers to install missing ones on first run.

---

## License

MIT

---

*Browser extension saves 5–40%. For 50–90% compression on the same file, use the desktop app with Ghostscript.*
