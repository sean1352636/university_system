"""The sixth form's scheduled jobs.

Each job calls the feature's own domain code — nothing here re-implements
a feature. A job returns a :class:`core.JobResult`; anything that went
wrong without stopping the job goes in ``errors`` (the run is recorded
as *Partial*), and an exception fails the run with its traceback.

E-mail and SMS always go through the sixth form outbox
(:mod:`messages.delivery`), which obeys the platform delivery mode
(inbox_only / sandbox / live) — no job sends mail any other way.
"""

from __future__ import annotations

import datetime as _dt
import logging

from education_system.systems.sixth_form.infrastructure.scheduler.core import (
    JobResult,
    JobSpec,
    register,
)

logger = logging.getLogger(__name__)

_CATEGORY_COMMS = "Communications"
_CATEGORY_ACADEMIC = "Teaching & Assessment"
_CATEGORY_ALERTS = "Monitoring & Alerts"
_CATEGORY_EXAMS = "Exams"
_CATEGORY_SYSTEM = "System"
_CATEGORY_ADMISSIONS = "Admissions"


# ── Communications ──────────────────────────────────────────────────

def publish_scheduled_announcements() -> JobResult:
    from education_system.systems.sixth_form.domains.communications.domain.announcements import (
        announcements as a,
    )
    published, expired_unseen = a.publish_due()
    expired = a.auto_expire()
    return JobResult(
        f"{len(published)} scheduled announcement(s) published"
        + (f" ({', '.join(x.title for x in published[:5])})" if published else "")
        + f"; {len(expired_unseen)} expired before publishing; "
          f"{expired} published announcement(s) expired")


def dispatch_notifications() -> JobResult:
    from education_system.systems.sixth_form.domains.communications.domain.notifications import (
        channel_delivery,
        notifications as n,
    )
    sent = n.send_due_scheduled()
    report = channel_delivery.deliver_pending()
    expired = n.auto_expire()
    return JobResult(
        f"{len(sent)} scheduled notification(s) sent to the in-app inbox; "
        f"{report.summary}; {expired} expired",
        errors=list(report.errors))


def send_scheduled_messages() -> JobResult:
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as m,
    )
    r = m.send_due_scheduled()
    return JobResult(
        f"{r.due} scheduled message(s) due: {r.sent} sent, {r.waiting} queued in "
        f"the outbox (held by the delivery mode / no SMS provider / retrying), "
        f"{r.failed} failed", errors=list(r.errors or []))


def process_message_outbox() -> JobResult:
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        delivery as d,
    )
    r = d.process_outbox()
    status = d.channel_status()
    return JobResult(
        f"{r.attempted} delivery attempt(s): {r.sent} sent, {r.failed} failed / "
        f"retrying, {r.waiting} waiting. " + " · ".join(status.lines()),
        errors=list(r.errors or []))


def run_recurring_bulk_jobs() -> JobResult:
    from education_system.systems.sixth_form.domain.learners.bulk_operations import (
        recurring,
    )
    r = recurring.run_due_schedules()
    return JobResult(r.summary, errors=r.errors)


def alumni_drip_campaigns() -> JobResult:
    from education_system.systems.sixth_form.domain.learners.alumni import messaging
    ticks = messaging.tick_drip()
    return JobResult(f"{len(ticks)} drip e-mail step(s) handed to the outbox")


def calendar_reminders() -> JobResult:
    from education_system.systems.sixth_form.domain.academics.calendar import (
        calendar_notifications as cn,
        calendar_recurrence as cr,
    )
    res = JobResult()
    series = cr.sweep(actor="system:scheduler")
    res.add(f"recurring events: {series.summary}")
    queued = cn.sweep_reminders()
    res.add(f"{queued} event reminder(s) queued")
    sent, failed = cn.send_queued()
    res.add(f"drain: {sent} sent, {failed} failed (others held in the outbox or "
            "addressed to an audience)")
    if failed:
        res.errors.append(f"{failed} calendar notification(s) failed — see "
                          "Calendar → Notifications")
    return res


def library_reminders() -> JobResult:
    from education_system.systems.sixth_form.domain.academics.library import (
        library_notifications as ln,
        library_reservations as lr,
    )
    expired = lr.expire_holds()
    due_soon = ln.run_due_soon_sweep()
    overdue = ln.run_overdue_sweep()
    return JobResult(f"{expired} hold(s) expired; {due_soon} due-soon and "
                     f"{overdue} overdue notice(s) sent to the outbox")


