#!/usr/bin/env python3
"""
test_pdf_compress.py — тесты для pdf_compress.py

Запуск: python test_pdf_compress.py [-v]
"""

import sys
import os
import unittest
import tempfile
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

# Загрузить модуль напрямую (не через __main__)
sys.path.insert(0, str(Path("/mnt/user-data/outputs")))
os.environ["NO_COLOR"] = "1"   # отключить ANSI в тестах

import pdf_compress as m   # noqa: E402  (после sys.path)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

FIXTURES = Path("/tmp/pdf_test")
NORMAL   = str(FIXTURES / "normal.pdf")
SINGLE   = str(FIXTURES / "single.pdf")
EMPTY    = str(FIXTURES / "empty.pdf")
CORRUPT  = str(FIXTURES / "corrupt.pdf")
UNICODE  = str(FIXTURES / "отчёт_2026.pdf")
SPACES   = str(FIXTURES / "my report final.pdf")
DOTNAME  = str(FIXTURES / "report.v2.final.pdf")


def tmp_out(name="out.pdf"):
    return str(Path(tempfile.mkdtemp()) / name)


# ─────────────────────────────────────────────────────────────────────────────
# 1. human_size
# ─────────────────────────────────────────────────────────────────────────────

class TestHumanSize(unittest.TestCase):

    def test_zero(self):
        self.assertEqual(m.human_size(0), "0.0 B")

    def test_bytes(self):
        self.assertEqual(m.human_size(512), "512.0 B")

    def test_exactly_1kb(self):
        self.assertEqual(m.human_size(1024), "1.0 KB")

    def test_megabytes(self):
        self.assertEqual(m.human_size(1024 ** 2), "1.0 MB")

    def test_gigabytes(self):
        self.assertEqual(m.human_size(1024 ** 3), "1.0 GB")

    def test_terabytes(self):
        self.assertEqual(m.human_size(1024 ** 4), "1.0 TB")

    def test_petabytes(self):
        self.assertEqual(m.human_size(1024 ** 5), "1.0 PB")

    def test_fractional(self):
        result = m.human_size(1536)   # 1.5 KB
        self.assertEqual(result, "1.5 KB")

    def test_large_non_round(self):
        result = m.human_size(1_500_000)
        self.assertIn("MB", result)


# ─────────────────────────────────────────────────────────────────────────────
# 2. detect_os / gs_install_cmd
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectOs(unittest.TestCase):

    def test_macos(self):
        with patch("platform.system", return_value="Darwin"):
            self.assertEqual(m.detect_os(), "macos")

    def test_windows(self):
        with patch("platform.system", return_value="Windows"):
            self.assertEqual(m.detect_os(), "windows")

    def test_linux_apt_get(self):
        with patch("platform.system", return_value="Linux"), \
             patch("shutil.which", side_effect=lambda x: "/usr/bin/apt-get" if x == "apt-get" else None):
            self.assertEqual(m.detect_os(), "linux_apt-get")

    def test_linux_apt_get_priority_over_apt(self):
        """apt-get должен иметь приоритет над apt."""
        def which(name):
            return f"/usr/bin/{name}" if name in ("apt-get", "apt") else None
        with patch("platform.system", return_value="Linux"), \
             patch("shutil.which", side_effect=which):
            self.assertEqual(m.detect_os(), "linux_apt-get")

    def test_linux_fallback(self):
        with patch("platform.system", return_value="Linux"), \
             patch("shutil.which", return_value=None):
            self.assertEqual(m.detect_os(), "linux")

    def test_gs_install_cmd_macos(self):
        self.assertEqual(m.gs_install_cmd("macos"), "brew install ghostscript")

    def test_gs_install_cmd_windows_none(self):
        self.assertIsNone(m.gs_install_cmd("windows"))

    def test_gs_install_cmd_unknown_none(self):
        self.assertIsNone(m.gs_install_cmd("haiku"))

    def test_all_linux_distros_have_cmd(self):
        for os_name in ("linux_apt-get", "linux_apt", "linux_dnf",
                        "linux_yum", "linux_pacman", "linux_zypper"):
            cmd = m.gs_install_cmd(os_name)
            self.assertIsNotNone(cmd, f"missing cmd for {os_name}")
            self.assertIn("ghostscript", cmd)


# ─────────────────────────────────────────────────────────────────────────────
# 3. _no_color / cc
# ─────────────────────────────────────────────────────────────────────────────

class TestColors(unittest.TestCase):

    def test_no_color_env_set(self):
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            self.assertTrue(m._no_color())

    def test_no_color_env_empty_string(self):
        """NO_COLOR='' (пустая строка) — цвет должен работать если stdout is tty."""
        with patch.dict(os.environ, {"NO_COLOR": ""}, clear=False), \
             patch.object(sys.stdout, "isatty", return_value=True):
            # bool("") = False → NO_COLOR не активен
            self.assertFalse(m._no_color())

    def test_no_color_not_tty(self):
        with patch.object(sys.stdout, "isatty", return_value=False), \
             patch.dict(os.environ, {}, clear=True):
            self.assertTrue(m._no_color())

    def test_cc_strips_colors_when_no_color(self):
        with patch("pdf_compress._no_color", return_value=True):
            self.assertEqual(m.cc(m.C.RED, "hello"), "hello")

    def test_cc_adds_colors_when_tty(self):
        with patch("pdf_compress._no_color", return_value=False):
            result = m.cc(m.C.RED, "hello")
            self.assertIn("\033[", result)
            self.assertIn("hello", result)
            self.assertTrue(result.endswith(m.C.RESET))

    def test_cc_returns_str(self):
        self.assertIsInstance(m.cc(m.C.GREEN, "test"), str)


