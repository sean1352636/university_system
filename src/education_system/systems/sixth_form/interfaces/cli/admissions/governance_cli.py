"""Admissions CLI: data governance — GDPR erasure requests (two-person),
the erasure log, the retention policy, archived records — and the DSL
admissions queue.

A safeguarding-only user (no admissions permission) who opens
"Admissions" is sent straight to :func:`dsl_queue_menu` by
``admissions_cli.run``.
"""

from __future__ import annotations

import json

from education_system.systems.sixth_form.domain.admissions import (
    applicant_details as details,
    record_safety,
    references as refs,
    retention,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.interfaces.cli.admissions._common import (
    _UserAbort,
    _attempt,
    _can,
    _input,
    _pause,
    _pick_applicant,
    _pick_from,
    _run_submenu,
    _yes,
)


# ── Erasure (two-person rule) ──────────────────────────────────────

def _req_line(r: record_safety.ErasureRequest) -> str:
    return (f"#{r.request_id:<4} {r.applicant_id:<10} [{r.status:<8}] "
            f"asked {r.requested_at[:16]} by {r.requested_by or '—'}: "
            f"{r.reason}"
            + (f" — {r.decided_by} {r.decided_at[:16] if r.decided_at else ''}"
               f" {r.decision_note or ''}" if r.decided_by else ""))


def list_requests_flow() -> None:
    st = _pick_from("Show", ["Pending", "All"] + [
        s for s in record_safety.REQUEST_STATUSES if s != "Pending"],
        default="Pending")
    rows = record_safety.list_erasure_requests(
        status=None if st == "All" else st)
    print(f"\n═══ Erasure Requests ({st}) ═══")
    for r in rows:
        print("  " + _req_line(r))
    if not rows:
        print("  (none)")
    _pause()


def request_erasure_flow() -> None:
    a = _pick_applicant()
    reason = _input("Reason (e.g. the data subject's request)",
                    allow_empty=False)
    ok, r = _attempt(record_safety.request_erasure, a.applicant_id,
                     reason=reason)
    if ok:
        print(f"  ✓ Request #{r.request_id} recorded — someone else with the "
              "governance permission must approve it.")
    _pause()


def _pick_pending() -> record_safety.ErasureRequest:
    rows = record_safety.list_erasure_requests(status="Pending")
    if not rows:
        print("    No pending erasure requests.")
        raise _UserAbort
    labels = [_req_line(r) for r in rows]
    return rows[labels.index(_pick_from("Request", labels))]


def approve_flow() -> None:
    if not record_safety.can_approve_erasure():
        print("  ✗ Approving an erasure needs the governance permission.")
        _pause()
        return
    r = _pick_pending()
    print("  Approving erases the applicant and every related record and "
          "file now. This cannot be undone.")
    if _input("  Type 'ERASE' to approve", default="") != "ERASE":
        print("  Cancelled.")
        return
    ok, done = _attempt(record_safety.approve_erasure, r.request_id,
                        note=_input("Note") or None)
    if ok:
        print("  ✓ Approved and erased." if done else
              "  ✓ Approved (the applicant was already gone).")
    _pause()


def reject_flow() -> None:
    if not record_safety.can_approve_erasure():
        print("  ✗ Deciding an erasure needs the governance permission.")
        _pause()
        return
    r = _pick_pending()
    ok, _ = _attempt(record_safety.reject_erasure, r.request_id,
                     note=_input("Reason for rejecting", allow_empty=False))
    if ok:
        print("  ✓ Rejected (noted on the applicant's timeline)")
    _pause()


def erasure_log_flow() -> None:
    print("\n═══ Erasure Log ═══")
    rows = record_safety.erasure_log()
    for e in rows:
        try:
            counts = json.loads(e.get("rows_json") or "{}")
        except ValueError:
            counts = {}
        total = sum(v for v in counts.values() if isinstance(v, int))
        print(f"  {e['erased_at'][:16]}  {e['applicant_id']:<10} requested by "
              f"{e.get('requested_by') or '—'}, approved by "
              f"{e.get('approved_by') or '—'}  ({total} row(s)) — "
              f"{e.get('reason') or ''}")
    if not rows:
        print("  (nothing erased)")
    _pause()


ERASURE_MENU = [
    ("Erasure requests", list_requests_flow),
    ("Request erasure of an applicant", request_erasure_flow),
    ("Approve a request (second person, erases)", approve_flow),
    ("Reject a request", reject_flow),
    ("Erasure log", erasure_log_flow),
]


def erasure_menu() -> None:
    _run_submenu("Admissions — GDPR Erasure (two-person)", [
        e for e in ERASURE_MENU
        if _can(access.ADMISSIONS) or e[1] in (list_requests_flow,
                                                approve_flow, reject_flow,
                                                erasure_log_flow)])


# ── Retention policy ───────────────────────────────────────────────

def policy_flow() -> None:
    p = retention.get_policy()
    print("\n═══ Retention Policy ═══")
    print(f"  {'ON' if p.enabled else 'OFF'} — {p.text}")
    if p.enabled_by:
        print(f"  enabled by {p.enabled_by} {p.enabled_at or ''}")
    if p.updated_by:
        print(f"  last changed by {p.updated_by} {p.updated_at or ''}")
    if not _can(access.GOVERNANCE):
        print("  (changing it needs the governance permission)")
        _pause()
        return
    if _yes("\n  Change it?"):
        enabled = _yes("Policy on?", default="y" if p.enabled else "n")
        months = _input("Months to keep", default=str(p.months))
        statuses = []
        for st in retention.ELIGIBLE_STATUSES:
            if _yes(f"  Applies to {st}?",
                    default="y" if st in p.statuses else "n"):
                statuses.append(st)
        ok, p2 = _attempt(retention.set_policy, enabled=enabled,
                          months=int(months) if months.isdigit() else months,
                          statuses=statuses)
        if ok:
            print(f"  ✓ {'ON' if p2.enabled else 'OFF'} — {p2.text}")
    _pause()


def candidates_flow() -> None:
    rows = retention.candidates()
    print("\n═══ Due for Erasure Under the Policy ═══")
    for c in rows:
        print(f"  {c.applicant_id:<10} {c.name[:24]:<24} [{c.status}] "
              f"{c.intake_year or '—'}{' archived' if c.archived else ''}  "
              f"clock from {c.clock_from} → due {c.due_on}")
    if not rows:
        print("  (none)")
    _pause()


def run_flow() -> None:
    ok, preview = _attempt(retention.run, dry_run=True)
    if not ok:
        _pause()
        return
    print(f"\n  Dry run: {preview.summary}")
    if not preview.candidates:
        _pause()
        return
    if not _can(access.GOVERNANCE):
        print("  (a real run needs the governance permission)")
        _pause()
        return
    if preview.enabled and _input(
            "  Type 'ERASE' to erase them now", default="") == "ERASE":
        ok, res = _attempt(retention.run, dry_run=False)
        if ok:
            print(f"  ✓ {res.summary}")
            for e in res.errors:
                print(f"  ✗ {e}")
    _pause()


def run_history_flow() -> None:
    rows = retention.run_history()
    print("\n═══ Retention Runs ═══")
    for r in rows:
        print(f"  {r['at'][:16]}  {r.get('run_by') or 'scheduler':<14} "
              f"{'dry run' if r['dry_run'] else 'RUN':<8} candidates "
              f"{r['candidates']:>4}  erased {r['erased']:>4}"
              + ("  (errors)" if r.get("errors_json") else ""))
    if not rows:
        print("  (none)")
    _pause()


# ── DSL queue (safeguarding) ───────────────────────────────────────

def dsl_queue_flow() -> None:
    print("\n═══ DSL Admissions Queue ═══")
    ok, rows = _attempt(details.dsl_queue)
    if not ok:
        _pause()
        return
    for d in rows:
        print(f"  {d.applicant_id:<10} {d.name[:24]:<24} [{d.status}] "
              f"{d.previous_school or ''}")
        for why in d.reasons:
            print(f"      • {why}")
    if not rows:
        print("  (nobody waiting)")
    elif _yes("\n  Read the safeguarding handover for one?"):
        labels = [f"{d.applicant_id} {d.name}" for d in rows]
        aid = _pick_from("Applicant", labels).split()[0]
        view = details.get_sensitive(aid)
        print(f"\n  {aid}: {view.visible.get('safeguarding') or '(none recorded)'}")
        if view.received_from:
            print(f"  received from {view.received_from}")
        if _yes("  Update the safeguarding handover text?"):
            text = _input("Text (blank clears)",
                          default=view.visible.get("safeguarding") or "")
            frm = _input("Received from",
                         default=view.received_from or "") or None
            ok, _ = _attempt(details.set_sensitive, aid, "safeguarding",
                             text or None, received_from=frm)
            if ok:
                print("  ✓ Saved (the timeline records only that it changed)")
    _pause()


def dsl_flagged_flow() -> None:
    ids = refs.dsl_flagged_applicants()
    print("\n  Applicants whose referee asked for DSL contact: "
          + (", ".join(ids) or "none"))
    _pause()


def dsl_queue_menu() -> None:
    _run_submenu("Admissions — DSL Queue", [
        ("DSL queue (referee flags + handovers)", dsl_queue_flow),
        ("Referee DSL-contact flags only", dsl_flagged_flow),
    ])


# ── Archived ───────────────────────────────────────────────────────

def archived_flow() -> None:
    from education_system.systems.sixth_form.interfaces.cli.admissions.applicant_records_cli import (
        list_archived_flow,
    )
    list_archived_flow()


MENU = [
    ("GDPR erasure requests…", erasure_menu),
    ("─" * 6, lambda: None),
    ("Retention policy", policy_flow),
    ("Applications due under the policy", candidates_flow),
    ("Run the policy (dry run first)", run_flow),
    ("Retention run history", run_history_flow),
    ("─" * 6, lambda: None),
    ("Archived applicants", archived_flow),
    ("DSL queue (safeguarding)", dsl_queue_menu),
]


def run() -> None:
    _run_submenu("Admissions Data Governance", MENU)

