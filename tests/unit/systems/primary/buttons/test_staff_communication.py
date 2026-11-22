"""Button tests for the Primary School main menu: Staff & Communication.

Every label in the category is opened on an empty sandbox (see ``conftest``)
from both front ends:

* GUI - ``NAV_CATEGORIES`` maps each label to a real ``open_*`` method, and
  calling it puts a window on screen with no error box, stub text or
  "Could not open";
* CLI - ``_submenu`` routes each label to its area's ``dispatch``, the
  area's own header is printed, and backing out with ``0`` / Enter leaves
  cleanly with no ``[stub]`` or error text.

Then a handful of behaviour checks through the CLI flows and the domain
modules behind the buttons (staff directory, visitors, announcements,
messaging, letter templates, newsletters), and the access rules: nothing in
this category is admin-only, so a teacher opens all of it, while pupil and
parent accounts see none of it.
"""

from __future__ import annotations

import re

import pytest

from education_system.systems.primary import cli_main, gui_main

CATEGORY = "Staff & Communication"

#: label -> GUI handler, in menu order.
EXPECTED: dict[str, str] = {
    "Staff Directory": "open_staff",
    "Teaching Assistants": "open_tas",
    "Staff HR": "open_staff_hr",
    "Staff Absence": "open_staff_absence",
    "Staff Wellbeing": "open_staff_wellbeing",
    "Recruitment": "open_recruitment",
    "Appraisals": "open_appraisals",
    "CPD": "open_cpd",
    "DBS Checks": "open_dbs_checks",
    "Visitors": "open_visitors",
    "Parent Contacts": "open_parents",
    "Parents' Evenings": "open_parents_evenings",
    "Newsletters": "open_newsletters",
    "Announcements": "open_announcements",
    "Notifications": "open_notifications",
    "Activity Feed": "open_activity_feed",
    "Email / Messaging": "open_messaging",
    "Letter Templates": "open_letter_templates",
    "Document Hub": "open_document_hub",
    "Attachments": "open_attachments",
}
LABELS = list(EXPECTED)

#: The page heading each GUI button draws in the main window's content area
#: (the title passed to ``kit.show_page``); here every one is the label.
GUI_PAGE_TITLES = {label: label for label in LABELS}

#: Enough "Back" / Enter answers to leave any nested menu.
BACK_OUT = ["0", ""] * 20

#: Text a CLI screen prints when it crashed or fell through to the stub.
CLI_FAILURE_MARKERS = ("[stub]", "Traceback", "Error:", "Error opening",
                       "Unexpected error", "not yet implemented")


def _gui_items() -> list[tuple[str, str]]:
    return dict(gui_main.NAV_CATEGORIES)[CATEGORY]


def _cli_items() -> list[str]:
    return dict(cli_main.CATEGORIES)[CATEGORY]


def _run_cli(label, auth, scripted_input, capsys, then=()):
    """Open *label* from the category submenu, answer *then*, back out.
    Returns (stdout, prompts seen)."""
    items = _cli_items()
    choice = str(items.index(label) + 1)
    prompts = scripted_input([choice, *then, *BACK_OUT])
    cli_main._submenu(CATEGORY, items, auth=auth)
    return capsys.readouterr().out, prompts


def _header(label: str) -> re.Pattern[str]:
    """The area's own header line: ``── Label ──`` or ``-- Label --``."""
    return re.compile(r"(──|--)\s*" + re.escape(label) + r"\s*(──|--)")


def _assert_cli_clean(out: str) -> None:
    for marker in CLI_FAILURE_MARKERS:
        assert marker not in out, f"{marker!r} in CLI output:\n{out[-2000:]}"


# ── Menu catalogue ───────────────────────────────────────────────────

def test_gui_category_lists_expected_labels_and_handlers():
    assert dict(_gui_items()) == EXPECTED
    assert [label for label, _h in _gui_items()] == LABELS


def test_cli_category_lists_same_labels_as_gui():
    assert _cli_items() == LABELS


@pytest.mark.parametrize("label", LABELS)
def test_gui_handler_is_a_real_method(label):
    handler = EXPECTED[label]
    cls = gui_main.PrimarySchoolMainGUI
    # Defined on the class itself, so the nav button never falls back to
    # the "not yet implemented" stub.
    assert handler in vars(cls), f"{handler} missing for {label}"
    assert callable(getattr(cls, handler))
    assert getattr(cls, handler) is not cls._show_stub


