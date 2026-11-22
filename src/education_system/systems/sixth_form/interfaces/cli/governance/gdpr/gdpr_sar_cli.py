"""CLI for subject access requests: deadlines (one calendar month,
extendable once by up to two) and compiling a learner's SAR bundle.
Reached from the GDPR menu (see ``gdpr_cli._MENU``)."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.governance.gdpr import sar
from education_system.systems.sixth_form.domains.finance.interfaces.cli import (
    _prompts as ui,
)


def _who() -> str:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access.current().username or ui.ask("Your name", required=True)


@ui.handler
def deadlines() -> None:
    sar_only = ui.yes_no("Subject access requests only?", default=True)
    rows = sar.deadlines(open_only=True, sar_only=sar_only)
    ui.table(("#", "Subject", "Ref", "Type", "Received", "Due", "Extended",
              "Days", "RAG", "Compiled"),
             [(d.request_id, d.subject_name[:22], d.subject_ref or "",
               d.request_type[:20], d.received_date, d.due_date,
               d.extended_due_date or "", d.days_remaining, d.rag,
               (d.compiled_at or "")[:16]) for d in rows],
             empty="(no open requests)")


@ui.handler
def extend() -> None:
    rid = ui.ask_int("Request #")
    d = sar.get_deadline(rid)
    if d is None:
        raise sar.ValidationError(f"No request #{rid}")
    print(f"  {d.subject_name} · due {d.due_date}")
    print("  An extension is allowed once, for a complex request or several "
          "requests,\n  and the requester must be told before the original "
          "due date.")
    months = ui.ask_int(f"Extend by months (1-{sar.EXTENSION_MONTHS})",
                        default=sar.EXTENSION_MONTHS)
    out = sar.extend_deadline(rid, reason=ui.ask("Reason", required=True),
                              by=_who(), months=months)
    print(f"\n  ✓ New deadline {out.effective_due}.")


@ui.handler
def preview() -> None:
    sid = ui.pick_student()
    included, safeguarding = sar.scan(sid)
    ui.table(("Table", "Key", "Rows", "Via", "Review"),
             [(t.table, t.key_column, len(t.rows), t.via or "",
               t.review_reason or (", ".join(t.flagged_columns)
                                   and "columns: "
                                   + ", ".join(t.flagged_columns)))
              for t in included], empty="(no records found)")
    if safeguarding:
        print("\n  Safeguarding records exist (NOT exported — for the DSL):")
        for table, ids in safeguarding.items():
            print(f"    {table}: {len(ids)} record(s)")


@ui.handler
def compile_bundle() -> None:
    sid = ui.pick_student()
    rid = ui.ask_int("Linked request # (blank = none)", required=False)
    print("  Safeguarding records are never included; they are listed for "
          "the DSL to decide.")
    if not ui.yes_no("Compile the bundle now?", default=True):
        return
    b = sar.compile_sar(sid, request_id=rid, compiled_by=_who())
    print(f"\n  ✓ {b.total_rows} row(s) from {len(b.included)} table(s) "
          f"written to\n    {b.folder}")
    if b.review_tables:
        print(f"  ! {len(b.review_tables)} table(s) may hold third-party data"
              " — see REDACTION_REVIEW.txt before release.")
    if b.safeguarding:
        print(f"  ! Safeguarding records in {len(b.safeguarding)} table(s) — "
              "see DSL_REVIEW.txt (not in the bundle).")


MENU = [
    ("SAR Deadlines", deadlines),
    ("Extend SAR Deadline", extend),
    ("SAR Preview (what would be included)", preview),
    ("Compile SAR Bundle", compile_bundle),
]
