"""
Safeguarding — interactive CLI.

Wired to the service-layer managers in
``student_affairs.safeguarding.services.*``, which read/write the central
``student_records.db`` (table ``safeguarding_submissions`` and siblings) —
the same database the Safeguarding GUI (``safeguarding.gui.app``) uses.
Anything created here is visible in the GUI and vice-versa.

Covers the areas the GUI staff console exposes: case management (list /
create / view / lifecycle / assign / note / action / close), submissions &
triage, the mandatory-reporting queue, reviews / SLA / escalation, the DSL
notification digest, SAR bundle export + retention purge, and leadership
analytics.

The module carries its own role-based permission model
(``safeguarding.permissions``). Privileged operations (close, assign, export,
purge, mark-reported) are gated with ``require(...)`` and skipped with a clear
message when the current user's role lacks the permission. The current user is
resolved via the module's own ``_get_current_user`` (EDU_AUTH_* env / global
auth), falling back to the ``auth`` object passed by the launcher.
"""

from __future__ import annotations

import os
from typing import Optional

from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.analysis import (
    analyse_text,
)
from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.auth import (
    _get_current_user,
)
from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.db import (
    init_db,
)
from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.permissions import (
    require,
)
from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.services.analytics import (
    incident_heatmap,
    leadership_stats,
)
from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.services.cases import (
    OUTCOME_CODES,
    _LIFECYCLE_STATES,
    add_action_item,
    add_case_note,
    assign_case,
    close_case,
    due_reviews,
    export_cases_csv,
    list_action_items,
    list_assignments,
    list_case_notes,
    list_referrals,
    schedule_review,
    set_lifecycle_state,
)
from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.services.compliance import (
    acknowledge_mandatory_report,
    list_mandatory_cases,
)
from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.services.notifications import (
    daily_dsl_digest,
    list_notifications,
    stuck_case_alerts,
)
from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.services.oncall import (
    add_oncall_window,
    get_oncall_dsl,
)
from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.services.retention import (
    generate_sar_bundle,
    purge_due_records,
)
from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.services.submissions import (
    fetch_submissions,
    fetch_user_submissions,
    get_submission,
    resolve_content,
    save_submission,
    update_submission_status,
)


