"""CLI flows for Sixth Form Admissions."""

from __future__ import annotations

import logging
from typing import Callable
from education_system.systems.sixth_form.interfaces.cli.admissions._common import (
    _pause,
    _run_submenu,
    _sub,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.analytics_cli import (
    analytics_flow,
    cohort_compare_flow,
    conversion_kpi_flow,
    export_csv_flow,
    export_summary_pdf_flow,
    forecast_flow,
    funnel_report_flow,
    import_csv_flow,
    live_analytics_flow,
    source_report_flow,
    subject_demand_flow,
    time_to_decision_flow,
    weekly_trend_flow,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.applicant_actions_cli import (
    applicant_actions_flow,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.applicant_records_cli import (
    archive_applicant_flow,
    list_archived_flow,
    restore_applicant_flow,
    delete_applicant_flow,
    edit_applicant,
    filter_applicants,
    list_all,
    list_open,
    new_applicant,
    preset_awaiting,
    preset_interviews_this_week,
    preset_offers_outstanding,
    stale_report,
    summary_flow,
    view_applicant,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.browse_cli import (
    activity_feed_flow,
    age_filter_flow,
    column_chooser_flow,
    duplicate_report_flow,
    quick_search_flow,
    saved_views_flow,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.bulk_cli import (
    bulk_add_note_flow,
    bulk_assign_interviewer_flow,
    bulk_follow_up_flow,
    bulk_reject_flow,
    bulk_set_source_flow,
    bulk_status_flow,
    email_list_flow,
    export_pdf_flow,
    gdpr_batch_export_flow,
    merge_duplicates_flow,
    print_list_flow,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.conversion_cli import (
    conversion_preview_flow,
    intake_log_flow,
    bulk_enrol_flow,
    convert_flow,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.decisions_cli import (
    defer_flow,
    reopen_flow,
    accept_offer_flow,
    decision_day_flow,
    decline_offer_flow,
    expiring_offers_flow,
    make_offer_flow,
    offers_flow,
    reference_chase_all_flow,
    reject_flow,
    set_status_flow,
    tasks_flow,
    waitlist_auto_promote_flow,
    waitlist_flow,
    withdraw_flow,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.interviews_cli import (
    bulk_schedule_flow,
    calendar_view_flow,
    cancel_interview_flow,
    detect_clashes_flow,
    export_all_ics_flow,
    export_ics_flow,
    interviews_agenda_flow,
    no_show_flow,
    no_show_report_flow,
    panel_view_flow,
    record_interview_flow,
    record_outcome_flow,
    reschedule_batch_flow,
    reschedule_flow,
    room_assignment_flow,
    schedule_interview_flow,
    send_reminders_flow,
    slot_capacity_flow,
)

logger = logging.getLogger(__name__)


_BROWSE_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List All",                 list_all),
    ("List Open",                list_open),
    ("Filter (sort/subject/…)",  filter_applicants),
    ("Preset: Awaiting decision", preset_awaiting),
    ("Preset: Offers outstanding", preset_offers_outstanding),
    ("Preset: Interviews this week", preset_interviews_this_week),
    ("Report: Overdue / stale",  stale_report),
]

_BROWSE_MENU += [
    ("Quick search",             quick_search_flow),
    ("Filter by age range",      age_filter_flow),
    ("Choose columns…",          column_chooser_flow),
    ("Saved views…",             saved_views_flow),
    ("Duplicate report",         duplicate_report_flow),
    ("Activity feed",            activity_feed_flow),
]

_BULK_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Bulk change status",       bulk_status_flow),
    ("Bulk reject (shared reason)", bulk_reject_flow),
    ("Bulk add note",            bulk_add_note_flow),
    ("Bulk set source",          bulk_set_source_flow),
    ("Bulk assign interviewer",  bulk_assign_interviewer_flow),
    ("Bulk toggle follow-up",    bulk_follow_up_flow),
    ("─" * 6,                    lambda: None),
    ("Copy email list",          email_list_flow),
    ("Export selection to PDF",  export_pdf_flow),
    ("Print applicant list",     print_list_flow),
    ("GDPR batch export",        gdpr_batch_export_flow),
    ("Merge duplicates",         merge_duplicates_flow),
]

_APPLICANT_MENU: list[tuple[str, Callable[[], None]]] = [
    ("View",                     view_applicant),
    ("New Applicant",            new_applicant),
    ("Edit Applicant",           edit_applicant),
    ("Actions… (per applicant)", applicant_actions_flow),
    ("─" * 6,                    lambda: None),
    ("Bulk & selection…",        lambda: _run_submenu("Bulk & Selection",
                                                       _BULK_MENU)),
    ("Delete Applicant",         delete_applicant_flow),
    ("Archive Applicant",        archive_applicant_flow),
    ("Archived Applicants",      list_archived_flow),
    ("Restore Archived Applicant", restore_applicant_flow),
    ("Profile, contacts, ID & sensitive…", _sub("applicant_profile_cli")),
]

_INTERVIEW_TOOLS_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Calendar (month)",         calendar_view_flow),
    ("Panel view (by interviewer)", panel_view_flow),
    ("Slot capacity",            slot_capacity_flow),
    ("Detect clashes",           detect_clashes_flow),
    ("─" * 6,                    lambda: None),
    ("Bulk schedule",            bulk_schedule_flow),
    ("Reschedule a whole day",   reschedule_batch_flow),
    ("Assign room",              room_assignment_flow),
    ("─" * 6,                    lambda: None),
    ("Send reminders",           send_reminders_flow),
    ("No-show report",           no_show_report_flow),
    ("Export all .ics",          export_all_ics_flow),
]

_INTERVIEW_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Agenda (with clashes/load)", interviews_agenda_flow),
    ("Schedule Interview",       schedule_interview_flow),
    ("Record outcome (+ score)", record_outcome_flow),
    ("Record interview notes",   record_interview_flow),
    ("Reschedule",               reschedule_flow),
    ("Cancel",                   cancel_interview_flow),
    ("No-show",                  no_show_flow),
    ("Export .ics",              export_ics_flow),
    ("─" * 6,                    lambda: None),
    ("More tools…",              lambda: _run_submenu("Interview Tools",
                                                      _INTERVIEW_TOOLS_MENU)),
    ("Slots, rooms & day sheet…", _sub("interview_slots_cli")),
]

_OFFER_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Make Offer (+ builder/expiry)", make_offer_flow),
    ("Accept Offer",             accept_offer_flow),
    ("Decline Offer",            decline_offer_flow),
    ("Reject (with reason)",     reject_flow),
    ("Withdraw",                 withdraw_flow),
    ("Change Status",            set_status_flow),
    ("─" * 6,                    lambda: None),
    ("Pending offers…",          offers_flow),
    ("Waitlist (rank/promote)",  waitlist_flow),
    ("Auto-promote top of waitlist", waitlist_auto_promote_flow),
    ("Decision day",             decision_day_flow),
    ("Expiring offers",          expiring_offers_flow),
    ("Chase all references",     reference_chase_all_flow),
    ("Reopen closed application", reopen_flow),
    ("Defer to a later intake",  defer_flow),
]


_CONVERSION_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Convert to Student (checklist)", convert_flow),
    ("Bulk enrol accepted",      bulk_enrol_flow),
    ("Conversion record",        _sub("applicant_extras_cli",
                                      "conversion_record_flow")),
    ("Conversion gates (preview)", conversion_preview_flow),
    ("Intake log (from secondary)", intake_log_flow),
]

_ANALYTICS_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Full dashboard",           analytics_flow),
    ("Conversion funnel",        funnel_report_flow),
    ("Source effectiveness",     source_report_flow),
    ("Applications by week",     weekly_trend_flow),
    ("Subject demand",           subject_demand_flow),
    ("Time to decision",         time_to_decision_flow),
    ("Conversion KPI",           conversion_kpi_flow),
    ("Cohort comparison",        cohort_compare_flow),
    ("Enrolment forecast",       forecast_flow),
    ("Live analytics (watch)",   live_analytics_flow),
    ("Export summary PDF",       export_summary_pdf_flow),
]

_DATA_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Summary",                  summary_flow),
    ("Analytics…",               lambda: _run_submenu("Analytics",
                                                       _ANALYTICS_MENU)),
    ("Tasks (worklist)",         tasks_flow),
    ("─" * 6,                    lambda: None),
    ("Export CSV",               export_csv_flow),
    ("Import CSV",               import_csv_flow),
    ("Insights (conversion, stages, reasons, places)…",
     _sub("insights_cli")),
]

