"""Assessment & Progress buttons of the Primary School System main menu.

Every label in the category, GUI (``NAV_CATEGORIES``) and CLI
(``CATEGORIES``), is opened on an empty sandbox: the screen must open its
real view (no stub, no "Could not open", no error box / ``Error:`` line).
Then a handful of flows are driven end to end with scripted answers and
checked through the domain modules - the phonics screening pass mark, the
MTC "expected" threshold, the KS2 RWM headline, the EYFS GLD rule, target
review dates, pupil-report publishing and early-warning severity.

None of the labels here are admin-only, so a teacher opens every one; a
parent account opens none of them.

All data lives in the ``primary_sandbox`` temp directory (autouse in
``conftest.py``); nothing here may touch ``var/``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

CATEGORY = "Assessment & Progress"

# label -> text the opened screen shows as its title (GUI page heading - the
# title passed to ``kit.show_page`` - and CLI menu header).
EXPECTED: dict[str, str] = {
    "Assessment Records": "Assessment Records",
    "Phonics Screening": "Phonics Screening Check",
    "Multiplication Check": "Multiplication Tables Check",
    "KS1 SATs": "KS1 SATs",
    "KS2 SATs": "KS2 SATs",
    "EYFS Profile": "EYFS Profile",
    "Target Setting": "Target Setting",
    "Intervention Tracking": "Intervention Tracking",
    "Early Warning": "Early Warning",
    "Observations": "Observations",
    "Pupil Reports": "Pupil Reports",
}
LABELS = list(EXPECTED)

# Leaves any nested menu: "0" backs out of a screen, "" answers a "Press
# Enter" prompt (and is also "back" in every screen menu here).
BACK_OUT = ["0", ""] * 20


# ── helpers ──────────────────────────────────────────────────────────

def _gui_items() -> list[tuple[str, str]]:
    from education_system.systems.primary.gui_main import NAV_CATEGORIES
    return dict(NAV_CATEGORIES)[CATEGORY]


def _cli_items() -> list[str]:
    from education_system.systems.primary.cli_main import CATEGORIES
    return dict(CATEGORIES)[CATEGORY]


def _handler(label: str) -> str:
    return dict(_gui_items())[label]


def _new_pupil(year_group: str = "6", first: str = "Ada", last: str = "Lovelace"):
    from education_system.systems.primary.domain.learners.pupils import pupils
    return pupils.create_pupil({
        "first_name": first, "last_name": last, "year_group": year_group,
        "date_of_birth": "2014-09-01",
    })


def _run_cli(label: str, answers: list[str], scripted_input, capsys, auth) -> str:
    """Open *label* from the category submenu, answer *answers* inside the
    screen, then back out to the caller. Returns everything printed."""
    from education_system.systems.primary import cli_main

    items = _cli_items()
    scripted_input([str(items.index(label) + 1), *answers, *BACK_OUT])
    cli_main._submenu(CATEGORY, items, auth=auth)
    return capsys.readouterr().out


def _assert_clean(out: str) -> None:
    assert "[stub]" not in out
    assert "not yet implemented" not in out
    assert "Traceback" not in out
    assert "Error:" not in out
    assert "Error opening" not in out
    assert "Validation error" not in out


def _parent_principal(monkeypatch):
    from education_system.systems.primary.domain import access
    auth = SimpleNamespace(current_user={
        "username": "parent1", "role": "parent", "email": "p@example.test",
        "systems": [{"system_key": "primary", "role": "parent"}],
    })
    principal = access.from_auth(auth)
    monkeypatch.setattr(access.POLICY, "_current", principal)
    return auth, principal


def _open_in_gui(gui, label, toplevels):
    before = set(toplevels(gui))
    getattr(gui, _handler(label))()
    gui.root.update_idletasks()
    return [w for w in toplevels(gui) if w not in before]


def _tree_rows(widget) -> list[tuple]:
    from tkinter import ttk

    rows: list[tuple] = []

    def walk(w):
        if isinstance(w, ttk.Treeview):
            rows.extend(tuple(str(v) for v in w.item(iid, "values"))
                        for iid in w.get_children())
        for child in w.winfo_children():
            walk(child)

    walk(widget)
    return rows


# ── 1. Menu catalogue ───────────────────────────────────────────────

def test_gui_category_lists_every_assessment_button():
    assert [label for label, _h in _gui_items()] == LABELS


def test_cli_category_matches_gui_labels():
    assert _cli_items() == LABELS


@pytest.mark.parametrize("label", LABELS)
def test_gui_handler_is_a_real_method(label):
    from education_system.systems.primary.gui_main import PrimarySchoolMainGUI
    handler = _handler(label)
    method = getattr(PrimarySchoolMainGUI, handler, None)
    assert callable(method), f"{label}: {handler} missing on PrimarySchoolMainGUI"
    assert method.__qualname__ == f"PrimarySchoolMainGUI.{handler}"


@pytest.mark.parametrize("label", LABELS)
def test_cli_label_has_a_dispatcher(label):
    """Each label is claimed by an area ``dispatch`` (not left to the stub
    line), checked without opening the screen."""
    import importlib

    modules = {
        "Assessment Records": "assessment.assessment_cli",
        "Phonics Screening": "assessment.phonics_screening.phonics_screening_cli",
        "Multiplication Check": "assessment.mtc.mtc_cli",
        "KS1 SATs": "assessment.ks1_sats.ks1_sats_cli",
        "KS2 SATs": "assessment.ks2_sats.ks2_sats_cli",
        "EYFS Profile": "assessment.eyfs_profile.eyfs_profile_cli",
        "Target Setting": "assessment.target_setting.target_setting_cli",
        "Intervention Tracking": "assessment.intervention_tracking.intervention_tracking_cli",
        "Early Warning": "assessment.early_warning.early_warning_cli",
        "Observations": "assessment.observations.observations_cli",
        "Pupil Reports": "operations.reporting.pupil_reports.pupil_reports_cli",
    }
    mod = importlib.import_module(
        f"education_system.systems.primary.interfaces.cli.{modules[label]}")
    assert label in mod._DISPATCH


# ── 2. GUI: every button opens its screen ───────────────────────────

@pytest.mark.gui
@pytest.mark.parametrize("label", LABELS)
def test_gui_button_opens_screen(label, primary_gui, content_text, page_text,
                                 toplevels):
    gui = primary_gui
    new = _open_in_gui(gui, label, toplevels)
    text = content_text(gui)

    assert "not yet implemented" not in text
    assert "Could not open" not in text
    assert "does not have access" not in text
    assert not [m for m in gui.messages if m[0] == "showerror"], gui.messages
    assert new == [], f"{label} opened a window: {[w.title() for w in new]}"
    assert gui.content_frame.winfo_children(), f"{label} showed nothing"
    assert gui._current_page and gui._current_page[0] == EXPECTED[label]
    assert EXPECTED[label] in page_text(gui).splitlines()


# ── 3. CLI: every button opens its screen ───────────────────────────

@pytest.mark.parametrize("label", LABELS)
def test_cli_button_opens_screen(label, fake_auth, admin_principal,
                                 scripted_input, capsys):
    out = _run_cli(label, [], scripted_input, capsys, fake_auth)
    _assert_clean(out)
    assert EXPECTED[label] in out


# ── 4. Behaviour ────────────────────────────────────────────────────

def test_cli_phonics_screening_pass_mark_is_32(fake_auth, admin_principal,
                                               scripted_input, capsys):
    from education_system.systems.primary.domain.assessment.phonics_screening import (
        phonics_screening as ps,
    )
    pupil = _new_pupil("1")
    out = _run_cli("Phonics Screening", [
        "5", pupil.pupil_id, "2025-26", "1", "31", "2026-06-10", "", "",
        "5", pupil.pupil_id, "2026-27", "2", "32", "2027-06-10", "retake", "",
    ], scripted_input, capsys, fake_auth)
    _assert_clean(out)
    assert "Pass mark: 32/40" in out
    assert "31/40 (fail)" in out
    assert "32/40 (pass)" in out

    results = {r.attempt: r for r in ps.list_for_pupil(pupil.pupil_id)}
    assert results[1].score == 31 and not results[1].passed
    assert results[2].score == 32 and results[2].passed
    summary = ps.year_summary("2026-27")
    assert summary["passed"] == 1 and summary["pass_rate"] == 100.0


def test_cli_phonics_screening_rejects_bad_score_and_attempt(
        fake_auth, admin_principal, scripted_input, capsys):
    from education_system.systems.primary.domain.assessment.phonics_screening import (
        phonics_screening as ps,
    )
    pupil = _new_pupil("1")
    out = _run_cli("Phonics Screening", [
        "5", pupil.pupil_id, "2025-26", "1", "41", "", "",
        "5", pupil.pupil_id, "2025-26", "3", "20", "", "",
    ], scripted_input, capsys, fake_auth)
    assert "Validation error: Score must be between 0 and 40" in out
    assert "Validation error: Attempt must be one of 1, 2" in out
    assert ps.list_for_pupil(pupil.pupil_id) == []


def test_cli_mtc_expected_threshold_and_full_marks(fake_auth, admin_principal,
                                                   scripted_input, capsys):
    from education_system.systems.primary.domain.assessment.mtc import mtc
    a = _new_pupil("4", "Alan", "Turing")
    b = _new_pupil("4", "Grace", "Hopper")
    c = _new_pupil("4", "Katherine", "Johnson")
    out = _run_cli("Multiplication Check", [
        "5", a.pupil_id, "2025-26", "19", "", "", "",
        "5", b.pupil_id, "2025-26", "20", "", "", "",
        "5", c.pupil_id, "2025-26", "25", "", "", "",
        "5", c.pupil_id, "2025-26", "26", "", "",   # out of range: no Enter prompt
        "4", "2025-26", "",
    ], scripted_input, capsys, fake_auth)
    assert "Validation error: Score must be between 0 and 25" in out
    assert "Internal 'expected' threshold: 20" in out

    by_pupil = {rec.pupil_id: rec for rec, _p in mtc.list_results(academic_year="2025-26")}
    assert len(by_pupil) == 3
    assert not by_pupil[a.pupil_id].met_expected
    assert by_pupil[b.pupil_id].met_expected and not by_pupil[b.pupil_id].full_marks
    assert by_pupil[c.pupil_id].full_marks
    s = mtc.year_summary("2025-26")
    assert (s["total"], s["met_expected"], s["below_expected"], s["full_marks"]) == (3, 2, 1, 1)
    assert "Met expected:  2" in out


def test_ks1_and_ks2_outcome_rules(fake_auth, admin_principal):
    from education_system.systems.primary.domain.assessment.ks1_sats import ks1_sats
    from education_system.systems.primary.domain.assessment.ks2_sats import ks2_sats
    from education_system.systems.primary.domain.learners.pupils.pupils import ValidationError

    assert [ks2_sats.suggest_outcome(s) for s in (None, 99, 100, 109, 110)] == [
        None, "WTS", "EXS", "EXS", "GDS"]
    assert [ks1_sats.suggest_outcome(s) for s in (84, 99, 100, 110)] == [
        "WTS", "WTS", "EXS", "GDS"]

    pupil = _new_pupil("2")
    # Science is a KS2 subject only; scaled scores stop at 60-130.
    with pytest.raises(ValidationError):
        ks1_sats.create({"pupil_id": pupil.pupil_id, "academic_year": "2025-26",
                         "subject": "Science", "outcome": "EXS"})
    with pytest.raises(ValidationError):
        ks1_sats.create({"pupil_id": pupil.pupil_id, "academic_year": "2025-26",
                         "subject": "Reading", "scaled_score": 131, "outcome": "GDS"})
    rec = ks1_sats.create({"pupil_id": pupil.pupil_id, "academic_year": "2025-26",
                           "subject": "Reading", "scaled_score": 104, "outcome": "exs"})
    assert rec.outcome == "EXS" and rec.at_or_above_expected
    with pytest.raises(ValidationError):   # one row per pupil/year/subject
        ks1_sats.create({"pupil_id": pupil.pupil_id, "academic_year": "2025-26",
                         "subject": "Reading", "outcome": "WTS"})


def test_cli_ks2_rwm_counts_only_pupils_exs_in_all_three(
        fake_auth, admin_principal, scripted_input, capsys):
    from education_system.systems.primary.domain.assessment.ks2_sats import ks2_sats
    met = _new_pupil("6", "Mary", "Somerville")
    short = _new_pupil("6", "Charles", "Babbage")
    out = _run_cli("KS2 SATs", [
        "6", met.pupil_id, "2025-26", "Reading", "105", "EXS", "", "", "",
        "6", met.pupil_id, "2025-26", "Maths", "112", "GDS", "", "", "",
        "6", met.pupil_id, "2025-26", "EGPS", "100", "EXS", "", "", "",
        "6", short.pupil_id, "2025-26", "Reading", "101", "EXS", "", "", "",
        "6", short.pupil_id, "2025-26", "Maths", "95", "WTS", "", "", "",
        "6", short.pupil_id, "2025-26", "Science", "", "EXS", "", "", "",
        "5", "2025-26", "",
    ], scripted_input, capsys, fake_auth)
    _assert_clean(out)
    assert "Pupils with any KS2 record: 2" in out
    assert "Reading, Maths, EGPS: 1 (50.0%)" in out
    s = ks2_sats.cohort_combined_summary("2025-26")
    assert (s["pupils_recorded"], s["exs_in_RWM"]) == (2, 1)


def test_cli_eyfs_gld_needs_every_prime_and_specific_elg(
        fake_auth, admin_principal, scripted_input, capsys):
    from education_system.systems.primary.domain.assessment.eyfs_profile import (
        eyfs_profile as eyfs,
    )
    pupil = _new_pupil("R", "Rosalind", "Franklin")
    for code in eyfs.GLD_CODES[1:]:
        eyfs.set_elg(pupil.pupil_id, "2025-26", code, "Expected")
    assert not eyfs.get_profile(pupil.pupil_id, "2025-26").has_gld

    # Non-GLD ELGs (Understanding the World, Arts) never count towards GLD.
    eyfs.set_elg(pupil.pupil_id, "2025-26", "UW01", "Emerging")
    out = _run_cli("EYFS Profile", [
        "3", pupil.pupil_id, "2025-26", eyfs.GLD_CODES[0].lower(), "expected", "", "", "",
        "4", "2025-26", "", "",
    ], scripted_input, capsys, fake_auth)
    _assert_clean(out)
    assert f"Recorded {eyfs.GLD_CODES[0]} for {pupil.pupil_id} (2025-26) -> Expected" in out
    profile = eyfs.get_profile(pupil.pupil_id, "2025-26")
    assert profile.has_gld and profile.gld_missing == []
    assert "Good Lvl of Dev (GLD):  1 (100.0%)" in out

    # Re-recording an ELG updates it in place (upsert), and Emerging breaks GLD.
    eyfs.set_elg(pupil.pupil_id, "2025-26", eyfs.GLD_CODES[0], "Emerging")
    profile = eyfs.get_profile(pupil.pupil_id, "2025-26")
    assert profile.elgs_recorded == len(eyfs.GLD_CODES) + 1
    assert profile.gld_missing == [eyfs.GLD_CODES[0]]


def test_cli_assessment_record_and_summary(fake_auth, admin_principal,
                                           scripted_input, capsys):
    from education_system.systems.primary.domain.assessment import assessment
    pupil = _new_pupil("3")
    out = _run_cli("Assessment Records", [
        "5", pupil.pupil_id, "2025-26", "Autumn", "Maths", "GDS", "88", "2025-12-01", "", "",
        "5", pupil.pupil_id, "2025-26", "Autumn", "Reading", "WTS", "55", "", "", "",
        "4", "2025-26", "", "", "",
    ], scripted_input, capsys, fake_auth)
    _assert_clean(out)
    assert "-> GDS" in out and "-> WTS" in out
    rows = assessment.list_for_pupil(pupil.pupil_id)
    assert sorted((r.subject, r.grade) for r in rows) == [("Maths", "GDS"), ("Reading", "WTS")]
    s = assessment.grade_summary(academic_year="2025-26")
    assert s["total"] == 2 and s["at_or_above_exs"] == 1
    assert "At or above EXS: 1 (50.0%)" in out


def test_cli_target_review_date_cannot_precede_set_on(fake_auth, admin_principal,
                                                      scripted_input, capsys):
    from education_system.systems.primary.domain.assessment.target_setting import (
        target_setting as targets,
    )
    pupil = _new_pupil("5")
    out = _run_cli("Target Setting", [
        "5", pupil.pupil_id, "2025-26", "Maths", "EXS", "", "2025-10-01", "2025-09-01", "", "",
        "5", pupil.pupil_id, "2025-26", "Maths", "EXS", "", "2025-10-01", "2026-02-01", "", "", "",
    ], scripted_input, capsys, fake_auth)
    assert "Validation error: Review date cannot be before the set-on date" in out
    rows = targets.list_for_pupil(pupil.pupil_id)
    assert len(rows) == 1
    assert rows[0].target_grade == "EXS" and rows[0].status == "open"


def test_cli_pupil_report_published_report_is_locked(fake_auth, admin_principal,
                                                     scripted_input, capsys):
    from education_system.systems.primary.domain.operations.reporting.pupil_reports import (
        pupil_reports as reports,
    )
    pupil = _new_pupil("4")
    out = _run_cli("Pupil Reports", [
        # 6) create draft: id, year, term, headline, author, attendance,
        # behaviour, three multi-line blocks (each ended by ""), notes, Enter
        "6", pupil.pupil_id, "2025-26", "Autumn", "A strong term", "Ms Teach", "96",
        "Good", "Settled well.", "", "", "", "", "",
    ], scripted_input, capsys, fake_auth)
    _assert_clean(out)
    (draft,) = reports.list_for_pupil(pupil.pupil_id)
    assert draft.status == "draft" and not draft.is_published

    rid = str(draft.report_id)
    out = _run_cli("Pupil Reports", [
        "8", rid, "2025-12-15", "",
        "7", rid,
    ], scripted_input, capsys, fake_auth)
    assert f"Report #{rid} published on 2025-12-15" in out
    assert "Report is published — revert to draft first." in out
    rec = reports.get(draft.report_id)
    assert rec.is_published and rec.published_on == "2025-12-15"


def test_cli_early_warning_at_risk_uses_severity_floor(fake_auth, admin_principal,
                                                       scripted_input, capsys):
    from education_system.systems.primary.domain.assessment.early_warning import (
        early_warning as ew,
    )
    risky = _new_pupil("3", "Ada", "Risky")
    calm = _new_pupil("3", "Bo", "Calm")
    ew.create({"pupil_id": risky.pupil_id, "severity": "High",
               "title": "Falling reading age", "raised_date": "2025-10-01"})
    ew.create({"pupil_id": calm.pupil_id, "severity": "Low",
               "title": "Missed homework", "raised_date": "2025-10-01"})
    ew.create({"pupil_id": calm.pupil_id, "severity": "Critical", "status": "Resolved",
               "resolution": "Sorted", "title": "Old issue", "raised_date": "2025-09-01",
               "resolved_date": "2025-09-20"})
    out = _run_cli("Early Warning", ["8", "", ""], scripted_input, capsys, fake_auth)
    _assert_clean(out)
    assert "1 pupil(s) with open alerts at ≥ High" in out
    assert "Falling reading age" in out
    assert "Old issue" not in out and "Missed homework" not in out
    assert set(ew.pupils_at_risk(severity_min="Low")) == {risky.pupil_id, calm.pupil_id}


@pytest.mark.gui
def test_gui_phonics_screening_lists_pass_and_fail(primary_gui, toplevels):
    from education_system.systems.primary.domain.assessment.phonics_screening import (
        phonics_screening as ps,
    )
    p1 = _new_pupil("1", "Pass", "Pupil")
    p2 = _new_pupil("1", "Fail", "Pupil")
    ps.create({"pupil_id": p1.pupil_id, "academic_year": "2025-26", "attempt": 1, "score": 35})
    ps.create({"pupil_id": p2.pupil_id, "academic_year": "2025-26", "attempt": 1, "score": 12})

    assert _open_in_gui(primary_gui, "Phonics Screening", toplevels) == []
    rows = {r[1]: r for r in _tree_rows(primary_gui.content_frame)}
    assert rows[p1.pupil_id][6:8] == ("35/40", "pass")
    assert rows[p2.pupil_id][6:8] == ("12/40", "fail")


# ── 5. Access ───────────────────────────────────────────────────────

def test_no_assessment_label_is_restricted_for_staff(staff_principal):
    from education_system.systems.primary.domain import access
    for label in LABELS:
        assert label not in access.ADMIN_ONLY
        assert staff_principal.can_open(label), label
    menu = dict(staff_principal.visible_menu(
        __import__("education_system.systems.primary.cli_main",
                   fromlist=["CATEGORIES"]).CATEGORIES, labels_only=True))
    assert menu[CATEGORY] == LABELS


@pytest.mark.parametrize("label", LABELS)
def test_cli_teacher_can_open(label, staff_auth, staff_principal,
                              scripted_input, capsys):
    out = _run_cli(label, [], scripted_input, capsys, staff_auth)
    _assert_clean(out)
    assert "does not have access" not in out
    assert EXPECTED[label] in out


@pytest.mark.gui
@pytest.mark.parametrize("label", LABELS)
def test_gui_teacher_can_open(label, primary_gui, staff_principal,
                              content_text, page_text, toplevels):
    gui = primary_gui
    gui.principal = staff_principal
    new = _open_in_gui(gui, label, toplevels)
    text = content_text(gui)
    assert "does not have access" not in text
    assert new == [], f"{label} opened a window: {[w.title() for w in new]}"
    assert EXPECTED[label] in page_text(gui).splitlines()


def test_parent_menu_hides_assessment_category(monkeypatch):
    from education_system.systems.primary.cli_main import CATEGORIES
    _auth, principal = _parent_principal(monkeypatch)
    assert CATEGORY not in dict(principal.visible_menu(CATEGORIES, labels_only=True))
    assert not any(principal.can_open(label) for label in LABELS)


@pytest.mark.parametrize("label", ["Assessment Records", "KS2 SATs", "Pupil Reports"])
def test_cli_parent_is_refused(label, monkeypatch, scripted_input, capsys):
    auth, _principal = _parent_principal(monkeypatch)
    out = _run_cli(label, [], scripted_input, capsys, auth)
    assert f"Your account does not have access to {label}." in out
    assert f"-- {EXPECTED[label]} --" not in out


@pytest.mark.gui
@pytest.mark.parametrize("label", ["Assessment Records", "Early Warning", "Pupil Reports"])
def test_gui_parent_is_refused(label, primary_gui, monkeypatch, content_text, toplevels):
    gui = primary_gui
    _auth, gui.principal = _parent_principal(monkeypatch)
    new = _open_in_gui(gui, label, toplevels)
    assert new == []
    assert f"Your account does not have access to {label}." in content_text(gui)
