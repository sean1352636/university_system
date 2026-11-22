"""Finance buttons of the Primary School System main menu (GUI and CLI).

Every Finance entry - Dinner Money, Trips & Payments, Receipts, Expense
Claims, Funding and School Census - opens its real screen on an empty
sandbox in the GUI and in the CLI, admin-only access is enforced for a
teacher, and the money flows behind the buttons do what the screens say:
a dinner-money top-up becomes a lunch receipt for the same amount, an
expense claim moves Draft → Submitted → Under Review → Approved → Paid,
a trip payment becomes a trip receipt, funding streams total their
allocations, and a census return counts the pupils on roll (the old FE
learner-aim / ILR half is gone from the census screens).

All tests run inside ``primary_sandbox`` (see ``conftest.py``).
"""

from __future__ import annotations

import re

import pytest

CATEGORY = "Finance"

#: The Finance sidebar of the GUI: label → handler method.
GUI_FINANCE = {
    "Dinner Money": "open_dinner_money",
    "Trips & Payments": "open_trips_payments",
    "Receipts": "open_receipts",
    "Expense Claims": "open_expense_claims",
    "Funding": "open_funding",
    "School Census": "open_census",
}
LABELS = list(GUI_FINANCE)

#: What each CLI screen prints as its own title once opened.
CLI_HEADERS = {
    "Dinner Money": "-- Dinner Money --",
    "Trips & Payments": "── Trips & Payments ──",
    "Receipts": "── Receipts ──",
    "Expense Claims": "── Expense Claims ──",
    "Funding": "── Funding ──",
    "School Census": "── School Census ──",
}

#: The page heading each GUI button draws in the main window's content area.
GUI_TITLES = {
    "Dinner Money": "Dinner Money",
    "Trips & Payments": "Trips & Payments",
    "Receipts": "Receipts",
    "Expense Claims": "Expense Claims",
    "Funding": "Funding",
    "School Census": "School Census",
}

_PAD = ["0", ""] * 20
#: Words of the removed FE learner-aim / ILR half of the census.
_AIMS_RE = re.compile(r"\b(learner[ -])?aims?\b|\bILR\b", re.IGNORECASE)
_CLI_FAILURES = ("[stub]", "Traceback", "Error:", "Unexpected error", "not yet implemented")


# ── Helpers ──────────────────────────────────────────────────────────

def _make_pupil(first="Ada", last="Lovelace", year_group="3", roll_status=None):
    from education_system.systems.primary.domain.learners.pupils import pupils
    data = {"first_name": first, "last_name": last, "year_group": year_group}
    if roll_status is None:
        return pupils.create_pupil(data)
    return pupils.create_pupil(data, roll_status=roll_status)


def _finance_items() -> list[str]:
    from education_system.systems.primary import cli_main
    return dict(cli_main.CATEGORIES)[CATEGORY]


def _run_cli(capsys, scripted_input, auth, answers):
    """Run the Finance submenu with *answers* (padded with backs); return
    the captured stdout."""
    from education_system.systems.primary import cli_main
    scripted_input(list(answers) + _PAD)
    cli_main._submenu(CATEGORY, _finance_items(), auth=auth)
    return capsys.readouterr().out


def _open_cli_label(capsys, scripted_input, auth, label, extra=()):
    items = _finance_items()
    return _run_cli(capsys, scripted_input, auth,
                    [str(items.index(label) + 1), *extra])


def _widget_text(widget) -> str:
    """Every visible string under *widget*: labels, buttons, notebook tab
    titles, tree headings and Text contents."""
    import tkinter as tk
    from tkinter import ttk

    seen: list[str] = []

    def walk(w):
        try:
            text = w.cget("text")
            if text:
                seen.append(str(text))
        except (tk.TclError, AttributeError):
            pass
        if isinstance(w, ttk.Notebook):
            for tab in w.tabs():
                seen.append(str(w.tab(tab, "text")))
        if isinstance(w, ttk.Treeview):
            for col in w["columns"]:
                seen.append(str(w.heading(col, "text")))
        if isinstance(w, tk.Text):
            seen.append(w.get("1.0", "end"))
        if isinstance(w, (tk.Tk, tk.Toplevel)):
            seen.append(str(w.title()))
        for child in w.winfo_children():
            walk(child)

    walk(widget)
    return "\n".join(seen)


