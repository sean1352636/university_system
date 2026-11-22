"""Pastoral & Wellbeing buttons of the Primary School System main menu.

Every button in the category is opened from the GUI sidebar handler and from
the CLI submenu on an empty sandbox (see ``conftest.py``), then a handful of
flows are driven end to end with a real pupil. The category carries the
safeguarding-lead rules from ``domain/access.py``:

* ``Safeguarding`` is *raise only* for staff who are not a DSL - they get the
  "raise a concern" form, never the list of concerns;
* ``Prevent Duty`` is for admins and DSLs only;
* a DSL is a staff record with ``is_dsl`` whose staff id or e-mail matches
  the login.
"""

from __future__ import annotations

import pytest

CATEGORY = "Pastoral & Wellbeing"

EXPECTED_GUI = [
    ("Class Teachers", "open_class_teachers"),
    ("Behaviour Log", "open_behaviour"),
    ("House Points", "open_house_points"),
    ("Safeguarding", "open_safeguarding"),
    ("SEND", "open_send"),
    ("Pupil Premium", "open_pupil_premium"),
    ("Accessibility", "open_accessibility"),
    ("Wellbeing", "open_wellbeing"),
    ("Pupil Support", "open_pupil_support"),
    ("Attendance Concerns", "open_attendance_concerns"),
    ("Absence Requests", "open_absence_requests"),
    ("First Aid", "open_first_aid"),
    ("Medical Records", "open_medical"),
    ("Emergency Contacts", "open_emergency"),
    ("Prevent Duty", "open_prevent_duty"),
    ("Equality & Diversity", "open_equality_diversity"),
    ("Complaints", "open_complaints"),
    ("Feedback", "open_feedback"),
    ("Surveys", "open_surveys"),
    ("School Council", "open_school_council"),
    ("Breakfast / After-School Club", "open_wraparound_care"),
    ("Transport", "open_transport"),
]
EXPECTED_LABELS = [label for label, _handler in EXPECTED_GUI]

#: The page heading each GUI button draws in the main window's content area
#: (the title passed to ``kit.show_page``); the label unless listed here.
GUI_PAGE_TITLES = {label: label for label in EXPECTED_LABELS}
GUI_PAGE_TITLES["Emergency Contacts"] = "Emergency & Drills"

# The heading each CLI screen prints when it opens.
CLI_HEADERS = {
    "Class Teachers": "-- Class Teachers --",
    "Behaviour Log": "── Behaviour Log ──",
    "House Points": "-- House Points --",
    "Safeguarding": "── Safeguarding ──",
    "SEND": "── SEND ──",
    "Pupil Premium": "── Pupil Premium ──",
    "Accessibility": "── Accessibility ──",
    "Wellbeing": "── Wellbeing ──",
    "Pupil Support": "── Pupil Support ──",
    "Attendance Concerns": "── Attendance Concerns ──",
    "Absence Requests": "── Absence Requests ──",
    "First Aid": "── First Aid ──",
    "Medical Records": "-- Medical Records --",
    "Emergency Contacts": "── Emergency & Drills ──",
    "Prevent Duty": "── Prevent Duty ──",
    "Equality & Diversity": "── Equality & Diversity ──",
    "Complaints": "── Complaints ──",
    "Feedback": "── Feedback ──",
    "Surveys": "── Surveys ──",
    "School Council": "── School Council ──",
    "Breakfast / After-School Club": "-- Breakfast / After-School Club --",
    "Transport": "── Transport ──",
}

BACK_OUT = ["0", ""] * 20


# ── helpers ──────────────────────────────────────────────────────────

class _Auth:
    """A signed-in session for someone other than the conftest's admin and
    teacher (the conftest's ``FakeAuth`` cannot be imported here)."""

    def __init__(self, username: str, role: str):
        self.current_user = {
            "username": username,
            "role": role,
            "user_id": 2,
            "id": 2,
            "email": f"{username}@example.test",
            "display_name": username,
            "systems": [{"system_key": "primary", "role": role}],
        }

    def get_current_user(self):
        return self.current_user

    def is_authenticated(self) -> bool:
        return True

    def logout(self) -> None:
        pass


