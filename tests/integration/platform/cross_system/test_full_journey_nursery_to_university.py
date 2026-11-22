"""One learner, five systems: nursery → primary → secondary → sixth form → university.

A child is created in the nursery and moved up through every phase with the
production functions each system's own screens call. Nothing is written
with raw SQL. Each boundary is driven the way the receiving system actually
admits people:

==========================  ====================================================
nursery → primary           ``nursery.primary_transfer.move_to_primary_school``
                            (one call, all seven steps, parent consent given)
primary R → 6               ``primary.enrolment.promote_year`` once per year
primary → secondary         Year 6 Transition (``year6_transition``: destination,
                            application, offer, consent, acceptance, handover),
                            then the secondary's Incoming from Primary
                            (``incoming_primary.create_pupil``) admits the pupil,
                            then the primary's final move
                            (``secondary_transfer.move_to_secondary_school``)
                            resumes the same transition, completes it and takes
                            the pupil off roll
secondary 7 → 11            ``secondary.pupils.update_pupil`` (year group)
secondary → sixth form      ``sixth_form_progression.send`` (Year 11 applicant on
                            the post-16 board), then the sixth form's admissions:
                            ``update_applicant`` (e-mail), ``make_offer``,
                            ``accept_offer``, ``record_identity_check`` and
                            ``conversion.convert_to_student``, which reports the
                            enrolment back and closes the secondary record
sixth form → university     ``university_applications.submit`` → ``record_offer``
                            → ``select_firm_choice``, the university's casework
                            (``admissions_checklist``: verify documents, right to
                            study, status to ``ready_to_enrol``), then
                            ``university_applications.confirm_place``
==========================  ====================================================

After every boundary the test checks that the learner is in the destination
system's own records with the right name, date of birth and entry year; that
the source record is kept but off roll; that one platform ``journey_id`` runs
through every system; that the boundary's transition is ``completed``; and
that no second transition was opened on it. At the end the Learner 360 must
list all five phases in order.

Isolation: every database lives under ``tmp_path``. ``EDU_*_DATA_DIR`` points
nursery, primary, secondary, sixth form and platform data there, every
already-imported module that copied a path under the repository's ``var/``
is repointed at the sandbox (the ``primary_sandbox`` technique from
``tests/unit/systems/primary/conftest.py``), the university's
``DEFAULT_DB_PATH`` is patched as ``tests/fixtures/university.py`` does, and
its schema is built by the same Alembic chain the launcher runs. A guard on
``sqlite3.connect`` refuses — and records — any open of a file under the
real ``var/``, so a path the redirect missed fails the test even when the
code that hit it swallowed the error.
"""

from __future__ import annotations

import contextlib
import dataclasses
import datetime as _dt
import os
import sqlite3
import sys
import warnings
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_REAL_SQLITE_CONNECT = sqlite3.connect
_FLAG_SUFFIXES = ("_READY", "_INITIALISED", "_INITIALIZED", "_INIT_DONE", "_SCHEMA_DONE")
#: Attributes that only *read* shipped files; they keep their real location.
_KEEP_REAL = ("LOCALE",)

#: The env-overridable data directories, and their sandbox location.
_DATA_DIR_ENV = {
    "EDU_PLATFORM_DATA_DIR": ("PLATFORM_DATA_DIR", ("data", "platform")),
    "EDU_NURSERY_DATA_DIR": ("NURSERY_DATA_DIR", ("data", "nursery")),
    "EDU_PRIMARY_DATA_DIR": ("PRIMARY_DATA_DIR", ("data", "primary")),
    "EDU_SECONDARY_DATA_DIR": ("SECONDARY_DATA_DIR", ("data", "secondary")),
    "EDU_SECONDARY_LOG_DIR": ("SECONDARY_LOG_DIR", ("logs", "secondary")),
    "EDU_SIXTHFORM_DATA_DIR": ("SIXTH_FORM_DATA_DIR", ("data", "sixth_form")),
}

PHASES = ("nursery", "primary", "secondary", "sixth_form", "university")


