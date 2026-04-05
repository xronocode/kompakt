#!/usr/bin/env python3
"""
pdf_compress.py — интерактивное сжатие PDF.

Режимы запуска:
  python pdf_compress.py              — интерактивное меню
  python pdf_compress.py input.pdf    — указать файл, выбрать параметры в меню
  python pdf_compress.py input.pdf -q low -o out.pdf  — полностью без меню
  python pdf_compress.py --methods    — статус зависимостей
  python pdf_compress.py --help       — справка
"""

import sys
import os
import argparse
import subprocess
import shutil
import platform
import logging
import functools
from pathlib import Path
from typing import Optional

# ── Константы ─────────────────────────────────────────────────────────────────

QUALITY_OPTIONS = [
    {
        "key":         "low",
        "gs":          "screen",
        "img":         40,
        "label":       "Максимальное сжатие  [low]",
        "hint":        "72 dpi · сильная потеря качества · email, мессенджеры, веб",
        "suffix":      "_low",
    },
    {
        "key":         "medium",
        "gs":          "ebook",
        "img":         60,
        "label":       "Баланс  [medium]  ★ рекомендуется",
        "hint":        "150 dpi · приемлемое качество · большинство задач",
        "suffix":      "_medium",
    },
    {
        "key":         "high",
        "gs":          "printer",
        "img":         80,
        "label":       "Высокое качество  [high]",
        "hint":        "300 dpi · минимальное сжатие · печать, архивирование",
        "suffix":      "_high",
    },
]

SEP = "─" * 56

SORT_MODES = [
    ("name", "Имя  (A→Z)"),
    ("date", "Дата (новые первые)"),
    ("size", "Размер (большие первые)"),
]

# ── Цвета ANSI ────────────────────────────────────────────────────────────────

class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    CYAN    = "\033[1;36m"
    GREEN   = "\033[1;32m"
    YELLOW  = "\033[1;33m"
    RED     = "\033[1;31m"
    DIM     = "\033[2m"

def _no_color() -> bool:
    return not sys.stdout.isatty() or bool(os.environ.get("NO_COLOR"))

def cc(color: str, text: str) -> str:
    if _no_color():
        return text
    return color + text + C.RESET

# ── Определение ОС и команд установки ────────────────────────────────────────

def detect_os() -> str:
    s = platform.system()
    if s == "Darwin":  return "macos"
    if s == "Windows": return "windows"
    for pm in ("apt-get", "apt", "dnf", "yum", "pacman", "zypper"):  # apt-get приоритетнее apt (стабильнее)
        if shutil.which(pm):
            return f"linux_{pm}"
    return "linux"

def gs_install_cmd(os_name: str) -> Optional[str]:
    return {
        "macos":         "brew install ghostscript",
        "linux_apt-get": "sudo apt-get install -y ghostscript",
        "linux_apt":     "sudo apt install -y ghostscript",
        "linux_dnf":     "sudo dnf install -y ghostscript",
        "linux_yum":     "sudo yum install -y ghostscript",
        "linux_pacman":  "sudo pacman -S --noconfirm ghostscript",
        "linux_zypper":  "sudo zypper install -y ghostscript",
        "windows":       None,
    }.get(os_name)

def pypdf_install_cmd() -> str:
    """Возвращает строку только для отображения; запуск через _run_pip_install()."""
    return f"{sys.executable} -m pip install pypdf"

def _run_pip_install() -> bool:
    """Установить pypdf через список — корректно обрабатывает пробелы в пути к python."""
    print(f"\n  {cc(C.DIM, pypdf_install_cmd())}")
    return subprocess.run(
        [sys.executable, "-m", "pip", "install", "pypdf"],
        shell=False,
    ).returncode == 0

# ── Проверка зависимостей ─────────────────────────────────────────────────────

def find_gs() -> Optional[str]:
    return shutil.which("gs") or shutil.which("gswin64c") or shutil.which("gswin32c")

def check_pypdf() -> bool:
    try:
        import pypdf  # noqa
        return True
    except ImportError:
        return False

@functools.lru_cache(maxsize=1)
def get_deps() -> dict:
    """Кэшируется после первого вызова — избегает повторных syscall."""
    os_name = detect_os()
    return {
        "os":      os_name,
        "gs":      find_gs(),
        "pypdf":   check_pypdf(),
        "gs_cmd":  gs_install_cmd(os_name),
        "pip_cmd": pypdf_install_cmd(),
    }