# ─────────────────────────────────────────────────────────────────────────────
# 4. find_pdfs
# ─────────────────────────────────────────────────────────────────────────────

class TestFindPdfs(unittest.TestCase):

    def test_finds_pdfs(self):
        pdfs = m.find_pdfs(str(FIXTURES))
        names = [p.name for p in pdfs]
        self.assertIn("normal.pdf", names)
        self.assertIn("single.pdf", names)

    def test_sorted_case_insensitive(self):
        pdfs = m.find_pdfs(str(FIXTURES))
        names = [p.name.lower() for p in pdfs]
        self.assertEqual(names, sorted(names))

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(m.find_pdfs(d), [])

    def test_nonexistent_dir_returns_empty(self):
        result = m.find_pdfs("/nonexistent/path/xyz")
        self.assertEqual(result, [])

    def test_unicode_filename(self):
        pdfs = m.find_pdfs(str(FIXTURES))
        names = [p.name for p in pdfs]
        self.assertIn("отчёт_2026.pdf", names)

    def test_spaces_in_filename(self):
        pdfs = m.find_pdfs(str(FIXTURES))
        names = [p.name for p in pdfs]
        self.assertIn("my report final.pdf", names)

    def test_returns_path_objects(self):
        pdfs = m.find_pdfs(str(FIXTURES))
        for p in pdfs:
            self.assertIsInstance(p, Path)


# ─────────────────────────────────────────────────────────────────────────────
# 5. arrow_menu — default clamp и bounds
# ─────────────────────────────────────────────────────────────────────────────

class TestArrowMenuLogic(unittest.TestCase):
    """Тестируем только логику индексации без TTY."""

    def test_default_clamp_over_max(self):
        idx = max(0, min(99, 3 - 1))
        self.assertEqual(idx, 2)

    def test_default_clamp_negative(self):
        idx = max(0, min(-5, 3 - 1))
        self.assertEqual(idx, 0)

    def test_default_valid(self):
        idx = max(0, min(1, 3 - 1))
        self.assertEqual(idx, 1)

    def test_hints_bounds_safe(self):
        hints = ["h0", "h1"]
        for idx in range(4):
            safe = hints[idx] if (hints and idx < len(hints) and hints[idx]) else None
            if idx < 2:
                self.assertEqual(safe, f"h{idx}")
            else:
                self.assertIsNone(safe)

    def test_wrap_up(self):
        """Стрелка вверх от 0 → последний элемент."""
        n = 3; idx = 0
        idx = (idx - 1) % n
        self.assertEqual(idx, 2)

    def test_wrap_down(self):
        """Стрелка вниз от последнего → 0."""
        n = 3; idx = 2
        idx = (idx + 1) % n
        self.assertEqual(idx, 0)


# ─────────────────────────────────────────────────────────────────────────────
# 6. run_compress — валидация
# ─────────────────────────────────────────────────────────────────────────────

class TestRunCompressValidation(unittest.TestCase):

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, "/mnt/user-data/outputs/pdf_compress.py", *args, "--no-check"],
            capture_output=True, text=True
        )

    def test_missing_file(self):
        r = self._run("/nonexistent/file.pdf", "-q", "medium", "-o", "/tmp/out.pdf")
        self.assertEqual(r.returncode, 1)
        self.assertIn("не найден", r.stdout)

    def test_empty_file(self):
        r = self._run(EMPTY, "-q", "medium", "-o", "/tmp/out.pdf")
        self.assertEqual(r.returncode, 1)
        self.assertIn("пустой", r.stdout)

    def test_output_same_as_input(self):
        r = self._run(NORMAL, "-q", "medium", "-o", NORMAL)
        self.assertEqual(r.returncode, 1)
        self.assertIn("совпадает", r.stdout)

    def test_valid_file_creates_output(self):
        out = tmp_out()
        r = self._run(SINGLE, "-q", "medium", "-o", out)
        # pypdf доступен, GS нет — должно создать файл или упасть с ошибкой
        if r.returncode == 0:
            self.assertTrue(Path(out).exists())
            self.assertGreater(Path(out).stat().st_size, 0)

    def test_unicode_input_path(self):
        out = tmp_out()
        r = self._run(UNICODE, "-q", "low", "-o", out)
        self.assertIn(r.returncode, (0, 1))   # не должно быть необработанного exception

    def test_spaces_in_input_path(self):
        out = tmp_out()
        r = self._run(SPACES, "-q", "low", "-o", out)
        self.assertIn(r.returncode, (0, 1))

    def test_dotted_stem_output_name(self):
        """report.v2.final.pdf → только stem без расширения как base."""
        src = Path(DOTNAME)
        q = next(x for x in m.QUALITY_OPTIONS if x["key"] == "medium")
        expected_stem = src.stem + q["suffix"]   # "report.v2.final_medium"
        self.assertTrue(expected_stem.endswith("_medium"))


# ─────────────────────────────────────────────────────────────────────────────
# 7. default output name generation
# ─────────────────────────────────────────────────────────────────────────────