def search_subscriptions() -> JobResult:
    from education_system.systems.sixth_form.domain.learners.advanced_search import (
        history,
    )
    fired = history.poll_subscriptions()
    return JobResult(f"{len(fired)} saved-search subscription(s) had new results")


# ── Teaching & assessment ───────────────────────────────────────────

def coursework_deadlines() -> JobResult:
    from education_system.systems.sixth_form.domain.academics.assignments import (
        assignments_scheduling as sch,
        integrity,
    )
    res = JobResult()
    late = integrity.sweep_late_submissions()
    res.add(f"{late.get('marked_missing', 0)} overdue submission(s) marked Missing")
    for label, fn in (("reminders", sch.sweep_reminders),
                      ("chasers", sch.sweep_chasers)):
        r = fn()
        res.add(f"{label}: {r.message}")
        if r.failures:
            res.errors.append(f"{label}: {r.failures} failure(s)"
                              + (f" — {'; '.join(r.detail[:5])}" if r.detail else ""))
    return res


# ── Monitoring & alerts ─────────────────────────────────────────────

def early_warning_scan() -> JobResult:
    from education_system.systems.sixth_form.domain.assessment.early_warning import (
        early_warning as ew,
    )
    r = ew.scan(raised_by="Scheduled scan")
    by = ", ".join(f"{k}: {v}" for k, v in r.sources.items()) or "none"
    return JobResult(f"{r.created} alert(s) raised ({by}); "
                     f"{r.skipped_duplicates} already open", errors=list(r.errors))


def risk_scan() -> JobResult:
    from education_system.systems.sixth_form.domain.assessment.risk_analytics import (
        risk_analytics as ra,
    )
    errors: list[str] = []
    results = ra.scan_all(errors=errors)
    high = sum(1 for r in results if r.band in ("High", "Critical"))
    return JobResult(f"{len(results)} learner(s) assessed and snapshotted; "
                     f"{high} High/Critical", errors=errors)


def automation_rules() -> JobResult:
    from education_system.systems.sixth_form.domain.governance.automation_rules import (
        automation_rules as ar,
    )
    r = ar.run_rules()
    return JobResult(f"{r['rules_run']} rule(s) run, {r.get('matches', 0)} match(es), "
                     f"{r['new_actions']} new action(s)",
                     errors=list(r.get("errors") or []))


def attendance_safeguarding() -> JobResult:
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_safeguarding as sg,
    )
    r = sg.sweep(raised_by="Scheduled sweep")
    return JobResult(r.summary)


def register_nudges() -> JobResult:
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_nudges as nudges,
    )
    # notify=False: the nudge e-mails in that module go straight to SMTP,
    # bypassing the delivery mode, so the scheduled run records and
    # escalates nudges in-app only.
    r = nudges.sweep(notify=False)
    return JobResult(r.summary)


def punctuality_sanctions() -> JobResult:
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_punctuality as p,
    )
    r = p.sweep()
    return JobResult(f"{r.checked} learner(s) checked, {r.raised} sanction "
                     f"trigger(s) raised, {r.skipped_existing} already raised")


def evidence_enforcement() -> JobResult:
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_evidence as ev,
    )
    r = ev.enforce_overdue(actor="system:scheduler")
    return JobResult(f"{r.checked} overdue evidence requirement(s) checked, "
                     f"{r.recoded} mark(s) recoded", errors=list(r.failed))


# ── Exams ───────────────────────────────────────────────────────────

def exam_results_inbox() -> JobResult:
    from education_system.systems.sixth_form.domain.assessment.exams_office import (
        results_inbox,
    )
    r = results_inbox.process_inbox()
    return JobResult(r.summary, errors=r.errors)


def exam_results_release() -> JobResult:
    from education_system.systems.sixth_form.domain.assessment.exams_office import (
        results_day,
    )
    done = results_day.release_due(actor="system:scheduler")
    if not done:
        return JobResult("No results day is due for release")
    return JobResult("; ".join(
        f"{rel.season} {rel.year} {rel.exam_board or '(all boards)'}: "
        f"{comp} paper + {qual} qualification result(s) released"
        for rel, comp, qual in done))


