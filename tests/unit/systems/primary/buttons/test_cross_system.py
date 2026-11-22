"""Button tests for the Primary School System's **Cross-System** menu.

Every label in the category is opened from the real main GUI
(``PrimarySchoolMainGUI.open_*``) and from the real CLI submenu
(``cli_main._submenu``) against the empty sandbox from ``conftest.py``.
These screens are the shared platform ones (Learner 360 / promotion through
``journey_cli``, analytics, calendar, central admin, GDPR, documents, the
self-service portal and certificates), so they read the sandbox platform
databases, never the live ones.

Behaviour checked end to end: promotion hands ``journey_cli.promote`` the
pupil and the consent answers (GUI and CLI), declining any step changes
nothing, and a certificate generated from the Certificates menu verifies as
VALID by its number. Access: Central Admin Portal is admin-only; teachers
keep the rest; pupils and parents get none of it.
"""

from __future__ import annotations

import builtins
import re

import pytest

CATEGORY = "Cross-System"

#: (label, GUI handler) in sidebar order.
EXPECTED_ITEMS = [
    ("Student Journey", "open_student_journey"),
    ("Promote to Next System", "open_promote"),
    ("Analytics Dashboard", "open_cross_analytics"),
    ("Cross-System Calendar", "open_cross_calendar"),
    ("Central Admin Portal", "open_central_admin"),
    ("GDPR Compliance", "open_cross_gdpr"),
    ("Shared Documents", "open_shared_documents"),
    ("Pupil Self-Service", "open_self_service"),
    ("Certificates", "open_certificates"),
]
EXPECTED_LABELS = [label for label, _handler in EXPECTED_ITEMS]

#: Labels only an admin may open.
ADMIN_ONLY = {"Central Admin Portal"}

#: Labels the CLI hands to a shared platform terminal menu.
PLATFORM_MENU_LABELS = {
    "Analytics Dashboard", "Cross-System Calendar", "Central Admin Portal",
    "GDPR Compliance", "Shared Documents", "Pupil Self-Service", "Certificates",
}

#: Text each GUI screen shows once it has opened.
GUI_MARKERS = {
    "Student Journey": "Learner 360",
    "Analytics Dashboard": "Cross-System Analytics Dashboard",
    "Cross-System Calendar": "Cross-System Calendar",
    "Central Admin Portal": "Central Admin Portal",
    "GDPR Compliance": "Generate SAR Report",
    "Shared Documents": "Shared Documents",
    "Pupil Self-Service": "Student Self-Service Portal",
    "Certificates": "Certificate Verification",
}

#: (answers after choosing the label, text the CLI screen prints).
#: Student Journey and Promote ask for an id first; a blank one cancels.
CLI_SCREENS = {
    "Student Journey": ([""], "Cancelled."),
    "Promote to Next System": ([""], "Cancelled."),
    "Analytics Dashboard": ([], "Cross-System Analytics Dashboard"),
    "Cross-System Calendar": ([], "=== Cross-System Calendar ==="),
    "Central Admin Portal": ([], "Central Admin Portal"),
    "GDPR Compliance": ([], "GDPR Compliance"),
    "Shared Documents": ([], "Shared Documents"),
    "Pupil Self-Service": ([], "Student Self-Service Portal"),
    "Certificates": ([], "Certificates & Transcripts"),
}

#: Enough "Back" / "Enter" answers to leave every nested menu.
BACK_OUT = ["0", ""] * 20


# ── helpers ──────────────────────────────────────────────────────────

def _gui_items() -> list[tuple[str, str]]:
    from education_system.systems.primary import gui_main
    return list(dict(gui_main.NAV_CATEGORIES)[CATEGORY])


def _cli_items() -> list[str]:
    from education_system.systems.primary import cli_main
    return list(dict(cli_main.CATEGORIES)[CATEGORY])


@pytest.fixture(autouse=True)
def journey_reads_patched_input(monkeypatch):
    """``journey_cli.dispatch`` takes ``input_fn=input`` as a default, which
    binds whatever ``builtins.input`` was when the module was first imported.
    Look it up at call time instead so ``scripted_input`` feeds the Student
    Journey / Promote prompts (and an unscripted prompt fails, not hangs)."""
    from education_system.platform.cross_system import journey_cli

    monkeypatch.setitem(journey_cli.dispatch.__kwdefaults__, "input_fn",
                        lambda prompt="": builtins.input(prompt))