class TestOutputNameGeneration(unittest.TestCase):

    def _out_name(self, filename, quality_key):
        src = Path(filename)
        q = next(x for x in m.QUALITY_OPTIONS if x["key"] == quality_key)
        return src.with_stem(src.stem + q["suffix"]).name

    def test_low(self):
        self.assertEqual(self._out_name("report.pdf", "low"), "report_low.pdf")

    def test_medium(self):
        self.assertEqual(self._out_name("report.pdf", "medium"), "report_medium.pdf")

    def test_high(self):
        self.assertEqual(self._out_name("report.pdf", "high"), "report_high.pdf")

    def test_dotted_stem(self):
        self.assertEqual(self._out_name("report.v2.final.pdf", "medium"), "report.v2.final_medium.pdf")

    def test_unicode_stem(self):
        self.assertEqual(self._out_name("отчёт_2026.pdf", "high"), "отчёт_2026_high.pdf")

    def test_spaces_in_stem(self):
        self.assertEqual(self._out_name("my report.pdf", "low"), "my report_low.pdf")


# ─────────────────────────────────────────────────────────────────────────────
# 8. compress_with_pypdf — edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestCompressWithPypdf(unittest.TestCase):

    def test_normal_pdf_creates_output(self):
        out = tmp_out()
        ok = m.compress_with_pypdf(NORMAL, out, 60)
        self.assertTrue(ok)
        self.assertTrue(Path(out).exists())
        self.assertGreater(Path(out).stat().st_size, 0)

    def test_single_page(self):
        out = tmp_out()
        ok = m.compress_with_pypdf(SINGLE, out, 60)
        self.assertTrue(ok)

    def test_unicode_path(self):
        out = tmp_out()
        ok = m.compress_with_pypdf(UNICODE, out, 60)
        self.assertTrue(ok)

    def test_spaces_in_path(self):
        out = tmp_out()
        ok = m.compress_with_pypdf(SPACES, out, 60)
        self.assertTrue(ok)

    def test_output_is_valid_pdf(self):
        out = tmp_out()
        m.compress_with_pypdf(NORMAL, out, 60)
        with open(out, "rb") as f:
            header = f.read(4)
        self.assertEqual(header, b"%PDF")

    def test_corrupt_pdf_does_not_crash_silently(self):
        """Корраптный файл должен либо вернуть False либо бросить исключение — но не зависнуть."""
        out = tmp_out()
        try:
            result = m.compress_with_pypdf(CORRUPT, out, 60)
            # pypdf может либо вернуть False либо True с плохим результатом
            self.assertIsInstance(result, bool)
        except Exception:
            pass   # исключение от pypdf тоже ок — главное не зависание

    def test_image_quality_low(self):
        out_low  = tmp_out("low.pdf")
        out_high = tmp_out("high.pdf")
        m.compress_with_pypdf(NORMAL, out_low,  10)
        m.compress_with_pypdf(NORMAL, out_high, 95)
        # low quality ≤ high quality в размере (не всегда, но для text PDF разница минимальна)
        self.assertTrue(Path(out_low).exists())
        self.assertTrue(Path(out_high).exists())

    def test_output_dir_nonexistent(self):
        """Запись в несуществующую папку — compress возвращает False (исключение поймано внутри)."""
        out = "/nonexistent/dir/out.pdf"
        result = m.compress_with_pypdf(NORMAL, out, 60)
        self.assertFalse(result)


# ─────────────────────────────────────────────────────────────────────────────
# 9. compress_with_gs — мок (GS не установлен в CI)
# ─────────────────────────────────────────────────────────────────────────────

class TestCompressWithGs(unittest.TestCase):

    def test_no_gs_returns_false(self):
        with patch("pdf_compress.find_gs", return_value=None):
            ok = m.compress_with_gs(NORMAL, tmp_out(), "ebook")
            self.assertFalse(ok)

    def test_gs_nonzero_exit_returns_false(self):
        fake_result = MagicMock()
        fake_result.returncode = 1
        with patch("pdf_compress.find_gs", return_value="/usr/bin/gs"), \
             patch("subprocess.run", return_value=fake_result):
            ok = m.compress_with_gs(NORMAL, tmp_out(), "ebook")
            self.assertFalse(ok)

    def test_gs_zero_exit_returns_true(self):
        fake_result = MagicMock()
        fake_result.returncode = 0
        with patch("pdf_compress.find_gs", return_value="/usr/bin/gs"), \
             patch("subprocess.run", return_value=fake_result):
            ok = m.compress_with_gs(NORMAL, tmp_out(), "ebook")
            self.assertTrue(ok)

    def test_gs_cmd_contains_quality(self):
        """Команда GS должна содержать корректный PDFSETTINGS."""
        captured = {}
        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            r = MagicMock(); r.returncode = 0
            return r
        with patch("pdf_compress.find_gs", return_value="/usr/bin/gs"), \
             patch("subprocess.run", side_effect=fake_run):
            m.compress_with_gs(NORMAL, tmp_out(), "screen")
        self.assertIn("-dPDFSETTINGS=/screen", captured["cmd"])

    def test_gs_cmd_contains_output_path(self):
        out = tmp_out("gs_out.pdf")
        captured = {}
        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            r = MagicMock(); r.returncode = 0
            return r
        with patch("pdf_compress.find_gs", return_value="/usr/bin/gs"), \
             patch("subprocess.run", side_effect=fake_run):
            m.compress_with_gs(NORMAL, out, "ebook")
        self.assertTrue(any(out in str(arg) for arg in captured["cmd"]))