_MAIN_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Browse & search…",   lambda: _run_submenu("Browse", _BROWSE_MENU)),
    ("Applicants…",        lambda: _run_submenu("Applicants",
                                                 _APPLICANT_MENU)),
    ("Interviews…",        lambda: _run_submenu("Interviews",
                                                 _INTERVIEW_MENU)),
    ("Offers & decisions…", lambda: _run_submenu("Offers & Decisions",
                                                  _OFFER_MENU)),
    ("Conversion…",        lambda: _run_submenu("Conversion",
                                                 _CONVERSION_MENU)),
    ("Reports & data…",    lambda: _run_submenu("Reports & Data",
                                                 _DATA_MENU)),
    ("─" * 6,              lambda: None),
    ("Programme choices…", _sub("applicant_extras_cli",
                                "programme_choices_flow")),
    ("Entry requirements & GCSEs…", _sub("entry_requirements_cli")),
    ("GCSE results day…",  _sub("results_day_cli")),
    ("Open events…",       _sub("open_events_cli")),
    ("Feeder-school references…", _sub("references_cli")),
    ("Online applications…", _sub("online_applications_cli")),
    ("Year 11 transition (CTF)…", _sub("year11_cli")),
    ("Cycles, places & criteria…", _sub("cycles_cli")),
    ("Data governance (erasure, retention)…", _sub("governance_cli")),
    ("DSL queue (safeguarding)…", _sub("governance_cli", "dsl_queue_menu")),
]


def run() -> None:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    p = access.current()
    if not p.can(access.ADMISSIONS) and p.can(access.SAFEGUARDING):
        # The DSL sees "Admissions" for the safeguarding queue only.
        from education_system.systems.sixth_form.interfaces.cli.admissions.governance_cli import (
            dsl_queue_menu,
        )
        dsl_queue_menu()
        return
    _run_submenu("Admissions", _MAIN_MENU)


def dispatch(label: str) -> bool:
    if label != "Admissions":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Admissions CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