@pytest.fixture
def promote_calls(monkeypatch):
    """Replace ``journey_cli.promote``; returns the list of (args, kwargs)."""
    from education_system.platform.cross_system import journey_cli

    calls: list[tuple[tuple, dict]] = []

    def fake_promote(*args, **kwargs):
        calls.append((args, kwargs))
        return "transfer recorded"

    monkeypatch.setattr(journey_cli, "promote", fake_promote)
    return calls


def _run_cli(label, auth, scripted_input, capsys, answers=()):
    """Open *label* from the Cross-System submenu, then back out.
    Returns (stdout, prompts seen)."""
    from education_system.systems.primary import cli_main

    items = _cli_items()
    choice = str(items.index(label) + 1)
    prompts = scripted_input([choice, *answers, *BACK_OUT])
    cli_main._submenu(CATEGORY, items, auth=auth)
    return capsys.readouterr().out, prompts


def _assert_clean_cli(out: str, label: str) -> None:
    assert "[stub]" not in out, f"{label} fell through to the stub"
    assert "Traceback" not in out, out
    assert "Error:" not in out, f"{label} printed an error:\n{out}"
    assert "Error opening" not in out, out
    assert "Promotion failed" not in out, out


def _answers(monkeypatch, module, kind, values, messages):
    """Make ``module.kind`` return *values* in order (recorded in *messages*)."""
    queue = list(values)

    def call(title="", message="", *args, **kwargs):
        messages.append((kind, str(title), str(message)))
        return queue.pop(0) if queue else None

    monkeypatch.setattr(module, kind, call)


# ── Catalogue ────────────────────────────────────────────────────────

def test_gui_category_lists_the_cross_system_screens():
    assert _gui_items() == EXPECTED_ITEMS


def test_cli_category_matches_the_gui():
    assert _cli_items() == EXPECTED_LABELS


@pytest.mark.parametrize("label,handler", EXPECTED_ITEMS)
def test_gui_handler_is_a_real_method(label, handler):
    from education_system.systems.primary.gui_main import PrimarySchoolMainGUI

    method = getattr(PrimarySchoolMainGUI, handler, None)
    assert callable(method), f"{label}: {handler} is missing (would show the stub)"
    assert handler in vars(PrimarySchoolMainGUI), f"{handler} is not defined on the GUI"


def test_cli_platform_menus_are_importable_runs():
    import importlib
    import inspect

    from education_system.systems.primary import cli_main

    assert set(cli_main._PLATFORM_MENUS) == PLATFORM_MENU_LABELS
    for label, (module_name, func) in cli_main._PLATFORM_MENUS.items():
        run = getattr(importlib.import_module(module_name), func, None)
        assert callable(run), f"{label}: {module_name}.{func} missing"
        assert "auth" in inspect.signature(run).parameters, label


def test_journey_labels_are_routed_by_journey_cli():
    from education_system.platform.cross_system import journey_cli

    assert journey_cli.CLI_MENU_ITEMS == ["Student Journey", "Promote to Next System"]
    assert set(journey_cli.CLI_MENU_ITEMS) | PLATFORM_MENU_LABELS == set(EXPECTED_LABELS)


# ── GUI: every screen opens ──────────────────────────────────────────

@pytest.mark.gui
@pytest.mark.parametrize("label", list(GUI_MARKERS))
def test_gui_screen_opens(label, primary_gui, content_text):
    handler = dict(EXPECTED_ITEMS)[label]
    getattr(primary_gui, handler)()
    primary_gui.root.update_idletasks()

    text = content_text(primary_gui)
    assert "Could not open" not in text, text
    assert "not yet implemented" not in text, f"{label} showed the stub"
    assert "does not have access" not in text
    assert not [m for m in primary_gui.messages if m[0] == "showerror"], primary_gui.messages
    assert GUI_MARKERS[label] in text, f"{label} put nothing recognisable on screen"
    assert primary_gui.status_var.get() == f"Opened: {label}"


# ── GUI: Promote to Next System ──────────────────────────────────────

@pytest.mark.gui
def test_gui_promote_cancelled_at_pupil_id_changes_nothing(primary_gui, promote_calls):
    before = primary_gui.status_var.get()
    primary_gui.open_promote()  # askstring → None

    assert promote_calls == []
    kinds = [m[0] for m in primary_gui.messages]
    assert kinds == ["askstring"], primary_gui.messages
    assert primary_gui.status_var.get() == before