def _record_callback_errors(gui) -> list:
    errors: list = []
    gui.root.report_callback_exception = lambda *exc: errors.append(exc)
    return errors


# ── 1. The menus list the Finance buttons ────────────────────────────

def test_gui_finance_category_lists_every_button_with_a_real_handler():
    from education_system.systems.primary import gui_main

    nav = dict(gui_main.NAV_CATEGORIES)
    assert CATEGORY in nav
    assert dict(nav[CATEGORY]) == GUI_FINANCE
    for label, handler in nav[CATEGORY]:
        method = getattr(gui_main.PrimarySchoolMainGUI, handler, None)
        assert callable(method), f"{label}: no {handler} on PrimarySchoolMainGUI"
        assert method.__qualname__ == f"PrimarySchoolMainGUI.{handler}", (
            f"{label}: {handler} is not defined on the main window")


def test_cli_finance_category_lists_the_same_buttons():
    assert _finance_items() == LABELS


def test_finance_labels_are_admin_only():
    from education_system.systems.primary.domain import access
    assert access.FINANCE_LABELS == frozenset(LABELS)
    assert access.FINANCE_LABELS <= access.ADMIN_ONLY


# ── 2. GUI: every button opens its screen ────────────────────────────

@pytest.mark.gui
@pytest.mark.parametrize("label", LABELS)
def test_gui_button_opens_screen(primary_gui, toplevels, label):
    gui = primary_gui
    errors = _record_callback_errors(gui)
    before_children = set(gui.content_frame.winfo_children())
    before_tops = set(toplevels(gui))

    getattr(gui, GUI_FINANCE[label])()
    gui.root.update_idletasks()

    new_tops = [w for w in toplevels(gui) if w not in before_tops]
    new_children = [w for w in gui.content_frame.winfo_children()
                    if w not in before_children]
    assert not new_tops, f"{label} opened a window: {[w.title() for w in new_tops]}"
    assert new_children, f"{label} put nothing in the content area"
    shown = _widget_text(gui.content_frame)
    assert "not yet implemented" not in shown
    assert "not available" not in shown.lower()
    assert GUI_TITLES[label] in shown.splitlines(), f"{label}: no page heading"
    assert gui._current_page and gui._current_page[0] == GUI_TITLES[label]
    assert not [m for m in gui.messages if m[0] == "showerror"], gui.messages
    assert not errors, errors


@pytest.mark.gui
def test_gui_census_shows_pupils_on_roll_and_no_learner_aims(primary_gui, toplevels):
    _make_pupil("Ada", "Lovelace", "3")
    _make_pupil("Alan", "Turing", "5")
    _make_pupil("Grace", "Hopper", "R", roll_status="applicant")
    gui = primary_gui
    before = set(toplevels(gui))

    gui.open_census()
    gui.root.update_idletasks()

    assert set(toplevels(gui)) == before, "School Census opened a window"
    shown = _widget_text(gui.content_frame)
    assert "School Census" in shown.splitlines()
    assert "Pupils on roll       : 2" in shown
    assert not _AIMS_RE.search(shown), _AIMS_RE.search(shown)


@pytest.mark.gui
def test_gui_dinner_money_lists_a_pupils_balance(primary_gui, toplevels):
    from education_system.systems.primary.domain.finance.dinner_money import (
        dinner_money as dm,
    )
    pupil = _make_pupil()
    dm.credit(pupil.pupil_id, amount_pounds="10.00")
    dm.charge_meal(pupil.pupil_id, amount_pounds="2.50")
    gui = primary_gui
    before = set(toplevels(gui))

    gui.open_dinner_money()
    gui.root.update_idletasks()

    assert set(toplevels(gui)) == before, "Dinner Money opened a window"
    shown = _widget_text(gui.content_frame)
    assert "Dinner Money" in shown.splitlines()
    assert "Ledger entries" in shown
    assert "Pupil balances" in shown


# ── 3. CLI: every button opens its screen ────────────────────────────