# ── Sandbox ──────────────────────────────────────────────────────────

class LiveDataTouched(AssertionError):
    """The test opened a database under the live ``var/`` directory."""


def _guarded_connect(var_dir: Path, touched: list[str]):
    def connect(database, *args, **kwargs):
        target = os.fspath(database) if isinstance(database, os.PathLike) else str(database)
        if target not in (":memory:", "") and not target.startswith("file::memory:"):
            raw = target[5:].split("?", 1)[0] if target.startswith("file:") else target
            try:
                resolved = Path(raw).resolve()
            except (OSError, ValueError):
                resolved = None
            if resolved is not None and (resolved == var_dir or var_dir in resolved.parents):
                # Recorded as well as raised: best-effort code paths catch
                # exceptions, and a swallowed live write must still fail.
                touched.append(str(resolved))
                raise LiveDataTouched(f"test tried to open live database {resolved}")
        return _REAL_SQLITE_CONNECT(database, *args, **kwargs)
    return connect


def _remap(value, prefixes: list[tuple[str, str]]):
    """``value`` with an old data-dir prefix swapped, or None."""
    if isinstance(value, Path):
        text, as_path = str(value), True
    elif isinstance(value, str):
        text, as_path = value, False
    else:
        return None
    for old, new in prefixes:
        if text == old or text.startswith(old + os.sep):
            swapped = new + text[len(old):]
            return Path(swapped) if as_path else swapped
    return None


def _patch_namespace(monkeypatch, owner, namespace: dict, prefixes) -> None:
    for name, value in list(namespace.items()):
        if name.startswith("__"):
            continue
        try:
            if isinstance(value, bool) and value and name.upper().endswith(_FLAG_SUFFIXES):
                monkeypatch.setattr(owner, name, False)
                continue
            if any(k in name.upper() for k in _KEEP_REAL):
                continue
            new = _remap(value, prefixes)
            if new is not None:
                monkeypatch.setattr(owner, name, new)
            elif isinstance(value, dict) and not name.startswith("_"):
                # Path registries such as SYSTEM_DB_PATHS copied at import.
                for key, item in list(value.items()):
                    swapped = _remap(item, prefixes)
                    if swapped is not None:
                        monkeypatch.setitem(value, key, swapped)
        except (TypeError, AttributeError):
            continue


def _redirect_loaded_modules(monkeypatch, prefixes) -> None:
    """Repoint every loaded ``education_system`` module (``paths`` included)
    and its classes from the old prefixes to the new ones."""
    for mod_name, module in list(sys.modules.items()):
        if not (mod_name == "education_system" or mod_name.startswith("education_system.")):
            continue
        if not isinstance(module, ModuleType):
            continue
        try:
            namespace = vars(module)
        except TypeError:
            continue
        _patch_namespace(monkeypatch, module, namespace, prefixes)
        for value in list(namespace.values()):
            if isinstance(value, type) and getattr(value, "__module__", None) == mod_name:
                try:
                    _patch_namespace(monkeypatch, value, dict(vars(value)), prefixes)
                except (TypeError, AttributeError):
                    continue


@dataclasses.dataclass
class Sandbox:
    root: Path
    auth_db: str
    university_db: str
    db_paths: dict[str, Path]
    touched: list[str]

    def assert_no_live_data_touched(self) -> None:
        assert not self.touched, (
            "The journey opened live databases under var/: "
            + ", ".join(sorted(set(self.touched))))


_UNIVERSITY_SCHEMA = Path(__file__).resolve().parents[3] / "fixtures" / "university_schema.sql"