def _install(auth, monkeypatch):
    from education_system.systems.primary.domain import access
    principal = access.from_auth(auth)
    monkeypatch.setattr(access.POLICY, "_current", principal)
    return principal


def _make_dsl(*, email: str | None = None):
    from education_system.systems.primary.domain.staff import staff
    data = {"first_name": "Dee", "last_name": "Lead", "is_dsl": True}
    if email:
        data["email"] = email
    return staff.create_staff(data)


def _pupil(first: str = "Ada", last: str = "Lovelace", year: str = "3"):
    from education_system.systems.primary.domain.learners.pupils import pupils
    return pupils.create_pupil(
        {"first_name": first, "last_name": last, "year_group": year})


def _items():
    from education_system.systems.primary.cli_main import CATEGORIES
    return dict(CATEGORIES)[CATEGORY]


def _choice(label: str) -> str:
    return str(_items().index(label) + 1)


def _run_cli(label, answers, *, auth, scripted_input, capsys):
    from education_system.systems.primary import cli_main
    prompts = scripted_input([_choice(label), *answers])
    cli_main._submenu(CATEGORY, _items(), auth=auth)
    return capsys.readouterr().out, prompts


def _assert_clean(out: str) -> None:
    assert "[stub]" not in out
    assert "Traceback" not in out
    assert "Error:" not in out
    assert "Validation error" not in out


def _require_display():
    tk = pytest.importorskip("tkinter")
    try:
        probe = tk.Tk()
        probe.destroy()
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")


def _gui_for(auth, principal, monkeypatch):
    """A ``PrimarySchoolMainGUI`` for any principal, with message boxes
    recorded in ``gui.messages`` (like the conftest's admin ``primary_gui``)."""
    _require_display()
    from tkinter import messagebox, simpledialog

    from education_system.systems.primary import gui_main

    messages: list[tuple[str, str, str]] = []

    def recorder(kind, result):
        def call(title="", message="", *args, **kwargs):
            messages.append((kind, str(title), str(message)))
            return result
        return call

    for kind, result in (("showinfo", "ok"), ("showwarning", "ok"),
                         ("showerror", "ok"), ("askyesno", False),
                         ("askokcancel", False), ("askyesnocancel", None),
                         ("askquestion", "no"), ("askretrycancel", False)):
        monkeypatch.setattr(messagebox, kind, recorder(kind, result))
    for kind in ("askstring", "askinteger", "askfloat"):
        monkeypatch.setattr(simpledialog, kind, recorder(kind, None))
    monkeypatch.setattr(gui_main, "install_idle_logout",
                        lambda root, logout: (lambda: None))
    gui = gui_main.PrimarySchoolMainGUI(auth, principal)
    gui.messages = messages
    gui.root.withdraw()
    return gui


def _destroy(gui) -> None:
    import tkinter as tk
    try:
        for child in gui.root.winfo_children():
            child.destroy()
        gui.root.destroy()
    except tk.TclError:
        pass


@pytest.fixture
def dialogs_return_immediately(monkeypatch):
    """Modal dialogs (``wait_window`` / ``wait_visibility``) return at once,
    leaving the dialog open so the test can see it."""
    import tkinter as tk
    monkeypatch.setattr(tk.Misc, "wait_window", lambda self, window=None: None)
    # The test window is withdrawn, so a transient dialog never becomes
    # viewable and ``wait_visibility`` would block forever.
    monkeypatch.setattr(tk.Misc, "wait_visibility", lambda self, window=None: None)


# ── 1. The catalogue ─────────────────────────────────────────────────

def test_gui_nav_category_lists_every_pastoral_button():
    from education_system.systems.primary import gui_main
    entries = dict(gui_main.NAV_CATEGORIES)[CATEGORY]
    assert entries == EXPECTED_GUI