# ── GUI: every button opens a screen ─────────────────────────────────

@pytest.mark.gui
@pytest.mark.parametrize("label", LABELS)
def test_gui_button_opens_screen(label, primary_gui, content_text, page_text,
                                 toplevels):
    gui = primary_gui
    before = set(toplevels(gui))

    getattr(gui, EXPECTED[label])()
    gui.root.update_idletasks()

    text = content_text(gui)
    assert "not yet implemented" not in text
    assert "Could not open" not in text
    assert "does not have access" not in text
    errors = [m for m in gui.messages if m[0] == "showerror"]
    assert not errors, errors
    opened = [w for w in toplevels(gui) if w not in before]
    # Each of these screens is a page in the main window, headed by the label.
    assert opened == [], f"{label} opened a window: {[w.title() for w in opened]}"
    assert gui.content_frame.winfo_children(), "nothing on screen"
    title = GUI_PAGE_TITLES[label]
    assert gui._current_page and gui._current_page[0] == title, gui._current_page
    assert title in page_text(gui).splitlines(), f"{label}: no {title!r} heading"


# ── CLI: every item opens its area's menu ────────────────────────────

@pytest.mark.parametrize("label", LABELS)
def test_cli_item_opens_area_menu(label, fake_auth, admin_principal,
                                  scripted_input, capsys):
    out, prompts = _run_cli(label, fake_auth, scripted_input, capsys)

    _assert_cli_clean(out)
    assert _header(label).search(out), f"no header for {label}:\n{out[:1500]}"
    # Picked the item, backed out of the area, then out of the submenu.
    assert len(prompts) >= 3


# ── Behaviour: Staff Directory ───────────────────────────────────────

def test_staff_roles_and_departments_are_primary_school_values():
    from education_system.systems.primary.domain.staff import staff

    for role in ("Headteacher", "Deputy Headteacher", "EYFS Lead", "KS1 Lead",
                 "KS2 Lead", "SENCO", "Teaching Assistant",
                 "Higher Level Teaching Assistant", "Midday Supervisor",
                 "Safeguarding Lead (DSL)"):
        assert role in staff.ROLES
    for dept in ("EYFS", "KS1", "KS2", "Phonics & Reading", "SEND"):
        assert dept in staff.DEPARTMENTS
    secondary_words = ("Sixth Form", "Head of Year", "KS3", "KS4", "KS5",
                       "Exams Officer")
    for value in (*staff.ROLES, *staff.DEPARTMENTS):
        assert not any(w in value for w in secondary_words), value
    assert staff.DEFAULT_ROLE in staff.ROLES
    assert staff.DEFAULT_DEPARTMENT in staff.DEPARTMENTS


def test_staff_rejects_role_outside_primary_list():
    from education_system.systems.primary.domain.staff import staff

    with pytest.raises(staff.ValidationError):
        staff.create_staff({"first_name": "Sam", "last_name": "Hill",
                            "role": "Head of Sixth Form"})
    assert staff.list_staff() == []


def test_cli_new_staff_member_is_listed(fake_auth, admin_principal,
                                       scripted_input, capsys):
    from education_system.systems.primary.domain.staff import staff

    role_no = str(staff.ROLES.index("SENCO") + 1)
    dept_no = str(staff.DEPARTMENTS.index("SEND") + 1)
    new_staff = [
        "6",                    # New
        "Mrs", "Ada", "Lovelace",
        role_no, dept_no, "",   # role, department, status (default)
        "", "", "", "",         # work phone, personal phone, room, manager
        "", "",                 # start (today), end
        "n", "y", "n",          # tutor, DSL, examiner
        "", "",                 # qualifications, notes
        "",                     # Press Enter
    ]
    list_all = ["2", ""]         # List All Staff, Enter leaves the actions
    out, _ = _run_cli("Staff Directory", fake_auth, scripted_input, capsys,
                      then=[*new_staff, *list_all])

    _assert_cli_clean(out)
    rows = staff.list_staff()
    assert len(rows) == 1
    member = rows[0]
    assert (member.first_name, member.last_name) == ("Ada", "Lovelace")
    assert member.role == "SENCO" and member.department == "SEND"
    assert member.is_dsl and not member.is_tutor
    assert member.staff_id.startswith("T")
    assert member.email.endswith("@primary.sch.uk")
    assert f"Created {member.staff_id}" in out
    listing = out.split("Staff Directory ═══", 1)[1]
    assert member.staff_id in listing and "Ada Lovelace" in listing
    assert "1 staff." in listing


