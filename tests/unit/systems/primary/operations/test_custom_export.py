"""Custom Export (systems.primary.domain.operations.reporting.custom_export.custom_export).

The button tests check every dataset returns its declared columns; these
check the engine: filters, column choice, each output format's exact
content, file export and its result figures. Files go only under tmp_path.
"""

from __future__ import annotations

import csv
import io
import json
from types import SimpleNamespace

import pytest

from education_system.systems.primary.domain.academics.attendance import attendance as ATT
from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.operations.reporting.custom_export import (
    custom_export as CE,
)
from education_system.systems.primary.domain.pastoral.behaviour import behaviour as BH

MON, TUE, WED = "2030-01-07", "2030-01-08", "2030-01-09"
COLS = ["pupil_id", "first_name", "year_group"]


def _pupil(first, last, year, **extra):
    return P.create_pupil({"first_name": first, "last_name": last, "year_group": year,
                           "date_of_birth": "2019-01-01", **extra})


def _school():
    """Two pupils in list order (year group, then surname)."""
    return _pupil("Ann", "Zed", "2"), _pupil("Bob", "Young", "5", send_status="yes")


# ── cell helpers ──

def test_get_reads_dicts_objects_and_dotted_paths():
    row = SimpleNamespace(a=1, inner={"b": SimpleNamespace(c="deep")}, none=None)
    assert CE._get(row, "a") == 1
    assert CE._get(row, "inner.b.c") == "deep"
    assert CE._get(row, "none.x") is None
    assert CE._get(row, "missing") is None
    assert CE._get({"k": {"j": 2}}, "k.j") == 2


def test_stringify_and_json_safe():
    assert [CE._stringify(v) for v in (None, True, False, [1, None, "x"], 2.5)] == \
        ["", "true", "false", "1, , x", "2.5"]
    obj = SimpleNamespace(x=1)
    assert CE._json_safe({"a": (1, None), "b": {2}, "c": obj}) == \
        {"a": [1, None], "b": [2], "c": str(obj)}


# ── registry ──

def test_list_datasets_sorted_by_label():
    labels = [d.label for d in CE.list_datasets()]
    assert labels == sorted(labels, key=str.lower)
    assert "pupils" in {d.key for d in CE.list_datasets()}


def test_get_dataset_unknown():
    with pytest.raises(CE.ValidationError, match="Unknown dataset 'nope'. Try one of: "):
        CE.get_dataset("nope")


# ── fetch / filters ──

def test_fetch_attendance_filters_and_limit():
    a, b = _school()
    for p in (a, b):
        for d in (MON, TUE, WED):
            ATT.record_mark(p.pupil_id, d, "AM", "P")
    rows = CE.fetch("attendance", filters={"pupil_id": a.pupil_id, "date_from": TUE})
    assert [(r.pupil_id, r.date) for r in rows] == [(a.pupil_id, WED), (a.pupil_id, TUE)]
    assert len(CE.fetch("attendance")) == 6
    assert len(CE.fetch("attendance", limit=4)) == 4


def test_fetch_ignores_unknown_and_blank_filters():
    _school()
    assert len(CE.fetch("pupils", filters={"year_group": "5"})) == 2   # not a pupils filter
    a, b = _school()
    ATT.record_mark(a.pupil_id, MON, "AM", "P")
    assert len(CE.fetch("attendance", filters={"pupil_id": "", "colour": "red"})) == 1


def test_fetch_behaviour_filters():
    a, b = _school()
    BH.log_incident({"pupil_id": a.pupil_id, "incident_type": "Achievement",
                     "incident_date": MON, "description": "x"})
    BH.log_incident({"pupil_id": b.pupil_id, "incident_type": "Disruption",
                     "incident_date": TUE, "description": "y", "severity": "High"})
    assert [r.pupil_id for r in CE.fetch("behaviour", filters={"severity": "High"})] == \
        [b.pupil_id]
    assert [r.incident_date for r in CE.fetch("behaviour", filters={"date_to": MON})] == [MON]


# ── render ──

def test_render_csv_selected_columns():
    a, b = _school()
    text = CE.render("pupils", columns=COLS)
    assert list(csv.reader(io.StringIO(text))) == [
        ["Pupil ID", "First name", "Year"], [a.pupil_id, "Ann", "2"], [b.pupil_id, "Bob", "5"]]


