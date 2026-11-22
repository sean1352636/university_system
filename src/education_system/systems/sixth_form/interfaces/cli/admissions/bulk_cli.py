"""Admissions CLI: bulk actions on a selection, merging duplicates, exports of a selection."""

from __future__ import annotations

import json
from datetime import date as _date
from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
    record_safety,
)
from education_system.systems.sixth_form.domain.admissions import (
    applicant_reports as reports,
)
from education_system.systems.sixth_form.domain.admissions.admissions import (
    Applicant,
    DECISION_REASONS,
    SOURCES,
    STATUSES,
)
from education_system.systems.sixth_form.interfaces.cli.admissions._common import (
    _UserAbort,
    _age,
    _input,
    _pause,
    _pick_applicant,
    _pick_from,
    _pick_many_applicants,
    _send_to_printer,
    _yes,
    _attempt,
)



def _write_applicants_pdf(path: str, rows: list[Applicant]) -> None:
    """Landscape-A4 table of applicants (mirrors the GUI export)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )
    from education_system.platform import branding
    styles = getSampleStyleSheet()
    cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=8,
                          leading=9)

    def P(text: str):
        safe = (text or "—").replace("&", "&amp;").replace(
            "<", "&lt;").replace(">", "&gt;")
        return Paragraph(safe, cell)

    header = ["ID", "Name", "Age", "Status", "Offer", "Source", "Subjects"]
    table_rows: list[list] = [header]
    for a in rows:
        age = _age(a.dob)
        table_rows.append([
            a.applicant_id, P(a.full_name),
            str(age) if age is not None else "—", P(a.status),
            a.offer_type or "—", P(a.application_source),
            P(", ".join(a.subjects))])
    widths = [2, 4.2, 1.2, 3.2, 2.6, 3, 8]
    tbl = Table(table_rows, repeatRows=1, colWidths=[w * cm for w in widths])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3b63")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f0f4fa")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    doc = SimpleDocTemplate(path, pagesize=landscape(A4), leftMargin=1 * cm,
                            rightMargin=1 * cm, topMargin=1 * cm,
                            bottomMargin=1 * cm)
    doc.build([
        Paragraph(f"{branding.SYSTEM_NAME} — Admissions", styles["Title"]),
        Paragraph(f"{len(rows)} applicant(s) · generated "
                  f"{_date.today().isoformat()}", styles["Normal"]),
        Spacer(1, 8), tbl])


# ── Bulk actions (items 2, 39) ────────────────────────────────────

def bulk_status_flow() -> None:
    print("\n═══ Bulk Change Status ═══")
    try:
        picks = _pick_many_applicants()
        new_status = _pick_from("New status for all",
                                [st for st in STATUSES if st != "Enrolled"])
    except _UserAbort:
        print("\n  Cancelled.")
        return
    ok, fail = 0, []
    for a in picks:
        try:
            data.set_status(a.applicant_id, new_status)
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail.append(f"{a.applicant_id}: {e}")
    print(f"\n  ✓ {ok} updated → {new_status}")
    for f in fail:
        print(f"  ✗ {f}")
    _pause()


# ══ Bulk & selection flows (GUI items 1–15) ═══════════════════════
# Item 1 (bulk change status) is already covered by bulk_status_flow.

def bulk_reject_flow() -> None:
    """Item 2 — reject several applicants with one shared reason."""
    print("\n═══ Bulk Reject ═══")
    try:
        picks = _pick_many_applicants()
        reason = _pick_from("Shared rejection reason", list(DECISION_REASONS))
    except _UserAbort:
        print("\n  Cancelled.")
        return
    ok, fail = 0, []
    for a in picks:
        try:
            data.record_decision(a.applicant_id, "Rejected", reason=reason)
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail.append(f"{a.applicant_id}: {e}")
    print(f"\n  ✓ {ok} rejected — {reason}")
    for f in fail:
        print(f"  ✗ {f}")
    _pause()


def bulk_add_note_flow() -> None:
    """Item 3 — append the same note to several applicants."""
    print("\n═══ Bulk Add Note ═══")
    try:
        picks = _pick_many_applicants()
        body = _input("Note to append to each", allow_empty=False)
        author = _input("Author", default="admissions-cli")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    ok, fail = 0, []
    for a in picks:
        try:
            data.add_note(a.applicant_id, body, author=author or None)
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail.append(f"{a.applicant_id}: {e}")
    print(f"\n  ✓ Note added to {ok} applicant(s).")
    for f in fail:
        print(f"  ✗ {f}")
    _pause()


def bulk_set_source_flow() -> None:
    """Item 4 — correct the application source across a selection."""
    print("\n═══ Bulk Set Source ═══")
    try:
        picks = _pick_many_applicants()
        source = _pick_from("New application source", list(SOURCES))
    except _UserAbort:
        print("\n  Cancelled.")
        return
    ok, fail = 0, []
    for a in picks:
        try:
            data.update_applicant(a.applicant_id,
                                  {"application_source": source})
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail.append(f"{a.applicant_id}: {e}")
    print(f"\n  ✓ Source set to {source} for {ok} applicant(s).")
    for f in fail:
        print(f"  ✗ {f}")
    _pause()


def bulk_assign_interviewer_flow() -> None:
    """Item 5 — assign one interviewer to several applicants."""
    print("\n═══ Bulk Assign Interviewer ═══")
    try:
        picks = _pick_many_applicants()
        who = _input("Interviewer name (blank clears)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    ok, fail = 0, []
    for a in picks:
        try:
            data.update_applicant(a.applicant_id,
                                  {"interviewer": who or None})
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail.append(f"{a.applicant_id}: {e}")
    print(f"\n  ✓ Interviewer '{who or '(cleared)'}' set for {ok}.")
    for f in fail:
        print(f"  ✗ {f}")
    _pause()


def _do_merge(primary: Applicant, other: Applicant) -> None:
    """Merge through record_safety: blanks are filled, notes/documents/
    history move across, and the duplicate is kept (archived, pointing at
    the kept record) — nothing is deleted."""
    reason = _input("Reason for the merge", default="Duplicate application")
    ok, res = _attempt(record_safety.merge_applicants, primary.applicant_id,
                       other.applicant_id, reason=reason or None)
    if not ok:
        return
    print(f"\n  ✓ Merged {other.applicant_id} into {primary.applicant_id}: "
          f"{len(res.filled)} field(s) filled"
          + (f" ({', '.join(res.filled)})" if res.filled else ""))
    for table, n in (res.moved or {}).items():
        print(f"      moved {n} row(s) from {table}")
    for table, n in (res.left_on_duplicate or {}).items():
        print(f"      left on {other.applicant_id}: {n} row(s) in {table}")
    print(f"    {other.applicant_id} is archived as merged (restore it from "
          "'Archived applicants' if this was a mistake).")


def merge_duplicates_flow() -> None:
    """Item 6 — merge a duplicate record into a kept applicant."""
    print("\n═══ Merge Duplicates ═══")
    try:
        primary = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    dupes = data.find_duplicates(
        email=primary.email, first_name=primary.first_name,
        last_name=primary.last_name, dob=primary.dob,
        exclude_id=primary.applicant_id)
    if not dupes:
        print(f"  No potential duplicates for {primary.applicant_id}.")
        _pause()
        return
    print(f"\n  Potential duplicates of {primary.applicant_id} "
          f"({primary.full_name}):")
    for i, d in enumerate(dupes, 1):
        print(f"    {i:>2}) {d.applicant_id}  {d.full_name[:24]:<24}  "
              f"{d.email or 'no email'}")
    try:
        raw = _input(f"  Merge which #1..{len(dupes)} into "
                     f"{primary.applicant_id}?", allow_empty=False)
        if not raw.isdigit() or not (1 <= int(raw) <= len(dupes)):
            print("  ✗ Invalid choice.")
            _pause()
            return
        other = dupes[int(raw) - 1]
        if not _yes(f"Merge {other.applicant_id} into "
                    f"{primary.applicant_id} (the duplicate is archived, "
                    "not deleted)?"):
            print("\n  Cancelled.")
            return
        _do_merge(primary, other)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _pause()


def email_list_flow() -> None:
    """Item 11 — collect a selection's email addresses."""
    print("\n═══ Email List ═══")
    try:
        picks = _pick_many_applicants()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    emails = [a.email for a in picks if a.email and a.email.strip()]
    if not emails:
        print("  None of the selected applicants have an email address.")
        _pause()
        return
    joined = "; ".join(emails)
    print(f"\n  {len(emails)} address(es):\n\n  {joined}")
    if _yes("\n  Save to a file?"):
        path = _input("Save to path", default="emails.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(joined + "\n")
        print(f"  ✓ Saved to {path}")
    _pause()


def export_pdf_flow() -> None:
    """Item 12 — export a selection to a formatted PDF."""
    print("\n═══ Export Selection to PDF ═══")
    try:
        picks = _pick_many_applicants()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    path = _input("Save PDF to path", default="applicants.pdf")
    try:
        _write_applicants_pdf(path, picks)
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"  ✓ Exported {len(picks)} applicant(s) to {path}")
    _pause()