@pytest.mark.parametrize("label,handler", EXPECTED_GUI, ids=EXPECTED_LABELS)
def test_gui_handler_is_a_real_method(label, handler):
    from education_system.systems.primary.gui_main import PrimarySchoolMainGUI
    method = getattr(PrimarySchoolMainGUI, handler, None)
    assert callable(method), f"{label}: {handler} would fall back to the stub"


def test_cli_category_matches_the_gui():
    assert _items() == EXPECTED_LABELS


def test_no_pastoral_button_is_admin_only():
    from education_system.systems.primary.domain import access
    assert not set(EXPECTED_LABELS) & access.ADMIN_ONLY
    assert access.POLICY.dsl_only == {"Prevent Duty"}
    assert access.POLICY.raise_only == {"Safeguarding"}


# ── 2. GUI: every button opens a screen (admin) ──────────────────────

@pytest.mark.gui
@pytest.mark.parametrize("label,handler", EXPECTED_GUI, ids=EXPECTED_LABELS)
def test_gui_button_opens(label, handler, primary_gui, content_text, page_text,
                          toplevels, dialogs_return_immediately):
    gui = primary_gui
    before_children = set(gui.content_frame.winfo_children())
    before_tops = set(toplevels(gui))

    getattr(gui, handler)()
    gui.root.update_idletasks()

    text = content_text(gui)
    assert "not yet implemented" not in text
    assert "Could not open" not in text
    assert "does not have access" not in text
    assert not [m for m in gui.messages if m[0] == "showerror"], gui.messages
    new_tops = [w for w in toplevels(gui) if w not in before_tops]
    new_children = set(gui.content_frame.winfo_children()) - before_children
    assert not new_tops, f"{label} opened a window: {[w.title() for w in new_tops]}"
    assert new_children, f"{label} put nothing in the content area"
    title = GUI_PAGE_TITLES[label]
    assert gui._current_page and gui._current_page[0] == title, gui._current_page
    assert title in page_text(gui).splitlines(), f"{label}: no {title!r} heading"


# ── 3. CLI: every button opens its screen (admin) ────────────────────

@pytest.mark.parametrize("label", EXPECTED_LABELS)
def test_cli_button_opens(label, fake_auth, admin_principal, scripted_input,
                          capsys):
    out, _prompts = _run_cli(label, BACK_OUT, auth=fake_auth,
                             scripted_input=scripted_input, capsys=capsys)
    _assert_clean(out)
    assert CLI_HEADERS[label] in out
    assert "does not have access" not in out


# ── 4. Behaviour ─────────────────────────────────────────────────────

def test_cli_behaviour_log_incident_then_list(fake_auth, admin_principal,
                                              scripted_input, capsys):
    from education_system.systems.primary.domain.pastoral.behaviour import behaviour
    pupil = _pupil()
    answers = [
        "1",                                  # Log incident
        pupil.pupil_id, "2026-11-02", "10:15", "Hall", "",
        "Helping others", "3", "", "Helped a classmate", "Ms Test", "",
        "", "",
        "2", "", "", "", "", "", "", "", "",  # List incidents + Enter
        "0", "0",
    ]
    out, _ = _run_cli("Behaviour Log", answers, auth=fake_auth,
                      scripted_input=scripted_input, capsys=capsys)
    _assert_clean(out)
    assert "Logged #1 (Helping others, pts=+3" in out
    assert "1 incident(s):" in out
    assert pupil.pupil_id in out

    [incident] = behaviour.list_incidents(pupil_id=pupil.pupil_id)
    assert incident.polarity == "positive"
    assert incident.points == 3
    assert incident.description == "Helped a classmate"


def test_behaviour_sign_rules_are_enforced():
    from education_system.systems.primary.domain.pastoral.behaviour import behaviour
    pupil = _pupil()
    with pytest.raises(behaviour.ValidationError):
        behaviour.log_incident({"pupil_id": pupil.pupil_id,
                                "incident_type": "Disruption", "points": "2",
                                "description": "Shouting"})
    bad = behaviour.log_incident({"pupil_id": pupil.pupil_id,
                                  "incident_date": "2026-11-02",
                                  "incident_type": "Disruption",
                                  "description": "Shouting"})
    assert bad.points == -1
    with pytest.raises(behaviour.ValidationError):
        behaviour.log_incident({"pupil_id": "NOPE", "incident_type": "Lateness",
                                "description": "Late"})