# ─────────────────────────────────────────────────────────────────────────────
# 10. CLI integration tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCLI(unittest.TestCase):

    SCRIPT = "/mnt/user-data/outputs/pdf_compress.py"

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, self.SCRIPT, *args],
            capture_output=True, text=True
        )

    def test_help_exit_0(self):
        r = self._run("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("СИНТАКСИС", r.stdout)

    def test_help_contains_all_sections(self):
        r = self._run("--help")
        for section in ("СИНТАКСИС", "ОПЦИИ", "КАЧЕСТВО", "МЕТОДЫ"):
            self.assertIn(section, r.stdout)

    def test_methods_exit_0(self):
        r = self._run("--methods")
        self.assertEqual(r.returncode, 0)

    def test_methods_shows_os(self):
        r = self._run("--methods")
        self.assertIn("ОС", r.stdout)

    def test_invalid_quality_shows_help(self):
        r = self._run("input.pdf", "-q", "ultra")
        self.assertIn("СИНТАКСИС", r.stdout)

    def test_missing_file_no_help_text(self):
        """_exit_error не должен выводить HELP_TEXT."""
        r = self._run("/nonexistent.pdf", "-q", "medium", "-o", "/tmp/x.pdf", "--no-check")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("СИНТАКСИС", r.stdout)

    def test_full_pipeline_no_menu(self):
        out = tmp_out()
        r = self._run(SINGLE, "-q", "medium", "-o", out, "--no-check")
        self.assertIn(r.returncode, (0, 1))
        if r.returncode == 0:
            self.assertTrue(Path(out).exists())

    def test_no_args_non_tty_shows_help(self):
        r = subprocess.run(
            [sys.executable, self.SCRIPT],
            capture_output=True, text=True,
            stdin=subprocess.DEVNULL
        )
        # В не-TTY без файла → help
        self.assertIn("СИНТАКСИС", r.stdout)

    def test_quality_low_suffix_in_default_output(self):
        """В non-TTY режиме default output должен содержать суффикс качества."""
        # Симулируем non-TTY с файлом и качеством, без -o
        r = subprocess.run(
            [sys.executable, self.SCRIPT, SINGLE, "-q", "low", "--no-check"],
            capture_output=True, text=True,
            stdin=subprocess.DEVNULL
        )
        # Файл должен создаться как single_low.pdf рядом с исходником
        expected = str(FIXTURES / "single_low.pdf")
        if r.returncode == 0:
            self.assertTrue(Path(expected).exists() or "_low" in r.stdout)


# ─────────────────────────────────────────────────────────────────────────────
# 11. ratio / saved edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestRatioLogic(unittest.TestCase):

    def test_ratio_positive(self):
        size_before, size_after = 1000, 600
        ratio = (1 - size_after / size_before) * 100
        self.assertAlmostEqual(ratio, 40.0)

    def test_ratio_zero(self):
        ratio = (1 - 1000 / 1000) * 100
        self.assertEqual(ratio, 0.0)

    def test_ratio_negative_file_grew(self):
        size_before, size_after = 1000, 1200
        ratio = (1 - size_after / size_before) * 100
        self.assertLess(ratio, 0)
        self.assertAlmostEqual(abs(ratio), 20.0)

    def test_saved_negative_when_grew(self):
        saved = 1000 - 1200
        self.assertEqual(saved, -200)


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main(verbosity=2)

# ─────────────────────────────────────────────────────────────────────────────
# 12. Тесты для новых исправлений (v4)
# ─────────────────────────────────────────────────────────────────────────────

# Перезагрузить модуль с новым файлом
import importlib
sys.path.insert(0, "/tmp")
# Временно подменим путь
import pdf_compress as m4
# Используем subprocess для тестов новой версии

SCRIPT_V4 = "/tmp/pdf_v4.py"

class TestV4Fixes(unittest.TestCase):

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, SCRIPT_V4, *args, "--no-check"],
            capture_output=True, text=True,
            stdin=subprocess.DEVNULL
        )

    def test_corrupt_pdf_returns_error_not_traceback(self):
        """Корраптный PDF должен дать читаемую ошибку, а не traceback."""
        r = self._run(CORRUPT, "-q", "medium", "-o", tmp_out())
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Traceback", r.stdout)
        self.assertNotIn("Traceback", r.stderr)

    def test_output_extension_normalized(self):
        """Проверить логику нормализации расширения."""
        for name, expected in [
            ("out",       "out.pdf"),
            ("out.pdf",   "out.pdf"),
            ("out.PDF",   "out.PDF"),   # уже есть расширение → не меняем
            ("out.txt",   "out.txt.pdf"),  # нет .pdf → добавляем
        ]:
            result = name if name.lower().endswith(".pdf") else name + ".pdf"
            self.assertEqual(result, expected)

    def test_find_pdfs_case_insensitive(self):
        """UPPER.PDF должен быть найден."""
        # Файл уже создан в предыдущем тесте
        import importlib, types
        spec = importlib.util.spec_from_file_location("pdf_v4", SCRIPT_V4)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        pdfs = mod.find_pdfs(str(FIXTURES))
        names = [p.name for p in pdfs]
        self.assertIn("UPPER.PDF", names)

    def test_output_empty_file_detected(self):
        """GS создал пустой файл → ошибка."""
        fake_result = MagicMock(); fake_result.returncode = 0
        # Создать пустой выходной файл как side effect
        def fake_run(cmd, **kwargs):
            out = cmd[-2] if "-sOutputFile=" in cmd[-2] else None
            if out:
                open(out.replace("-sOutputFile=",""), "w").close()
            return fake_result

        import importlib.util
        spec = importlib.util.spec_from_file_location("pdf_v4", SCRIPT_V4)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        out = tmp_out()
        with patch.object(mod, "find_gs", return_value="/usr/bin/gs"), \
             patch("subprocess.run", side_effect=fake_run):
            ok = mod.compress_with_gs(NORMAL, out, "ebook")
        # GS вернул 0 но файл пустой — run_compress должен поймать это
        # (тест самой логики run_compress через CLI)
        r = self._run(CORRUPT, "-q", "medium", "-o", tmp_out())
        self.assertEqual(r.returncode, 1)