@pytest.mark.gui
def test_gui_promote_declined_at_confirm_changes_nothing(primary_gui, promote_calls,
                                                         monkeypatch):
    from tkinter import simpledialog

    _answers(monkeypatch, simpledialog, "askstring", ["P0001"], primary_gui.messages)
    before = primary_gui.status_var.get()
    primary_gui.open_promote()  # askyesno → False at "Promote pupil"

    assert promote_calls == []
    assert ("askyesno", "Promote pupil") in [m[:2] for m in primary_gui.messages]
    assert not [m for m in primary_gui.messages if m[0] in ("showinfo", "showerror")]
    assert primary_gui.status_var.get() == before


@pytest.mark.gui
def test_gui_promote_with_consent_calls_journey_promote(primary_gui, promote_calls,
                                                        monkeypatch):
    from tkinter import messagebox, simpledialog

    from education_system.platform.cross_system import journey_cli

    msgs = primary_gui.messages
    _answers(monkeypatch, simpledialog, "askstring", ["  P0001 ", "SG-REF-7"], msgs)
    _answers(monkeypatch, messagebox, "askyesno", [True, True, True], msgs)
    primary_gui.open_promote()

    assert len(promote_calls) == 1, msgs
    args, kwargs = promote_calls[0]
    assert args == ("primary", "P0001")
    if journey_cli.promote_accepts_consent("primary"):
        assert kwargs["consent"] == journey_cli.build_consent(
            "primary", medical=True, support=True)
        assert kwargs["safeguarding_reference"] == "SG-REF-7"
        consent_qs = [m for m in msgs if m[:2] == ("askyesno", "Consent to share")]
        assert len(consent_qs) == 2
    assert ("showinfo", "Promoted") in [m[:2] for m in msgs]
    assert primary_gui.status_var.get().startswith("Promoted P0001")


@pytest.mark.gui
def test_gui_promote_unknown_pupil_says_so(primary_gui, monkeypatch):
    """The sandbox has no pupils: the real promotion refuses and the window
    shows why, instead of crashing or claiming success."""
    from tkinter import messagebox, simpledialog

    msgs = primary_gui.messages
    _answers(monkeypatch, simpledialog, "askstring", ["NOPUPIL9", None], msgs)
    _answers(monkeypatch, messagebox, "askyesno", [True, True, True], msgs)
    before = primary_gui.status_var.get()
    primary_gui.open_promote()

    errors = [m for m in msgs if m[0] == "showerror"]
    assert errors, msgs
    assert errors[0][1] == "Promotion failed"
    assert "NOPUPIL9" in errors[0][2]
    assert ("showinfo", "Promoted") not in [m[:2] for m in msgs]
    assert primary_gui.status_var.get() == before
    assert primary_gui.root.winfo_exists()


# ── CLI: every screen opens and goes back ────────────────────────────

@pytest.mark.parametrize("label", EXPECTED_LABELS)
def test_cli_screen_opens_and_backs_out(label, fake_auth, admin_principal,
                                        scripted_input, capsys):
    answers, marker = CLI_SCREENS[label]
    out, _prompts = _run_cli(label, fake_auth, scripted_input, capsys, answers)

    _assert_clean_cli(out, label)
    assert "does not have access" not in out
    assert marker in out, f"{label} did not open:\n{out}"
    assert out.count(f"── {CATEGORY} ──") >= 2, "did not return to the submenu"


def test_cli_student_journey_asks_for_an_id(fake_auth, admin_principal,
                                            scripted_input, capsys):
    _out, prompts = _run_cli("Student Journey", fake_auth, scripted_input, capsys, [""])
    assert any("Student/Pupil ID (or journey ID)" in p for p in prompts), prompts


def test_cli_student_journey_unknown_pupil(fake_auth, admin_principal,
                                           scripted_input, capsys):
    out, _prompts = _run_cli("Student Journey", fake_auth, scripted_input, capsys,
                             ["NOPUPIL9"])
    _assert_clean_cli(out, "Student Journey")
    assert "No journey found" in out, out


# ── CLI: Promote to Next System ──────────────────────────────────────