def test_house_points_award_shows_on_cli_leaderboard(fake_auth, admin_principal,
                                                     scripted_input, capsys):
    from education_system.systems.primary.domain.pastoral.house_points import house_points
    pupil = _pupil()
    oak = house_points.create_house({"name": "Oak", "colour": "Green"})
    house_points.create_house({"name": "Ash"})
    house_points.award_points({"house_id": oak.house_id,
                               "pupil_id": pupil.pupil_id, "points": 5,
                               "reason": "Kindness"})

    totals = {house.name: pts for house, pts in house_points.house_totals()}
    assert totals == {"Oak": 5, "Ash": 0}
    assert house_points.pupil_total(pupil.pupil_id) == 5

    out, _ = _run_cli("House Points", BACK_OUT, auth=fake_auth,
                      scripted_input=scripted_input, capsys=capsys)
    _assert_clean(out)
    assert "Leaderboard:" in out
    assert "Oak" in out


# ── 4. Health ────────────────────────────────────────────────────────

def test_first_aid_incident_is_listed_and_counted():
    from education_system.systems.primary.domain.pastoral.health.first_aid import first_aid
    pupil = _pupil()
    first_aid.create({"pupil_id": pupil.pupil_id, "incident_date": "2026-11-02",
                      "incident_time": "12:30", "location": "Playground",
                      "injury_type": "Cut/Graze", "description": "Fell over",
                      "treatment": "Cleaned and plaster", "treated_by": "Ms Aid",
                      "parent_contacted": True})
    [row] = first_aid.list_incidents(pupil_id=pupil.pupil_id)
    assert row.location == "Playground"
    assert row.injury_type == "Cut/Graze"
    summary = first_aid.cohort_summary()
    assert summary["total"] == 1
    assert summary["parent_contacted"] == 1
    assert summary["by_injury"] == {"Cut/Graze": 1}


def test_medical_record_shows_in_cli_header(fake_auth, admin_principal,
                                            scripted_input, capsys):
    from education_system.systems.primary.domain.pastoral.health.medical_records import (
        medical_records,
    )
    pupil = _pupil()
    medical_records.create({"pupil_id": pupil.pupil_id, "record_type": "allergy",
                            "title": "Peanut allergy", "severity": "critical"})
    out, _ = _run_cli("Medical Records", BACK_OUT, auth=fake_auth,
                      scripted_input=scripted_input, capsys=capsys)
    _assert_clean(out)
    assert "Active: 1/1" in out
    assert "Critical (active): 1" in out
    assert "Pupils with records: 1" in out


# ── 4. Wellbeing, absence, SEND ──────────────────────────────────────

def test_low_wellbeing_check_in_flags_the_pupil():
    from education_system.systems.primary.domain.pastoral.wellbeing import wellbeing
    sad, happy = _pupil("Sam", "Low"), _pupil("Hal", "High")
    wellbeing.log_checkin({"pupil_id": sad.pupil_id, "checkin_date": "2026-11-02",
                           "mood_rating": 1})
    wellbeing.log_checkin({"pupil_id": happy.pupil_id,
                           "checkin_date": "2026-11-02", "mood_rating": 5})
    flagged = wellbeing.low_wellbeing(threshold=2)
    assert set(flagged) == {sad.pupil_id}


