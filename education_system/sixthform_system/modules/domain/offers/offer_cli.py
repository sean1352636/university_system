"""CLI flows for Sixth Form University Offers."""

from __future__ import annotations

import logging
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.offers import offers
from education_system.sixthform_system.modules.domain.students import students
from education_system.sixthform_system.modules.domain.ucas import ucas as data
from education_system.sixthform_system.modules.domain.students import students as student_data
from education_system.sixthform_system.modules.domain.ucas import ucas as ucas_data
from education_system.sixthform_system.modules.domain.offers.offers import (
    OFFER_DECISION_STATUSES,
    OfferRow,
    ValidationError,
)
from education_system.sixthform_system.modules.domain.ucas.ucas import (
    DECISION_STATUSES,
    FINAL_DECISIONS,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "", allow_empty: bool = True) -> str:
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


def _pick_from(label: str, options: list[str], default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}", default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel' to abort).")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print(f"    Out of range (1..{len(options)}).")
            continue
        return options[n - 1]


def _pick_choice() -> int:
    """Pick any UCAS choice."""
    rows = data.list_offer_rows()
    if not rows:
        print("    No UCAS choices exist.")
        raise _UserAbort
    print("\n  UCAS choices:")
    for i, r in enumerate(rows, 1):
        print(f"    {i:>3}) choice #{r.choice_id:<3}  {r.student_id:<10}  "
              f"{r.university[:14]:<14}  {r.course_name[:22]:<22}  "
              f"[{r.decision_status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or choice ID)",
                     allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].choice_id
            target = next((r for r in rows if r.choice_id == n), None)
            if target:
                return target.choice_id
            print(f"    Out of range (1..{len(rows)}).")


# ── Listing ───────────────────────────────────────────────────────

def _print_offer_rows(rows: list[OfferRow]) -> None:
    if not rows:
        print("\n  (no offers)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'University':<14}  "
          f"{'Course':<22}  {'Decision':<20}  {'Deadline':<10}  "
          f"{'Final':<10}  Pred")
    print("  " + "-" * 108)
    for r in rows:
        d = r.details
        deadline = (d.reply_deadline if d and d.reply_deadline else "—")
        print(f"  {r.choice_id:>4}  {r.student_id:<10}  "
              f"{r.university[:14]:<14}  {r.course_name[:22]:<22}  "
              f"{r.decision_status[:20]:<20}  "
              f"{deadline:<10}  {(r.final_decision or '—'):<10}  "
              f"{r.predicted_grade or '—'}")
    print(f"\n  {len(rows)} offer row(s).")


def list_all() -> None:
    print("\n═══ University Offers ═══")
    rows = data.list_offer_rows(offers_only=True)
    _print_offer_rows(rows)
    _row_action_loop(rows)


def list_choices() -> None:
    """All UCAS choices (including rejections / withdrawals)."""
    print("\n═══ All UCAS Choices ═══")
    rows = data.list_offer_rows()
    _print_offer_rows(rows)
    _row_action_loop(rows)