def print_list_flow() -> None:
    """Item 13 — send the applicant list to the default printer."""
    print("\n═══ Print Applicant List ═══")
    rows = data.list_applicants()
    if not rows:
        print("  (nothing to print)")
        _pause()
        return
    lines = [f"Admissions — {len(rows)} applicants — "
             f"{_date.today().isoformat()}", "",
             f"{'ID':<8} {'Name':<22} {'Age':>3} {'Status':<18} Subjects"]
    for a in rows:
        age = _age(a.dob)
        lines.append(f"{a.applicant_id:<8} {a.full_name[:22]:<22} "
                     f"{(str(age) if age is not None else '—'):>3} "
                     f"{a.status:<18} {', '.join(a.subjects)}")
    try:
        _send_to_printer("\n".join(lines) + "\n")
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ Could not print: {e}")
        _pause()
        return
    print(f"  ✓ Sent {len(rows)} applicant(s) to the default printer.")
    _pause()


def bulk_follow_up_flow() -> None:
    """Item 14 — set/clear the follow-up flag on a selection."""
    print("\n═══ Bulk Follow-up ═══")
    try:
        picks = _pick_many_applicants()
        flag = _yes("Turn follow-up ON? (n = clear)", default="y")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    ok, fail = 0, []
    for a in picks:
        try:
            data.set_follow_up(a.applicant_id, flag)
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail.append(f"{a.applicant_id}: {e}")
    print(f"\n  ✓ Follow-up {'set' if flag else 'cleared'} on {ok}.")
    for f in fail:
        print(f"  ✗ {f}")
    _pause()


def gdpr_batch_export_flow() -> None:
    """Item 49 — export several applicants' GDPR bundles to one file."""
    print("\n═══ GDPR Batch Export ═══")
    try:
        picks = _pick_many_applicants()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    path = _input("Save JSON to path", default="gdpr_batch.json")
    bundle, fail = {}, []
    for a in picks:
        try:
            bundle[a.applicant_id] = reports.gdpr_export(a.applicant_id)
        except Exception as e:  # noqa: BLE001
            fail.append(f"{a.applicant_id}: {e}")
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(bundle, fh, indent=2, default=str)
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"  ✓ Exported {len(bundle)} bundle(s) to {path}")
    for f in fail:
        print(f"  ✗ {f}")
    _pause()