# --------------------------------------------------------------------------- #
# Small input helpers
# --------------------------------------------------------------------------- #
def _prompt(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or default


def _prompt_int(text: str, *, allow_blank: bool = True) -> Optional[int]:
    while True:
        raw = input(f"{text}: ").strip()
        if not raw:
            if allow_blank:
                return None
            print("A value is required.")
            continue
        try:
            return int(raw)
        except ValueError:
            print("Please enter a whole number.")


def _pause() -> None:
    input("\nPress Enter to continue...")


def _header(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def _current_user(auth) -> dict:
    """Resolve the acting user dict (with role/permissions).

    Prefers the module's own resolver (EDU_AUTH_* env vars / global auth),
    falling back to the ``auth`` object handed in by the launcher, then to a
    plain staff-role stub for standalone dev use."""
    try:
        user = _get_current_user()
        if user:
            return user
    except Exception:
        pass
    raw = getattr(auth, "current_user", None)
    if isinstance(raw, dict) and raw:
        u = dict(raw)
        u.setdefault("username", u.get("name") or "cli-user")
        u.setdefault("role", "staff")
        u.setdefault("full_name", u.get("username"))
        return u
    return {"username": "cli-user", "role": "staff", "full_name": "CLI User"}


def _username(user: dict) -> str:
    return user.get("username") or user.get("full_name") or "cli-user"


def _require(user: dict, permission: str) -> bool:
    """Return True if the user may perform *permission*, else print why not."""
    if require(user, permission):
        return True
    print(f"\n✗ Your role ('{user.get('role') or '?'}') lacks permission "
          f"'{permission}'.")
    return False


# --------------------------------------------------------------------------- #
# Shared list renderer
# --------------------------------------------------------------------------- #
def _print_case_rows(rows) -> None:
    print(f"\n{'ID':<5}{'Subject':<22}{'Submitted':<18}{'Sev':<10}{'Status':<12}Categories")
    print("-" * 90)
    for r in rows:
        cats = r[5] or ""
        print(f"{r[0]:<5}{(r[1] or r[2] or '')[:21]:<22}"
              f"{(r[3] or '')[:17]:<18}"
              f"{(r[4] or '')[:9]:<10}"
              f"{(r[6] or '')[:11]:<12}"
              f"{cats[:28]}")


# --------------------------------------------------------------------------- #
# 1. Case Management
# --------------------------------------------------------------------------- #
def _list_cases() -> None:
    status = _prompt("Status filter (Pending/Closed/..., blank = all)")
    severity = _prompt("Severity filter (CRITICAL/HIGH/MEDIUM/LOW, blank = all)")
    lifecycle = _prompt("Lifecycle filter (Open/Triage/Action/Monitoring/Closed, blank = all)")
    rows = fetch_submissions(
        status_filter=status or None,
        severity_filter=severity or None,
        lifecycle_filter=lifecycle or None,
    )
    if not rows:
        print("\nNo cases match.")
        return
    _print_case_rows(rows)


def _create_case(auth) -> None:
    user = _current_user(auth)
    if not _require(user, "submit"):
        return
    content = _prompt("Concern text / disclosure")
    if not content:
        print("Concern text is required.")
        return
    location = _prompt("Location / campus (optional)")
    department = _prompt("Department / school (optional)")
    try:
        matches, overall = analyse_text(content)
        categories = {cat: info["snippets"] for cat, info in matches.items()}
        sid = save_submission(
            user,
            content,
            overall,
            categories,
            case_location=location or None,
            case_department=department or None,
        )
        cat_names = ", ".join(categories.keys()) or "(none detected)"
        print(f"\n✓ Logged case #{sid} — severity {overall}; categories: {cat_names}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _view_case(auth) -> None:
    user = _current_user(auth)
    case_id = _prompt_int("Case id", allow_blank=False)
    case = get_submission(case_id)
    if not case:
        print(f"\nNo case with id {case_id}.")
        return
    print(f"\n--- Case {case_id} ---")
    for key in ("full_name", "username", "role", "submitted_at", "severity",
                "categories", "status", "lifecycle_state", "risk_score",
                "assigned_to", "sla_due_at", "sla_breached", "outcome_code",
                "closure_reason", "case_location", "case_department",
                "mandatory_reporting", "mandatory_status", "retention_until",
                "next_review_at", "purged"):
        print(f"  {key:<20}: {case.get(key) if case.get(key) is not None else '-'}")
    if _require(user, "view_case"):
        try:
            content, transcription = resolve_content(case_id)
            print("\n  Content:")
            print(f"    {(content or '(empty)')[:500]}")
            if transcription:
                print(f"  Transcription:\n    {transcription[:300]}")
        except Exception as e:
            print(f"  (could not resolve content: {e})")
    notes = list_case_notes(case_id)
    print(f"\n  Notes ({len(notes)}):")
    for author, note, created in notes:
        print(f"    [{(created or '')[:19]}] {author}: {(note or '')[:60]}")
    actions = list_action_items(case_id)
    print(f"\n  Action items ({len(actions)}):")
    for a in actions:
        print(f"    #{a[0]} [{a[4]}] {(a[1] or '')[:40]} (owner={a[2] or '-'}, due={a[3] or '-'})")
    referrals = list_referrals(case_id)
    print(f"\n  Referrals ({len(referrals)}):")
    for ref in referrals:
        print(f"    #{ref[0]} {ref[1]} ref={ref[3] or '-'} status={ref[5]}")
    assignments = list_assignments(case_id)
    print(f"\n  Assignment history ({len(assignments)}):")
    for asg in assignments:
        print(f"    [{(asg[2] or '')[:19]}] {asg[0]} (by {asg[1]})")


def _update_lifecycle(auth) -> None:
    user = _current_user(auth)
    if not _require(user, "add_action"):
        return
    case_id = _prompt_int("Case id", allow_blank=False)
    print(f"  States: {', '.join(_LIFECYCLE_STATES)}")
    state = _prompt("New lifecycle state")
    if not state:
        print("State is required.")
        return
    try:
        set_lifecycle_state(case_id, state, actor=_username(user))
        print(f"\n✓ Case {case_id} lifecycle → {state}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _assign_case(auth) -> None:
    user = _current_user(auth)
    if not _require(user, "assign"):
        return
    case_id = _prompt_int("Case id", allow_blank=False)
    oncall = get_oncall_dsl()
    default_assignee = oncall.get("username") if oncall else ""
    assignee = _prompt("Assign to (username)", default=default_assignee)
    if not assignee:
        print("Assignee is required.")
        return
    note = _prompt("Note (optional)")
    try:
        assign_case(case_id, assignee, assigned_by=_username(user), note=note)
        print(f"\n✓ Case {case_id} assigned to {assignee}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _add_note(auth) -> None:
    user = _current_user(auth)
    if not _require(user, "add_note"):
        return
    case_id = _prompt_int("Case id", allow_blank=False)
    note = _prompt("Note text")
    if not note:
        print("Note text is required.")
        return
    try:
        add_case_note(case_id, _username(user), note)
        print(f"\n✓ Note added to case {case_id}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _add_action(auth) -> None:
    user = _current_user(auth)
    if not _require(user, "add_action"):
        return
    case_id = _prompt_int("Case id", allow_blank=False)
    title = _prompt("Action title")
    if not title:
        print("Action title is required.")
        return
    owner = _prompt("Owner (optional)")
    due = _prompt("Due date (YYYY-MM-DD, optional)")
    try:
        add_action_item(case_id, title, owner or None, due or None)
        print(f"\n✓ Action item added to case {case_id}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _close_case(auth) -> None:
    user = _current_user(auth)
    if not _require(user, "close"):
        return
    case_id = _prompt_int("Case id", allow_blank=False)
    print("\n  Outcome codes:")
    for code, desc in OUTCOME_CODES:
        print(f"    {code:<12}{desc}")
    outcome = _prompt("Outcome code")
    reason = _prompt("Closure reason")
    if not outcome or not reason:
        print("Outcome code and reason are required.")
        return
    try:
        close_case(case_id, outcome, reason, _username(user))
        print(f"\n✓ Closed case {case_id} ({outcome}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _case_menu(auth) -> None:
    while True:
        _header("Case Management")
        print("[1] List cases")
        print("[2] Create / log a case")
        print("[3] View case (+ notes / actions / referrals)")
        print("[4] Update lifecycle state")
        print("[5] Assign / escalate to DSL")
        print("[6] Add case note")
        print("[7] Add action item")
        print("[8] Close case")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_cases()
        elif choice == "2":
            _create_case(auth)
        elif choice == "3":
            _view_case(auth)
        elif choice == "4":
            _update_lifecycle(auth)
        elif choice == "5":
            _assign_case(auth)
        elif choice == "6":
            _add_note(auth)
        elif choice == "7":
            _add_action(auth)
        elif choice == "8":
            _close_case(auth)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 2. Submissions & Triage
# --------------------------------------------------------------------------- #
def _triage_queue() -> None:
    lifecycle = _prompt("Lifecycle filter (blank = all, e.g. Triage)")
    rows = fetch_submissions(lifecycle_filter=lifecycle or None)
    if not rows:
        print("\nTriage queue is empty.")
        return
    _print_case_rows(rows)


def _user_submissions() -> None:
    username = _prompt("Reporter username")
    if not username:
        print("Username is required.")
        return
    rows = fetch_user_submissions(username)
    if not rows:
        print(f"\nNo submissions for {username}.")
        return
    print(f"\n{'ID':<5}{'Submitted':<22}{'Severity':<12}Status")
    print("-" * 50)
    for r in rows:
        print(f"{r[0]:<5}{(r[1] or '')[:21]:<22}{(r[2] or '')[:11]:<12}{r[3] or ''}")


def _update_status(auth) -> None:
    user = _current_user(auth)
    if not _require(user, "view_case"):
        return
    sub_id = _prompt_int("Submission id", allow_blank=False)
    status = _prompt("New status (Pending/In Review/Actioned/Closed)")
    if not status:
        print("Status is required.")
        return
    note = _prompt("Review note (optional)")
    try:
        update_submission_status(sub_id, status, _username(user), note)
        print(f"\n✓ Submission {sub_id} → {status}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _triage_menu(auth) -> None:
    while True:
        _header("Submissions & Triage")
        print("[1] Triage queue (risk-sorted)")
        print("[2] Submissions by reporter")
        print("[3] Update submission status")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _triage_queue()
        elif choice == "2":
            _user_submissions()
        elif choice == "3":
            _update_status(auth)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 3. Mandatory Reporting Queue
# --------------------------------------------------------------------------- #
def _list_mandatory() -> None:
    status = _prompt("Status filter (Pending/Reported, blank = all)")
    rows = list_mandatory_cases(status=status or None)
    if not rows:
        print("\nNo mandatory-reporting cases.")
        return
    print(f"\n{'ID':<5}{'Subject':<24}{'Severity':<12}{'Status':<12}Reported")
    print("-" * 66)
    for r in rows:
        print(f"{r[0]:<5}{(r[1] or r[2] or '')[:23]:<24}"
              f"{(r[3] or '')[:11]:<12}"
              f"{(r[4] or 'Pending')[:11]:<12}"
              f"{(r[5] or '-')[:19]}")


def _mark_reported(auth) -> None:
    user = _current_user(auth)
    if not _require(user, "close"):
        return
    case_id = _prompt_int("Case id", allow_blank=False)
    reference = _prompt("External reference (optional)")
    try:
        acknowledge_mandatory_report(case_id, _username(user), external_reference=reference)
        print(f"\n✓ Case {case_id} marked as reported to the statutory agency.")
    except Exception as e:
        print(f"\n✗ {e}")


def _mandatory_menu(auth) -> None:
    while True:
        _header("Mandatory Reporting Queue")
        print("[1] List mandatory-reporting cases")
        print("[2] Mark case as reported")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_mandatory()
        elif choice == "2":
            _mark_reported(auth)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 4. Reviews, SLA & Escalation
# --------------------------------------------------------------------------- #
def _due_reviews() -> None:
    within = _prompt_int("Include reviews due within N days (blank = now)") or 0
    rows = due_reviews(within_days=within)
    if not rows:
        print("\nNo reviews due.")
        return
    print(f"\n{'ID':<5}{'Subject':<24}{'Severity':<10}{'Next review':<22}Lifecycle")
    print("-" * 74)
    for r in rows:
        print(f"{r[0]:<5}{(r[1] or r[2] or '')[:23]:<24}"
              f"{(r[3] or '')[:9]:<10}"
              f"{(r[4] or '')[:21]:<22}"
              f"{r[5] or ''}")


def _schedule_review(auth) -> None:
    user = _current_user(auth)
    if not _require(user, "add_action"):
        return
    case_id = _prompt_int("Case id", allow_blank=False)
    days = _prompt_int("Review in N days", allow_blank=False)
    try:
        schedule_review(case_id, days, actor=_username(user))
        print(f"\n✓ Review for case {case_id} scheduled in {days} day(s).")
    except Exception as e:
        print(f"\n✗ {e}")


def _sla_alerts(auth) -> None:
    user = _current_user(auth)
    try:
        sent = stuck_case_alerts(actor=_username(user))
        print(f"\n✓ Refreshed SLA flags; queued {sent} breach alert(s).")
    except Exception as e:
        print(f"\n✗ {e}")


def _show_oncall() -> None:
    oncall = get_oncall_dsl()
    if not oncall:
        print("\nNo DSL is currently on call.")
        return
    print(f"\nOn-call DSL: {oncall.get('full_name') or '-'} ({oncall.get('username')})")


def _add_oncall() -> None:
    username = _prompt("DSL username")
    if not username:
        print("Username is required.")
        return
    full_name = _prompt("Full name (optional)")
    starts = _prompt("Starts at (YYYY-MM-DD HH:MM)")
    ends = _prompt("Ends at (YYYY-MM-DD HH:MM)")
    if not starts or not ends:
        print("Start and end are required.")
        return
    try:
        add_oncall_window(username, full_name or None, starts, ends)
        print(f"\n✓ Added on-call window for {username}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _reviews_menu(auth) -> None:
    while True:
        _header("Reviews, SLA & Escalation")
        print("[1] Cases due for review")
        print("[2] Schedule a review")
        print("[3] Queue SLA-breach alerts")
        print("[4] Show current on-call DSL")
        print("[5] Add on-call window")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _due_reviews()
        elif choice == "2":
            _schedule_review(auth)
        elif choice == "3":
            _sla_alerts(auth)
        elif choice == "4":
            _show_oncall()
        elif choice == "5":
            _add_oncall()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 5. Notifications & DSL Digest
# --------------------------------------------------------------------------- #
def _generate_digest(auth) -> None:
    user = _current_user(auth)
    try:
        body = daily_dsl_digest(actor=_username(user))
        print("\n" + body)
    except Exception as e:
        print(f"\n✗ {e}")


def _list_notifications() -> None:
    case_id = _prompt_int("Filter by case id (blank = all recent)")
    rows = list_notifications(case_id=case_id)
    if not rows:
        print("\nNo notifications.")
        return
    print(f"\n{'ID':<5}{'Case':<6}{'Channel':<9}{'Recipient':<26}{'Status':<9}Queued")
    print("-" * 78)
    for r in rows:
        print(f"{r[0]:<5}{str(r[1] or '-'):<6}{(r[2] or '')[:8]:<9}"
              f"{(r[3] or '')[:25]:<26}"
              f"{(r[7] or '')[:8]:<9}"
              f"{(r[5] or '')[:19]}")


def _notifications_menu(auth) -> None:
    while True:
        _header("Notifications & DSL Digest")
        print("[1] Generate daily DSL digest")
        print("[2] List notifications")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _generate_digest(auth)
        elif choice == "2":
            _list_notifications()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 6. SAR Export & Retention
# --------------------------------------------------------------------------- #
def _sar_export(auth) -> None:
    user = _current_user(auth)
    if not _require(user, "export"):
        return
    subject = _prompt("Subject username")
    if not subject:
        print("Subject username is required.")
        return
    out_dir = _prompt("Output directory", default=os.path.join(os.getcwd(), "safeguarding_exports"))
    try:
        path, n = generate_sar_bundle(subject, out_dir, _username(user))
        print(f"\n✓ SAR bundle written: {path} ({n} case(s)).")
    except Exception as e:
        print(f"\n✗ {e}")


def _export_csv(auth) -> None:
    user = _current_user(auth)
    if not _require(user, "export"):
        return
    out_path = _prompt("Output CSV path",
                       default=os.path.join(os.getcwd(), "safeguarding_cases.csv"))
    since = _prompt("Since (YYYY-MM-DD, optional)")
    until = _prompt("Until (YYYY-MM-DD, optional)")
    try:
        path, n = export_cases_csv(
            out_path, since=since or None, until=until or None, actor=_username(user))
        print(f"\n✓ Exported {n} case(s) to {path}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _retention_purge(auth) -> None:
    user = _current_user(auth)
    if not _require(user, "export"):
        return
    dry = _prompt("Dry-run? (Y/n)", default="Y").lower() not in ("n", "no")
    try:
        count, ids = purge_due_records(actor=_username(user), dry_run=dry)
        verb = "would be purged" if dry else "purged"
        print(f"\n✓ {count} record(s) {verb}. Ids: {ids}")
    except Exception as e:
        print(f"\n✗ {e}")


def _retention_menu(auth) -> None:
    while True:
        _header("SAR Export & Retention")
        print("[1] Export SAR bundle for a subject")
        print("[2] Export cases CSV")
        print("[3] Retention purge (dry-run / commit)")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _sar_export(auth)
        elif choice == "2":
            _export_csv(auth)
        elif choice == "3":
            _retention_purge(auth)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 7. Analytics & Leadership Stats
# --------------------------------------------------------------------------- #
def _leadership_stats() -> None:
    days = _prompt_int("Period in days (default 90)") or 90
    stats = leadership_stats(days=days)
    print(f"\n--- Leadership stats (last {stats['period_days']} days) ---")
    print(f"  Total cases        : {stats['total']}")
    print(f"  By severity        : {stats['by_severity']}")
    print(f"  By lifecycle       : {stats['by_lifecycle']}")
    print(f"  By outcome         : {stats['by_outcome']}")
    print(f"  SLA breaches       : {stats['sla_breaches']}")
    print(f"  Mandatory flags    : {stats['mandatory_flags']}")
    print(f"  Avg days to close  : {stats['avg_days_to_close']}")


def _heatmap() -> None:
    days = _prompt_int("Window in days (default 90)") or 90
    grid = incident_heatmap(days=days)
    if not grid:
        print("\nNo incidents in window.")
        return
    print(f"\n--- Incident heatmap (last {days} days) ---")
    for dept, sev_counts in grid.items():
        print(f"  {dept}: {sev_counts}")


def _analytics_menu(auth) -> None:
    while True:
        _header("Analytics & Leadership Stats")
        print("[1] Leadership stats")
        print("[2] Incident heatmap by department")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _leadership_stats()
        elif choice == "2":
            _heatmap()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_safeguarding_menu(auth) -> None:
    """Run the Safeguarding CLI loop."""
    try:
        init_db()
    except Exception:
        pass  # tables may already exist / be created lazily
    while True:
        print("\n" + "=" * 50)
        print("            SAFEGUARDING")
        print("=" * 50)
        print("1. Case Management")
        print("2. Submissions & Triage")
        print("3. Mandatory Reporting Queue")
        print("4. Reviews, SLA & Escalation")
        print("5. Notifications & DSL Digest")
        print("6. SAR Export & Retention")
        print("7. Analytics & Leadership Stats")
        print("8. Return to Main Menu")
        print("=" * 50)

        try:
            choice = input("\nEnter your choice (1-8): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return

        try:
            if choice == "1":
                _case_menu(auth)
            elif choice == "2":
                _triage_menu(auth)
            elif choice == "3":
                _mandatory_menu(auth)
            elif choice == "4":
                _reviews_menu(auth)
            elif choice == "5":
                _notifications_menu(auth)
            elif choice == "6":
                _retention_menu(auth)
            elif choice == "7":
                _analytics_menu(auth)
            elif choice == "8":
                print("Returning to main menu...")
                return
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            print("\nCancelled.")
        except Exception as e:  # keep the menu resilient
            print(f"❌ Error: {e}")


__all__ = ["run_safeguarding_menu"]
