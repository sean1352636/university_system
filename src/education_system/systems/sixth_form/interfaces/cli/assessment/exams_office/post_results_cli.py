"""CLI: post-results services."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.assessment.exams_office import (
    post_results as pr,
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
    yes,
)


def list_all() -> None:
    season, year = series()
    rows = pr.list_requests(season=season, year=year)
    show_table([("#", 4), ("Student", 10), ("Code", 10), ("Service", 28), ("Deadline", 10),
                ("Consent", 7), ("Status", 16), ("Was", 4), ("Outcome", 24), ("Now", 4)],
               [(r.request_id, r.student_id, r.code, r.service,
                 (r.deadline or "") + ("!" if r.overdue else ""),
                 "Yes" if r.consent_obtained else "", r.status, r.original_grade,
                 r.outcome, r.new_grade) for r in rows])
    pause()


def new() -> None:
    from education_system.systems.sixth_form.domain.assessment.exam_results import (
        exam_results as _results,
    )
    from education_system.systems.sixth_form.domain.assessment.exams_office import (
        results_day,
    )
    season, year = series()
    sid = ask("Student ID", required=True)
    options: dict[str, tuple[str, int]] = {}
    for r in _results.list_results(student_id=sid, season=season, year=year,
                                   released_only=False):
        options[f"{r.paper_code} ({r.result.grade})"] = ("result_id", r.result.result_id)
    for q in results_day.list_qualification_results(student_id=sid, season=season,
                                                    year=year, released_only=False):
        options[f"{q.entry_code} overall ({q.grade})"] = ("qual_result_id", q.qual_result_id)
    if not options:
        print("  No results for that student in the series.")
        return
    key, rid = options[pick("Result", list(options))]
    service = pick("Service", list(pr.SERVICES))
    consent = yes("Candidate's written consent received")
    req = pr.create_request({key: rid, "service": service, "consent_obtained": consent,
                             "consent_ref": ask("Consent form reference") if consent else "",
                             "fee": ask("Fee (blank = fee list)"),
                             "fee_paid_by": ask("Fee paid by")})
    print(f"  ✓ Request #{req.request_id}; deadline {req.deadline or 'unknown (set results day)'}")
    pause()


def consent() -> None:
    rid = int(ask("Request #", required=True))
    pr.record_consent(rid, consent_ref=ask("Consent form reference") or None)
    print("  ✓ Consent recorded")


def submit() -> None:
    rid = int(ask("Request #", required=True))
    pr.submit_request(rid, board_reference=ask("Board reference") or None)
    print("  ✓ Submitted")


def outcome() -> None:
    rid = int(ask("Request #", required=True))
    out = pick("Outcome", list(pr.OUTCOMES))
    req = pr.record_outcome(rid, outcome=out, new_grade=ask("New grade (if changed)") or None,
                            new_marks=ask("New marks") or None)
    print(f"  ✓ Recorded ({req.outcome}); fee refunded: {'yes' if req.fee_refunded else 'no'}")
    pause()


def withdraw() -> None:
    rid = int(ask("Request #", required=True))
    if yes("Withdraw it"):
        pr.withdraw_request(rid, reason=ask("Reason") or None)
        print("  ✓ Withdrawn")


def fees() -> None:
    b = board()
    season, year = series()
    service = pick("Service", list(pr.SERVICES))
    pr.set_fee(b, season, year, service, ask("Fee (£)", required=True))
    print("  ✓ Fee saved")


def deadlines() -> None:
    season, year = series()
    lines = [f"POST-RESULTS DEADLINES — {season} {year}", ""]
    for b, service, days, when in pr.deadlines_table(season, year):
        lines.append(f"{b:<18} {service:<36} +{days:<3} {when or '(no results day set)'}")
    save_text("\n".join(lines) + "\n", f"post_results_{season}{year}.txt")


MENU = [("List requests", list_all), ("New request", new), ("Record consent", consent),
        ("Submit to board", submit), ("Record outcome", outcome), ("Withdraw", withdraw),
        ("Set fee", fees), ("Deadlines", deadlines)]


def run() -> None:
    run_menu("Post-Results Services", MENU)