def test_cli_promote_with_consent_calls_journey_promote(fake_auth, admin_principal,
                                                        scripted_input, capsys,
                                                        promote_calls):
    from education_system.platform.cross_system import journey_cli

    accepts = journey_cli.promote_accepts_consent("primary")
    answers = ["P0001", *(["y", "y", "SG-REF-7"] if accepts else [])]
    out, prompts = _run_cli("Promote to Next System", fake_auth, scripted_input,
                            capsys, answers)

    assert len(promote_calls) == 1, out
    args, kwargs = promote_calls[0]
    assert args == ("primary", "P0001")
    if accepts:
        assert kwargs == {
            "consent": journey_cli.build_consent("primary", medical=True, support=True),
            "safeguarding_reference": "SG-REF-7",
        }
        assert any(journey_cli.MEDICAL_CONSENT_QUESTION in p for p in prompts)
        assert any(journey_cli.SUPPORT_CONSENT_QUESTION in p for p in prompts)
    assert "Promoted P0001" in out, out


def test_cli_promote_cancelled_changes_nothing(fake_auth, admin_principal,
                                              scripted_input, capsys, promote_calls):
    out, _prompts = _run_cli("Promote to Next System", fake_auth, scripted_input,
                             capsys, [""])
    assert promote_calls == []
    assert "Cancelled." in out


def test_cli_promote_unknown_pupil_says_so(fake_auth, admin_principal,
                                          scripted_input, capsys):
    from education_system.platform.cross_system import journey_cli

    accepts = journey_cli.promote_accepts_consent("primary")
    answers = ["NOPUPIL9", *(["y", "y", ""] if accepts else [])]
    out, _prompts = _run_cli("Promote to Next System", fake_auth, scripted_input,
                             capsys, answers)
    assert "Traceback" not in out
    assert "Promotion failed" in out and "NOPUPIL9" in out, out
    assert "Promoted NOPUPIL9" not in out


# ── CLI: Certificates ────────────────────────────────────────────────

_CERT_NO = re.compile(r"Certificate No:\s*(CERT-[0-9A-F]+)")


def _generate_answers(student_id: str) -> list[str]:
    # 6) Generate → id, course, award date, type 2 (achievement), grade,
    # additional info, issued by (default), then Enter at "Press Enter".
    return ["6", student_id, "Reading Champion", "2026-07-01", "2",
            "Gold", "", "", ""]


def test_cli_certificates_generate_then_verify_from_primary_menu(
        fake_auth, admin_principal, scripted_input, capsys):
    """The Primary menu's Certificates: a certificate generated there must
    verify by its number afterwards."""
    out, _ = _run_cli("Certificates", fake_auth, scripted_input, capsys,
                      _generate_answers("P0001"))
    _assert_clean_cli(out, "Certificates")
    found = _CERT_NO.search(out)
    assert found, out
    number = found.group(1)

    out, _ = _run_cli("Certificates", fake_auth, scripted_input, capsys,
                      ["7", number, ""])
    assert "[VALID]" in out, f"certificate {number} did not persist:\n{out}"
    assert "Reading Champion" in out


def test_certificates_cli_generate_then_verify(fake_auth, scripted_input, capsys,
                                               tmp_path):
    from education_system.platform.features.certificates import certificates_cli

    db = str(tmp_path / "certificates.db")
    scripted_input([*_generate_answers("P0001"), "0"])
    certificates_cli.run(db_path=db, auth=fake_auth)
    out = capsys.readouterr().out
    assert "Certificate generated successfully!" in out, out
    number = _CERT_NO.search(out).group(1)

    scripted_input(["7", number, "", "0"])
    certificates_cli.run(db_path=db, auth=fake_auth)
    out = capsys.readouterr().out
    assert "[VALID]" in out, out
    assert number in out and "Reading Champion" in out
    assert "admin3" in out  # issued by defaults to the signed-in user

    scripted_input(["7", "CERT-NOTREAL0000", "", "0"])
    certificates_cli.run(db_path=db, auth=fake_auth)
    assert "[INVALID]" in capsys.readouterr().out


def test_certificates_cli_student_sees_only_own_menu(staff_auth, scripted_input,
                                                     capsys, tmp_path):
    from education_system.platform.features.certificates import certificates_cli
    from education_system.platform.features.certificates.certificate_service import (
        CertificateService,
    )

    db = str(tmp_path / "certificates.db")
    svc = CertificateService(db)
    mine = svc.generate_certificate("1", "merit", "Times Tables Star", "2026-06-01")
    other = svc.generate_certificate("P0999", "merit", "Someone Else's Award", "2026-06-01")

    pupil = type(staff_auth)(username="pupil1", role="student")  # user_id 1
    scripted_input(["1", "", "0"])
    certificates_cli.run(db_path=db, auth=pupil)
    out = capsys.readouterr().out

    assert "My Certificates & Transcript" in out
    assert "1) My certificates" in out
    assert "Generate" not in out and "Revoke" not in out and "Show all" not in out
    assert mine["certificate_number"] in out
    assert other["certificate_number"] not in out
    assert "Someone Else's Award" not in out


