"""CLI: certificate deliveries, issue log, unclaimed and retention notices."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.assessment.exams_office import (
    certificates as ct,
)
from education_system.systems.sixth_form.interfaces.cli.assessment.exams_office.exams_cli_helpers import (
    ask,
    board,
    pause,
    pick,
    run_menu,
    save_text,
    series,
    show_table,
)


def batches() -> None:
    rows = ct.list_batches()
    show_table([("#", 4), ("Board", 18), ("Series", 12), ("Received", 10), ("Number", 6),
                ("Keep until", 10)],
               [(b.batch_id, b.exam_board, f"{b.season} {b.year}", b.received_date,
                 b.count_received, b.retain_until) for b in rows])
    pause()


def new_batch() -> None:
    b = board()
    season, year = series()
    batch = ct.record_batch({"exam_board": b, "season": season, "year": year,
                             "received_date": ask("Received date (blank = today)"),
                             "count_received": ask("Number received")})
    print(f"  ✓ Delivery #{batch.batch_id} logged; "
          f"{len(ct.list_certificates(batch_id=batch.batch_id))} candidate(s) listed")
    pause()


def certificates(unclaimed: bool = False) -> None:
    bid = ask("Delivery # (blank = all)")
    rows = ct.list_certificates(batch_id=int(bid) if bid else None, unclaimed_only=unclaimed)
    show_table([("#", 5), ("Student", 10), ("Name", 22), ("Board", 18), ("Series", 12),
                ("Issued", 10), ("Method", 24), ("Collected by", 16)],
               [(c.certificate_id, c.student_id, c.full_name, c.exam_board, c.series,
                 c.issued_date, c.method, c.collected_by) for c in rows])
    pause()


def issue() -> None:
    cid = int(ask("Certificate #", required=True))
    method = pick("Method", list(ct.ISSUE_METHODS), default=ct.ISSUE_METHODS[0])
    ct.issue(cid, method=method, collected_by=ask("Collected by") or None,
             signature_ref=ask("Signature (e.g. issue sheet p.3)") or None)
    print("  ✓ Issued")


def retention() -> None:
    lines = [f"UNCLAIMED CERTIFICATES — RETENTION ({ct.RETENTION_MONTHS} months)", ""]
    for c, left in ct.retention_notices():
        state = "may now be destroyed/returned" if left < 0 else f"{left} day(s) left"
        lines.append(f"{c.student_id:<10} {(c.full_name or ''):<24} {c.exam_board:<18} "
                     f"{c.series:<14} keep until {c.retain_until}  {state}")
    save_text("\n".join(lines) + "\n", "certificate_retention.txt")


MENU = [("Deliveries", batches), ("Log a delivery", new_batch),
        ("Certificates", certificates), ("Unclaimed", lambda: certificates(True)),
        ("Issue a certificate", issue), ("Retention notices", retention)]


def run() -> None:
    run_menu("Certificates", MENU)