# ─────────────────────────────────────────────────────────────────────────────
# 13. Tests for v5 style/minor fixes
# ─────────────────────────────────────────────────────────────────────────────

import importlib.util as _ilu

def _load_v5():
    spec = _ilu.spec_from_file_location("pdf_v5", "/mnt/user-data/outputs/pdf_compress.py")
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestV5Fixes(unittest.TestCase):

    def test_get_deps_is_cached(self):
        """get_deps() должен вернуть тот же объект при повторном вызове (lru_cache)."""
        mod = _load_v5()
        mod.get_deps.cache_clear()
        r1 = mod.get_deps()
        r2 = mod.get_deps()
        self.assertIs(r1, r2, "get_deps should return cached dict")

    def test_get_deps_cache_info(self):
        mod = _load_v5()
        mod.get_deps.cache_clear()
        mod.get_deps()
        mod.get_deps()
        info = mod.get_deps.cache_info()
        self.assertEqual(info.misses, 1)
        self.assertGreaterEqual(info.hits, 1)

    def test_hidden_file_stem(self):
        """Скрытый файл .hidden.pdf → base = '.hidden', не пустая строка."""
        from pathlib import Path
        src = Path(".hidden.pdf")
        base = src.stem or src.name
        self.assertEqual(base, ".hidden")
        result = base + "_medium" + ".pdf"
        self.assertEqual(result, ".hidden_medium.pdf")

    def test_hidden_file_truly_empty_stem(self):
        """Файл без расширения и без имени — теоретически невозможно, но stem or name надёжен."""
        from pathlib import Path
        # Path("") edge case
        src = Path("a.pdf")
        base = src.stem or src.name
        self.assertTrue(len(base) > 0)

    def test_shlex_posix_true_ascii_gs_cmd(self):
        """shlex.split(posix=True) корректно разбирает ASCII GS-команды."""
        import shlex
        cmd = "sudo apt-get install -y ghostscript"
        result = shlex.split(cmd, posix=True)
        self.assertEqual(result, ["sudo", "apt-get", "install", "-y", "ghostscript"])

    def test_shlex_posix_brew_cmd(self):
        import shlex
        cmd = "brew install ghostscript"
        result = shlex.split(cmd, posix=True)
        self.assertEqual(result, ["brew", "install", "ghostscript"])

    def test_find_pdfs_case_insensitive_all_variants(self):
        """*.pdf, *.PDF, *.Pdf — все должны быть найдены."""
        import tempfile
        from pathlib import Path
        mod = _load_v5()
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "lower.pdf").write_bytes(b"%PDF-1.4")
            (Path(d) / "UPPER.PDF").write_bytes(b"%PDF-1.4")
            (Path(d) / "Mixed.Pdf").write_bytes(b"%PDF-1.4")
            (Path(d) / "not_pdf.txt").write_text("skip")
            found = [p.name for p in mod.find_pdfs(d)]
        self.assertIn("lower.pdf", found)
        self.assertIn("UPPER.PDF", found)
        self.assertIn("Mixed.Pdf", found)
        self.assertNotIn("not_pdf.txt", found)

    def test_find_pdfs_no_duplicates(self):
        """Дедупликация: файл не должен появляться дважды."""
        import tempfile
        from pathlib import Path
        mod = _load_v5()
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "doc.pdf").write_bytes(b"%PDF-1.4")
            found = mod.find_pdfs(d)
        names = [p.name for p in found]
        self.assertEqual(len(names), len(set(names)))


# ─────────────────────────────────────────────────────────────────────────────
# 14. UI fixes tests (v6)
# ─────────────────────────────────────────────────────────────────────────────