# ── Access ───────────────────────────────────────────────────────────

def test_teacher_may_open_everything_but_central_admin(staff_principal):
    for label in EXPECTED_LABELS:
        assert staff_principal.can_open(label) is (label not in ADMIN_ONLY), label


@pytest.mark.parametrize("role", ["student", "parent"])
def test_pupils_and_parents_get_no_cross_system_screens(role, staff_auth):
    from education_system.systems.primary.domain import access

    principal = access.from_auth(type(staff_auth)(username=f"{role}1", role=role))
    assert not [label for label in EXPECTED_LABELS if principal.can_open(label)]


@pytest.mark.parametrize("label", sorted(ADMIN_ONLY))
def test_cli_teacher_refused_admin_only(label, staff_auth, staff_principal,
                                        scripted_input, capsys):
    out, _ = _run_cli(label, staff_auth, scripted_input, capsys)
    assert f"Your account does not have access to {label}." in out
    assert "System health" not in out  # the admin portal's own menu never ran
    _assert_clean_cli(out, label)


@pytest.mark.parametrize("label", ["Certificates", "Shared Documents"])
def test_cli_teacher_opens_shared_screens(label, staff_auth, staff_principal,
                                          scripted_input, capsys):
    answers, marker = CLI_SCREENS[label]
    out, _ = _run_cli(label, staff_auth, scripted_input, capsys, answers)
    assert "does not have access" not in out
    assert marker in out
    _assert_clean_cli(out, label)


@pytest.fixture
def teacher_gui(staff_auth, staff_principal, monkeypatch):
    """A ``PrimarySchoolMainGUI`` for a teacher (message boxes recorded)."""
    tk = pytest.importorskip("tkinter")
    try:
        probe = tk.Tk()
        probe.destroy()
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")

    from tkinter import messagebox, simpledialog

    from education_system.systems.primary import gui_main

    messages: list[tuple[str, str, str]] = []

    def recorder(kind, result):
        def call(title="", message="", *args, **kwargs):
            messages.append((kind, str(title), str(message)))
            return result
        return call

    for kind, result in (("showinfo", "ok"), ("showwarning", "ok"), ("showerror", "ok"),
                         ("askyesno", False), ("askokcancel", False),
                         ("askyesnocancel", None), ("askquestion", "no")):
        monkeypatch.setattr(messagebox, kind, recorder(kind, result))
    for kind in ("askstring", "askinteger", "askfloat"):
        monkeypatch.setattr(simpledialog, kind, recorder(kind, None))
    monkeypatch.setattr(gui_main, "install_idle_logout", lambda root, logout: (lambda: None))

    gui = gui_main.PrimarySchoolMainGUI(staff_auth, staff_principal)
    gui.messages = messages
    gui.root.withdraw()
    try:
        yield gui
    finally:
        try:
            for child in gui.root.winfo_children():
                child.destroy()
            gui.root.destroy()
        except tk.TclError:
            pass


@pytest.mark.gui
@pytest.mark.parametrize("label", sorted(ADMIN_ONLY))
def test_gui_teacher_refused_admin_only(label, teacher_gui, content_text):
    getattr(teacher_gui, dict(EXPECTED_ITEMS)[label])()
    teacher_gui.root.update_idletasks()

    text = content_text(teacher_gui)
    assert f"Your account does not have access to {label}." in text
    assert GUI_MARKERS[label] + "\nRefresh All" not in text  # the portal never built
    assert teacher_gui.status_var.get() == "Not available for this account"


@pytest.mark.gui
def test_gui_teacher_sidebar_hides_admin_only(teacher_gui):
    from education_system.systems.primary import gui_main

    visible = dict(teacher_gui.principal.filter_menu(gui_main.NAV_CATEGORIES))
    labels = [label for label, _handler in visible[CATEGORY]]
    assert labels == [lb for lb in EXPECTED_LABELS if lb not in ADMIN_ONLY]


@pytest.mark.gui
def test_gui_teacher_opens_certificates(teacher_gui, content_text):
    teacher_gui.open_certificates()
    teacher_gui.root.update_idletasks()
    text = content_text(teacher_gui)
    assert "does not have access" not in text
    assert "Could not open" not in text
    assert GUI_MARKERS["Certificates"] in text