# ── Behaviour: Visitors ──────────────────────────────────────────────

def test_visitor_sign_in_and_out_shows_on_site(fake_auth, admin_principal,
                                               scripted_input, capsys):
    from education_system.systems.primary.domain.operations.visitors import visitors

    v = visitors.create_visitor({"visitor_name": "Pat Plumber",
                                 "visitor_type": "Contractor",
                                 "purpose": "Boiler service"})
    assert v.status == "Expected"
    with pytest.raises(visitors.ValidationError):
        visitors.create_visitor({"visitor_name": "No Type",
                                 "visitor_type": "Alien"})

    signed_in = visitors.sign_in(v.visitor_id, badge_number="B7")
    assert signed_in.status == "Signed In"
    assert signed_in.badge_number == "B7" and signed_in.arrived_at

    out, _ = _run_cli("Visitors", fake_auth, scripted_input, capsys,
                      then=["2"])  # On site now
    _assert_cli_clean(out)
    assert "Pat Plumber" in out

    signed_out = visitors.sign_out(v.visitor_id)
    assert signed_out.status == "Signed Out" and signed_out.signed_out_at
    out, _ = _run_cli("Visitors", fake_auth, scripted_input, capsys,
                      then=["2"])
    assert "Pat Plumber" not in out


# ── Behaviour: Announcements ─────────────────────────────────────────

def test_published_announcement_is_live(fake_auth, admin_principal,
                                        scripted_input, capsys):
    from education_system.systems.primary.domain.operations.communications.announcements import (
        announcements,
    )

    a = announcements.create_announcement({
        "title": "Sports Day moved to Friday", "category": "Sport",
        "body": "Bring a water bottle.", "audiences": ["parents", "students"]})
    assert a.status == "Draft"
    assert announcements.list_announcements(live_only=True) == []

    published = announcements.publish(a.announcement_id)
    assert published.status == "Published" and published.published_on
    live = announcements.list_announcements(live_only=True)
    assert [x.announcement_id for x in live] == [a.announcement_id]

    out, _ = _run_cli("Announcements", fake_auth, scripted_input, capsys,
                      then=["2"])  # Live now
    _assert_cli_clean(out)
    assert "Sports Day moved to Friday" in out

    with pytest.raises(announcements.ValidationError):
        announcements.create_announcement({"title": "Bad", "priority": 9})


# ── Behaviour: Email / Messaging ─────────────────────────────────────

def test_message_send_marks_sent_without_real_email(monkeypatch):
    import smtplib

    from education_system.systems.primary.domain.operations.communications.messages import (
        messages,
    )

    def no_smtp(*args, **kwargs):
        raise AssertionError("tried to open a real SMTP connection")

    monkeypatch.setattr(smtplib, "SMTP", no_smtp)
    monkeypatch.setattr(smtplib, "SMTP_SSL", no_smtp)

    draft = messages.create_message({
        "subject": "Year 3 trip", "body": "Letter attached.",
        "to_name": "Mrs Brown", "to_address": "brown@example.test",
        "from_address": "office@primary.sch.uk"})
    assert draft.status == "Draft" and draft.direction == "Outgoing"
    assert draft.thread_id.startswith(messages.THREAD_PREFIX)

    sent = messages.send_message(draft.message_id)
    assert sent.status == "Sent" and sent.sent_at
    with pytest.raises(messages.ValidationError):
        messages.send_message(draft.message_id)  # already sent

    with pytest.raises(messages.ValidationError):
        messages.create_message({"subject": "x", "body": "y",
                                 "to_address": "not-an-email"})
    with pytest.raises(messages.ValidationError):
        messages.create_message({"subject": "x", "body": "y",
                                 "direction": "Incoming", "status": "Queued",
                                 "channel": "Phone"})


# ── Behaviour: Letter Templates ──────────────────────────────────────

def test_letter_template_renders_merge_fields():
    from education_system.systems.primary.domain.operations.communications.letter_templates import (
        letter_templates as lt,
    )

    t = lt.create_template({
        "name": "Absence follow-up",
        "subject_line": "{{pupil_name}} was absent",
        "body": "Dear {{parent_name}},\n{{pupil_name}} was absent on {{date}}."})
    assert t.detected_placeholders == ["pupil_name", "parent_name", "date"]

    partial = lt.render(t, {"pupil_name": "Ella"}, track_use=False)
    assert partial.missing_fields == ["parent_name", "date"]
    assert partial.subject == "Ella was absent"
    assert "{{parent_name}}" in partial.body

    full = lt.render(t.template_id, {"pupil_name": "Ella", "parent_name": "Mr Khan",
                                     "date": "2026-11-04"})
    assert full.missing_fields == []
    assert full.body == "Dear Mr Khan,\nElla was absent on 2026-11-04."
    assert lt.get_template(t.template_id).use_count == 1

    with pytest.raises(lt.ValidationError):
        lt.create_template({"name": "Absence follow-up", "body": "dup"})