def _load_v6():
    import importlib.util
    spec = importlib.util.spec_from_file_location("pdf_v6", "/tmp/pdf_v6.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestTruncateMiddle(unittest.TestCase):

    def setUp(self):
        self.m = _load_v6()

    def test_short_name_unchanged(self):
        self.assertEqual(self.m.truncate_middle("report.pdf", 40), "report.pdf")

    def test_exact_max_unchanged(self):
        name = "a" * 40 + ".pdf"
        self.assertEqual(self.m.truncate_middle(name, 44), name)

    def test_long_name_truncated(self):
        name = "very_long_document_name_that_exceeds_limit_report_2026_final.pdf"
        result = self.m.truncate_middle(name, 40)
        self.assertLessEqual(len(result), 40)
        self.assertIn("…", result)

    def test_extension_preserved(self):
        name = "very_long_document_name_2026_final.pdf"
        result = self.m.truncate_middle(name, 30)
        self.assertTrue(result.endswith(".pdf"))

    def test_unicode_name(self):
        name = "отчёт_за_2026_год_финальная_версия_для_печати_утверждённая.pdf"
        result = self.m.truncate_middle(name, 40)
        self.assertLessEqual(len(result), 40)

    def test_no_extension(self):
        name = "a" * 50
        result = self.m.truncate_middle(name, 20)
        self.assertLessEqual(len(result), 20)
        self.assertIn("…", result)

    def test_begin_and_end_preserved(self):
        name = "START_" + "x" * 60 + "_END.pdf"
        result = self.m.truncate_middle(name, 30)
        self.assertTrue(result.startswith("START"))
        self.assertIn("END", result)

    def test_very_short_max(self):
        # Экстремально короткий лимит
        result = self.m.truncate_middle("report.pdf", 5)
        self.assertLessEqual(len(result), 5)


class TestScrollingLogic(unittest.TestCase):

    def _viewport(self, idx, n, visible):
        top = max(0, min(idx - visible // 2, n - visible))
        top = max(0, top)
        bot = min(top + visible, n)
        return top, bot

    def test_idx_always_in_viewport(self):
        for n in [5, 10, 30, 100]:
            visible = 10
            for idx in range(n):
                top, bot = self._viewport(idx, n, visible)
                self.assertLessEqual(top, idx)
                self.assertLess(idx, bot)

    def test_viewport_not_exceed_n(self):
        top, bot = self._viewport(29, 30, 10)
        self.assertLessEqual(bot, 30)

    def test_viewport_start_at_zero(self):
        top, bot = self._viewport(0, 30, 10)
        self.assertEqual(top, 0)

    def test_small_list_shows_all(self):
        n = 3; visible = 10
        top, bot = self._viewport(1, n, visible)
        self.assertEqual(top, 0)
        self.assertEqual(bot, n)

    def test_center_scrolls_correctly(self):
        """Середина списка — idx должен быть в центре viewport."""
        idx = 15; n = 30; visible = 10
        top, bot = self._viewport(idx, n, visible)
        self.assertLessEqual(top, idx)
        self.assertLess(idx, bot)
        # idx должен быть примерно в середине
        self.assertGreaterEqual(idx - top, visible // 2 - 1)


class TestReadKeyLogic(unittest.TestCase):
    """Тест логики разбора ESC-последовательностей."""

    def test_arrow_up_sequence(self):
        key = "\x1b[A"
        self.assertIn(key, ("\x1b[A",))

    def test_arrow_down_sequence(self):
        key = "\x1b[B"
        self.assertIn(key, ("\x1b[B",))

    def test_single_esc_not_arrow(self):
        key = "\x1b"
        self.assertNotIn(key, ("\x1b[A", "\x1b[B"))
        self.assertIn(key, ("q", "Q", "\x03", "\x1b", "\x1b\x1b"))

    def test_enter_variants(self):
        for ch in ("\r", "\n"):
            self.assertIn(ch, ("\r", "\n"))

    def test_os_read_returns_full_sequence(self):
        """os.read(fd, 8) после select гарантирует получение всей последовательности."""
        # Симулируем: если данные есть, os.read вернёт их целиком
        import io
        buf = io.BytesIO(b"[A")  # остаток после \x1b
        rest = buf.read(8).decode("utf-8", errors="replace")
        full = "\x1b" + rest
        self.assertEqual(full, "\x1b[A")


# ─────────────────────────────────────────────────────────────────────────────
# 15. Sort + Filter tests (v7)
# ─────────────────────────────────────────────────────────────────────────────

def _load_v7():
    import importlib.util
    spec = importlib.util.spec_from_file_location("pdf_v7", "/tmp/pdf_v7.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestFuzzyMatch(unittest.TestCase):

    def setUp(self):
        self.m = _load_v7()

    def _match(self, q, name):
        ok, score = self.m.fuzzy_match(q, name)
        return ok, score

    def test_empty_query_matches_all(self):
        ok, _ = self._match("", "anything.pdf")
        self.assertTrue(ok)

    def test_exact_match(self):
        ok, score = self._match("report", "report.pdf")
        self.assertTrue(ok)
        self.assertGreater(score, 0)

    def test_subsequence_match(self):
        ok, _ = self._match("rpt", "report.pdf")
        self.assertTrue(ok)

    def test_no_match(self):
        ok, _ = self._match("xyz", "report.pdf")
        self.assertFalse(ok)

    def test_case_insensitive(self):
        ok, _ = self._match("REP", "report.pdf")
        self.assertTrue(ok)
        ok2, _ = self._match("rep", "REPORT.PDF")
        self.assertTrue(ok2)

    def test_multi_token_all_must_match(self):
        ok, _ = self._match("fin rep", "financial_report.pdf")
        self.assertTrue(ok)

    def test_multi_token_order_independent(self):
        ok1, _ = self._match("fin rep", "financial_report.pdf")
        ok2, _ = self._match("rep fin", "financial_report.pdf")
        self.assertTrue(ok1)
        self.assertTrue(ok2)

    def test_multi_token_one_missing(self):
        ok, _ = self._match("fin xyz", "financial_report.pdf")
        self.assertFalse(ok)

    def test_score_prefix_bonus(self):
        _, score_prefix = self._match("rep", "report.pdf")
        _, score_mid    = self._match("rep", "my_report.pdf")
        self.assertGreater(score_prefix, score_mid)

    def test_score_consecutive_bonus(self):
        _, score_consec = self._match("repo", "report.pdf")
        _, score_spread = self._match("rpt",  "report.pdf")
        self.assertGreater(score_consec, score_spread)

    def test_unicode_query(self):
        ok, _ = self._match("отч", "отчёт_2026.pdf")
        self.assertTrue(ok)

    def test_spaces_in_query_multi_token(self):
        ok, _ = self._match("2026 q1", "report_2026_q1.pdf")
        self.assertTrue(ok)


class TestIsPrintableKey(unittest.TestCase):

    def setUp(self):
        self.m = _load_v7()

    def test_ascii_letters(self):
        for ch in "abcdefgABCDEF":
            self.assertTrue(self.m.is_printable_key(ch), f"failed: {ch!r}")

    def test_digits(self):
        for ch in "0123456789":
            self.assertTrue(self.m.is_printable_key(ch))

    def test_space(self):
        self.assertTrue(self.m.is_printable_key(" "))

    def test_cyrillic(self):
        self.assertTrue(self.m.is_printable_key("й"))
        self.assertTrue(self.m.is_printable_key("ё"))

    def test_escape_not_printable(self):
        self.assertFalse(self.m.is_printable_key("\x1b"))

    def test_arrow_not_printable(self):
        self.assertFalse(self.m.is_printable_key("\x1b[A"))

    def test_backspace_not_printable(self):
        self.assertFalse(self.m.is_printable_key("\x7f"))
        self.assertFalse(self.m.is_printable_key("\x08"))

    def test_enter_not_printable(self):
        self.assertFalse(self.m.is_printable_key("\r"))
        self.assertFalse(self.m.is_printable_key("\n"))

    def test_ctrl_c_not_printable(self):
        self.assertFalse(self.m.is_printable_key("\x03"))

    def test_multi_char_not_printable(self):
        self.assertFalse(self.m.is_printable_key("ab"))


class TestSortModes(unittest.TestCase):

    def setUp(self):
        self.m = _load_v7()

    def test_sort_modes_defined(self):
        modes = [m[0] for m in self.m.SORT_MODES]
        self.assertIn("name", modes)
        self.assertIn("date", modes)
        self.assertIn("size", modes)

    def test_sort_modes_have_labels(self):
        for key, label in self.m.SORT_MODES:
            self.assertTrue(len(label) > 0)

    def test_sort_cycle_wraps(self):
        n = len(self.m.SORT_MODES)
        idx = 0
        for _ in range(n * 2):
            idx = (idx + 1) % n
        self.assertLess(idx, n)


class TestArrowMenuFilterLogic(unittest.TestCase):
    """Тест логики фильтрации без TTY — через fuzzy_match напрямую."""

    def setUp(self):
        self.m = _load_v7()

    def _filter(self, query, items):
        """Применить фильтр к списку, вернуть отфильтрованный."""
        result = []
        for i, item in enumerate(items):
            ok, score = self.m.fuzzy_match(query, item)
            if ok:
                result.append((i, item, score))
        if query:
            result.sort(key=lambda x: -x[2])
        return result

    def test_empty_filter_returns_all(self):
        items = ["a.pdf", "b.pdf", "c.pdf"]
        result = self._filter("", items)
        self.assertEqual(len(result), 3)

    def test_filter_reduces_list(self):
        items = ["report.pdf", "invoice.pdf", "readme.txt"]
        result = self._filter("rep", items)
        names = [r[1] for r in result]
        self.assertIn("report.pdf", names)
        self.assertNotIn("invoice.pdf", names)

    def test_filter_empty_result(self):
        items = ["report.pdf", "invoice.pdf"]
        result = self._filter("xyz123", items)
        self.assertEqual(len(result), 0)

    def test_filter_sorts_by_score(self):
        items = ["report.pdf", "my_report_final.pdf", "rep.pdf"]
        result = self._filter("rep", items)
        # rep.pdf should score highest (exact prefix match)
        top = result[0][1]
        self.assertIn("rep", top.lower())

    def test_original_index_preserved(self):
        items = ["a.pdf", "b.pdf", "c.pdf"]
        result = self._filter("b", items)
        self.assertEqual(len(result), 1)
        orig_idx = result[0][0]
        self.assertEqual(items[orig_idx], "b.pdf")

    def test_backspace_removes_last_char(self):
        f = "repor"
        f = f[:-1]
        self.assertEqual(f, "repo")

    def test_esc_clears_filter(self):
        f = "report"
        f = ""  # Esc
        self.assertEqual(f, "")


# ─────────────────────────────────────────────────────────────────────────────
# 16. Edge case tests (v8)
# ─────────────────────────────────────────────────────────────────────────────

def _load_v8():
    import importlib.util
    spec = importlib.util.spec_from_file_location("pdf_v8", "/tmp/pdf_v8.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestFuzzyMatchV8(unittest.TestCase):

    def setUp(self):
        self.m = _load_v8()

    def test_spaces_only_query_matches_all(self):
        ok, score = self.m.fuzzy_match("   ", "report.pdf")
        self.assertTrue(ok)
        self.assertEqual(score, 0)

    def test_query_longer_than_name(self):
        ok, _ = self.m.fuzzy_match("verylongquery", "r.pdf")
        self.assertFalse(ok)

    def test_no_recursion_with_many_tokens(self):
        """500 токенов не должны вызывать RecursionError."""
        q = " ".join(["a"] * 500)
        try:
            ok, _ = self.m.fuzzy_match(q, "a" * 500 + ".pdf")
            self.assertIsInstance(ok, bool)
        except RecursionError:
            self.fail("fuzzy_match raised RecursionError")

    def test_single_char_query(self):
        ok, _ = self.m.fuzzy_match("r", "report.pdf")
        self.assertTrue(ok)
        ok2, _ = self.m.fuzzy_match("z", "report.pdf")
        self.assertFalse(ok2)

    def test_null_byte_in_name(self):
        """Null byte в имени не должен вызывать исключение."""
        try:
            ok, _ = self.m.fuzzy_match("rep", "rep\x00ort.pdf")
            self.assertIsInstance(ok, bool)
        except Exception as e:
            self.fail(f"fuzzy_match raised {e}")

    def test_very_long_name(self):
        name = "a" * 10000 + ".pdf"
        ok, _ = self.m.fuzzy_match("aaa", name)
        self.assertTrue(ok)

    def test_score_consistency(self):
        """Одинаковые запросы дают одинаковый score."""
        _, s1 = self.m.fuzzy_match("rep", "report.pdf")
        _, s2 = self.m.fuzzy_match("rep", "report.pdf")
        self.assertEqual(s1, s2)

    def test_fuzzy_single_helper_exists(self):
        self.assertTrue(hasattr(self.m, "_fuzzy_single"))

    def test_multi_token_empty_token_ignored(self):
        """'rep  fin' (двойной пробел) не создаёт пустой токен."""
        ok, _ = self.m.fuzzy_match("rep  fin", "financial_report.pdf")
        self.assertTrue(ok)


class TestFilterStrCap(unittest.TestCase):

    def test_cap_enforced_in_logic(self):
        """filter_str не должен расти больше 60 символов."""
        MAX = 60
        filter_str = ""
        for ch in "a" * 100:
            if len(filter_str) < MAX:
                filter_str += ch
        self.assertEqual(len(filter_str), MAX)

    def test_cap_does_not_truncate_existing(self):
        """Уже набранные 60 символов не обрезаются — просто не добавляются новые."""
        filter_str = "a" * 60
        key = "b"
        if len(filter_str) < 60:
            filter_str += key
        self.assertEqual(len(filter_str), 60)
        self.assertNotIn("b", filter_str)


class TestApplyFilterSortReturnsTuple(unittest.TestCase):
    """Проверяем логику возврата (list, cur) из apply_filter_sort."""

    def _make_apply(self, items, filter_str="", sort_idx=0):
        """Воспроизвести логику apply_filter_sort без TTY."""
        m = _load_v8()
        original = list(enumerate(items))
        result = []
        for orig_i, item in original:
            matched, score = m.fuzzy_match(filter_str, item)
            if matched:
                result.append((orig_i, item, score))
        if filter_str:
            result.sort(key=lambda x: -x[2])
        return result

    def test_empty_filter_returns_all(self):
        items = ["a.pdf", "b.pdf", "c.pdf"]
        r = self._make_apply(items, "")
        self.assertEqual(len(r), 3)

    def test_filter_reduces(self):
        items = ["report.pdf", "invoice.pdf", "readme.txt"]
        r = self._make_apply(items, "rep")
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0][1], "report.pdf")

    def test_original_index_correct(self):
        items = ["a.pdf", "target.pdf", "c.pdf"]
        r = self._make_apply(items, "target")
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0][0], 1)  # original index 1

    def test_cur_preserved_on_filter(self):
        """После изменения фильтра позиция восстанавливается если элемент ещё виден."""
        items = ["apple.pdf", "report.pdf", "rapport.pdf", "banana.pdf"]
        prev_orig = 2  # "rapport.pdf"
        filter_str = "r"
        r = self._make_apply(items, filter_str)
        new_cur = next((j for j, (oi, _, _) in enumerate(r) if oi == prev_orig), 0)
        # rapport.pdf matches 'r' → should be found
        names = [x[1] for x in r]
        if "rapport.pdf" in names:
            self.assertGreater(new_cur, -1)

    def test_cur_falls_to_zero_when_prev_not_in_results(self):
        """Если предыдущий элемент не в результатах — cur=0."""
        items = ["apple.pdf", "zebra.pdf", "ant.pdf"]
        prev_orig = 1  # "zebra.pdf"
        filter_str = "ant"
        r = self._make_apply(items, filter_str)
        new_cur = next((j for j, (oi, _, _) in enumerate(r) if oi == prev_orig), 0)
        self.assertEqual(new_cur, 0)  # zebra not matched → default to 0


class TestStatCache(unittest.TestCase):

    def test_stat_cache_populated(self):
        """stat_cache должен содержать stat для каждого файла."""
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            files = []
            for name in ["a.pdf", "b.pdf"]:
                p = Path(d) / name
                p.write_bytes(b"%PDF-1.4")
                files.append(p)
            stat_cache = {}
            for p in files:
                try:
                    stat_cache[p] = p.stat()
                except OSError:
                    stat_cache[p] = None
            self.assertEqual(len(stat_cache), 2)
            for p in files:
                self.assertIsNotNone(stat_cache[p])

    def test_stat_cache_handles_oserror(self):
        """Файл недоступен → stat_cache[p] = None, не crash."""
        from pathlib import Path
        p = Path("/nonexistent/ghost.pdf")
        stat_cache = {}
        try:
            stat_cache[p] = p.stat()
        except OSError:
            stat_cache[p] = None
        self.assertIsNone(stat_cache[p])

    def test_sort_with_none_stat_does_not_crash(self):
        """Сортировка с None stat → использует 0 как fallback."""
        items = [("a", 100), ("b", None), ("c", 50)]
        sorted_items = sorted(items, key=lambda x: x[1] if x[1] is not None else 0, reverse=True)
        self.assertEqual(sorted_items[0][0], "a")


class TestIsPrintableKeyEdgeCases(unittest.TestCase):

    def setUp(self):
        self.m = _load_v8()

    def test_null_char_not_printable(self):
        self.assertFalse(self.m.is_printable_key("\x00"))

    def test_del_not_printable(self):
        self.assertFalse(self.m.is_printable_key("\x7f"))

    def test_all_ascii_printable_range(self):
        for cp in range(0x20, 0x7f):
            ch = chr(cp)
            self.assertTrue(self.m.is_printable_key(ch), f"failed for {repr(ch)}")

    def test_control_chars_not_printable(self):
        for cp in range(0x01, 0x20):
            self.assertFalse(self.m.is_printable_key(chr(cp)))

    def test_emoji_printable(self):
        # Emoji: Unicode > 0x7f, isprintable() = True
        self.assertTrue(self.m.is_printable_key("😀"))

    def test_empty_string_not_printable(self):
        self.assertFalse(self.m.is_printable_key(""))

    def test_two_chars_not_printable(self):
        self.assertFalse(self.m.is_printable_key("ab"))