# ── Admissions ──────────────────────────────────────────────────────
# Jobs run with nobody signed in, so admissions work names itself with
# _guard.system_actor (the domain refuses anonymous calls).

def _admissions_comms(func_name: str):
    """The admissions e-mail function *func_name*, or None when the
    admissions comms module (or that function) is not available."""
    try:
        from education_system.systems.sixth_form.domain.admissions import (
            admissions_comms,
        )
    except ImportError:
        return None
    return getattr(admissions_comms, func_name, None)


def admissions_offer_expiry() -> JobResult:
    from education_system.systems.sixth_form.domain.admissions import (
        _guard,
        cycles,
    )
    with _guard.system_actor("admissions.offer_expiry"):
        lapsed, errors = cycles.lapse_expired_offers()
        warn = cycles.offers_needing_warning()
    return JobResult(
        f"{len(lapsed)} unanswered offer(s) lapsed to Withdrawn "
        f"(\"{cycles.LAPSE_REASON}\")"
        + (f": {', '.join(lapsed[:10])}" if lapsed else "")
        + f"; {len(warn)} offer(s) expire within {cycles.WARNING_DAYS} days "
          "and are due a warning", errors=errors)


def admissions_offer_warnings() -> JobResult:
    from education_system.systems.sixth_form.domain.admissions import (
        _guard,
        cycles,
    )
    send = _admissions_comms("send_offer_expiry_warning")
    with _guard.system_actor("admissions.offer_warnings"):
        due = cycles.offers_needing_warning()
        if send is None:
            return JobResult(
                f"{len(due)} offer(s) due an expiry warning; not sent — the "
                "admissions e-mail module is not available")
        res = JobResult()
        sent = 0
        for a in due:
            try:
                send(a.applicant_id)
                cycles.record_warning_sent(a.applicant_id, a.offer_expiry)
                sent += 1
            except Exception as e:  # noqa: BLE001 - one applicant failing must not stop the rest
                logger.exception("Offer expiry warning for %s failed",
                                 a.applicant_id)
                res.errors.append(f"{a.applicant_id}: {type(e).__name__}: {e}")
    res.add(f"{sent} of {len(due)} offer expiry warning(s) handed to the outbox")
    return res


def admissions_reference_chase() -> JobResult:
    from education_system.systems.sixth_form.domain.admissions import (
        _guard,
        references,
    )
    send = _admissions_comms("send_reference_chase")
    with _guard.system_actor("admissions.reference_chase"):
        due = references.chase_list()
        if send is None:
            logger.info("Reference chase: admissions_comms.send_reference_chase "
                        "is not available; %d chase(s) skipped", len(due))
            return JobResult(
                f"{len(due)} overdue reference(s) due a chase; not sent — the "
                "admissions e-mail module is not available")
        res = JobResult()
        sent = 0
        today = _dt.date.today().isoformat()
        for ref in due:
            try:
                send(ref.reference_id)
                after = references.get_reference(ref.reference_id)
                # Record the chase if the e-mail step did not already.
                if after is not None and after.is_open and (
                        after.last_chased_on or "")[:10] != today:
                    references.chase(ref.reference_id)
                sent += 1
            except Exception as e:  # noqa: BLE001 - one reference failing must not stop the rest
                logger.exception("Reference chase #%s failed", ref.reference_id)
                res.errors.append(f"reference #{ref.reference_id}: "
                                  f"{type(e).__name__}: {e}")
    res.add(f"{sent} of {len(due)} overdue reference chase(s) sent")
    return res


def admissions_retention() -> JobResult:
    from education_system.systems.sixth_form.domain.admissions import (
        _guard,
        retention,
    )
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    with _guard.system_actor("admissions.retention",
                             (access.ADMISSIONS, access.GOVERNANCE)):
        r = retention.run(dry_run=False)
    return JobResult(r.summary, errors=list(r.errors))


def _admissions_staff_ids() -> list[str]:
    """Active staff whose job role carries the ``admissions`` capability
    (per-user grants live in auth.db and are not read here)."""
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    from education_system.systems.sixth_form.domain.staff import staff as _staff
    roles = {r for r, caps in access.JOB_ROLE_CAPABILITIES.items()
             if access.ADMISSIONS in caps}
    return [s.staff_id for s in _staff.list_staff(active_only=True)
            if s.role in roles]