@pytest.mark.parametrize("label", LABELS)
def test_cli_button_opens_screen(capsys, scripted_input, fake_auth, admin_principal, label):
    out = _open_cli_label(capsys, scripted_input, fake_auth, label)

    assert CLI_HEADERS[label] in out
    for bad in _CLI_FAILURES:
        assert bad not in out, f"{label}: {bad!r} in output\n{out}"


@pytest.mark.parametrize("label", LABELS)
def test_cli_back_out_returns_to_finance_menu(capsys, scripted_input, fake_auth,
                                              admin_principal, label):
    """After backing out of a screen the Finance menu is shown again."""
    out = _open_cli_label(capsys, scripted_input, fake_auth, label)
    after = out.split(CLI_HEADERS[label], 1)[1]
    assert f"── {CATEGORY} ──" in after


def test_cli_census_screens_have_no_learner_aims(capsys, scripted_input, fake_auth,
                                                 admin_principal):
    out = _open_cli_label(capsys, scripted_input, fake_auth, "School Census")
    screen = out.split(CLI_HEADERS["School Census"], 1)[1].split(f"── {CATEGORY} ──")[0]
    assert "Summary" in screen
    assert not _AIMS_RE.search(screen), _AIMS_RE.search(screen)


# ── 4. Behaviour behind the buttons ─────────────────────────────────

def test_dinner_money_topup_becomes_a_lunch_receipt():
    from education_system.systems.primary.domain.finance.dinner_money import (
        dinner_money as dm,
    )
    from education_system.systems.primary.domain.finance.receipts import receipts

    pupil = _make_pupil()
    top_up = dm.credit(pupil.pupil_id, amount_pounds="12.50", recorded_by="office")
    dm.charge_meal(pupil.pupil_id, amount_pounds="2.40")
    assert dm.pupil_balance(pupil.pupil_id) == 1250 - 240

    receipt = receipts.receipt_from_dinner_money_topup(top_up.entry_id)

    assert receipt.status == "Issued"
    assert receipt.total_amount == pytest.approx(12.50)
    assert receipt.student_id == pupil.pupil_id
    assert receipt.payer_name == pupil.full_name
    assert receipt.received_by == "office"
    assert receipt.reference == f"DM-{top_up.entry_id}"
    assert receipt.receipt_number.startswith("R-")
    (line,) = receipts.list_lines(receipt.receipt_id)
    assert line.kind == "lunch"
    assert line.kind in receipts.LINE_KINDS
    assert line.source_id == top_up.entry_id
    assert line.amount == pytest.approx(12.50)


def test_meal_charge_cannot_be_receipted():
    from education_system.systems.primary.domain.finance.dinner_money import (
        dinner_money as dm,
    )
    from education_system.systems.primary.domain.finance.receipts import receipts

    pupil = _make_pupil()
    charge = dm.charge_meal(pupil.pupil_id, amount_pounds="2.40")
    assert charge.amount_pence == -240
    with pytest.raises(receipts.ValidationError):
        receipts.receipt_from_dinner_money_topup(charge.entry_id)
    assert receipts.list_receipts() == []


def test_receipt_draft_issue_void_and_voucher_method():
    from education_system.systems.primary.domain.finance.receipts import receipts

    assert set(receipts.LINE_KINDS) == {"general", "lunch", "trip", "club",
                                        "uniform", "other"}
    assert "Voucher" in receipts.PAYMENT_METHODS
    pupil = _make_pupil()
    draft = receipts.create_receipt(
        {"issued_date": "2026-11-02", "payer_name": "Mrs Lovelace",
         "student_id": pupil.pupil_id, "method": "Voucher"},
        [{"description": "Club fee", "amount": 15, "kind": "club"},
         {"description": "PE kit", "amount": "7.50", "kind": "uniform"}],
    )
    assert draft.status == "Draft"
    assert draft.method == "Voucher"
    assert draft.total_amount == pytest.approx(22.50)

    issued = receipts.issue(draft.receipt_id)
    assert issued.status == "Issued"
    voided = receipts.void_receipt(draft.receipt_id, "Paid twice")
    assert voided.is_voided
    assert voided.void_reason == "Paid twice"
    s = receipts.summary()
    assert (s.total_receipts, s.voided, s.issued) == (1, 1, 0)


