"""CLI flow for Registration Forms & Signatures (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.admissions.registration_forms import (
    registration_forms as data,
)
from education_system.systems.nursery.domain.admissions.registration_forms.registration_forms import (
    FORM_TYPES,
    SOURCES,
    ValidationError,
)

logger = logging.getLogger(__name__)

_REASON_TEXT = {
    "never-signed": "never signed",
    "superseded": "signed an older version",
    "expired": "needs renewing",
    "declined": "declined",
}


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _safe(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print(f"  Validation error: {e}")
        except Exception as e:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _ask(label: str, current=None) -> str:
    cur = "" if current is None else str(current)
    suffix = f" [{cur}]" if cur else ""
    v = _prompt(f"  {label}{suffix}: ")
    return v if v else cur


def _yn(flag: bool) -> str:
    return "Yes" if flag else "No"


def _show_children() -> None:
    try:
        choices = data.list_pupil_choices()
    except Exception:
        logger.exception("Could not load child choices")
        return
    if choices:
        print("  Children:")
        for _id, label in choices:
            print(f"    {label}")


@_safe
def open_manager() -> None:
    logger.debug("CLI: registration_forms open_manager")
    while True:
        s = data.summary()
        print("\n  ── Registration Forms & Signatures ──")
        print(f"  Forms: {s['templates']} ({s['active_templates']} active, "
              f"{s['required_forms']} required)")
        print(f"  Signatures: {s['signed']} signed, {s['declined']} declined, "
              f"{s['superseded']} superseded")
        if s["outstanding"]:
            reasons = ", ".join(f"{_REASON_TEXT[k]}: {v}" for k, v
                                in s["outstanding_by_reason"].items() if v)
            print(f"  ⚠ {s['outstanding']} outstanding form(s) across "
                  f"{s['children_with_gaps']} child(ren) — {reasons}")
        print("\n   F) Forms & versions    S) Signatures    O) Outstanding")
        print("   G) Sign a form    C) A child's file    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "f":
            open_templates()
        elif choice == "s":
            open_submissions()
        elif choice == "o":
            open_outstanding()
        elif choice == "g":
            open_sign()
        elif choice == "c":
            open_child_file()
        else:
            print("  Invalid selection.")


# ── Templates & versions ─────────────────────────────────────────────────────

def _print_templates(rows: list[data.FormTemplate]) -> None:
    if not rows:
        print("  (no forms published)")
        return
    print(f"  {'ID':<8} {'Name':<32} {'Type':<24} {'Ver':<6} {'Req':<4} "
          f"{'Renew':<7} {'Status'}")
    print(f"  {'-'*8} {'-'*32} {'-'*24} {'-'*6} {'-'*4} {'-'*7} {'-'*8}")
    for t in rows:
        renew = f"{t.renew_months}m" if t.renew_months else "-"
        print(f"  {t.template_id:<8} {t.name[:32]:<32} {t.form_type:<24} "
              f"{t.version:<6} {_yn(t.required):<4} {renew:<7} {t.status}")


@_safe
def open_templates() -> None:
    while True:
        print("\n  ── Forms & Versions ──")
        _print_templates(data.list_templates())
        print("\n   A) Publish a new form    R) Revise (issue next version)")
        print("   V) View wording    H) Version history    T) Retire")
        print("   X) Delete    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add_template()
        elif choice == "r":
            open_revise()
        elif choice == "v":
            open_view_template()
        elif choice == "h":
            open_history()
        elif choice == "t":
            tid = _prompt("  Template ID to retire: ")
            if tid:
                t = data.retire_template(tid)
                print(f"  Retired {t.label}.")
        elif choice == "x":
            tid = _prompt("  Template ID to delete: ")
            if tid:
                print(f"  Deleted {tid}." if data.delete_template(tid)
                      else "  No form with that ID.")
        else:
            print("  Invalid selection.")


@_safe
def open_add_template() -> None:
    print("\n  ── Publish a Form ──")
    print(f"  Types: {', '.join(FORM_TYPES)}")
    fields = {
        "form_type": _ask("Form type"),
        "name": _ask("Name"),
        "version": _ask("Version", "1.0"),
        "required": _ask("Required of every child? (y/n)", "y"),
        "renew_months": _ask("Renew every N months (blank = never)"),
        "notes": _ask("Notes"),
    }
    print("  Enter the wording being signed. Finish with a single '.' line.")
    lines: list[str] = []
    while True:
        line = _prompt("  > ")
        if line == ".":
            break
        lines.append(line)
    fields["body"] = "\n".join(lines)
    t = data.create_template(fields)
    print(f"\n  Published {t.label} ({t.template_id}).")


@_safe
def open_revise() -> None:
    tid = _prompt("  Template ID to revise: ")
    if not tid:
        print("  Cancelled.")
        return
    old = data.get_template(tid)
    if old is None:
        print("  No form with that ID.")
        return
    print(f"\n  Current wording of {old.label}:\n")
    print("    " + old.body.replace("\n", "\n    "))
    print("\n  Enter the NEW wording. Finish with a single '.' line.")
    lines: list[str] = []
    while True:
        line = _prompt("  > ")
        if line == ".":
            break
        lines.append(line)
    version = _prompt("  New version (blank = auto): ")
    note = _prompt("  What changed: ")
    print("  Existing signatures against the old wording become 'superseded'.")
    if _prompt("  Issue the new version? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    t = data.revise(tid, "\n".join(lines), version=version or None,
                    notes=note or None)
    print(f"\n  Issued {t.label} ({t.template_id}). v{old.version} retired.")


@_safe
def open_view_template() -> None:
    tid = _prompt("  Template ID: ")
    t = data.get_template(tid)
    if t is None:
        print("  No form with that ID.")
        return
    print(f"\n  ── {t.label} ({t.form_type}) ──")
    print(f"  Status: {t.status}   Required: {_yn(t.required)}   "
          f"Effective: {t.effective_from or '-'}")
    print(f"  Wording hash: {t.body_hash[:16]}…")
    print(f"\n    {t.body.replace(chr(10), chr(10) + '    ')}")
    _prompt("\n  Press Enter to continue...")


@_safe
def open_history() -> None:
    print(f"  Types: {', '.join(FORM_TYPES)}")
    form_type = _prompt("  Form type: ")
    rows = data.version_history(form_type)
    if not rows:
        print("  No versions of that form.")
        return
    print(f"\n  ── Version history — {form_type} ──")
    for t in rows:
        marker = "current" if t.status == "active" else t.status
        print(f"  v{t.version:<6} {t.effective_from or '-':<12} {marker:<10} "
              f"{t.template_id}")
        if t.notes:
            print(f"           {t.notes}")
    _prompt("  Press Enter to continue...")


# ── Signatures ───────────────────────────────────────────────────────────────

def _print_submissions(rows: list[data.FormSubmission]) -> None:
    if not rows:
        print("  (no signatures recorded)")
        return
    print(f"  {'ID':<8} {'Child':<20} {'Form':<24} {'Ver':<6} {'Signed by':<20} "
          f"{'When':<12} {'Status'}")
    print(f"  {'-'*8} {'-'*20} {'-'*24} {'-'*6} {'-'*20} {'-'*12} {'-'*10}")
    for s in rows:
        print(f"  {s.submission_id:<8} {(s.child_name or s.pupil_id)[:20]:<20} "
              f"{s.form_type:<24} {s.template_version:<6} "
              f"{(s.signature_name or '-')[:20]:<20} "
              f"{(s.signed_at or '-')[:10]:<12} {s.status}")


@_safe
def open_submissions() -> None:
    while True:
        print("\n  ── Signatures ──")
        _print_submissions(data.list_submissions())
        print("\n   V) Verify a signature    G) Sign a form    X) Delete")
        print("   0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "v":
            open_verify()
        elif choice == "g":
            open_sign()
        elif choice == "x":
            sid = _prompt("  Submission ID to delete: ")
            if sid and _prompt(f"  Delete {sid}? (y/N): ").lower() == "y":
                print(f"  Deleted {sid}." if data.delete_submission(sid)
                      else "  No submission with that ID.")
        else:
            print("  Invalid selection.")


@_safe
def open_sign() -> None:
    print("\n  ── Record a Signature ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    choices = data.list_template_choices()
    if not choices:
        print("  No active forms to sign — publish one first.")
        return
    print("  Active forms:")
    for tid, label in choices:
        print(f"    {tid}  {label}")
    tid = _prompt("  Template ID: ")
    t = data.get_template(tid)
    if t is None:
        print("  No form with that ID.")
        return
    print(f"\n  {t.label} — the wording being agreed:\n")
    print("    " + t.body.replace("\n", "\n    "))
    fields = {
        "pupil_id": pid,
        "template_id": tid,
        "respondent_name": _ask("Signed by (full name)"),
        "respondent_relationship": _ask("Relationship to the child"),
        "signature_name": _ask("Typed signature (blank = same as name)"),
        "source": _ask(f"Source ({'/'.join(SOURCES)})", "portal"),
        "witnessed_by": _ask("Witnessed by (staff ID, optional)"),
        "notes": _ask("Notes"),
    }
    if _prompt("  Confirm the parent agrees to the wording above? (y/N): "
               ).lower() != "y":
        fields["status"] = "declined"
        print("  Recording as declined.")
    s = data.sign(fields)
    print(f"\n  Recorded {s.submission_id} — {s.form_type} v"
          f"{s.template_version}, {s.status}.")
    if s.signature_hash:
        print(f"  Signature digest: {s.signature_hash[:16]}…")


@_safe
def open_verify() -> None:
    sid = _prompt("  Submission ID: ")
    if not sid:
        print("  Cancelled.")
        return
    ok, message = data.verify_submission(sid)
    print(f"\n  {'✔' if ok else '✘'} {message}")
    _prompt("  Press Enter to continue...")


# ── Outstanding ──────────────────────────────────────────────────────────────

def _print_gaps(rows: list[data.FormGap]) -> None:
    if not rows:
        print("  Every required form is signed and current.")
        return
    print(f"  {'Child':<24} {'Form':<26} {'Version':<9} {'Why'}")
    print(f"  {'-'*24} {'-'*26} {'-'*9} {'-'*24}")
    for g in rows:
        print(f"  {(g.child_name or g.pupil_id)[:24]:<24} "
              f"{g.template.form_type:<26} v{g.template.version:<8} "
              f"{_REASON_TEXT.get(g.reason, g.reason)}")


@_safe
def open_outstanding() -> None:
    print("\n  ── Outstanding Forms ──")
    _print_gaps(data.all_outstanding())
    _prompt("  Press Enter to continue...")


@_safe
def open_child_file() -> None:
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    print(f"\n  ── Forms on file for {pid} ──")
    _print_submissions(data.list_submissions(pupil_id=pid))
    print("\n  Outstanding:")
    _print_gaps(data.outstanding_for(pid))
    _prompt("  Press Enter to continue...")


_DISPATCH = {"Registration Forms & Signatures": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching registration_forms CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