def test_absence_request_approval_authorises_it():
    from education_system.systems.primary.domain.pastoral.absence_requests import (
        absence_requests,
    )
    pupil = _pupil()
    req = absence_requests.create({
        "pupil_id": pupil.pupil_id, "requested_by": "Mrs Lovelace",
        "start_date": "2026-11-16", "end_date": "2026-11-17",
        "category": "Family event (wedding/funeral)", "reason": "Wedding"})
    assert req.status == "Pending"
    decided = absence_requests.decide(req.request_id, approve=True,
                                      decided_by="Head")
    assert decided.status == "Approved"
    assert decided.authorisation == "Authorised"
    [listed] = absence_requests.list_requests(pupil_id=pupil.pupil_id)
    assert listed.status == "Approved"


def test_send_record_joins_the_register():
    from education_system.systems.primary.domain.pastoral.send import send
    pupil = _pupil()
    send.upsert({"pupil_id": pupil.pupil_id, "academic_year": "2026/27"})
    [record] = send.list_records()
    assert record.pupil_id == pupil.pupil_id
    assert send.get_for(pupil.pupil_id, "2026/27") is not None


# ── 5. Access: safeguarding lead rules ───────────────────────────────

def test_dsl_is_matched_by_email_and_staff_id(monkeypatch):
    lead = _make_dsl(email="dsl.lead@example.test")
    by_email = _install(_Auth("dsl.lead", "teacher"), monkeypatch)
    assert by_email.is_dsl
    by_id = _install(_Auth(lead.staff_id, "teacher"), monkeypatch)
    assert by_id.is_dsl


def test_staff_record_without_dsl_flag_is_not_a_dsl(monkeypatch):
    from education_system.systems.primary.domain.staff import staff
    staff.create_staff({"first_name": "Ty", "last_name": "Teach",
                        "email": "plain@example.test"})
    principal = _install(_Auth("plain", "teacher"), monkeypatch)
    assert not principal.is_dsl
    assert not principal.can_open("Prevent Duty")
    assert principal.opens_raise_only("Safeguarding")


def test_access_matrix_for_the_category(staff_principal, monkeypatch):
    from education_system.systems.primary.domain import access
    admin = access.from_auth(_Auth("boss", "admin"))
    _make_dsl(email="dsl1@example.test")
    dsl = access.from_auth(_Auth("dsl1", "teacher"))
    for label in EXPECTED_LABELS:
        assert admin.can_open(label), label
        assert dsl.can_open(label), label
        assert staff_principal.can_open(label) is (label != "Prevent Duty"), label
    assert staff_principal.opens_raise_only("Safeguarding")
    assert not dsl.opens_raise_only("Safeguarding")
    assert not admin.opens_raise_only("Safeguarding")
    pupil = access.from_auth(_Auth("kid", "student"))
    assert not any(pupil.can_open(label) for label in EXPECTED_LABELS)


def test_cli_teacher_safeguarding_only_raises_a_concern(staff_auth, staff_principal,
                                                        scripted_input, capsys):
    from education_system.systems.primary.domain.safeguarding import safeguarding
    pupil = _pupil()
    answers = [
        pupil.pupil_id, "", "", "2026-11-02", "", "Playground",
        "Pupil said something worrying", "teacher1",
    ] + [""] * 11 + ["0"]
    out, _ = _run_cli("Safeguarding", answers, auth=staff_auth,
                      scripted_input=scripted_input, capsys=capsys)
    _assert_clean(out)
    assert "Raise Safeguarding Concern" in out
    assert "Raised concern #1" in out
    assert "List concerns" not in out
    [concern] = safeguarding.list_concerns()
    assert concern.pupil_id == pupil.pupil_id
    assert concern.description == "Pupil said something worrying"
    assert concern.confidential


def test_cli_teacher_cannot_open_prevent_duty(staff_auth, staff_principal,
                                              scripted_input, capsys):
    out, _ = _run_cli("Prevent Duty", ["0"], auth=staff_auth,
                      scripted_input=scripted_input, capsys=capsys)
    assert "Your account does not have access to Prevent Duty." in out
    assert CLI_HEADERS["Prevent Duty"] not in out