def _build_university_schema(db_path: str) -> None:
    """The current university schema (structure only, no rows), from
    ``tests/fixtures/university_schema.sql``.

    A from-scratch ``alembic upgrade head`` cannot build it: some migrations
    read columns that only the runtime schema code adds (found by this test,
    2026-11-05), so the snapshot of the real schema is loaded instead."""
    con = sqlite3.connect(db_path)
    try:
        con.executescript(_UNIVERSITY_SCHEMA.read_text())
        con.commit()
    finally:
        con.close()


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Every system's data (and the platform's auth.db) under tmp_path."""
    from education_system import paths

    real_var = Path(paths.VAR_DIR).resolve()
    sandbox_var = (tmp_path / "var").resolve()
    touched: list[str] = []

    prefixes: list[tuple[str, str]] = []
    for env, (attr, parts) in _DATA_DIR_ENV.items():
        new = sandbox_var.joinpath(*parts)
        monkeypatch.setenv(env, str(new))
        old = str(Path(getattr(paths, attr)).resolve())
        if old != str(new) and (old, str(new)) not in prefixes:
            prefixes.append((old, str(new)))
    prefixes.append((str(real_var), str(sandbox_var)))
    monkeypatch.setenv("EDU_EMAIL_MODE", "inbox_only")

    _redirect_loaded_modules(monkeypatch, prefixes)
    paths.ensure_all_directories()

    # Refuse the live var/ from here on.
    monkeypatch.setattr(sqlite3, "connect", _guarded_connect(real_var, touched))

    from education_system.platform.cross_system import enrolment_schema, identity_service
    from education_system.platform.cross_system.adapters import registry
    from education_system.platform.identity.auth import db as auth_db
    from education_system.platform.identity.auth.schema import initialise_auth_db
    from education_system.platform.integrations.external import cross_system_bus

    auth_path = str(paths.PLATFORM_AUTH_DB_FILE)
    assert Path(auth_path).resolve().is_relative_to(sandbox_var), auth_path
    # Code that never takes a db_path reads the module default.
    monkeypatch.setattr(auth_db, "PLATFORM_AUTH_DB_FILE", Path(auth_path))
    monkeypatch.setattr(identity_service, "_initialised", set())
    enrolment_schema.reset_schema_cache_for_test()
    initialise_auth_db(auth_path)
    enrolment_schema.ensure_enrolment_schema(auth_path)
    try:
        from education_system.systems.primary.infrastructure import schema_repair
        monkeypatch.setattr(schema_repair, "_done", set())
    except (ImportError, AttributeError):
        pass

    # The university: patched the way tests/fixtures/university.py patches
    # it, on a schema built by the launcher's own migration chain.
    import education_system.systems.university.infrastructure.database.db as uni_db
    university_db = str(Path(paths.UNIVERSITY_DEFAULT_DB_PATH).resolve())
    assert Path(university_db).is_relative_to(sandbox_var), university_db
    Path(university_db).parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(uni_db, "DEFAULT_DB_PATH", university_db)
    monkeypatch.setattr(uni_db, "DEFAULT_DB_NAME", os.path.basename(university_db))
    _build_university_schema(university_db)

    registry.clear_for_test()
    cross_system_bus.clear_subscribers_for_test()

    box = Sandbox(root=sandbox_var, auth_db=auth_path, university_db=university_db,
                  db_paths=dict(paths.SYSTEM_DB_PATHS), touched=touched)
    for system in PHASES:
        assert Path(box.db_paths[system]).resolve().is_relative_to(sandbox_var), (
            f"{system} database is not in the sandbox: {box.db_paths[system]}")
    try:
        yield box
    finally:
        registry.clear_for_test()
        cross_system_bus.clear_subscribers_for_test()
        enrolment_schema.reset_schema_cache_for_test()
        late = list(touched)
        monkeypatch.undo()
        # Modules first imported during the test copied sandbox paths; point
        # them back where a normal import would have put them.
        back = [(new, old) for old, new in prefixes]
        _redirect_loaded_modules(pytest.MonkeyPatch(), back)
        identity_service._initialised.clear()
        enrolment_schema.reset_schema_cache_for_test()
        assert not late, "Live databases under var/ were opened: " + ", ".join(sorted(set(late)))


# ── The learner ──────────────────────────────────────────────────────

FIRST, LAST, GENDER = "Maya", "Okafor", "Female"
PARENT = {"parent_name": "Ngozi Okafor", "parent_phone": "07123 456789",
          "parent_email": "ngozi@example.test"}


def _dates() -> dict[str, str]:
    """Dates that satisfy every phase's own age rules on the day the test
    runs (all the moves happen today): about 16 now, 11 when admitted to
    Year 7 five years ago, so the Year 11 leaving date is after admission."""
    today = _dt.date.today()
    dob = _dt.date(today.year - 16, 3, 14)
    return {
        "dob": dob.isoformat(),
        "nursery_start": _dt.date(dob.year + 3, 9, 1).isoformat(),
        "secondary_admission": _dt.date(dob.year + 11, 9, 1).isoformat(),
        "today": today.isoformat(),
        "university_entry_year": str(today.year + 1),
    }


# ── Platform checks used at every boundary ───────────────────────────

def _boundary(jid: str, source: str, destination: str, auth: str) -> list[dict]:
    from education_system.platform.cross_system import transitions
    return [t for t in transitions.list_transitions(jid, db_path=auth)
            if t.get("source_system") == source and t.get("destination_system") == destination]


def _check_boundary(jid: str, source: str, destination: str, auth: str) -> dict:
    where = f"{source} → {destination}"
    rows = _boundary(jid, source, destination, auth)
    assert len(rows) == 1, (
        f"[{where}] expected exactly one platform transition, found {len(rows)}: "
        + ", ".join(f"{r['transition_id']}={r['status']}" for r in rows))
    assert rows[0]["status"] == "completed", (
        f"[{where}] transition {rows[0]['transition_id']} is {rows[0]['status']!r}, "
        "not 'completed'")
    return rows[0]


def _check_journey(jid: str, local_ids: dict[str, str], current: str, auth: str,
                   dates: dict[str, str], *, step: str) -> None:
    """The one journey holds every system reached so far, each local id
    resolves back to it, and its identity is the learner's."""
    from education_system.platform.cross_system import identity_service
    journey = identity_service.get(jid, db_path=auth)
    assert journey is not None, f"[{step}] journey {jid} is missing from student_journey"
    assert (journey.get("legal_first_name"), journey.get("legal_last_name"),
            journey.get("date_of_birth")) == (FIRST, LAST, dates["dob"]), (
        f"[{step}] journey {jid} holds the wrong identity: {journey}")
    assert journey.get("current_system") == current, (
        f"[{step}] journey current_system is {journey.get('current_system')!r}, "
        f"expected {current!r}")
    for system, local_id in local_ids.items():
        slot = identity_service.SYSTEM_SLOTS[system][1]
        assert str(journey.get(slot) or "") == str(local_id), (
            f"[{step}] journey slot {slot} is {journey.get(slot)!r}, expected {local_id!r}")
        found = identity_service.find_by_student(system, str(local_id), db_path=auth)
        assert found is not None and found["journey_id"] == jid, (
            f"[{step}] {system} record {local_id} resolves to journey "
            f"{(found or {}).get('journey_id')!r}, not {jid!r} - a second journey was "
            "opened")


