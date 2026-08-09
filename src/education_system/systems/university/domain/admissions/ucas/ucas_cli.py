"""CLI flows for university-side UCAS management."""

from __future__ import annotations

import logging
from typing import Callable

from education_system.systems.university.domain.admissions.ucas import (
    ucas as data,
    ucas_links as links_data,
)
from education_system.systems.university.domain.admissions.ucas.ucas import (
    APP_STATUSES,
    Applicant,
    DECIDABLE,
    DECISION_STATUSES,
    UcasError,
)
from education_system.systems.university.domain.admissions.ucas.ucas_links import (
    LINK_STATUSES,
    UcasLinkError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


def _input(prompt: str, *, default: str = "",
            allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number.")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_applicant() -> Applicant:
    rows = data.list_applicants()
    if not rows:
        print("    No UCAS applicants for this university.")
        raise _UserAbort
    for i, a in enumerate(rows, 1):
        print(f"    {i:>3}) {a.student_id:<12}  "
              f"{a.student_name[:22]:<22}  "
              f"{a.course_name[:28]:<28}  [{a.decision_status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or student id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
        match = next((r for r in rows
                       if r.student_id.lower() == raw.lower()), None)
        if match:
            return match
        print("    No matching applicant.")


# ── Rendering ────────────────────────────────────────────────────

def _print_table(rows: list[Applicant]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'Student':<12} {'Name':<22}  {'Course':<28}  "
          f"{'Cycle':>5}  {'App':<10}  {'Decision':<20}  Submitted")
    print("  " + "-" * 120)
    for a in rows:
        print(f"  {a.student_id:<12} "
              f"{a.student_name[:22]:<22}  "
              f"{a.course_name[:28]:<28}  "
              f"{a.cycle_year:>5}  "
              f"{a.app_status:<10}  "
              f"{a.decision_status:<20}  "
              f"{a.submitted_at or '—'}")
    print(f"\n  {len(rows)} applicant(s).")


def _print_full(a: Applicant) -> None:
    full = data.get_full_application(a.application_id)
    if full is None:
        print("    (application disappeared)")
        return
    print()
    print(f"    Student          : {full.student_id}  "
          f"({full.student_name})")
    print(f"    Email            : {full.student_email}")
    print(f"    Date of birth    : {full.student_dob or '—'}")
    print(f"    A-Level subjects : "
          f"{', '.join(full.subjects) or '—'}")
    print(f"    Cycle / UCAS ID  : {full.cycle_year}  "
          f"/  {full.ucas_id or '—'}")
    print(f"    App status       : {full.app_status}")
    print(f"    Submitted        : {full.submitted_at or '—'}")
    if full.personal_statement:
        print("\n    Personal statement:")
        for line in full.personal_statement.splitlines():
            print(f"      {line}")
    print("\n    Choices:")
    print(f"      {'Slot':<4}  {'University':<28}  "
          f"{'Course':<24}  {'Decision':<20}  {'Final':<10}  Terms")
    for c in full.choices:
        mark = "→ " if c.choice_id == full.our_choice_id else "  "
        print(f"      {mark}{c.choice_order:<2}  "
              f"{c.university[:28]:<28}  "
              f"{c.course_name[:24]:<24}  "
              f"{c.decision_status:<20}  "
              f"{c.final_decision or '—':<10}  "
              f"{c.offer_terms or '—'}")
    print("    (→ = this university's choice)")


# ── Flows ────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ UCAS Applicants — All ═══")
    _print_table(data.list_applicants())
    _pause()


def list_awaiting() -> None:
    print("\n═══ UCAS Applicants — Awaiting decision ═══")
    _print_table(data.list_applicants(decision_status="Awaiting"))
    _pause()


def list_offers() -> None:
    print("\n═══ UCAS Applicants — Offers made ═══")
    rows = (data.list_applicants(decision_status="Conditional Offer")
            + data.list_applicants(decision_status="Unconditional Offer"))
    _print_table(rows)
    _pause()


def list_by_status() -> None:
    try:
        status = _pick_from("Filter by decision status",
                              list(DECISION_STATUSES))
        print(f"\n═══ Applicants with decision: {status} ═══")
        _print_table(data.list_applicants(decision_status=status))
        _pause()
    except _UserAbort:
        return


def search_applicants() -> None:
    try:
        q = _input("Search (name / id / course)", allow_empty=False)
        print(f"\n═══ Applicants matching {q!r} ═══")
        _print_table(data.list_applicants(search=q))
        _pause()
    except _UserAbort:
        return


def view_applicant() -> None:
    try:
        a = _pick_applicant()
        _print_full(a)
        _pause()
    except _UserAbort:
        return


def record_decision_flow() -> None:
    print("\n═══ Record Admissions Decision ═══")
    try:
        a = _pick_applicant()
        _print_full(a)
        print(f"\n    Current decision: {a.decision_status}")
        decision = _pick_from("New decision", list(DECIDABLE),
                                default=a.decision_status
                                if a.decision_status in DECIDABLE
                                else None)
        offer_terms = a.offer_terms or ""
        if decision == "Conditional Offer":
            offer_terms = _input(
                "Offer terms (e.g. 'ABB including B in Maths')",
                default=offer_terms,
                allow_empty=False,
            )
        elif decision == "Unconditional Offer":
            offer_terms = _input("Offer terms (optional)",
                                    default=offer_terms or "Unconditional")
        else:
            offer_terms = _input(
                "Offer terms (leave blank to clear)",
                default=offer_terms)
        notes = _input("Decision notes (optional)",
                          default=a.choice_notes or "")
        out = data.record_decision(
            a.choice_id, decision,
            offer_terms=offer_terms or None,
            notes=notes or None,
        )
        print(f"\n  ✓ Decision recorded: {out.decision_status}"
              f" (terms: {out.offer_terms or '—'})")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except UcasError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("record_decision_flow failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def show_summary() -> None:
    print("\n═══ UCAS Summary ═══")
    try:
        s = data.summary()
        print(f"\n  University           : {s.university_name}")
        print(f"  Total applicants     : {s.total_applicants}")
        print(f"  Awaiting decision    : {s.awaiting_decision}")
        print(f"  Offers made          : {s.offers_made}")
        print("\n  By decision:")
        for k, v in s.by_decision.items():
            if v:
                print(f"    {k:<22} {v:>3}")
        print("\n  By application status:")
        for k, v in s.by_app_status.items():
            if v:
                print(f"    {k:<14} {v:>3}")
        if s.by_course:
            print("\n  By course:")
            for k, v in sorted(s.by_course.items(),
                                 key=lambda kv: -kv[1]):
                print(f"    {k[:28]:<28} {v:>3}")
        if s.by_cycle:
            print("\n  By cycle year:")
            for k, v in sorted(s.by_cycle.items()):
                print(f"    {k:<6} {v:>3}")
        _pause()
    except UcasError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("show_summary failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


# ── Internal admin (links & notes) ────────────────────────────────

def _ensure_link_for_selected() -> int | None:
    """Pick an applicant and return the link_id (creating on demand).
    Returns ``None`` if the user aborts."""
    try:
        a = _pick_applicant()
    except _UserAbort:
        return None
    try:
        link = links_data.ensure_link_for_choice(
            sf_application_id=a.application_id,
            sf_choice_id=a.choice_id,
            sf_student_id=a.student_id,
        )
    except UcasLinkError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return None
    return link.link_id


def _print_link(link) -> None:
    print()
    print(f"    Link #{link.link_id}")
    print(f"    sf application : {link.sf_application_id}")
    print(f"    sf choice      : {link.sf_choice_id}")
    print(f"    sf student     : {link.sf_student_id}")
    print(f"    uni application: {link.uni_application_id or '—'}")
    print(f"    uni student    : {link.uni_student_id or '—'}")
    print(f"    status         : {link.status}")
    print(f"    linked by      : {link.linked_by or '—'}")
    print(f"    linked at      : {link.linked_at}")


def view_internal_notes() -> None:
    print("\n═══ Internal Admissions Notes ═══")
    link_id = _ensure_link_for_selected()
    if link_id is None:
        return
    try:
        link = links_data.get_link(link_id)
        notes = links_data.list_notes(link_id)
    except Exception as e:
        logger.exception("view_internal_notes failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    _print_link(link)
    print(f"\n    Notes ({len(notes)}):")
    if not notes:
        print("      (none)")
    else:
        for n in notes:
            print(f"      #{n.note_id:<4} {n.created_at}  "
                  f"by {n.author or '—'}")
            for line in n.body.splitlines():
                print(f"        {line}")
    _pause()


def add_internal_note_flow() -> None:
    print("\n═══ Add Internal Admissions Note ═══")
    link_id = _ensure_link_for_selected()
    if link_id is None:
        return
    print("\n  Enter note text (end with '.' on its own line):")
    lines: list[str] = []
    try:
        while True:
            ln = input("  > ")
            if ln.strip() == ".":
                break
            lines.append(ln)
    except (EOFError, KeyboardInterrupt):
        print("\n  (cancelled)")
        return
    body = "\n".join(lines).strip()
    if not body:
        print("\n  (empty — nothing saved)")
        _pause()
        return
    author = _input("Author (your name, blank for none)") or None
    try:
        n = links_data.add_note(link_id, body, author=author)
        print(f"\n  ✓ Added note #{n.note_id}.")
        _pause()
    except UcasLinkError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("add_internal_note_flow failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def update_internal_note_flow() -> None:
    print("\n═══ Update Internal Admissions Note ═══")
    try:
        nid = int(_input("Note id", allow_empty=False))
    except _UserAbort:
        return
    except ValueError:
        print("\n  ✗ Note id must be a number.")
        _pause()
        return
    note = links_data.get_note(nid)
    if note is None:
        print(f"\n  ✗ No note with id {nid}.")
        _pause()
        return
    print("\n  Current body:")
    for line in note.body.splitlines():
        print(f"    {line}")
    print("\n  New text (end with '.' on its own line):")
    lines: list[str] = []
    try:
        while True:
            ln = input("  > ")
            if ln.strip() == ".":
                break
            lines.append(ln)
    except (EOFError, KeyboardInterrupt):
        print("\n  (cancelled)")
        return
    new_body = "\n".join(lines).strip()
    if not new_body:
        print("\n  (empty — nothing changed)")
        _pause()
        return
    try:
        out = links_data.update_note(nid, new_body)
        print(f"\n  ✓ Updated note #{out.note_id}.")
        _pause()
    except UcasLinkError as e:
        print(f"\n  ✗ {e}")
        _pause()


def delete_internal_note_flow() -> None:
    print("\n═══ Delete Internal Admissions Note ═══")
    try:
        nid = int(_input("Note id", allow_empty=False))
    except _UserAbort:
        return
    except ValueError:
        print("\n  ✗ Note id must be a number.")
        _pause()
        return
    if not links_data.get_note(nid):
        print(f"\n  ✗ No note with id {nid}.")
        _pause()
        return
    raw = _input("Confirm delete (y/N)", default="n")
    if raw.strip().lower() not in ("y", "yes"):
        print("\n  (cancelled)")
        return
    if links_data.delete_note(nid):
        print(f"\n  ✓ Deleted note #{nid}.")
    _pause()


def attach_uni_application_flow() -> None:
    print("\n═══ Attach Uni Application to Link ═══")
    link_id = _ensure_link_for_selected()
    if link_id is None:
        return
    raw = _input("Uni application_id (blank to clear)", allow_empty=True)
    if not raw:
        try:
            links_data.attach_uni_application(link_id, None)
            print("\n  ✓ Cleared uni_application_id.")
        except UcasLinkError as e:
            print(f"\n  ✗ {e}")
        _pause()
        return
    try:
        uni_app_id = int(raw)
    except ValueError:
        print("\n  ✗ Must be a number.")
        _pause()
        return
    try:
        out = links_data.attach_uni_application(link_id, uni_app_id)
        print(f"\n  ✓ Attached uni application #{uni_app_id} to "
              f"link #{out.link_id}.")
        _pause()
    except UcasLinkError as e:
        print(f"\n  ✗ {e}")
        _pause()


def attach_uni_student_flow() -> None:
    print("\n═══ Attach Uni Student to Link ═══")
    link_id = _ensure_link_for_selected()
    if link_id is None:
        return
    raw = _input("Uni student_id (blank to clear)", allow_empty=True)
    target: str | None = raw or None
    try:
        out = links_data.attach_uni_student(link_id, target)
        print(f"\n  ✓ Attached uni student "
              f"{target or '—'} to link #{out.link_id}.")
        _pause()
    except UcasLinkError as e:
        print(f"\n  ✗ {e}")
        _pause()


def set_link_status_flow() -> None:
    print("\n═══ Set Link Status ═══")
    link_id = _ensure_link_for_selected()
    if link_id is None:
        return
    try:
        link = links_data.get_link(link_id)
        status = _pick_from("Status", list(LINK_STATUSES),
                              default=link.status)
        out = links_data.set_link_status(link_id, status)
        print(f"\n  ✓ Link #{out.link_id} status -> {out.status}.")
        _pause()
    except _UserAbort:
        return
    except UcasLinkError as e:
        print(f"\n  ✗ {e}")
        _pause()


def list_my_links() -> None:
    """List all links, optionally filtered by status, for the
    admissions team's pipeline view."""
    print("\n═══ Internal Links (Admissions Pipeline) ═══")
    try:
        status = _pick_from("Filter by status",
                              ["(any)", *LINK_STATUSES])
    except _UserAbort:
        return
    status_arg = None if status == "(any)" else status
    try:
        rows = links_data.list_links(status=status_arg)
    except UcasLinkError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not rows:
        print("\n  (no links)")
        _pause()
        return
    print(f"\n  {'Link':>5}  {'sf-app':>6}  {'sf-choice':>9}  "
          f"{'sf-student':<12}  {'uni-app':>8}  {'uni-student':<12}  "
          f"{'status':<10}  Linked-at")
    print("  " + "-" * 100)
    for l in rows:
        print(f"  {l.link_id:>5}  {l.sf_application_id:>6}  "
              f"{l.sf_choice_id:>9}  {l.sf_student_id:<12}  "
              f"{(l.uni_application_id or '—'):>8}  "
              f"{(l.uni_student_id or '—'):<12}  "
              f"{l.status:<10}  {l.linked_at}")
    print(f"\n  {len(rows)} link(s).")
    _pause()


def internal_admin_submenu() -> None:
    """Submenu for the internal link / notes workflow — kept off the
    main menu to avoid clutter."""
    items: list[tuple[str, Callable[[], None]]] = [
        ("List links (pipeline)",           list_my_links),
        ("View internal notes",             view_internal_notes),
        ("Add internal note",               add_internal_note_flow),
        ("Update internal note",            update_internal_note_flow),
        ("Delete internal note",            delete_internal_note_flow),
        ("Attach uni application to link",  attach_uni_application_flow),
        ("Attach uni student to link",      attach_uni_student_flow),
        ("Set link status",                 set_link_status_flow),
    ]
    while True:
        print("\n──── Internal admin (links & notes) ────")
        for i, (label, _fn) in enumerate(items, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(items)):
            print("  Invalid selection.")
            continue
        _label, fn = items[int(choice) - 1]
        try:
            fn()
        except _UserAbort:
            print("\n  (cancelled)")
        except Exception as e:
            logger.exception("Internal-admin flow crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


# ── Menu ─────────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all applicants",           list_all),
    ("Awaiting decision",             list_awaiting),
    ("Offers made",                   list_offers),
    ("List by decision status",       list_by_status),
    ("Search applicants",             search_applicants),
    ("View applicant detail",         view_applicant),
    ("Record admissions decision",    record_decision_flow),
    ("Internal admin (links/notes)",  internal_admin_submenu),
    ("Summary report",                show_summary),
]


def run() -> None:
    while True:
        print("\n══════ UCAS Management ══════")
        for i, (label, _fn) in enumerate(_MENU, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        _label, fn = _MENU[int(choice) - 1]
        try:
            fn()
        except _UserAbort:
            print("\n  (cancelled)")
        except Exception as e:
            logger.exception("UCAS CLI flow crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "UCAS Management":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("UCAS CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