@pytest.mark.parametrize("label", ["Safeguarding", "Prevent Duty"])
def test_cli_dsl_teacher_gets_the_full_screens(label, monkeypatch,
                                               scripted_input, capsys):
    _make_dsl(email="dsl1@example.test")
    auth = _Auth("dsl1", "teacher")
    assert _install(auth, monkeypatch).is_dsl
    out, _ = _run_cli(label, BACK_OUT, auth=auth,
                      scripted_input=scripted_input, capsys=capsys)
    _assert_clean(out)
    assert CLI_HEADERS[label] in out
    assert "does not have access" not in out
    if label == "Safeguarding":
        assert "List concerns" in out


def test_prevent_referral_by_dsl_is_counted(monkeypatch):
    from education_system.systems.primary.domain.safeguarding.prevent_duty import (
        prevent_duty,
    )
    _make_dsl(email="dsl1@example.test")
    pupil = _pupil()
    referral = {"pupil_id": pupil.pupil_id, "raised_by": "dsl1",
                "description": "Sharing extremist videos",
                "risk_level": "High",
                "referral_pathway": "Channel referral (Prevent)",
                "referral_date": "2026-11-03"}
    # An external referral needs the DSL informed first.
    with pytest.raises(ValueError, match="DSL must be informed"):
        prevent_duty.create(referral)
    assert prevent_duty.cohort_summary()["total"] == 0

    prevent_duty.create({**referral, "dsl_informed": True, "dsl_name": "Dee Lead"})
    summary = prevent_duty.cohort_summary()
    assert summary["total"] == 1
    assert summary["open"] == 1
    assert summary["high_risk"] == 1
    assert summary["channel"] == 1


@pytest.mark.gui
def test_gui_teacher_safeguarding_opens_raise_form_only(staff_auth, staff_principal,
                                                        monkeypatch, toplevels,
                                                        dialogs_return_immediately):
    from education_system.systems.primary.interfaces.gui.safeguarding import (
        safeguarding_views,
    )
    opened_records: list[object] = []
    real = safeguarding_views.open_safeguarding
    monkeypatch.setattr(safeguarding_views, "open_safeguarding",
                        lambda host: (opened_records.append(host), real(host)))
    gui = _gui_for(staff_auth, staff_principal, monkeypatch)
    try:
        before = set(toplevels(gui))
        gui.open_safeguarding()
        new = [w for w in toplevels(gui) if w not in before]
        assert [w.title() for w in new] == ["Raise safeguarding concern"]
        assert opened_records == []
        assert not [m for m in gui.messages if m[0] == "showerror"]
    finally:
        _destroy(gui)


@pytest.mark.gui
def test_gui_teacher_prevent_duty_is_denied(staff_auth, staff_principal,
                                           monkeypatch, content_text, toplevels):
    gui = _gui_for(staff_auth, staff_principal, monkeypatch)
    try:
        before = set(toplevels(gui))
        gui.open_prevent_duty()
        assert "Your account does not have access to Prevent Duty." in content_text(gui)
        assert set(toplevels(gui)) == before
    finally:
        _destroy(gui)


@pytest.mark.gui
@pytest.mark.parametrize("label,handler", [("Safeguarding", "open_safeguarding"),
                                           ("Prevent Duty", "open_prevent_duty")])
def test_gui_dsl_teacher_gets_the_full_screens(label, handler, monkeypatch,
                                               content_text, page_text, toplevels):
    _make_dsl(email="dsl1@example.test")
    auth = _Auth("dsl1", "teacher")
    principal = _install(auth, monkeypatch)
    assert principal.is_dsl
    gui = _gui_for(auth, principal, monkeypatch)
    try:
        before = set(toplevels(gui))
        getattr(gui, handler)()
        gui.root.update_idletasks()
        text = content_text(gui)
        assert "does not have access" not in text
        assert "Could not open" not in text
        assert label in text
        assert label in page_text(gui).splitlines()
        # The full screen renders in the content frame, not a raise dialog.
        assert [w for w in toplevels(gui) if w not in before] == []
        assert not [m for m in gui.messages if m[0] == "showerror"]
    finally:
        _destroy(gui)