def test_render_tsv_and_free_form_column():
    a, _ = _school()
    text = CE.render("pupils", fmt=" TSV ", columns=["first_name", "full_name", " "], limit=1)
    assert text == "First name\tfull_name\nAnn\tAnn Zed\n"


def test_render_json_and_jsonl():
    a, b = _school()
    data = json.loads(CE.render("pupils", fmt="json", columns=["pupil_id", "send_status"]))
    assert data == [{"Pupil ID": a.pupil_id, "SEND": None},
                    {"Pupil ID": b.pupil_id, "SEND": "yes"}]
    lines = CE.render("pupils", fmt="jsonl", columns=["first_name"]).splitlines()
    assert [json.loads(x) for x in lines] == [{"First name": "Ann"}, {"First name": "Bob"}]


def test_render_markdown_escapes_pipes_and_newlines():
    _pupil("Pip|Pop", "Line", "1", medical_notes="Asthma\nInhaler in bag")
    text = CE.render("pupils", fmt="markdown", columns=["first_name", "medical_notes"])
    assert text == ("| First name | Medical notes |\n|---|---|\n"
                    "| Pip\\|Pop | Asthma ⏎ Inhaler in bag |\n")


def test_render_full_column_set_by_default():
    _school()
    header = CE.render("pupils").splitlines()[0]
    assert header.split(",") == [h for _, h in CE.get_dataset("pupils").columns]


def test_render_refusals():
    with pytest.raises(CE.ValidationError, match="Format must be one of"):
        CE.render("pupils", fmt="xlsx")
    with pytest.raises(CE.ValidationError, match="No columns selected"):
        CE.render("pupils", columns=["  "])


def test_render_empty_dataset_is_header_only():
    assert CE.render("pupils", columns=COLS) == "Pupil ID,First name,Year\n"
    assert CE.render("pupils", fmt="json", columns=COLS) == "[]\n"


# ── export ──

@pytest.mark.parametrize("name,fmt", [("out.csv", "csv"), ("out.tsv", "tsv"),
                                      ("out.json", "json"), ("out.jsonl", "jsonl"),
                                      ("out.md", "markdown"), ("out.txt", "csv")])
def test_export_detects_format_and_counts(tmp_path, name, fmt):
    _school()
    path = tmp_path / "deep" / name
    res = CE.export("pupils", path, columns=COLS)
    assert (res.dataset_key, res.fmt, res.row_count, res.column_count, res.path) == \
        ("pupils", fmt, 2, 3, str(path))
    assert path.read_text(encoding="utf-8") == CE.render("pupils", fmt=fmt, columns=COLS)
    assert res.bytes_written == len(path.read_bytes())


def test_export_explicit_format_and_filters(tmp_path):
    a, b = _school()
    ATT.record_mark(a.pupil_id, MON, "AM", "I")
    ATT.record_mark(b.pupil_id, MON, "AM", "P")
    res = CE.export("attendance", tmp_path / "att.data", fmt="json",
                    columns=["pupil_id", "mark", "category"],
                    filters={"pupil_id": a.pupil_id})
    assert res.fmt == "json" and res.row_count == 1
    assert json.loads((tmp_path / "att.data").read_text(encoding="utf-8")) == \
        [{"Pupil": a.pupil_id, "Mark": "I", "Category": "auth_absent"}]


def test_export_row_count_with_multiline_cell(tmp_path):
    _pupil("Ann", "Zed", "2", medical_notes="Asthma\nInhaler in bag")
    res = CE.export("pupils", tmp_path / "p.csv", columns=["first_name", "medical_notes"])
    assert res.row_count == 1


def test_export_bytes_written_counts_bytes(tmp_path):
    _pupil("Zoë", "Brontë", "3")
    path = tmp_path / "p.csv"
    res = CE.export("pupils", path, columns=["first_name", "last_name"])
    assert res.bytes_written == len(path.read_bytes())


def test_export_unknown_dataset_writes_nothing(tmp_path):
    with pytest.raises(CE.ValidationError, match="Unknown dataset"):
        CE.export("ghosts", tmp_path / "x.csv")
    assert list(tmp_path.iterdir()) == []


# ── preview ──

def test_preview_headers_and_rows():
    a, b = _school()
    headers, rows = CE.preview("pupils", columns=COLS, limit=1)
    assert headers == ["Pupil ID", "First name", "Year"]
    assert rows == [[a.pupil_id, "Ann", "2"]]
    spec = CE.get_dataset("pupils")
    assert len(CE.preview(spec)[1]) == 2