def filter_offers() -> None:
    print("\n═══ Filter Offers ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        sid = _input("Student ID") or None
        uni = _input("University substring") or None
        decision = _input(
            f"Decision ({'/'.join(DECISION_STATUSES)})") or None
        final = _input(
            f"Final ({'/'.join(FINAL_DECISIONS)})") or None
        only_raw = _input("Offers only? (y/n)", default="y").lower()
        deadline_before = _input(
            "Deadline ≤ (YYYY-MM-DD, optional)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_offer_rows(
            student_id=sid, university_like=uni,
            decision_status=decision, final_decision=final,
            offers_only=only_raw in ("y", "yes"),
            deadline_before=deadline_before,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_offer_rows(rows)
    _row_action_loop(rows)


def per_student() -> None:
    print("\n═══ Per-Student Compare ═══")
    students = student_data.list_students()
    if not students:
        print("  No students.")
        _pause()
        return
    print("\n  Students:")
    for i, s in enumerate(students, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    try:
        raw = _input(f"  Pick #1..{len(students)} (or student ID)",
                     allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    sid = None
    if raw.isdigit():
        n = int(raw)
        if 1 <= n <= len(students):
            sid = students[n - 1].student_id
    if sid is None:
        match = next((s for s in students
                      if s.student_id.lower() == raw.lower()), None)
        sid = match.student_id if match else None
    if sid is None:
        print("  ✗ Unknown student.")
        _pause()
        return

    rows = data.offers_for_student(sid)
    student = student_data.get_student(sid)
    print(f"\n  {student.student_id}  {student.full_name}")
    if not rows:
        print("  (no UCAS choices)")
        _pause()
        return
    print()
    print(f"  {'Slot':<4}  {'University':<14}  {'Course':<22}  "
          f"{'Decision':<20}  {'Required':<22}  {'Pred':<5}  "
          f"{'Deadline':<10}  {'Final':<10}")
    print("  " + "-" * 124)
    for r in rows:
        d = r.details
        req = (d.grade_requirement if d and d.grade_requirement
               else r.offer_terms or "—")
        print(f"  {r.choice_order:<4}  {r.university[:14]:<14}  "
              f"{r.course_name[:22]:<22}  {r.decision_status[:20]:<20}  "
              f"{req[:22]:<22}  {(r.predicted_grade or '—'):<5}  "
              f"{(d.reply_deadline if d and d.reply_deadline else '—'):<10}  "
              f"{(r.final_decision or '—'):<10}")
    _row_action_loop(rows)


def view_offer(choice_id: int | None = None) -> None:
    print("\n═══ View Offer ═══")
    try:
        cid = choice_id if choice_id is not None else int(
            _input("Choice ID", allow_empty=False))
    except ValueError:
        print("  ✗ Choice ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    row = data.get_offer_row(cid)
    if row is None:
        print(f"  ✗ No UCAS choice #{cid}")
        _pause()
        return
    print()
    print(f"    Choice ID         : #{row.choice_id}")
    print(f"    Student           : {row.student_id}  {row.student_name}")
    print(f"    University        : {row.university}")
    print(f"    Course            : {row.course_name}"
          + (f" ({row.course_code})" if row.course_code else ""))
    print(f"    Entry year        : "
          f"{row.entry_year if row.entry_year else '—'}")
    print(f"    Decision status   : {row.decision_status}")
    print(f"    UCAS offer terms  : {row.offer_terms or '—'}")
    print(f"    Final decision    : {row.final_decision or '—'}")
    print(f"    Predicted grade   : {row.predicted_grade or '—'}")
    if row.details:
        d = row.details
        print(f"\n    Offer details (#{d.offer_id}):")
        print(f"      Grade requirement      : {d.grade_requirement or '—'}")
        print(f"      Alternative pathway    : {d.grade_alternative or '—'}")
        print(f"      Reply deadline         : {d.reply_deadline or '—'}")
        print(f"      Expiry date            : {d.expiry_date or '—'}")
        print(f"      Scholarship            : {d.scholarship or '—'}")
        print(f"      Accommodation guaranteed: "
              f"{'Yes' if d.accommodation_guaranteed else 'No'}")
        if d.notes:
            print(f"      Notes                  : {d.notes}")
    else:
        print("\n    (no offer details set)")
    _pause()


def edit_offer(choice_id: int | None = None) -> None:
    print("\n═══ Edit Offer ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        cid = choice_id if choice_id is not None else _pick_choice()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    row = data.get_offer_row(cid)
    if row is None:
        print(f"  ✗ No UCAS choice #{cid}")
        _pause()
        return
    existing = row.details

    try:
        req = _input("Grade requirement",
                     default=(existing.grade_requirement
                              if existing and existing.grade_requirement
                              else (row.offer_terms or "")))
        alt = _input("Alternative pathway",
                     default=(existing.grade_alternative
                              if existing and existing.grade_alternative
                              else ""))
        deadline = _input("Reply deadline (YYYY-MM-DD, optional)",
                          default=(existing.reply_deadline
                                   if existing and existing.reply_deadline
                                   else ""))
        expiry = _input("Expiry date (YYYY-MM-DD, optional)",
                        default=(existing.expiry_date
                                 if existing and existing.expiry_date
                                 else ""))
        scholarship = _input("Scholarship (optional)",
                             default=(existing.scholarship
                                      if existing and existing.scholarship
                                      else ""))
        accom_raw = _input(
            "Accommodation guaranteed? (y/n)",
            default=("y" if existing and existing.accommodation_guaranteed
                     else "n"),
        )
        notes = _input("Notes (optional)",
                       default=(existing.notes
                                if existing and existing.notes else ""))
    except _UserAbort:
        print("\n  Cancelled.")
        return

    try:
        data.save_details(cid, {
            "grade_requirement": req,
            "grade_alternative": alt,
            "reply_deadline":    deadline,
            "expiry_date":       expiry,
            "scholarship":       scholarship,
            "accommodation_guaranteed": accom_raw.lower() in ("y", "yes"),
            "notes":             notes,
        })
        print(f"\n  ✓ Saved offer details for choice #{cid}")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except Exception as e:
        logger.exception("save_details crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


def set_final(choice_id: int | None = None) -> None:
    print("\n═══ Set Final Decision ═══")
    print("  Final decisions: Firm / Insurance / Declined / (clear)")
    try:
        cid = choice_id if choice_id is not None else _pick_choice()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    row = data.get_offer_row(cid)
    if row is None:
        print(f"  ✗ No UCAS choice #{cid}")
        _pause()
        return
    try:
        final = _pick_from(
            "Final decision",
            ["(clear)", *FINAL_DECISIONS],
            default=row.final_decision or "(clear)",
        )
    except _UserAbort:
        print("\n  Cancelled.")
        return
    new_final = None if final == "(clear)" else final
    try:
        data.set_final_decision(cid, new_final)
        print(f"\n  ✓ Final decision for choice #{cid} set to "
              f"{new_final or '(cleared)'}")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except Exception as e:
        logger.exception("set_final_decision crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


def delete_details_flow(choice_id: int | None = None) -> None:
    print("\n═══ Clear Offer Details ═══")
    try:
        cid = choice_id if choice_id is not None else int(
            _input("Choice ID", allow_empty=False))
    except ValueError:
        print("  ✗ Choice ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if data.get_details_for_choice(cid) is None:
        print(f"  ✗ No offer details for choice #{cid}")
        _pause()
        return
    confirm = _input(
        "Remove the offer-details row? Type 'yes' to confirm "
        "(the UCAS choice itself stays)",
        default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_details(cid):
            print(f"\n  ✓ Cleared offer details for choice #{cid}")
    except Exception as e:
        logger.exception("delete_details crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


def summary() -> None:
    print("\n═══ Offer Summary ═══")
    try:
        raw = _input("Deadline window in days", default="30")
        days = int(raw)
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    summ = data.summary(deadline_window_days=days)
    print(f"\n  Choices: {summ.total_choices}  ·  Offers: {summ.total_offers}")
    print("\n  By decision status:")
    for st, n in sorted(summ.by_decision.items()):
        print(f"    {st:<22} : {n}")
    print("\n  By final decision:")
    for st, n in sorted(summ.by_final.items()):
        label = st if st != "(none)" else "Not decided"
        print(f"    {label:<22} : {n}")
    print(f"\n  Scholarships             : {summ.with_scholarship}")
    print(f"  Accommodation guaranteed : {summ.with_accommodation}")
    print(f"  Upcoming deadlines ({days}d, no final yet) : "
          f"{summ.upcoming_deadlines}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop(rows: list[OfferRow]) -> None:
    if not rows:
        _pause()
        return
    print()
    print("  Actions:  V) View   E) Edit   F) Firm   I) Insurance   "
          "D) Decline   C) Clear final   X) Clear details   "
          "(Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "f", "i", "d", "c", "x"):
            print("    Pick V/E/F/I/D/C/X or Enter.")
            continue
        try:
            raw = _input("Choice ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            cid = int(raw)
        except ValueError:
            print("    Choice ID must be a whole number.")
            continue
        if choice == "v":
            view_offer(cid)
        elif choice == "e":
            edit_offer(cid)
        elif choice == "f":
            _quick_final(cid, "Firm")
        elif choice == "i":
            _quick_final(cid, "Insurance")
        elif choice == "d":
            _quick_final(cid, "Declined")
        elif choice == "c":
            _quick_final(cid, None)
        elif choice == "x":
            delete_details_flow(cid)
        return


def _quick_final(choice_id: int, final: str | None) -> None:
    try:
        data.set_final_decision(choice_id, final)
        print(f"  ✓ Choice #{choice_id} → {final or '(cleared)'}")
    except ValidationError as e:
        print(f"  ✗ {e}")
    except Exception as e:
        logger.exception("set_final_decision crashed")
        print(f"  ✗ Unexpected error: {e}")
    _pause()


# ── Submenu dispatcher ───────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List Offers (offers only)",    list_all),
    ("List All UCAS Choices",        list_choices),
    ("Filter",                       filter_offers),
    ("Per-Student Compare",          per_student),
    ("View Offer",                   view_offer),
    ("Edit Offer",                   edit_offer),
    ("Set Final Decision",           set_final),
    ("Clear Offer Details",          delete_details_flow),
    ("Summary",                      summary),
]


def run() -> None:
    while True:
        print("\n── University Offers ──")
        for i, (label, _) in enumerate(_MENU, 1):
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
        _, handler = _MENU[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Offers CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "University Offers":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Offers CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