def enrolment_visa_expiry() -> JobResult:
    """Tell admissions staff about visas that have expired or expire
    within the warning window. Reads only — no record is changed."""
    from education_system.systems.sixth_form.domain.admissions import _guard
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        course_changes,
        identity_checks,
    )
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    with _guard.system_actor("enrolment.visa_expiry"):
        days = course_changes.get_setting(course_changes.VISA_WARNING_DAYS)
        rows = identity_checks.visa_expiring(within_days=days)
    if not rows:
        return JobResult(f"No visa expired or expiring within {days} days")
    staff_ids = _admissions_staff_ids()
    if not staff_ids:
        return JobResult(
            f"{len(rows)} visa(s) expired or expiring within {days} days; "
            "not sent — no active staff with an admissions role",
            errors=["No admissions staff to tell about expiring visas"])
    lines = []
    for r in rows:
        s = _students.get_student(r.student_id)
        name = s.full_name if s else r.student_id
        when = (f"expired {-r.days_left} day(s) ago" if r.expired
                else f"expires in {r.days_left} day(s)")
        visa = f"visa ({r.visa_type})" if r.visa_type else "visa"
        lines.append(f"- {name} ({r.student_id}): {visa} {when}, on "
                     f"{r.visa_expiry}")
    body = ("These learners with a live enrolment have a visa that has "
            f"expired or expires within {days} days:\n\n"
            + "\n".join(lines)
            + "\n\nCheck their right to study and record the new visa in "
              "Enrolment → Identity checks. This message changes no record.")
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as _messages,
    )
    result = _messages.bulk_send(
        subject=f"Visa expiry: {len(rows)} learner(s) need a right-to-study "
                "check", body=body, staff_ids=staff_ids, channel="Email",
        category="Admissions", priority="High", tags="enrolment,visa")
    return JobResult(
        f"{len(rows)} visa(s) expired or expiring within {days} days; "
        f"message handed to the outbox for {len(result.created)} admissions "
        "staff", errors=[f"{who}: {why}" for who, why in result.failed])


def onboarding_overdue_chase() -> JobResult:
    """In-app reminders to the owners of overdue onboarding tasks."""
    from education_system.systems.sixth_form.domain.admissions import _guard
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        onboarding_jobs,
    )
    with _guard.system_actor("onboarding.chase"):
        r = onboarding_jobs.chase_overdue()
    return JobResult(r.summary, errors=list(r.errors))


def onboarding_resync() -> JobResult:
    """Tick onboarding tasks whose record (login, ID card, tutor group,
    timetable …) now exists; re-open record-ticked ones whose record went."""
    from education_system.systems.sixth_form.domain.admissions import _guard
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        onboarding_jobs,
    )
    with _guard.system_actor("onboarding.resync"):
        r = onboarding_jobs.nightly_resync()
    return JobResult(r.summary, errors=list(r.errors))


# ── System ──────────────────────────────────────────────────────────

def nightly_backup() -> JobResult:
    from education_system.systems.sixth_form.infrastructure.integrations import (
        db_backup,
    )
    results = db_backup.backup_all(label="nightly")
    if not results:
        return JobResult("No sixth form database file exists yet — nothing to back up")
    return JobResult("; ".join(
        f"{r.source.name} → {r.backup.name} ({r.backup.size_label}, integrity "
        f"{r.integrity}, {len(r.removed)} old nightly copy(ies) rotated out)"
        for r in results) + f" — in {db_backup.backup_dir()}")


def housekeeping_expiry() -> JobResult:
    from education_system.systems.sixth_form.domains.communications.domain.notices import (
        notices,
    )
    from education_system.systems.sixth_form.domains.communications.domain.document_hub import (
        document_hub,
    )
    from education_system.systems.sixth_form.domains.operations.domain.id_cards import id_cards
    from education_system.systems.sixth_form.domains.operations.domain.parking import parking
    res = JobResult()
    for label, fn in (("notice(s) archived", notices.auto_archive_expired),
                      ("document(s) archived", document_hub.auto_archive_expired),
                      ("parking permit(s) expired", parking.expire_lapsed),
                      ("ID card(s) expired", id_cards.expire_lapsed)):
        try:
            res.add(f"{fn()} {label}")
        except Exception as e:  # noqa: BLE001 - one area failing must not stop the rest
            logger.exception("Housekeeping step failed: %s", label)
            res.errors.append(f"{label}: {type(e).__name__}: {e}")
    return res