def test_cli_topup_then_receipt_import(capsys, scripted_input, fake_auth, admin_principal):
    """Dinner Money (3: top-up) then Receipts (Import Dinner Money Top-up),
    through the Finance menu."""
    from education_system.systems.primary.domain.finance.dinner_money import (
        dinner_money as dm,
    )
    from education_system.systems.primary.domain.finance.receipts import receipts
    from education_system.systems.primary.interfaces.cli.finance.receipts import receipts_cli

    pupil = _make_pupil()
    items = _finance_items()
    out = _run_cli(capsys, scripted_input, fake_auth, [
        str(items.index("Dinner Money") + 1),
        "3", pupil.pupil_id, "20.00", "", "office", "", "",   # top-up + Enter
        "0",
    ])
    assert "New balance: £20.00" in out
    ((entry, _pupil),) = dm.list_entries()
    assert entry.kind == "credit" and entry.amount_pence == 2000

    import_choice = [n for n, (name, _) in enumerate(receipts_cli._MENU, 1)
                     if name == "Import Dinner Money Top-up"][0]
    out = _run_cli(capsys, scripted_input, fake_auth, [
        str(items.index("Receipts") + 1),
        str(import_choice), str(entry.entry_id), "", "y", "",
        "0",
    ])
    assert "✓ Created receipt R-" in out
    assert "£20.00" in out
    (receipt,) = receipts.list_receipts()
    assert receipt.status == "Issued"
    assert receipts.list_lines(receipt.receipt_id)[0].kind == "lunch"


def test_trip_payment_becomes_a_trip_receipt():
    from education_system.systems.primary.domain.finance.receipts import receipts
    from education_system.systems.primary.domain.finance.trips import trips

    pupil = _make_pupil()
    trip = trips.create_trip({"name": "Zoo visit", "start_date": "2026-12-01",
                              "year_group": "Year 3", "cost_per_place": "18.00",
                              "deposit": "5.00"})
    booking = trips.create_booking(trip.trip_id, {"student_id": pupil.pupil_id})
    deposit = trips.add_payment(booking.booking_id,
                                {"amount": "5.00", "method": "Voucher"})
    view = trips.view_booking(booking.booking_id)
    assert view.payment_state == "Deposit"
    assert view.balance == pytest.approx(13.00)

    receipt = receipts.receipt_from_trip_payment(deposit.payment_id)
    assert receipt.method == "Voucher"
    assert receipt.total_amount == pytest.approx(5.00)
    (line,) = receipts.list_lines(receipt.receipt_id)
    assert line.kind == "trip"
    assert "Zoo visit" in line.description

    trips.add_payment(booking.booking_id, {"amount": "13.00", "method": "Cash"})
    assert trips.view_booking(booking.booking_id).payment_state == "Paid"


def test_trip_booking_needs_a_real_pupil():
    from education_system.systems.primary.domain.finance.trips import trips

    trip = trips.create_trip({"name": "Museum", "start_date": "2026-12-01"})
    with pytest.raises(trips.ValidationError):
        trips.create_booking(trip.trip_id, {"student_id": "P9999999"})


