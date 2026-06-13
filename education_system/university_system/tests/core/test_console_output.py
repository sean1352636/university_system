"""Tests for modules.shared.utils.console_output."""
from unittest.mock import patch

import pytest

from education_system.university_system.modules.shared.utils.console_output import (
    Colors,
    ConsoleOutput,
)


@pytest.fixture
def co():
    """Console output with colors disabled — produces plain text we can assert on."""
    return ConsoleOutput(use_colors=False)


@pytest.fixture
def co_colors():
    """Force-enable colors regardless of TTY for color-output testing."""
    inst = ConsoleOutput.__new__(ConsoleOutput)
    inst.use_colors = True
    return inst


class TestColors:
    def test_codes_are_ansi_escape(self):
        assert Colors.RED.startswith("\033[")
        assert Colors.RESET == "\033[0m"

    def test_supports_color_no_isatty(self):
        with patch("sys.stdout", new_callable=lambda: object()):
            assert Colors.supports_color() is False


class TestColorize:
    def test_colorize_disabled_returns_plain(self, co):
        assert co._colorize("hello", Colors.RED) == "hello"

    def test_colorize_enabled_wraps(self, co_colors):
        assert co_colors._colorize("hello", Colors.RED) == f"{Colors.RED}hello{Colors.RESET}"


class TestBasicOutput:
    def test_print_plain(self, co, capsys):
        co.print("hi")
        assert capsys.readouterr().out == "hi\n"

    def test_print_with_color_disabled(self, co, capsys):
        co.print("hi", color=Colors.RED)
        # Colors are disabled, plain text emitted
        assert capsys.readouterr().out == "hi\n"

    def test_success(self, co, capsys):
        co.success("done")
        out = capsys.readouterr().out
        assert "✓" in out
        assert "done" in out

    def test_error(self, co, capsys):
        co.error("oops")
        out = capsys.readouterr().out
        assert "✗" in out
        assert "oops" in out

    def test_warning(self, co, capsys):
        co.warning("hmm")
        out = capsys.readouterr().out
        assert "⚠" in out
        assert "hmm" in out

    def test_info(self, co, capsys):
        co.info("fyi")
        out = capsys.readouterr().out
        assert "ℹ" in out
        assert "fyi" in out

    def test_no_prefix(self, co, capsys):
        co.success("x", prefix="")
        out = capsys.readouterr().out.strip()
        assert out == "x"


class TestFormattedOutput:
    def test_header_includes_title(self, co, capsys):
        co.header("My Title", width=40)
        out = capsys.readouterr().out
        assert "My Title" in out
        # Two equals-borders
        assert out.count("=" * 40) == 2

    def test_section_includes_title(self, co, capsys):
        co.section("Step 1", width=20)
        out = capsys.readouterr().out
        assert "Step 1" in out
        assert "-" * 20 in out

    def test_box_renders_border(self, co, capsys):
        co.box("hello world", width=20)
        out = capsys.readouterr().out
        assert "╔" in out and "╗" in out
        assert "╚" in out and "╝" in out
        assert "hello world" in out

    def test_box_handles_multiline(self, co, capsys):
        co.box("line1\nline2", width=20)
        out = capsys.readouterr().out
        assert "line1" in out
        assert "line2" in out

    def test_status_shows_label_and_value(self, co, capsys):
        co.status("DB", "ready", success=True)
        out = capsys.readouterr().out
        assert "DB" in out
        assert "ready" in out


class TestProgress:
    def test_at_zero(self, co, capsys):
        co.progress(0, 10, label="loading", width=10)
        out = capsys.readouterr().out
        assert "0.0%" in out
        assert "0/10" in out

    def test_at_completion_emits_newline(self, co, capsys):
        co.progress(10, 10, width=10)
        out = capsys.readouterr().out
        assert "100.0%" in out
        # newline appended when complete
        assert out.endswith("\n")

    def test_handles_zero_total(self, co, capsys):
        # Should not raise ZeroDivisionError
        co.progress(0, 0, width=10)
        out = capsys.readouterr().out
        assert "0.0%" in out


class TestTable:
    def test_renders_rows_and_headers(self, co, capsys):
        co.table(["A", "B"], [[1, 2], [3, 4]])
        out = capsys.readouterr().out
        assert "A" in out and "B" in out
        assert "1" in out and "4" in out
        # Border chars present
        assert "┌" in out and "└" in out

    def test_empty_rows_emits_warning(self, co, capsys):
        co.table(["A"], [])
        out = capsys.readouterr().out
        assert "No data" in out

    def test_with_title(self, co, capsys):
        co.table(["A"], [[1]], title="My Table")
        out = capsys.readouterr().out
        assert "My Table" in out


class TestSimpleTable:
    def test_renders_data(self, co, capsys):
        co.simple_table(["A", "B"], [["x", "y"]])
        out = capsys.readouterr().out
        assert "A" in out and "B" in out
        assert "x" in out and "y" in out

    def test_empty_rows_emits_warning(self, co, capsys):
        co.simple_table(["A"], [])
        out = capsys.readouterr().out
        assert "No data" in out


class TestKeyValueList:
    def test_renders_pairs(self, co, capsys):
        co.key_value_list({"name": "alice", "age": 30})
        out = capsys.readouterr().out
        assert "name" in out and "alice" in out
        assert "age" in out and "30" in out

    def test_with_title(self, co, capsys):
        co.key_value_list({"k": "v"}, title="Stats")
        out = capsys.readouterr().out
        assert "Stats" in out

    def test_empty_dict(self, co, capsys):
        # Should not crash on empty data
        co.key_value_list({})
        # Just verify no exception; output may be minimal
        capsys.readouterr()


class TestBanner:
    def test_default_style(self, co, capsys):
        co.banner("Welcome", width=40)
        out = capsys.readouterr().out
        assert "Welcome" in out
        # Double-line border default
        assert "╔" in out and "╗" in out

    def test_single_style(self, co, capsys):
        co.banner("Hi", width=20, style="single")
        out = capsys.readouterr().out
        assert "┌" in out

    def test_bold_style(self, co, capsys):
        co.banner("Hi", width=20, style="bold")
        out = capsys.readouterr().out
        assert "┏" in out

    def test_unknown_style_falls_back_to_single(self, co, capsys):
        co.banner("Hi", width=20, style="unknown_style")
        out = capsys.readouterr().out
        assert "┌" in out


class TestMenu:
    def test_numbered_options(self, co, capsys):
        co.menu("Main", ["one", "two", "three"])
        out = capsys.readouterr().out
        assert "Main" in out
        assert "[1]" in out and "[2]" in out and "[3]" in out
        assert "one" in out and "three" in out

    def test_unnumbered_options(self, co, capsys):
        co.menu("Main", ["a", "b"], show_numbers=False)
        out = capsys.readouterr().out
        assert "[1]" not in out
        assert "•" in out