# ── Behaviour: Newsletters ───────────────────────────────────────────

def test_newsletter_year_group_and_publish():
    from education_system.systems.primary.domain.operations.communications.newsletters import (
        newsletters as nl,
    )

    with pytest.raises(nl.ValidationError):
        nl.create({"title": "Y9 news", "academic_year": "2026-27",
                   "audience": "year_group", "target_year_group": "9"})
    issue = nl.create({"title": "Autumn 1", "academic_year": "2026-27",
                       "issue_number": 1, "audience": "year_group",
                       "target_year_group": "4"})
    assert issue.status == "draft" and issue.target_year_group == "4"
    with pytest.raises(nl.ValidationError):
        nl.create({"title": "Again", "academic_year": "2026-27", "issue_number": 1})
    assert nl.next_issue_number("2026-27") == 2

    published = nl.publish(issue.newsletter_id, published_on="2026-11-05")
    assert published.status == "published"
    assert published.published_on == "2026-11-05"


# ── Access ───────────────────────────────────────────────────────────

def test_no_label_in_category_is_restricted():
    from education_system.systems.primary.domain import access

    restricted = (access.POLICY.admin_only | access.POLICY.dsl_only
                  | access.POLICY.raise_only)
    assert not restricted & set(LABELS)


@pytest.mark.parametrize("label", LABELS)
def test_teacher_can_open_from_cli(label, staff_auth, staff_principal,
                                   scripted_input, capsys):
    assert staff_principal.can_open(label)
    out, _ = _run_cli(label, staff_auth, scripted_input, capsys)
    _assert_cli_clean(out)
    assert "does not have access" not in out
    assert _header(label).search(out)


def test_teacher_menu_shows_whole_category(staff_principal):
    menu = dict(staff_principal.visible_menu(cli_main.CATEGORIES, labels_only=True))
    assert menu[CATEGORY] == LABELS


@pytest.mark.gui
@pytest.mark.parametrize("label", ["Staff HR", "DBS Checks", "Email / Messaging"])
def test_teacher_can_open_from_gui(label, primary_gui, staff_principal,
                                   content_text, page_text, toplevels, monkeypatch):
    gui = primary_gui
    monkeypatch.setattr(gui, "principal", staff_principal)
    before = set(toplevels(gui))

    getattr(gui, EXPECTED[label])()
    gui.root.update_idletasks()

    assert "does not have access" not in content_text(gui)
    assert [w for w in toplevels(gui) if w not in before] == []
    assert GUI_PAGE_TITLES[label] in page_text(gui).splitlines()


@pytest.mark.parametrize("role", ["student", "parent"])
def test_pupil_and_parent_accounts_cannot_open_category(role, staff_auth, monkeypatch,
                                                        scripted_input, capsys):
    from education_system.systems.primary.domain import access

    auth = type(staff_auth)(username=f"{role}1", role=role)
    principal = access.from_auth(auth)
    monkeypatch.setattr(access.POLICY, "_current", principal)

    assert not any(principal.can_open(label) for label in LABELS)
    menu = dict(principal.visible_menu(cli_main.CATEGORIES, labels_only=True))
    assert CATEGORY not in menu

    out, _ = _run_cli("Staff Directory", auth, scripted_input, capsys)
    assert "Your account does not have access to Staff Directory." in out
    assert "── Staff Directory ──" not in out


@pytest.mark.gui
def test_parent_is_refused_in_gui(primary_gui, staff_auth, content_text, toplevels,
                                  monkeypatch):
    from education_system.systems.primary.domain import access

    gui = primary_gui
    parent = access.from_auth(type(staff_auth)(username="parent1", role="parent"))
    monkeypatch.setattr(gui, "principal", parent)
    before = set(toplevels(gui))

    gui.open_staff()
    gui.open_messaging()

    assert "Your account does not have access to Email / Messaging." in content_text(gui)
    assert [w for w in toplevels(gui) if w not in before] == []