def test_expense_claim_lifecycle():
    from education_system.systems.primary.domain.finance.expense_claims import (
        expense_claims as ec,
    )

    claim = ec.create_claim({"claim_ref": "EC-001", "claimant_id": "T001",
                             "claimant_name": "Ms Teacher", "title": "Art supplies",
                             "category": "Books / Materials"})
    assert claim.status == "Draft"
    with pytest.raises(ec.ValidationError, match="no lines"):
        ec.submit(claim.claim_id)

    ec.add_line(claim.claim_id, {"incurred_on": "2026-10-20", "quantity": 3,
                                 "unit_amount": "4.00", "vat_amount": "2.40",
                                 "category": "Books / Materials"})
    ec.add_line(claim.claim_id, {"incurred_on": "2026-10-21", "category": "Mileage",
                                 "mileage_miles": 10, "mileage_rate": "0.45"})
    claim = ec.get_claim(claim.claim_id)
    assert claim.line_count == 2
    assert claim.total_amount == pytest.approx(12.00 + 2.40 + 4.50)

    with pytest.raises(ec.ValidationError, match="Approved"):
        ec.pay(claim.claim_id)
    assert ec.submit(claim.claim_id).status == "Submitted"
    assert ec.begin_review(claim.claim_id).status == "Under Review"
    approved = ec.approve(claim.claim_id, approved_by="Head")
    assert (approved.status, approved.approved_by) == ("Approved", "Head")
    assert ec.summary().awaiting_payment_value == pytest.approx(18.90)
    paid = ec.pay(claim.claim_id, payment_reference="BACS-77", paid_on="2026-11-01")
    assert (paid.status, paid.paid_on, paid.payment_reference) == (
        "Paid", "2026-11-01", "BACS-77")
    s = ec.summary()
    assert (s.paid, s.paid_value, s.awaiting_payment_value) == (1, pytest.approx(18.90), 0)


def test_expense_claim_refs_are_unique():
    from education_system.systems.primary.domain.finance.expense_claims import (
        expense_claims as ec,
    )
    ec.create_claim({"claim_ref": "EC-9", "claimant_id": "T1", "title": "Taxi"})
    with pytest.raises(ec.ValidationError, match="already exists"):
        ec.create_claim({"claim_ref": "EC-9", "claimant_id": "T2", "title": "Bus"})


def test_cli_expense_claim_submit_without_lines_is_refused(capsys, scripted_input,
                                                           fake_auth, admin_principal):
    from education_system.systems.primary.domain.finance.expense_claims import (
        expense_claims as ec,
    )
    from education_system.systems.primary.interfaces.cli.finance.expense_claims import (
        expense_claims_cli,
    )

    claim = ec.create_claim({"claim_ref": "EC-002", "claimant_id": "T001",
                             "title": "Train fare"})
    submit = [n for n, (name, _) in enumerate(expense_claims_cli._MENU, 1)
              if name == "Submit"][0]
    out = _open_cli_label(capsys, scripted_input, fake_auth, "Expense Claims",
                          extra=[str(submit), "1", ""])
    assert "Cannot submit a claim with no lines" in out
    assert ec.get_claim(claim.claim_id).status == "Draft"


def test_funding_is_primary_and_streams_total_their_allocations():
    from education_system.systems.primary.domain.finance.funding import funding

    assert "Pupil Premium" in funding.STREAM_TYPES
    assert "Universal Infant Free School Meals" in funding.STREAM_TYPES
    assert "PE and Sport Premium" in funding.STREAM_TYPES
    assert "Pupil Premium Plus (Looked After)" in funding.FUNDING_BANDS
    joined = " ".join(funding.STREAM_TYPES + funding.FUNDING_BANDS).lower()
    for fe_only in ("16-19", "bursary", "adult education", "ilr"):
        assert fe_only not in joined

    pupil = _make_pupil()
    stream = funding.create_stream({"name": "PP 2026/27", "stream_type": "Pupil Premium",
                                    "funder": "ESFA", "academic_year": "2026-27",
                                    "allocated_amount": "3000"})
    alloc = funding.create_allocation({"learner_ref": pupil.pupil_id,
                                       "learner_name": pupil.full_name,
                                       "stream_id": stream.stream_id,
                                       "starts_on": "2026-09-01",
                                       "committed_amount": "1455",
                                       "band_value": "1455"})
    stream = funding.get_stream(stream.stream_id)
    assert stream.committed_amount == pytest.approx(1455)

    funding.record_drawdown(alloc.allocation_id, amount=455)
    with pytest.raises(funding.ValidationError, match="exceed"):
        funding.record_drawdown(alloc.allocation_id, amount=1001)
    done = funding.record_drawdown(alloc.allocation_id, amount=1000)
    assert done.status == "Drawn Down"
    assert funding.get_stream(stream.stream_id).drawn_down_amount == pytest.approx(1455)
    s = funding.summary()
    assert (s.total_streams, s.distinct_learners) == (1, 1)
    assert s.total_remaining == pytest.approx(3000 - 1455)