# ── Ввод с клавиатуры (стрелки) ───────────────────────────────────────────────

def _read_key() -> str:
    """
    Читать одно нажатие клавиши (включая escape-последовательности).
    После ESC использует select + os.read(fd, 8) — читает весь буфер
    за один вызов, избегая потери байт при посимвольном чтении.
    """
    import tty, termios, select
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            # Ждём остаток ESC-последовательности (обычно приходит за <5ms)
            ready = select.select([sys.stdin], [], [], 0.1)[0]
            if ready:
                # os.read читает все доступные байты (до 8) за один syscall
                rest = os.read(fd, 8).decode("utf-8", errors="replace")
                return ch + rest
            return ch  # одиночный Esc
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

def _can_interactive() -> bool:
    """Проверить, доступны ли tty/termios (не работают в pipe/CI)."""
    if not sys.stdin.isatty():
        return False
    try:
        import tty, termios  # noqa
        return True
    except ImportError:
        return False

# ── Интерактивное меню со стрелками ──────────────────────────────────────────

def arrow_menu(
    title: str,
    items: list,
    hints: Optional[list] = None,
    default: int = 0,
    sortable: bool = False,          # показывать ли цикл сортировки (клавиша s)
    sort_key: Optional[callable] = None,  # функция key для пересортировки
) -> Optional[int]:
    """
    Меню с навигацией стрелками, скроллингом, фильтром и сортировкой.
    Возвращает индекс в ИСХОДНОМ списке items или None при выходе.

    Клавиши:
      ↑↓        — навигация
      Enter     — подтвердить
      s / S     — цикл сортировки (если sortable=True)
      печатный  — добавить в фильтр
      Backspace — удалить последний символ фильтра
      Esc       — очистить фильтр / выйти
      q / Ctrl+C — выйти
    """
    # Работаем с парами (оригинальный_индекс, item, hint)
    original = list(enumerate(items))   # [(0, item0), (1, item1), ...]
    hints_list = hints or []

    sort_idx   = 0          # текущий режим сортировки
    filter_str = ""         # строка фильтра
    idx        = max(0, min(default, len(original) - 1))

    OVERHEAD = 9   # title + filter + 2×SEP + hint + nav + scroll indicators + blanks

    def apply_filter_sort(preserve_orig: int = -1):
        """
        Применить фильтр и вернуть список (orig_idx, item, score) отсортированный.
        preserve_orig: оригинальный индекс выбранного элемента для восстановления позиции.
        Возвращает (visible_list, new_cur).
        """
        result = []
        for orig_i, item in original:
            matched, score = fuzzy_match(filter_str, item)
            if matched:
                result.append((orig_i, item, score))
        if filter_str:
            result.sort(key=lambda x: -x[2])
        elif sortable and sort_key:
            mode = SORT_MODES[sort_idx % len(SORT_MODES)][0]
            result = sort_key(result, mode)
        # Восстановить позицию курсора если элемент ещё есть в результатах
        new_cur = 0
        if preserve_orig >= 0:
            for j, (oi, _, *__) in enumerate(result):
                if oi == preserve_orig:
                    new_cur = j
                    break
        return result, new_cur

    visible_items, cur = apply_filter_sort(idx)

    while True:
        rows = shutil.get_terminal_size((80, 24)).lines
        visible = max(3, rows - OVERHEAD)
        n = len(visible_items)

        # Пустой список после фильтра
        if n == 0:
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.flush()
            print(f"\n  {cc(C.BOLD, title)}")
            print(f"  {SEP}")
            fq = cc(C.YELLOW, f"🔍 {filter_str}") if filter_str else ""
            print(f"  {fq}  {cc(C.RED, 'ничего не найдено')}")
            print(f"  {SEP}")
            print(f"  {cc(C.DIM, 'Backspace — удалить символ   Esc — сбросить   q — выход')}")
            key = _read_key()
            if key in ("\x7f", "\x08") and filter_str:
                filter_str = filter_str[:-1]
                visible_items, cur = apply_filter_sort()
            elif key in ("\x1b",):
                filter_str = ""
                visible_items, cur = apply_filter_sort()
            elif key in ("q", "Q", "\x03"):
                sys.stdout.write("\033[2J\033[H"); sys.stdout.flush()
                return None
            continue

        cur = max(0, min(cur, n - 1))

        # Viewport
        top = max(0, min(cur - visible // 2, n - visible))
        top = max(0, top)
        bot = min(top + visible, n)

        # Строка фильтра и сортировки для заголовка
        sort_label = cc(C.DIM, f"[s: {SORT_MODES[sort_idx % len(SORT_MODES)][1]}]") if sortable and not filter_str else ""
        filter_label = (cc(C.YELLOW, f"🔍 {filter_str}") + cc(C.DIM, "▌")) if filter_str else cc(C.DIM, "начните вводить для поиска...")
        counter = cc(C.DIM, f"({cur + 1}/{n})")

        lines = []
        lines.append("")
        lines.append(f"  {cc(C.BOLD, title)}  {counter}  {sort_label}")
        lines.append(f"  {filter_label}")
        lines.append(f"  {SEP}")

        if top > 0:
            lines.append(f"  {cc(C.DIM, f'↑  ещё {top}')}")

        for i in range(top, bot):
            orig_i, item, *_ = visible_items[i]
            if i == cur:
                lines.append(f"  {cc(C.CYAN, '▶  ' + item)}")
            else:
                lines.append(f"     {cc(C.DIM, item)}")

        if bot < n:
            lines.append(f"  {cc(C.DIM, f'↓  ещё {n - bot}')}")

        lines.append(f"  {SEP}")

        # Подсказка для текущего элемента
        orig_cur, _, *_ = visible_items[cur]
        hint_cur = hints_list[orig_cur] if orig_cur < len(hints_list) else ""
        if hint_cur:
            lines.append(f"  {cc(C.YELLOW, 'ℹ')}  {hint_cur}")
        else:
            lines.append("")

        nav = "↑↓ навигация   Enter подтвердить   s сортировка   q выход" if sortable else "↑↓ навигация   Enter подтвердить   q выход"
        lines.append(f"  {cc(C.DIM, nav)}")
        lines.append("")

        sys.stdout.write("\033[2J\033[H")
        sys.stdout.write("\n".join(lines))
        sys.stdout.flush()

        key = _read_key()

        if key in ("\x1b[A",):              # ↑
            cur = (cur - 1) % n
        elif key in ("\x1b[B",):            # ↓
            cur = (cur + 1) % n
        elif key in ("\r", "\n"):           # Enter
            sys.stdout.write("\033[2J\033[H"); sys.stdout.flush()
            return visible_items[cur][0]     # вернуть оригинальный индекс
        elif key in ("s", "S") and sortable and not filter_str:
            sort_idx = (sort_idx + 1) % len(SORT_MODES)
            visible_items, cur = apply_filter_sort()
        elif key in ("\x7f", "\x08"):       # Backspace
            if filter_str:
                # Сохранить текущий элемент при удалении символа
                prev = visible_items[cur][0] if visible_items else -1
                filter_str = filter_str[:-1]
                visible_items, cur = apply_filter_sort(prev)
        elif key == "\x1b":                  # Esc
            if filter_str:
                # Сохранить текущий элемент при сбросе фильтра
                prev = visible_items[cur][0] if visible_items else -1
                filter_str = ""
                visible_items, cur = apply_filter_sort(prev)
            else:
                sys.stdout.write("\033[2J\033[H"); sys.stdout.flush()
                return None
        elif key in ("q", "Q", "\x03"):     # q / Ctrl+C
            sys.stdout.write("\033[2J\033[H"); sys.stdout.flush()
            return None
        elif is_printable_key(key):           # фильтр (макс. 60 символов)
            if len(filter_str) < 60:
                prev = visible_items[cur][0] if visible_items else -1
                filter_str += key
                visible_items, cur = apply_filter_sort(prev)


def text_input(prompt: str, default: str = "") -> str:
    """
    Простой ввод строки с подсказкой default.
    Enter без ввода → default.
    """
    hint = f" [{cc(C.DIM, default)}]" if default else ""
    try:
        val = input(f"  {prompt}{hint}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return val if val else default

# ── Сканирование PDF в текущей папке ─────────────────────────────────────────

def find_pdfs(directory: str = ".") -> list:
    """Найти все PDF в указанной папке, отсортировать по имени (регистронезависимо)."""
    try:
        p = Path(directory)
        # glob("*.pdf") регистрозависим на Linux — собираем оба варианта
        seen = set()
        results = []
        for pattern in ("*.pdf", "*.PDF", "*.Pdf"):
            for f in p.glob(pattern):
                if f not in seen:
                    seen.add(f)
                    results.append(f)
        return sorted(results, key=lambda f: f.name.lower())
    except PermissionError:
        print(cc(C.RED, f"  [!] Нет доступа к папке: {directory}"))
        return []

def human_size(size_bytes: int) -> str:
    value = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"

def truncate_middle(name: str, max_len: int) -> str:
    """Сократить длинное имя файла посередине: 'very_lon…al_v3.pdf'."""
    if len(name) <= max_len:
        return name
    dot = name.rfind(".")
    ext = name[dot:] if (dot > 0 and len(name) - dot <= 5) else ""
    stem = name[:dot] if ext else name
    budget = max_len - len(ext) - 1   # 1 для "…"
    if budget < 4:
        return name[:max_len - 1] + "…"
    left  = (budget + 1) // 2
    right = budget // 2
    return stem[:left] + "…" + stem[-right:] + ext

def _fuzzy_single(q: str, n: str) -> tuple:
    """Subsequence match одного токена q в строке n (оба уже lower())."""
    qi = 0; score = 0; consecutive = 0; last_ni = -1
    for ni, ch in enumerate(n):
        if qi < len(q) and ch == q[qi]:
            qi += 1
            if last_ni == ni - 1:
                consecutive += 1
                score += 10 + consecutive * 5
            else:
                consecutive = 0
                score += 1
            last_ni = ni
    matched = qi == len(q)
    if matched and n.startswith(q):
        score += 100
    return matched, score


def fuzzy_match(query: str, name: str) -> tuple:
    """
    Smart fuzzy match (итеративный, без рекурсии):
    - Пустой запрос    : всегда совпадает
    - Один токен       : subsequence match (символы в порядке)
    - Несколько токенов: каждый токен должен независимо совпасть
    Возвращает (matched: bool, score: int). Выше score = лучше совпадение.
    """
    q = query.strip().lower()
    n = name.lower()
    if not q:
        return True, 0
    tokens = q.split()
    total = 0
    for tok in tokens:          # итеративно — без рекурсии
        ok, sc = _fuzzy_single(tok, n)
        if not ok:
            return False, 0
        total += sc
    return True, total


def is_printable_key(key: str) -> bool:
    """True если key — один печатный символ (ASCII или Unicode)."""
    if len(key) != 1:
        return False
    cp = ord(key)
    if 0x20 <= cp <= 0x7e:
        return True
    return cp > 0x7f and key.isprintable()


def pdf_label(path: Path) -> str:
    """Метка файла для меню: имя (сокращается посередине) + размер."""
    cols = shutil.get_terminal_size((80, 24)).columns
    name_max = max(20, cols - 16)   # 16 = отступы (4) + пробелы (2) + размер (8) + DIM (2)
    name = truncate_middle(path.name, name_max)
    try:
        size = human_size(path.stat().st_size)
    except OSError:
        size = "?"
    return f"{name:<{name_max}}  {cc(C.DIM, size)}"

def pdf_hint(path: Path) -> str:
    try:
        size = path.stat().st_size
        return f"Полный путь: {path.resolve()}  ·  {human_size(size)}"
    except OSError:
        return str(path)

# ── Интерактивный помощник ────────────────────────────────────────────────────

def interactive_wizard(preset_file: Optional[str] = None) -> Optional[dict]:
    """
    Пройти через три шага:
      1. Выбор файла (если не задан)
      2. Выбор качества
      3. Подтверждение имени выходного файла
    Вернуть dict(input, output, quality) или None при отмене.
    """

    # ── Шаг 1: выбор файла ───────────────────────────────────────────────────
    if preset_file:
        src = Path(preset_file)
        if not src.exists():
            print(cc(C.RED, f"\n  [!] Файл не найден: {preset_file}\n"))
            return None
    else:
        pdfs = find_pdfs(".")
        if not pdfs:
            print(cc(C.RED, "\n  [!] В текущей папке нет PDF-файлов.\n"))
            print(f"  Укажите файл явно: python {Path(sys.argv[0]).name} file.pdf\n")
            return None

        # Кэшировать stat() один раз — sort не делает повторных syscall
        stat_cache = {}
        for p in pdfs:
            try:
                stat_cache[p] = p.stat()
            except OSError:
                stat_cache[p] = None

        labels = [pdf_label(p) for p in pdfs]
        hints  = [pdf_hint(p)  for p in pdfs]

        def sort_pdfs_fn(items_with_idx, mode):
            """Пересортировать список (orig_idx, item, score) по режиму (без stat syscall)."""
            def get_stat(entry):
                return stat_cache.get(pdfs[entry[0]])
            if mode == "date":
                return sorted(items_with_idx,
                    key=lambda e: get_stat(e).st_mtime if get_stat(e) else 0,
                    reverse=True)
            elif mode == "size":
                return sorted(items_with_idx,
                    key=lambda e: get_stat(e).st_size if get_stat(e) else 0,
                    reverse=True)
            else:  # name
                return sorted(items_with_idx, key=lambda e: pdfs[e[0]].name.lower())

        choice = arrow_menu(
            title="Шаг 1 из 3  —  Выберите PDF для сжатия",
            items=labels,
            hints=hints,
            sortable=True,
            sort_key=sort_pdfs_fn,
        )
        if choice is None:
            print("  Отменено.\n")
            return None
        src = pdfs[choice]

    # ── Шаг 2: уровень качества ───────────────────────────────────────────────
    q_labels = [q["label"]  for q in QUALITY_OPTIONS]
    q_hints  = [q["hint"]   for q in QUALITY_OPTIONS]

    q_choice = arrow_menu(
        title="Шаг 2 из 3  —  Выберите уровень сжатия",
        items=q_labels,
        hints=q_hints,
        default=1,          # medium по умолчанию
    )
    if q_choice is None:
        print("  Отменено.\n")
        return None
    quality = QUALITY_OPTIONS[q_choice]

    # ── Шаг 3: имя выходного файла ───────────────────────────────────────────
    default_out = (src.stem or src.name) + quality["suffix"] + ".pdf"

    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()
    print(f"\n  {cc(C.BOLD, 'Шаг 3 из 3  —  Имя выходного файла')}")
    print(f"  {SEP}")
    print(f"  Файл    : {cc(C.CYAN, src.name)}")
    print(f"  Качество: {cc(C.YELLOW, quality['label'])}")
    print(f"  {SEP}")
    out_name = text_input("Имя выходного файла", default_out)
    if not out_name.lower().endswith(".pdf"):
        out_name += ".pdf"
    out_path = str(Path(src).parent / out_name)

    # Защита от перезаписи исходника
    if Path(out_path).resolve() == src.resolve():
        print(cc(C.RED, "\n  [!] Имя совпадает с исходным файлом. Добавлен суффикс.\n"))
        out_path = str(src.with_stem(src.stem + quality["suffix"] + "_out"))

    return {
        "input":   str(src),
        "output":  out_path,
        "quality": quality["key"],
    }

# ── Проверка зависимостей (интерактивная) ─────────────────────────────────────

def _prompt_yn(question: str) -> bool:
    while True:
        try:
            ans = input(f"  {question} [y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        if ans in ("y", "yes", "д", "да"):   return True
        if ans in ("n", "no",  "н", "нет", ""): return False
        print("  Введите y или n.")

def _run_install(cmd: str) -> bool:
    """Запустить команду установки GS.
    shlex.split(posix=True) — корректен на Linux/macOS;
    на Windows GS-команды ASCII-only, поэтому posix=True безопасен.
    """
    import shlex
    print(f"\n  {cc(C.DIM, 'Выполняю: ' + cmd)}")
    return subprocess.run(shlex.split(cmd, posix=True), shell=False).returncode == 0

def dep_check_interactive(deps: dict) -> bool:
    gs_ok    = bool(deps["gs"])
    pypdf_ok = deps["pypdf"]
    if gs_ok and pypdf_ok:
        return True

    print(f"\n┌{SEP}")
    print( "│  Проверка зависимостей")
    print(f"├{SEP}")
    gs_str  = cc(C.GREEN, "✓  " + deps["gs"]) if gs_ok  else cc(C.RED, "✗  не найден")
    pyp_str = cc(C.GREEN, "✓  установлен")   if pypdf_ok else cc(C.RED, "✗  не установлен")
    print(f"│  Ghostscript : {gs_str}")
    print(f"│  pypdf       : {pyp_str}")
    print(f"└{SEP}")

    if not gs_ok:
        gs_cmd = deps["gs_cmd"]
        if gs_cmd:
            print(f"\n  Ghostscript даёт лучшее сжатие (50–90%).")
            if _prompt_yn("Установить Ghostscript сейчас?"):
                if _run_install(gs_cmd) and find_gs():
                    print(cc(C.GREEN, "  ✓ Ghostscript установлен."))
                    gs_ok = True
                else:
                    print(cc(C.RED,   "  ✗ Не удалось. Вручную:"))
                    print(f"    {gs_cmd}")
        else:
            print("\n  Ghostscript для Windows:")
            print("  https://www.ghostscript.com/releases/")

    if not pypdf_ok:
        print(f"\n  pypdf — резервный метод (5–30%).")
        if _prompt_yn("Установить pypdf сейчас?"):
            if _run_pip_install() and check_pypdf():
                print(cc(C.GREEN, "  ✓ pypdf установлен."))
                pypdf_ok = True
            else:
                print(cc(C.RED,   "  ✗ Не удалось. Вручную:"))
                print(f"    {deps['pip_cmd']}")

    if not gs_ok and not pypdf_ok:
        print(cc(C.RED, "\n  [!] Ни один метод недоступен.\n"))
        return False

    print()
    return True

def show_methods(deps: dict) -> None:
    gs_ok    = bool(deps["gs"])
    pypdf_ok = deps["pypdf"]
    print(f"\n┌{SEP}")
    print( "│  Статус зависимостей")
    print(f"├{SEP}")
    print(f"│  ОС            : {deps['os']}")
    print(f"│  Ghostscript   : {cc(C.GREEN, '✓  ' + deps['gs']) if gs_ok else cc(C.RED, '✗  не найден')}")
    print(f"│  pypdf         : {cc(C.GREEN, '✓  установлен') if pypdf_ok else cc(C.RED, '✗  не установлен')}")
    print(f"├{SEP}")
    print( "│  Команды установки")
    print(f"├{SEP}")
    print(f"│  GS  : {deps['gs_cmd'] or 'https://www.ghostscript.com/releases/'}")
    print(f"│  pip : {deps['pip_cmd']}")
    print(f"└{SEP}\n")

# ── Сжатие ────────────────────────────────────────────────────────────────────

HELP_TEXT = """
╔══════════════════════════════════════════════════════════╗
║       pdf_compress.py — справка по использованию        ║
╚══════════════════════════════════════════════════════════╝

ОПИСАНИЕ
  Интерактивное сжатие PDF.
  Без аргументов — запускает меню выбора файла и параметров.

СИНТАКСИС
  python pdf_compress.py                        интерактивный режим
  python pdf_compress.py input.pdf              выбрать параметры в меню
  python pdf_compress.py input.pdf -q low       без меню
  python pdf_compress.py input.pdf -q low -o out.pdf

ОПЦИИ
  -o, --output <файл>     Выходной файл (по умолчанию: <имя><суффикс>.pdf)
  -q, --quality           low | medium | high
  --methods               Статус зависимостей
  --no-check              Пропустить проверку зависимостей
  -h, --help              Эта справка

КАЧЕСТВО
  low     72 dpi  · макс. сжатие    · экран, email
  medium  150 dpi · баланс          · общее использование  ★
  high    300 dpi · мин. сжатие     · печать, архив

МЕТОДЫ
  Ghostscript — 50–90% · brew/apt install ghostscript
  pypdf       — 5–30%  · pip install pypdf
"""

def show_help_and_exit(error: Optional[str] = None) -> None:
    if error:
        print(cc(C.RED, f"\n  [!] Ошибка: {error}\n"))
    print(HELP_TEXT)
    sys.exit(1 if error else 0)

def compress_with_gs(input_path: str, output_path: str, quality: str) -> bool:
    gs = find_gs()
    if not gs:
        return False
    cmd = [
        gs, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS=/{quality}", "-dNOPAUSE", "-dQUIET", "-dBATCH",
        f"-sOutputFile={output_path}", input_path,
    ]
    return subprocess.run(cmd, capture_output=True).returncode == 0

def compress_with_pypdf(input_path: str, output_path: str, image_quality: int) -> bool:
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        print(cc(C.RED, "  [!] pypdf не установлен: pip install pypdf"))
        return False

    try:
        reader = PdfReader(input_path)
        writer = PdfWriter()
        for page in reader.pages:
            for img in page.images:
                try:
                    img.replace(img.image, quality=image_quality)
                except Exception as e:
                    logging.debug(f"image compress skip: {e}")
            writer.add_page(page)
        writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
        with open(output_path, "wb") as f:
            writer.write(f)
        return True
    except Exception as e:
        logging.debug(f"pypdf compress failed: {e}")
        return False

def _exit_error(msg: str) -> None:
    """Вывести краткое сообщение об ошибке и выйти без HELP_TEXT."""
    print(cc(C.RED, f"\n  [!] Ошибка: {msg}\n"))
    sys.exit(1)

def run_compress(input_path: str, output_path: str, quality_key: str) -> None:
    src = Path(input_path)

    if not src.exists():
        _exit_error(f"файл не найден: {input_path}")
    if Path(output_path).resolve() == src.resolve():
        _exit_error("выходной файл совпадает с исходным — укажите другое имя через -o")
    size_before = src.stat().st_size
    if size_before == 0:
        _exit_error(f"файл пустой: {input_path}")

    # Найти параметры качества
    q = next((x for x in QUALITY_OPTIONS if x["key"] == quality_key), QUALITY_OPTIONS[1])

    print(f"\n  {cc(C.BOLD, 'Сжатие PDF')}")
    print(f"  {SEP}")
    print(f"  Файл    : {cc(C.CYAN, src.name)}  ({human_size(size_before)})")
    print(f"  Качество: {cc(C.YELLOW, q['label'])}")
    print(f"  Вывод   : {output_path}")
    print(f"  {SEP}")

    ok = compress_with_gs(input_path, output_path, q["gs"])
    if ok:
        method = "Ghostscript"
    else:
        print(f"  {cc(C.DIM, 'Ghostscript недоступен, использую pypdf…')}")
        ok = compress_with_pypdf(input_path, output_path, q["img"])
        method = "pypdf" if ok else "—"

    out_path_obj = Path(output_path)
    if not ok or not out_path_obj.exists() or out_path_obj.stat().st_size == 0:
        print(cc(C.RED, "\n  [!] Ошибка: сжатие не выполнено.\n"))
        sys.exit(1)

    size_after = Path(output_path).stat().st_size
    ratio = (1 - size_after / size_before) * 100
    saved = size_before - size_after

    print(f"\n  {cc(C.GREEN, '✓ Готово')}  ({method})")
    print(f"  {SEP}")
    print(f"  До     : {human_size(size_before)}")
    print(f"  После  : {human_size(size_after)}")
    if ratio >= 0:
        print(f"  Сжатие : {cc(C.GREEN, f'{ratio:.1f}%')}  (сэкономлено {human_size(saved)})")
    else:
        print(f"  Сжатие : {cc(C.YELLOW, f'⚠ файл увеличился на {abs(ratio):.1f}%')}  (попробуйте Ghostscript)")
    print(f"  Файл   : {cc(C.CYAN, output_path)}")
    print()

# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("input",      nargs="?")
    parser.add_argument("-o", "--output")
    parser.add_argument("-q", "--quality", choices=["low", "medium", "high"])
    parser.add_argument("--methods",   action="store_true")
    parser.add_argument("--no-check",  action="store_true")
    parser.add_argument("-h", "--help", action="store_true")

    try:
        args = parser.parse_args()
    except SystemExit:
        show_help_and_exit()

    if args.help:
        show_help_and_exit()

    deps = get_deps()

    if args.methods:
        show_methods(deps)
        sys.exit(0)

    if not args.no_check:
        if not dep_check_interactive(deps):
            sys.exit(1)

    # ── Режим: полностью без меню (все аргументы заданы) ─────────────────────
    if args.input and args.quality and args.output:
        run_compress(args.input, args.output, args.quality)
        sys.exit(0)

    # ── Режим: частично или полностью интерактивный ───────────────────────────
    if not _can_interactive():
        # Не TTY (pipe, CI) — требуем явные аргументы
        if not args.input:
            show_help_and_exit("не указан входной файл (запуск не в TTY)")
        q_key = args.quality or "medium"
        q     = next(x for x in QUALITY_OPTIONS if x["key"] == q_key)
        src   = Path(args.input)
        out   = args.output or str(src.with_stem(src.stem + q["suffix"]))
        run_compress(str(src), out, q_key)
        sys.exit(0)

    # Интерактивный wizard
    params = interactive_wizard(preset_file=args.input)
    if params is None:
        sys.exit(0)

    # Если quality задан через CLI — переопределить
    if args.quality:
        params["quality"] = args.quality
    if args.output:
        params["output"] = args.output

    run_compress(params["input"], params["output"], params["quality"])
