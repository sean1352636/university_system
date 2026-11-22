"""Bulk operations (domain.learners.pupils.bulk_operations): CSV import/export, bulk edits."""

from __future__ import annotations

import csv

import pytest

from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.learners.pupils.bulk_operations import (
    bulk_operations as BO,
)


def _pupil(first="Ada", year="3", **extra):
    return P.create_pupil({"first_name": first, "last_name": "Test", "year_group": year,
                           **extra})


def _csv(path, header, *rows):
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return path


# ── BulkResult ───────────────────────────────────────────────────────

def test_bulk_result_ok_needs_work_and_no_failures():
    r = BO.BulkResult()
    assert r.ok is False
    r.processed, r.succeeded = 2, 2
    assert r.ok is True
    r.add_error(3, "bad", {"x": "1"})
    assert r.ok is False and r.failed == 1
    assert r.errors[0] == BO.RowError(3, "bad", {"x": "1"})


# ── import ───────────────────────────────────────────────────────────

def test_import_creates_pupils_and_reports_line_numbers(tmp_path):
    f = _csv(tmp_path / "in.csv",
             "First Name,Last Name,Year Group,Class Name,Send Status",
             "Ada,Lovelace,3,3A,YES",
             "Bad,Year,9,,",
             ",,,,",
             "Bo,Bee,R,,")
    r = BO.import_pupils_csv(f)
    assert (r.processed, r.succeeded, r.failed) == (3, 2, 1)
    assert r.errors[0].row_number == 3 and "Year group" in r.errors[0].message
    assert r.errors[0].raw["first_name"] == "Bad"
    made = [P.get_pupil(pid) for pid in r.created_ids]
    assert [(p.full_name, p.year_group, p.class_name, p.send_status) for p in made] == [
        ("Ada Lovelace", "3", "3A", "yes"), ("Bo Bee", "R", None, None)]
    assert r.ok is False


def test_import_handles_a_bom_and_extra_columns(tmp_path):
    f = tmp_path / "bom.csv"
    f.write_text("﻿first_name,last_name,year_group,favourite_colour\nA,B,1,red\n",
                 encoding="utf-8")
    r = BO.import_pupils_csv(f)
    assert r.ok and r.succeeded == 1


def test_import_refuses_missing_required_columns(tmp_path):
    f = _csv(tmp_path / "in.csv", "first_name,last_name", "A,B")
    with pytest.raises(P.ValidationError, match="missing required column\\(s\\): year_group"):
        BO.import_pupils_csv(f)
    assert P.list_pupils() == []


def test_import_refuses_missing_file_folder_and_empty_file(tmp_path):
    with pytest.raises(P.ValidationError, match="CSV file not found"):
        BO.import_pupils_csv(tmp_path / "nope.csv")
    with pytest.raises(P.ValidationError, match="Not a file"):
        BO.import_pupils_csv(tmp_path)
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(P.ValidationError, match="no header row"):
        BO.import_pupils_csv(empty)


def test_import_with_only_a_header_processes_nothing(tmp_path):
    r = BO.import_pupils_csv(_csv(tmp_path / "in.csv", "first_name,last_name,year_group"))
    assert (r.processed, r.succeeded, r.failed, r.ok) == (0, 0, 0, False)


# ── export ───────────────────────────────────────────────────────────

def test_export_writes_the_roll_with_blank_for_none(tmp_path):
    a = _pupil("Ada", class_name="3A", parent_phone="01234 567890")
    gone = _pupil("Gus")
    P.set_roll_status(gone.pupil_id, "left")
    out = tmp_path / "sub" / "out.csv"
    assert BO.export_pupils_csv(out) == 1
    with out.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert list(rows[0]) == list(BO.EXPORT_COLUMNS)
    assert rows[0]["pupil_id"] == a.pupil_id and rows[0]["email"] == a.email
    assert rows[0]["class_name"] == "3A" and rows[0]["parent_phone"] == "01234 567890"
    assert rows[0]["date_of_birth"] == "" and rows[0]["send_status"] == ""


def test_export_given_pupils_and_empty(tmp_path):
    a, _b = _pupil("A"), _pupil("B")
    assert BO.export_pupils_csv(tmp_path / "one.csv", pupils=[a]) == 1
    assert BO.export_pupils_csv(tmp_path / "none.csv", pupils=[]) == 0
    assert (tmp_path / "none.csv").read_text(encoding="utf-8").strip() == ",".join(
        BO.EXPORT_COLUMNS)


def test_export_then_import_round_trips(tmp_path):
    _pupil("Ada", class_name="3A", send_status="yes")
    BO.export_pupils_csv(tmp_path / "x.csv")
    r = BO.import_pupils_csv(tmp_path / "x.csv")
    assert r.ok and r.succeeded == 1
    copy = P.get_pupil(r.created_ids[0])
    assert (copy.first_name, copy.class_name, copy.send_status) == ("Ada", "3A", "yes")


# ── bulk update ──────────────────────────────────────────────────────

def test_bulk_update_year_group_keeps_other_fields():
    a = _pupil("A", class_name="3A", medical_notes="Asthma")
    b = _pupil("B")
    r = BO.bulk_update([a.pupil_id, " ", b.pupil_id, "P0000000"], "year_group", " 4 ")
    assert (r.processed, r.succeeded, r.failed) == (3, 2, 1)
    assert r.errors[0].row_number == 3 and "No pupil with id P0000000" in r.errors[0].message
    got = P.get_pupil(a.pupil_id)
    assert got.year_group == "4" and got.class_name == "3A" and got.medical_notes == "Asthma"


def test_bulk_update_class_and_send_status():
    a = _pupil("A", class_name="3A", send_status="yes")
    BO.bulk_update([a.pupil_id], "class_name", "3B")
    assert P.get_pupil(a.pupil_id).class_name == "3B"
    BO.bulk_update([a.pupil_id], "class_name", "")
    assert P.get_pupil(a.pupil_id).class_name is None
    BO.bulk_update([a.pupil_id], "send_status", "NO")
    assert P.get_pupil(a.pupil_id).send_status == "no"
    BO.bulk_update([a.pupil_id], "send_status", "")
    assert P.get_pupil(a.pupil_id).send_status is None


@pytest.mark.parametrize("field,value,message", [
    ("first_name", "X", "not bulk-updatable"),
    ("year_group", "", "Year group cannot be blank"),
    ("year_group", "7", "Year group must be one of"),
    ("send_status", "maybe", "SEND status must be"),
])
def test_bulk_update_refuses_bad_field_or_value_up_front(field, value, message):
    a = _pupil("A")
    with pytest.raises(P.ValidationError, match=message):
        BO.bulk_update([a.pupil_id], field, value)
    assert P.get_pupil(a.pupil_id).year_group == "3"


def test_bulk_update_with_no_ids_does_nothing():
    r = BO.bulk_update([], "class_name", "3A")
    assert (r.processed, r.succeeded, r.ok) == (0, 0, False)


# ── bulk delete ──────────────────────────────────────────────────────

def test_bulk_delete_counts_deleted_and_missing():
    a, b = _pupil("A"), _pupil("B")
    r = BO.bulk_delete([a.pupil_id, "", "P0000000", b.pupil_id])
    assert (r.processed, r.succeeded, r.failed) == (3, 2, 1)
    assert r.errors[0].raw == {"pupil_id": "P0000000"}
    assert P.list_pupils(include_off_roll=True) == []