def scheduler_history_prune() -> JobResult:
    from education_system.systems.sixth_form.infrastructure.scheduler import core
    n = core.prune_history()
    return JobResult(f"{n} run record(s) older than {core.HISTORY_KEEP_DAYS} days removed")


# ── Registration ────────────────────────────────────────────────────

def register_builtin_jobs() -> None:
    specs = (
        JobSpec("announcements.publish", "Publish scheduled announcements",
                publish_scheduled_announcements, category=_CATEGORY_COMMS,
                interval_minutes=5,
                description="Scheduled announcements whose publish date has come "
                            "go live; expired ones are moved to Expired."),
        JobSpec("notifications.dispatch", "Send notifications",
                dispatch_notifications, category=_CATEGORY_COMMS, interval_minutes=5,
                description="Scheduled notifications are sent to the in-app inbox; "
                            "Email/SMS copies go through the outbox; Push is recorded "
                            "as unavailable (no provider) — in-app only."),
        JobSpec("messages.scheduled", "Send scheduled messages",
                send_scheduled_messages, category=_CATEGORY_COMMS, interval_minutes=5,
                description="Bulk 'schedule message' rows are handed to the outbox "
                            "at their send time."),
        JobSpec("messages.outbox", "Process the message outbox",
                process_message_outbox, category=_CATEGORY_COMMS, interval_minutes=5,
                description="Retries queued / failed e-mail and SMS deliveries with "
                            "back-off, under the platform delivery mode."),
        JobSpec("bulk.recurring", "Recurring bulk jobs", run_recurring_bulk_jobs,
                category=_CATEGORY_COMMS, interval_minutes=5, lease_minutes=120,
                description="Runs each enabled recurring bulk schedule when its cron "
                            "time arrives (Bulk Operations → Schedule recurring job)."),
        JobSpec("alumni.drip", "Alumni drip campaigns", alumni_drip_campaigns,
                category=_CATEGORY_COMMS, daily_at="08:00",
                description="Sends the next step of every active alumni drip "
                            "enrolment through the outbox."),
        JobSpec("calendar.reminders", "Calendar reminders", calendar_reminders,
                category=_CATEGORY_COMMS, daily_at="06:45",
                description="Materialises recurring events, queues event reminders "
                            "and drains addressed calendar notifications to the outbox."),
        JobSpec("library.reminders", "Library reminders", library_reminders,
                category=_CATEGORY_COMMS, daily_at="07:00",
                description="Expires uncollected holds and sends due-soon and "
                            "overdue loan notices."),
        JobSpec("search.subscriptions", "Saved-search subscriptions",
                search_subscriptions, category=_CATEGORY_COMMS, daily_at="06:00",
                description="Re-runs scheduled saved searches and notifies their "
                            "owners of new results."),
        JobSpec("coursework.deadlines", "Coursework deadlines", coursework_deadlines,
                category=_CATEGORY_ACADEMIC, daily_at="06:30",
                description="Marks overdue work Missing, sends deadline reminders and "
                            "escalating chasers."),
        JobSpec("early_warning.scan", "Early-warning scan", early_warning_scan,
                category=_CATEGORY_ALERTS, daily_at="02:30",
                description="Raises early-warning alerts from attendance, behaviour "
                            "and targets. A failed source is reported, not hidden."),
        JobSpec("risk.scan", "Risk analytics scan", risk_scan,
                category=_CATEGORY_ALERTS, daily_at="02:45",
                description="Assesses every active learner and stores a risk snapshot."),
        JobSpec("automation.rules", "Automation rules", automation_rules,
                category=_CATEGORY_ALERTS, daily_at="03:15",
                description="Evaluates enabled automation rules (each over its own "
                            "window_days) and raises worklist actions."),
        JobSpec("attendance.safeguarding", "Attendance safeguarding sweep",
                attendance_safeguarding, category=_CATEGORY_ALERTS, daily_at="16:30",
                description="Looks for unexplained-absence patterns and alerts the "
                            "safeguarding lead."),
        JobSpec("attendance.nudges", "Register nudges", register_nudges,
                category=_CATEGORY_ALERTS, daily_at="16:00",
                description="Raises / escalates nudges for unsubmitted registers and "
                            "clears submitted ones (in-app)."),
        JobSpec("attendance.punctuality", "Punctuality sanctions",
                punctuality_sanctions, category=_CATEGORY_ALERTS, daily_at="17:00",
                enabled=False,
                description="Raises lateness sanctions for learners past a threshold. "
                            "Off by default — turn on once the thresholds are agreed."),
        JobSpec("attendance.evidence", "Enforce overdue absence evidence",
                evidence_enforcement, category=_CATEGORY_ALERTS, daily_at="18:00",
                enabled=False,
                description="Recodes absences whose promised evidence never arrived. "
                            "Off by default — it changes attendance marks."),
        JobSpec("exams.results_inbox", "Import exam board results",
                exam_results_inbox, category=_CATEGORY_EXAMS, interval_minutes=15,
                description="Imports A2C / EDI / CSV results files dropped in the "
                            "results inbox, under the results-day embargo."),
        JobSpec("exams.release", "Release results at embargo time",
                exam_results_release, category=_CATEGORY_EXAMS, interval_minutes=5,
                description="Releases a scheduled results day once its embargo time "
                            "has passed (Exams Office → Results day)."),
        JobSpec("admissions.offer_expiry", "Lapse unanswered offers",
                admissions_offer_expiry, category=_CATEGORY_ADMISSIONS,
                daily_at="06:10", enabled=False,
                description="Offers past their expiry date with no answer are "
                            "withdrawn (reason: No response from applicant); "
                            "lists offers expiring within 3 days. Off by "
                            "default — it withdraws applicants."),
        JobSpec("admissions.offer_warnings", "Offer expiry warnings",
                admissions_offer_warnings, category=_CATEGORY_ADMISSIONS,
                daily_at="08:15",
                description="E-mails applicants whose offer expires within 3 "
                            "days, once per expiry date, through the outbox."),
        JobSpec("admissions.reference_chase", "Chase overdue references",
                admissions_reference_chase, category=_CATEGORY_ADMISSIONS,
                daily_at="08:30",
                description="Sends a chaser for each overdue school reference "
                            "not chased in the last 7 days."),
        JobSpec("admissions.retention", "Admissions retention policy",
                admissions_retention, category=_CATEGORY_ADMISSIONS,
                daily_at="03:45",
                description="Erases unsuccessful applications past the "
                            "retention period. Does nothing until the policy "
                            "is turned on (Admissions → Retention)."),
        JobSpec("enrolment.visa_expiry", "Visa expiry warnings",
                enrolment_visa_expiry, category=_CATEGORY_ADMISSIONS,
                interval_minutes=7 * 24 * 60,
                description="Weekly: e-mails admissions staff (through the "
                            "outbox) a list of learners with a live "
                            "enrolment whose visa has expired or expires "
                            "within 60 days (the enrolment setting). "
                            "Changes no record."),
        JobSpec("onboarding.chase", "Chase overdue onboarding tasks",
                onboarding_overdue_chase, category=_CATEGORY_ADMISSIONS,
                daily_at="08:45",
                description="Puts an in-app reminder (no e-mail) in the "
                            "inbox of each member of staff who owns overdue "
                            "onboarding tasks (task owner, else checklist "
                            "owner, else admissions staff); each checklist "
                            "at most once a week."),
        JobSpec("onboarding.resync", "Onboarding record check",
                onboarding_resync, category=_CATEGORY_ADMISSIONS,
                daily_at="02:40",
                description="Ticks open onboarding tasks whose record now "
                            "exists (login, ID card, tutor group, timetable, "
                            "contacts, bursary …) and re-opens record-ticked "
                            "tasks whose record has gone. Hand-evidenced "
                            "tasks are never changed."),
        JobSpec("backup.nightly", "Nightly database backup", nightly_backup,
                category=_CATEGORY_SYSTEM, daily_at="01:30", lease_minutes=120,
                description="Verified backup of every sixth form database to the "
                            "system backup folder; old nightly copies rotate out."),
        JobSpec("housekeeping.expiry", "Expire lapsed items", housekeeping_expiry,
                category=_CATEGORY_SYSTEM, daily_at="00:15",
                description="Archives expired notices and documents; expires lapsed "
                            "parking permits and ID cards."),
        JobSpec("scheduler.prune", "Prune job history", scheduler_history_prune,
                category=_CATEGORY_SYSTEM, daily_at="00:30",
                description="Removes scheduled-job history older than 90 days."),
    )
    for spec in specs:
        register(spec)
