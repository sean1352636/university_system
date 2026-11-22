"""Data Export (modules.reporting.domain.data_export) on a scratch DB."""

from __future__ import annotations

import csv
import json
import zipfile

import pytest

from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
from education_system.systems.secondary.modules.reporting.domain import data_export as DX
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="dx_teacher", role="teacher")


@pytest.fixture(autouse=True)
def scratch(tmp_path):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    yield tmp_path
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


_n = 0


def _pupil(year=8, form="8A", **extra):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Pupil{_n}", "legal_last_name": f"Test{_n:03d}",
        "date_of_birth": f"{2026 - year - 4}-01-15", "gender": "Female", "year_group": year,
        "form_group": form, "admission_date": "2024-09-01", **extra}, actor=ADMIN)


@pytest.fixture
def school():
    from education_system.platform.identity.auth.core import UserAuth
    from education_system.systems.secondary import SYSTEM_KEY
    UserAuth(db_path=accounts._override).provision_user(
        "dx_teacher", "Teach!ng-Pass-123", display_name="Mr Data", email="d@school.org",
        systems=[(SYSTEM_KEY, "teacher")])
    maths = S.create({"code": "MATH", "name": "Mathematics"}, actor=ADMIN)
    g = TG.create({"code": "8x/Ma1", "subject_id": maths.subject_id, "year_group": 8,
                   "teacher_username": "dx_teacher"}, actor=ADMIN)
    mine = _pupil(legal_last_name="=HYPERLINK(\"x\")")
    other = _pupil(form="8B")
    y9 = _pupil(year=9, form="9A")
    TG.add_pupils([mine.pupil_id], g.group_id, actor=ADMIN)
    C.add_contact(mine.pupil_id, {"full_name": "Mum", "relationship": "Mother",
                                  "email": "mum@x.org"}, actor=ADMIN)
    for p in (mine, other):
        BH.log_incident({"pupil_id": p.pupil_id, "incident_type": "Achievement",
                         "description": "Great work"}, actor=ADMIN)
    return {"mine": mine, "other": other, "y9": y9, "group": g}


def test_columns_preview_filters(school):
    assert {d.key for d in DX.datasets_for(ADMIN)} == set(DX.DATASETS)
    assert not {"contacts", "sen", "exclusions"} & {d.key for d in DX.datasets_for(TEACHER)}
    assert "dob" not in [c.key for c in DX.columns_for(TEACHER, "pupils")]
    pv = DX.preview(ADMIN, "pupils", ["admission_no", "surname", "year"],
                    {"year_group": 8})
    assert pv["total"] == 2 and [c.key for c in pv["columns"]] == ["admission_no", "surname",
                                                                    "year"]
    pv = DX.preview(ADMIN, "pupils", None, {"form": "8b"})
    assert pv["total"] == 1
    with pytest.raises(DX.ValidationError):
        DX.preview(ADMIN, "pupils", ["nope"])
    with pytest.raises(DX.ValidationError):
        DX.preview(ADMIN, "pupils", None, {"year_group": 3})
    with pytest.raises(DX.ValidationError):
        DX.preview(ADMIN, "everything")


def test_teacher_scope_and_sensitive(school):
    pv = DX.preview(TEACHER, "pupils")
    assert [r[0] for r in pv["rows"]] == [school["mine"].admission_no]
    assert pv["scope"] == "own groups"
    assert DX.preview(TEACHER, "behaviour")["total"] == 1
    assert [r[0] for r in DX.preview(TEACHER, "groups")["rows"]] == ["8x/Ma1"]
    with pytest.raises(DX.PermissionDenied):
        DX.preview(TEACHER, "contacts")
    with pytest.raises(DX.PermissionDenied):
        DX.preview(TEACHER, "pupils", ["admission_no", "dob"])
    assert DX.preview(ADMIN, "contacts")["total"] == 1


def test_export_formats_are_formula_safe(school, scratch):
    n = DX.export(ADMIN, "pupils", scratch / "p.csv", columns=["admission_no", "surname"])
    rows = list(csv.reader(open(scratch / "p.csv", encoding="utf-8")))
    assert n == 3 and rows[0] == ["Admission no", "Surname"]
    assert any(r[1].startswith("'=HYPERLINK") for r in rows[1:])
    DX.export(ADMIN, "pupils", scratch / "p.md", columns=["surname"])
    assert "'=HYPERLINK" in (scratch / "p.md").read_text()
    DX.export(ADMIN, "pupils", scratch / "p.json", columns=["surname"])
    assert len(json.loads((scratch / "p.json").read_text())) == 3
    DX.export(ADMIN, "pupils", scratch / "p.txt", columns=["surname"], fmt="tsv", limit=1)
    assert len((scratch / "p.txt").read_text().splitlines()) == 2


def test_log_has_no_data_and_definitions_are_per_person(school, scratch):
    DX.export(TEACHER, "behaviour", scratch / "b.csv", filters={"year_group": 8})
    log = DX.history(TEACHER)
    assert log[0]["dataset"] == "behaviour" and log[0]["row_count"] == 1
    assert log[0]["filters"] == "year_group" and "Great work" not in json.dumps(log)
    assert DX.history(ADMIN, everyone=True)[0]["actor"] == "dx_teacher"
    assert DX.history(ADMIN) == []
    d = DX.save_definition(TEACHER, {"name": "My class", "dataset": "pupils",
                                     "columns": ["admission_no", "surname"], "fmt": "csv"})
    with pytest.raises(DX.ValidationError):
        DX.save_definition(TEACHER, {"name": "my CLASS", "dataset": "pupils"})
    with pytest.raises(DX.PermissionDenied):
        DX.save_definition(TEACHER, {"name": "Sneaky", "dataset": "contacts"})
    assert DX.list_definitions(ADMIN) == []
    with pytest.raises(DX.NotFound):
        DX.get_definition(ADMIN, d.definition_id)
    assert DX.run_definition(TEACHER, d.definition_id, scratch / "mine.csv") == 1
    d2 = DX.save_definition(TEACHER, {"name": "Renamed", "dataset": "pupils",
                                      "columns": ["surname"]}, d.definition_id)
    assert d2.columns == ["surname"]
    assert DX.delete_definition(TEACHER, d.definition_id)
    assert DX.list_definitions(TEACHER) == []


def test_packs(school, scratch):
    out = DX.run_pack(TEACHER, "pupils_core", scratch / "pack", zip_output=True)
    assert [f["dataset"] for f in out["files"]] == ["pupils", "forms"]
    assert [r["dataset"] for r in out["refused"]] == ["contacts"]
    with zipfile.ZipFile(out["archive"]) as z:
        assert "_manifest.json" in z.namelist()
    with pytest.raises(DX.ValidationError):
        DX.run_pack(ADMIN, [], scratch / "x")
    o = DX.overview(ADMIN)
    assert o["exports"] == 2 and o["rows"] >= 1


def test_cli_menu(school, scratch, monkeypatch, capsys):
    from education_system.systems.secondary.modules.reporting.cli import data_export_cli as M
    M._state.clear()
    path = scratch / "cli.csv"
    answers = iter(["11", "", "12", "1", "1,2", "", "", "8", "", "", "13", "1", "",
                    "", "", "", "", str(path), "", "", "1", "", "0"])
    monkeypatch.setattr("builtins.input", lambda _p="": next(answers))
    M.menu(TEACHER)
    out = capsys.readouterr().out
    assert "1 row(s) (own groups)" in out and "Exported 1 row(s)" in out
    assert "Total exports" in out and path.exists()