def test_census_summary_counts_pupils_on_roll():
    from education_system.systems.primary.domain.governance.compliance.census import census
    from education_system.systems.primary.domain.learners.pupils import pupils

    assert census.summary().pupils_on_roll == 0
    _make_pupil("Ada", "Lovelace", "3")
    leaver = _make_pupil("Alan", "Turing", "6")
    _make_pupil("Grace", "Hopper", "R", roll_status="applicant")
    _make_pupil("Mary", "Somerville", "1")
    pupils.set_roll_status(leaver.pupil_id, "left")

    assert census.summary().pupils_on_roll == 2


def test_census_submit_records_pupils_on_roll():
    from education_system.systems.primary.domain.governance.compliance.census import census

    assert not any("ilr" in t.lower() or "learner" in t.lower()
                   for t in census.RETURN_TYPES)
    for name in ("Ada", "Alan", "Grace"):
        _make_pupil(name, "Pupil", "4")
    ret = census.create_return({"return_type": "School Census - Autumn",
                                "academic_year": "2026-27",
                                "learner_count": 99})
    assert census.validate_return(ret.return_id).status == "Validated"

    submitted = census.submit_return(ret.return_id, submitted_by="office")
    assert submitted.status == "Submitted"
    assert submitted.learner_count == 3
    assert submitted.submitted_by == "office"
    accepted = census.accept_return(ret.return_id, accepted_on="2026-11-05")
    assert (accepted.status, accepted.accepted_on) == ("Accepted", "2026-11-05")
    s = census.summary()
    assert (s.total_returns, s.accepted, s.pupils_on_roll) == (1, 1, 3)
    with pytest.raises(census.ValidationError, match="already exists"):
        census.create_return({"return_type": "School Census - Autumn",
                              "academic_year": "2026-27"})


def test_cli_census_summary_shows_pupils_on_roll(capsys, scripted_input, fake_auth,
                                                 admin_principal):
    from education_system.systems.primary.interfaces.cli.governance.compliance.census import (
        census_cli,
    )
    _make_pupil("Ada", "Lovelace", "3")
    _make_pupil("Alan", "Turing", "5")
    summary = [n for n, (name, _) in enumerate(census_cli._MENU, 1)
               if name == "Summary"][0]
    out = _open_cli_label(capsys, scripted_input, fake_auth, "School Census",
                          extra=[str(summary), ""])
    assert "Pupils on roll       : 2" in out


# ── 5. Teachers are refused every Finance button ─────────────────────

@pytest.mark.parametrize("label", LABELS)
def test_teacher_refused_in_cli(capsys, scripted_input, staff_auth, staff_principal, label):
    assert not staff_principal.can_open(label)
    out = _open_cli_label(capsys, scripted_input, staff_auth, label)
    assert staff_principal.denied_message(label) in out
    assert CLI_HEADERS[label] not in out


def test_teacher_cli_menu_hides_finance(staff_principal):
    from education_system.systems.primary import cli_main

    visible = dict(staff_principal.visible_menu(cli_main.CATEGORIES, labels_only=True))
    assert not set(visible.get(CATEGORY, [])) & set(LABELS)


@pytest.mark.gui
@pytest.mark.parametrize("label", LABELS)
def test_teacher_refused_in_gui(staff_auth, staff_principal, monkeypatch, toplevels, label):
    tk = pytest.importorskip("tkinter")
    try:
        probe = tk.Tk()
        probe.destroy()
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")
    from education_system.systems.primary import gui_main

    monkeypatch.setattr(gui_main, "install_idle_logout", lambda root, logout: (lambda: None))
    gui = gui_main.PrimarySchoolMainGUI(staff_auth, staff_principal)
    gui.root.withdraw()
    try:
        before = set(toplevels(gui))
        getattr(gui, GUI_FINANCE[label])()
        assert set(toplevels(gui)) == before, f"{label} opened a window for a teacher"
        shown = _widget_text(gui.content_frame)
        assert staff_principal.denied_message(label) in shown
    finally:
        for child in gui.root.winfo_children():
            child.destroy()
        gui.root.destroy()

