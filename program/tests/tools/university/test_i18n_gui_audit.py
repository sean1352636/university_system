"""Tests for the university GUI internationalization audit."""

import ast
import json

from tools.university import i18n_gui_audit


def test_externalize_wraps_supported_gui_text_and_is_idempotent(tmp_path):
    source = tmp_path / "sample_gui.py"
    source.write_text(
        '"""Example GUI."""\n'
        "from __future__ import annotations\n"
        "from tkinter import messagebox, ttk\n\n"
        "def build(root):\n"
        "    root.title(\"Student records\")\n"
        "    ttk.Label(root, text=\"Student name:\")\n"
        "    messagebox.showerror(\"Error\", \"Record not found\")\n"
        "    query = \"SELECT name FROM students\"\n"
        "    return query\n",
        encoding="utf-8",
    )

    assert i18n_gui_audit.externalize(source) == 4
    transformed = source.read_text(encoding="utf-8")
    ast.parse(transformed)
    assert i18n_gui_audit.IMPORT in transformed
    assert transformed.count("_t(\"gui.auto.") == 4
    assert 'query = "SELECT name FROM students"' in transformed
    assert i18n_gui_audit.externalize(source) == 0
    assert i18n_gui_audit.scan(tmp_path) == []


def test_scan_reports_only_untranslated_supported_sinks(tmp_path):
    source = tmp_path / "sample_gui.py"
    source.write_text(
        "def build(ttk, logger):\n"
        "    ttk.Button(text='Save')\n"
        "    logger.info('Save clicked')\n",
        encoding="utf-8",
    )

    uncovered = i18n_gui_audit.scan(tmp_path)

    assert [(item.line, item.text) for item in uncovered] == [(2, "Save")]


def test_catalog_export_preserves_existing_locale_values(tmp_path):
    source_root = tmp_path / "gui"
    source_root.mkdir()
    (source_root / "sample.py").write_text(
        'label = _t("gui.auto.abc123", default="Save")\n', encoding="utf-8"
    )
    catalog = tmp_path / "locales" / "es" / "gui_auto.json"
    catalog.parent.mkdir(parents=True)
    catalog.write_text(
        json.dumps({"gui": {"auto": {"abc123": "Guardar"}}}), encoding="utf-8"
    )

    entries = i18n_gui_audit.catalog_entries(source_root)
    added = i18n_gui_audit.merge_catalog(catalog, entries)

    assert entries == {"gui.auto.abc123": "Save"}
    assert added == 0
    assert json.loads(catalog.read_text(encoding="utf-8"))["gui"]["auto"] == {
        "abc123": "Guardar"
    }


def test_semanticize_uses_module_context_and_readable_text(tmp_path):
    gui_root = tmp_path / "gui"
    source = gui_root / "staff" / "grievance_gui.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "def build(ttk):\n"
        "    ttk.Label(text=_t('gui.auto.abc123', default='Status:'))\n"
        "    ttk.Button(text=_t('gui.auto.def456', default='Save changes'))\n",
        encoding="utf-8",
    )
    locale_root = tmp_path / "locales"
    for language in ("en", "es"):
        catalog = locale_root / language / "gui_auto.json"
        catalog.parent.mkdir(parents=True)
        catalog.write_text(
            json.dumps(
                {
                    "gui": {
                        "auto": {
                            "abc123": "Estado:" if language == "es" else "Status:",
                            "def456": "Guardar cambios" if language == "es" else "Save changes",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

    occurrences, keys = i18n_gui_audit.semanticize(gui_root, locale_root)

    transformed = source.read_text(encoding="utf-8")
    assert occurrences == keys == 2
    assert "gui.staff.grievance.labels.status" in transformed
    assert "gui.staff.grievance.buttons.save_changes" in transformed
    spanish = json.loads(
        (locale_root / "es" / "gui_auto.json").read_text(encoding="utf-8")
    )
    assert "auto" not in spanish["gui"]
    assert spanish["gui"]["staff"]["grievance"]["labels"]["status"] == "Estado:"
    assert (
        spanish["gui"]["staff"]["grievance"]["buttons"]["save_changes"]
        == "Guardar cambios"
    )
