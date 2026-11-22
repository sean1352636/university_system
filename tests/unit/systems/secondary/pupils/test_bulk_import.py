"""Bulk Import rules (domain.bulk_import) on a scratch school DB and a scratch
auth.db (logins are real rows there, never in the live auth.db)."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.pupils.domain import bulk_import as B
from education_system.systems.secondary.modules.pupils.domain import pupil_accounts
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="teacher1", role="teacher")
TODAY = dt.date(2026, 11, 3)


@pytest.fixture(autouse=True)
def scratch(tmp_path):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    yield
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


def _csv(tmp_path, header, *rows, name="pupils.csv"):
    path = tmp_path / name
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return path


HEADER = ["Forename", "Surname", "DOB", "Gender", "Year", "Form", "admission_date",
          "contact1_name", "contact1_relationship", "contact1_email"]
AVA = ["Ava", "Stone", "15/01/2014", "F", "Year 8", "8k", "2026-09-01",
       "Jo Stone", "mother", "jo@example.com"]
BEN = ["Ben", "Hall", "2011-02-15", "M", "11", "", "2026-09-01", "", "", ""]


def _preview(tmp_path, *rows, header=HEADER):
    return B.preview(B.read_file(_csv(tmp_path, header, *rows)), today=TODAY)


# ── Reading + preview ───────────────────────────────────────────────

def test_preview_normalises_spellings_and_writes_nothing(tmp_path):
    pv = _preview(tmp_path, AVA, BEN)
    assert [r.status for r in pv.rows] == [B.READY, B.READY]
    ava = pv.rows[0]
    assert ava.line == 2
    assert ava.pupil["date_of_birth"] == "2014-01-15"
    assert ava.pupil["gender"] == "Female" and ava.pupil["year_group"] == "8"
    assert ava.contacts[0]["relationship"] == "Mother"
    assert P.list_pupils(roll_status=None) == []


def test_missing_required_column_and_empty_file(tmp_path):
    with pytest.raises(B.ValidationError, match="Missing column"):
        B.read_file(_csv(tmp_path, ["Forename", "Surname"], ["A", "B"]))
    with pytest.raises(B.ValidationError, match="no pupils"):
        B.read_file(_csv(tmp_path, HEADER, name="empty.csv"))
    with pytest.raises(B.ValidationError, match=".csv or .xlsx"):
        B.read_file(_csv(tmp_path, HEADER, AVA, name="pupils.pdf"))


def test_ignored_columns_reported(tmp_path):
    pv = _preview(tmp_path, AVA + ["x"], header=HEADER + ["Shoe size"])
    assert pv.ignored_columns == ["shoe_size"]
    assert pv.rows[0].status == B.READY


def test_row_errors_and_warnings(tmp_path):
    bad = ["", "Hall", "2011-02-30", "X", "12", "", "2026-09-01", "Jo", "aunt", ""]
    wrong_year = ["Cy", "Ray", "2014-01-15", "M", "9", "", "2026-09-01", "", "", ""]
    future = ["Di", "Ray", "2014-02-15", "F", "8", "", "2027-01-01", "", "", ""]
    no_date = ["Ed", "Ray", "2014-03-15", "M", "8", "", "", "", "", ""]
    pv = _preview(tmp_path, bad, wrong_year, future, no_date)
    statuses = [r.status for r in pv.rows]
    assert statuses == [B.ERROR, B.WARNING, B.ERROR, B.WARNING]
    text = " ".join(pv.rows[0].problems)
    for expect in ("first name", "Date of birth", "Gender", "Year group", "Contact 1"):
        assert expect.lower() in text.lower()
    assert any("future" in p for p in pv.rows[2].problems)
    assert any("today's date" in w for w in pv.rows[3].warnings)


def test_duplicates_in_file_and_on_file(tmp_path):
    P.create_pupil({"legal_first_name": "Ben", "legal_last_name": "Hall",
                    "date_of_birth": "2011-02-15", "gender": "Male", "year_group": 11,
                    "admission_date": "2026-09-01"}, actor=ADMIN)
    pv = _preview(tmp_path, BEN, AVA, AVA)
    assert [r.status for r in pv.rows] == [B.DUPLICATE, B.READY, B.ERROR]
    assert pv.rows[0].existing.startswith("SEC")
    assert "line 3" in pv.rows[2].problems[0]


# ── Import ───────────────────────────────────────────────────────────

def test_import_adds_pupils_contacts_and_job(tmp_path):
    pv = _preview(tmp_path, AVA, BEN)
    result = B.run_import(pv, actor=ADMIN, create_logins=False)
    assert len(result.created) == 2 and result.failed == []
    ava = next(p for p in result.created if p.legal_first_name == "Ava")
    assert ava.form_group == "8K"
    [contact] = C.list_for_pupil(ava.pupil_id)
    assert contact.email == "jo@example.com" and contact.receives_email
    job = B.get_job(result.job_id)
    assert (job.kind, job.done, job.failed, job.status) == ("import", 2, 0, "done")
    assert job.can_undo


def test_duplicates_skipped_unless_included(tmp_path):
    P.create_pupil({"legal_first_name": "Ben", "legal_last_name": "Hall",
                    "date_of_birth": "2011-02-15", "gender": "Male", "year_group": 11,
                    "admission_date": "2026-09-01"}, actor=ADMIN)
    pv = _preview(tmp_path, BEN)
    with pytest.raises(B.ValidationError, match="Nothing to import"):
        B.run_import(pv, actor=ADMIN, create_logins=False)
    result = B.run_import(pv, actor=ADMIN, create_logins=False, include_duplicates=True)
    assert len(result.created) == 1


def test_import_creates_logins_and_welcome_emails(tmp_path):
    pv = _preview(tmp_path, AVA)
    result = B.run_import(pv, actor=ADMIN, create_logins=True)
    assert result.login_errors == []
    account = pupil_accounts.get_for_pupil(result.created[0].pupil_id)
    assert account is not None and account.username == "ava"
    assert len(result.welcome_message_ids) == 1


def test_teacher_cannot_import(tmp_path):
    pv = _preview(tmp_path, AVA)
    with pytest.raises(B.PermissionDenied):
        B.run_import(pv, actor=TEACHER, create_logins=False)


def test_progress_reported(tmp_path):
    seen = []
    B.run_import(_preview(tmp_path, AVA, BEN), actor=ADMIN, create_logins=False,
                 progress=lambda i, n: seen.append((i, n)))
    assert seen == [(1, 2), (2, 2)]


# ── Undo ─────────────────────────────────────────────────────────────

def test_undo_import_removes_untouched_pupils_only(tmp_path):
    result = B.run_import(_preview(tmp_path, AVA, BEN), actor=ADMIN, create_logins=True)
    ava = next(p for p in result.created if p.legal_first_name == "Ava")
    ben = next(p for p in result.created if p.legal_first_name == "Ben")
    P.update_pupil(ben.pupil_id, {"form_group": "11B"}, actor=ADMIN)
    undone, kept = B.undo_job(result.job_id, actor=ADMIN)
    assert undone == 1 and kept == [(ben.admission_no, "record changed since the import")]
    assert P.get_pupil(ava.pupil_id) is None
    assert pupil_accounts.get_for_pupil(ava.pupil_id).status != "active"  # login removed
    assert P.get_pupil(ben.pupil_id) is not None
    assert B.get_job(result.job_id).status == "partly_undone"
    with pytest.raises(B.ValidationError):
        B.undo_job(result.job_id, actor=ADMIN)


def test_undo_import_keeps_pupil_whose_contacts_changed(tmp_path):
    result = B.run_import(_preview(tmp_path, AVA), actor=ADMIN, create_logins=False)
    pid = result.created[0].pupil_id
    C.add_contact(pid, {"full_name": "Sam Stone", "relationship": "Father",
                        "phone": "07700 900123"}, actor=ADMIN)
    undone, kept = B.undo_job(result.job_id, actor=ADMIN)
    assert undone == 0 and "contacts" in kept[0][1]


# ── Bulk update ──────────────────────────────────────────────────────

def _pupils(tmp_path):
    return B.run_import(_preview(tmp_path, AVA, BEN), actor=ADMIN,
                        create_logins=False).created


def test_bulk_update_preview_apply_undo(tmp_path):
    ava, ben = _pupils(tmp_path)
    checks = B.preview_update("fsm_eligible", "yes", [ava, ben])
    assert [(c.before, c.after, c.changes) for c in checks] == [(False, True, True)] * 2
    job_id, failed = B.run_update("fsm_eligible", "yes", [ava.pupil_id, ben.pupil_id],
                                  actor=ADMIN)
    assert failed == []
    assert P.get_pupil(ava.pupil_id).fsm_eligible is True
    P.update_pupil(ben.pupil_id, {"fsm_eligible": False}, actor=ADMIN)  # changed again
    undone, kept = B.undo_job(job_id, actor=ADMIN)
    assert undone == 1 and kept == [(ben.admission_no, "changed again since")]
    assert P.get_pupil(ava.pupil_id).fsm_eligible is False


def test_bulk_update_refusals(tmp_path):
    ava, ben = _pupils(tmp_path)
    with pytest.raises(B.ValidationError, match="Choose a field"):
        B.preview_update("legal_last_name", "X", [ava])
    checks = B.preview_update("year_group", "13", [ava])
    assert checks[0].problem and not checks[0].changes
    with pytest.raises(B.ValidationError, match="Nothing would change"):
        B.run_update("year_group", "8", [ava.pupil_id], actor=ADMIN)
    assert [c.after for c in B.preview_update("sen_status", "ehcp", [ava])] == ["E"]
    with pytest.raises(B.PermissionDenied):
        B.run_update("eal", "yes", [ava.pupil_id], actor=TEACHER)


def test_resolve_refs(tmp_path):
    ava, ben = _pupils(tmp_path)
    found, missing = B.resolve_refs(f"{ava.admission_no}, {ben.admission_no.lower()}\n"
                                    f"{ava.admission_no} NOPE")
    assert [p.pupil_id for p in found] == [ava.pupil_id, ben.pupil_id]
    assert missing == ["NOPE"]


# ── Bulk delete ──────────────────────────────────────────────────────

def test_bulk_delete_needs_reason_and_cannot_be_undone(tmp_path):
    ava, ben = _pupils(tmp_path)
    with pytest.raises(B.ValidationError, match="reason"):
        B.run_delete([ava.pupil_id], actor=ADMIN, reason=" ")
    job_id, failed = B.run_delete([ava.pupil_id, 9999], actor=ADMIN, reason="Wrong file")
    assert P.get_pupil(ava.pupil_id) is None and len(failed) == 1
    assert not B.get_job(job_id).can_undo
    with pytest.raises(B.ValidationError, match="deletes can't be undone"):
        B.undo_job(job_id, actor=ADMIN)
    assert P.history(ava.pupil_id)[0]["action"] == "delete"  # copy kept in the audit


# ── Export / template ────────────────────────────────────────────────

def test_export_round_trips_and_hides_sensitive_by_default(tmp_path):
    ava, _ben = _pupils(tmp_path)
    P.update_pupil(ava.pupil_id, {"notes": "=HYPERLINK(\"x\")", "fsm_eligible": True},
                   actor=ADMIN)
    out = tmp_path / "out.csv"
    assert B.export_csv(out, actor=ADMIN) == 2
    rows = list(csv.DictReader(out.open(encoding="utf-8-sig")))
    assert "notes" not in rows[0] and "fsm_eligible" not in rows[0]
    assert {r["contact1_email"] for r in rows} == {"jo@example.com", ""}
    B.export_csv(out, actor=ADMIN, include_sensitive=True, year_group=8)
    [row] = list(csv.DictReader(out.open(encoding="utf-8-sig")))
    assert row["notes"].startswith("'=") and row["fsm_eligible"] == "yes"
    # The exported layout imports again (as duplicates of who is already on file).
    pv = B.preview(B.read_file(out), today=TODAY)
    assert [r.status for r in pv.rows] == [B.DUPLICATE]
    assert pv.ignored_columns == ["admission_no", "roll_status", "leaving_date",
                                  "leaving_reason"]


def test_template_has_every_column(tmp_path):
    path = tmp_path / "t.csv"
    B.write_template(path)
    assert next(csv.reader(path.open(encoding="utf-8-sig"))) == list(B.COLUMNS)


def test_xlsx_import(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(HEADER)
    ws.append(["Ava", "Stone", dt.datetime(2014, 1, 15), "F", 8, "8K", dt.date(2026, 9, 1),
               "", "", ""])
    path = tmp_path / "pupils.xlsx"
    wb.save(path)
    pv = B.preview(B.read_file(path), today=TODAY)
    assert pv.rows[0].status == B.READY
    assert pv.rows[0].pupil["date_of_birth"] == "2014-01-15"