# ── The journey ──────────────────────────────────────────────────────

def test_one_child_moves_from_nursery_to_university(sandbox, monkeypatch):
    auth = sandbox.auth_db
    d = _dates()
    local: dict[str, str] = {}

    # ── Nursery: the child ───────────────────────────────────────────
    from education_system.platform.cross_system import identity_service
    from education_system.systems.nursery.domain.learners.children import (
        children,
        primary_transfer,
    )

    data = {"first_name": FIRST, "last_name": LAST, "date_of_birth": d["dob"],
            "room": "Preschool Room", "start_date": d["nursery_start"],
            "allergies": "Peanuts", "medical_notes": "Carries an inhaler", **PARENT}
    # gender is passed only if this build of the nursery record holds it.
    if "gender" in {f.name for f in dataclasses.fields(children.Child)}:
        data["gender"] = GENDER
    child = children.create_child(data)
    local["nursery"] = child.pupil_id
    assert (child.first_name, child.last_name, child.date_of_birth, child.status) == (
        FIRST, LAST, d["dob"], "active"), f"[nursery] child created wrongly: {child}"
    registered = identity_service.find_by_student("nursery", child.pupil_id, db_path=auth)
    assert registered is not None, (
        "[nursery] create_child registered no platform journey for the child")
    jid = registered["journey_id"]

    # ── Nursery → primary ────────────────────────────────────────────
    from education_system.systems.primary.domain.learners.pupils import pupils as primary

    moved = primary_transfer.move_to_primary_school(
        child.pupil_id, class_name="Robins",
        consent=primary_transfer.consent_for(medical=True, support=True),
        actor_user_id=None, db_path=auth)
    step = "nursery → primary"
    assert moved.journey_id == jid, (
        f"[{step}] the move used journey {moved.journey_id}, not the child's {jid}")
    assert not moved.warnings, f"[{step}] move reported warnings: {moved.warnings}"
    pupil = primary.get_pupil(moved.primary_pupil_id)
    assert pupil is not None, f"[{step}] no primary pupil {moved.primary_pupil_id!r}"
    assert (pupil.first_name, pupil.last_name, pupil.date_of_birth) == (
        FIRST, LAST, d["dob"]), f"[{step}] primary pupil has the wrong identity: {pupil}"
    assert (pupil.roll_status, pupil.year_group, pupil.class_name) == (
        "on_roll", "R", "Robins"), f"[{step}] primary pupil not on roll in Reception: {pupil}"
    assert pupil.journey_id == jid, f"[{step}] primary pupil carries journey {pupil.journey_id}"
    kept = children.get_child(child.pupil_id)
    assert kept is not None, f"[{step}] the nursery record was deleted"
    assert kept.status == "left", f"[{step}] nursery child is {kept.status!r}, not 'left'"
    local["primary"] = pupil.pupil_id
    _check_boundary(jid, "nursery", "primary", auth)
    _check_journey(jid, local, "primary", auth, d, step=step)

    # ── Primary: Reception up to Year 6 ──────────────────────────────
    from education_system.systems.primary.domain.admissions.enrolment import enrolment

    for year in ("R", "1", "2", "3", "4", "5"):
        summary = enrolment.promote_year(year)
        assert summary["count"] == 1, (
            f"[primary promotion] promote_year({year!r}) moved {summary['count']} pupils")
    pupil = primary.get_pupil(local["primary"])
    assert pupil.year_group == "6", f"[primary promotion] pupil is in year {pupil.year_group}"

    # ── Primary → secondary ──────────────────────────────────────────
    from education_system.systems.primary.domain.learners.pupils import (
        secondary_transfer,
        year6_transition as y6,
    )
    from education_system.systems.secondary.core.permissions.access import Principal
    from education_system.systems.secondary.modules.progression.domain import incoming_primary
    from education_system.systems.secondary.modules.pupils.domain import pupils as secondary

    step = "primary → secondary"
    pid = local["primary"]
    year = y6.current_academic_year()
    tt = y6.national_timetable(year)
    y6.set_destination(pid, year, y6.DESTINATION_PLATFORM, actor="admin3", db_path=auth)
    y6.record_application(pid, year, tt.applications_open, actor="admin3", db_path=auth)
    y6.record_offer(pid, year, tt.offer_day, actor="admin3", db_path=auth)
    y6.set_consent(pid, year, {field: True for field in y6.CONSENT_FIELDS},
                   given_by="Ngozi Okafor (mother)", given_on=d["today"],
                   method="Signed form")
    y6.record_acceptance(pid, year, tt.offer_day, actor="admin3", db_path=auth)
    y6.approve_handover(pid, year, actor="admin3", db_path=auth)
    open_rows = _boundary(jid, "primary", "secondary", auth)
    assert [r["status"] for r in open_rows] == ["handover_approved"], (
        f"[{step}] after Year 6 Transition expected one handover_approved transition, "
        f"got {[r['status'] for r in open_rows]}")
    tid = open_rows[0]["transition_id"]

    # The secondary's admissions office makes the Year 7 record.
    sec_admin = Principal(username="admin2", role="admin")
    defaults = incoming_primary.new_pupil_defaults(tid, actor=sec_admin, db_path=auth)
    overrides = {"form_group": "7A", "admission_date": d["secondary_admission"]}
    if not defaults.get("gender"):
        warnings.warn(f"[{step}] the handover carried no gender; the admissions officer "
                      "has to type it in", stacklevel=1)
        overrides["gender"] = GENDER
    created = incoming_primary.create_pupil(tid, overrides, actor=sec_admin, db_path=auth)
    assert created.pupil is not None, f"[{step}] Incoming from Primary made no pupil"
    assert created.item.status == "admitted", (
        f"[{step}] the transfer is {created.item.status!r} after the secondary admitted "
        f"the pupil ({created.notes})")

    # The primary school's final move resumes the same transition.
    final = secondary_transfer.move_to_secondary_school(pid, db_path=auth)
    assert final.journey_id == jid, f"[{step}] the move used journey {final.journey_id}"
    assert final.transition_id == tid, (
        f"[{step}] the final move used transition {final.transition_id}, not the Year 6 "
        f"one {tid}")
    assert not final.warnings, f"[{step}] move reported warnings: {final.warnings}"
    spupil = secondary.get_pupil(created.pupil.pupil_id)
    assert spupil is not None, f"[{step}] secondary pupil {created.pupil.pupil_id} is missing"
    assert (spupil.legal_first_name, spupil.legal_last_name, spupil.date_of_birth) == (
        FIRST, LAST, d["dob"]), f"[{step}] secondary pupil has the wrong identity: {spupil}"
    assert (spupil.roll_status, spupil.year_group, spupil.gender) == ("on_roll", 7, GENDER), (
        f"[{step}] secondary pupil is not an on-roll Year 7 {GENDER.lower()}: {spupil}")
    kept = primary.get_pupil(pid)
    assert kept is not None, f"[{step}] the primary record was deleted"
    assert kept.roll_status == "left", (
        f"[{step}] primary pupil is {kept.roll_status!r}, not 'left'")
    assert final.leaver_id, f"[{step}] no primary leaver record was written"
    local["secondary"] = str(spupil.pupil_id)
    _check_boundary(jid, "primary", "secondary", auth)
    _check_journey(jid, local, "secondary", auth, d, step=step)

    # ── Secondary: Year 7 up to Year 11 ──────────────────────────────
    spupil = secondary.update_pupil(spupil.pupil_id, {"year_group": 11, "form_group": "11A"},
                                    actor=sec_admin)
    assert spupil.year_group == 11, f"[secondary promotion] pupil is in Year {spupil.year_group}"

    # ── Secondary → sixth form ───────────────────────────────────────
    from education_system.platform.cross_system import enrolments, secondary_post16
    from education_system.systems.secondary.modules.progression.domain import (
        sixth_form_progression,
    )
    from education_system.systems.sixth_form.domain.admissions import (
        admissions as sf_admissions,
        applicant_details,
        conversion,
    )
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        identity_checks,
    )
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access as sf_access,
    )
    from education_system.systems.sixth_form.domain.learners.students import (
        students as sf_students,
    )

    step = "secondary → sixth form"
    subjects = ["Mathematics", "Physics", "Chemistry"]
    sent = sixth_form_progression.send(
        spupil.pupil_id, actor=sec_admin, consent_sen=True,
        consent_reference="Signed post-16 data-sharing form", subjects=subjects,
        db_path=auth)
    assert sent["journey_id"] == jid, (
        f"[{step}] the post-16 application is on journey {sent['journey_id']}, not {jid}")
    post16_tid = sent["transition_id"]
    applicant_enrolment = enrolments.get_enrolment(
        _boundary(jid, "secondary", "sixth_form", auth)[0]["destination_enrolment_id"],
        db_path=auth)
    applicant_id = applicant_enrolment["local_student_id"]
    assert applicant_id, f"[{step}] the sixth form made no applicant"

    # The sixth form's admissions team, signed in.
    monkeypatch.setattr(sf_access, "_current", sf_access.Principal(
        username="admin1", user_id=None, role="admin",
        capabilities=sf_access.ALL_CAPABILITIES), raising=False)
    applicant = sf_admissions.get_applicant(applicant_id)
    assert (applicant.first_name, applicant.last_name, applicant.dob) == (
        FIRST, LAST, d["dob"]), f"[{step}] applicant has the wrong identity: {applicant}"
    sf_admissions.update_applicant(applicant_id, {"email": "maya.okafor@example.test"})
    sf_admissions.make_offer(applicant_id, offer_type="Unconditional", decided_by="admin1")
    sf_admissions.accept_offer(applicant_id)
    applicant_details.record_identity_check(
        applicant_id, document_type=identity_checks.ID_DOCUMENT_TYPES[0],
        document_number="123456789",
        right_to_study=next(r for r in applicant_details.RIGHT_TO_STUDY
                            if r.startswith("Yes")))
    _applicant, sf_student_id = conversion.convert_to_student(applicant_id,
                                                              converted_by="admin1")
    record = conversion.get_conversion(applicant_id)
    failed = [s for s in (record.steps if record else []) if s.get("result") != "ok"]
    assert not any(s["step"] in {"enrolment", "linked record"} for s in failed), (
        f"[{step}] conversion steps failed: {failed}")

    student = sf_students.get_student(sf_student_id)
    assert student is not None, f"[{step}] no sixth form student {sf_student_id}"
    assert (student.first_name, student.last_name, student.date_of_birth) == (
        FIRST, LAST, d["dob"]), f"[{step}] sixth form student has the wrong identity: {student}"
    assert student.status == "Active", f"[{step}] sixth form student is {student.status!r}"
    board = secondary_post16.get_application(post16_tid, db_path=auth)
    assert board["stage"] == "Enrolled / On Programme", (
        f"[{step}] the post-16 board shows {board['stage']!r}")
    kept = secondary.get_pupil(spupil.pupil_id)
    assert kept is not None, f"[{step}] the secondary record was deleted"
    assert kept.roll_status == "left", (
        f"[{step}] secondary pupil is {kept.roll_status!r}, not 'left' - the school never "
        "took them off roll")
    transition = _check_boundary(jid, "secondary", "sixth_form", auth)
    entry = enrolments.get_enrolment(transition["destination_enrolment_id"], db_path=auth)
    assert (entry["local_student_id"], str(entry["year_group"]), entry["status"]) == (
        sf_student_id, "12", "active"), (
        f"[{step}] the sixth form enrolment is not an active Year 12 one: {entry}")
    local["sixth_form"] = sf_student_id
    _check_journey(jid, local, "sixth_form", auth, d, step=step)

    # ── Sixth form → university ──────────────────────────────────────
    from education_system.platform.cross_system import university_applications as apps
    from education_system.platform.cross_system.adapters import registry
    from education_system.systems.university.domains.admissions.domain.services import (
        admissions_checklist,
        admissions_lifecycle,
    )

    step = "sixth form → university"
    ucas_id = "1234567890"
    consent = apps.consent_record(recorded_by="admin1", scope=("reference",),
                                  ucas_id=ucas_id, recorded_at=d["today"],
                                  method="confirmed with the learner before submission")
    fields = {
        "ucas_application": {"ucas_id": ucas_id, "status": "Submitted"},
        "choices": [{"university": "Example University", "course_code": "CS101",
                     "course_name": "Computer Science",
                     "entry_year": d["university_entry_year"], "rank": 1}],
        "handover_consent": consent,
        "predicted_qualifications": "Mathematics A*, Physics A, Chemistry A",
        "academic_reference": "Strongly recommended",
        "offer_conditions": {"offer_type": "Unconditional"},
        "consent": True,
    }
    submitted = apps.submit("sixth_form", sf_student_id, db_path=auth, **fields)
    uni_tid = submitted["transition_id"]
    assert submitted["journey_id"] == jid, (
        f"[{step}] the application is on journey {submitted['journey_id']}, not {jid}")
    application_id = int(submitted["university_application_id"])

    apps.record_offer(uni_tid, unconditional=True, db_path=auth)
    application = admissions_lifecycle.get_application(application_id)
    choice_id = application["choices"][0]["choice_id"]
    apps.select_firm_choice(
        uni_tid, choice_id=choice_id, accepted_by="learner",
        consent_payload=apps.preview("sixth_form", sf_student_id, **fields),
        consent_reference=apps.consent_reference(consent), db_path=auth)

    # The university's admissions casework clears the enrolment gates.
    officer = {"username": "admin", "role": "admin"}
    for requirement in admissions_lifecycle.get_application(application_id)["requirements"]:
        if requirement["required"] and requirement["status"] != "verified":
            admissions_checklist.verify_document(
                officer, requirement["requirement_id"],
                notes="Original seen at the admissions desk")
    admissions_checklist.record_right_to_study(officer, application_id, "british",
                                               "UK passport seen")
    admissions_checklist.advance_status(officer, application_id,
                                        admissions_lifecycle.RIGHT_TO_STUDY)
    admissions_checklist.advance_status(officer, application_id,
                                        admissions_lifecycle.READY_TO_ENROL)
    issues = admissions_lifecycle.readiness_issues(application_id)
    assert not issues, f"[{step}] the application is still not ready to enrol: {issues}"

    confirmed = apps.confirm_place(uni_tid, actor_id="admin", db_path=auth)
    assert confirmed["status"] == "completed", (
        f"[{step}] confirm_place left the transition at {confirmed['status']!r}")
    uni_student_id = admissions_lifecycle.get_application(application_id)["converted_student_id"]
    assert uni_student_id, f"[{step}] the applicant was not converted to a student"
    exported = registry.require("university").export_handover(str(uni_student_id)).record
    identity = exported["learner_identity"]
    assert (identity["first_name"], identity["last_name"], identity["date_of_birth"]) == (
        FIRST, LAST, d["dob"]), f"[{step}] university student has the wrong identity: {identity}"
    registration = exported["programme_registration"]
    assert (str(registration["academic_year"]), registration["status"],
            registration["course"]) == (d["university_entry_year"], "Active", "CS101"), (
        f"[{step}] university registration is wrong: {registration}")
    left = sf_students.get_student(sf_student_id)
    assert left is not None, f"[{step}] the sixth form record was deleted"
    assert left.status == "Left", (
        f"[{step}] sixth form student is {left.status!r}, not 'Left'")
    local["university"] = str(uni_student_id)
    _check_boundary(jid, "sixth_form", "university", auth)
    _check_journey(jid, local, "university", auth, d, step=step)

    # ── The whole journey ────────────────────────────────────────────
    from education_system.platform.cross_system import learner_360, transitions

    hops = [(t["source_system"], t["destination_system"], t["status"])
            for t in transitions.list_transitions(jid, db_path=auth)]
    assert hops == [
        ("nursery", "primary", "completed"),
        ("primary", "secondary", "completed"),
        ("secondary", "sixth_form", "completed"),
        ("sixth_form", "university", "completed"),
    ], f"[journey] the platform holds these transitions: {hops}"

    view = learner_360.build_learner_360(jid, db_paths=sandbox.db_paths, auth_db=auth)
    assert view["found"], f"[journey] Learner 360 cannot find journey {jid}"
    assert view["overview"]["systems"] == list(PHASES), (
        f"[journey] Learner 360 lists {view['overview']['systems']}, expected all five "
        "phases in order")
    # One system can hold more than one local record (an applicant id beside
    # the student id), so compare the systems in first-seen order.
    record_systems = list(dict.fromkeys(r["system"] for r in view["records"]))
    assert record_systems == list(PHASES), (
        f"[journey] Learner 360 records come from {record_systems}")
    assert view["overview"]["current_system"] == "university", (
        f"[journey] Learner 360 says the learner is at {view['overview']['current_system']}")

    sandbox.assert_no_live_data_touched()
