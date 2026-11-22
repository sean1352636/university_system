"""Runs, previews and reports the selected bulk operation.

Split out of ``bulk_operations_views.py``, which re-exports every name here.
"""

from __future__ import annotations

from datetime import date as _date
from tkinter import ttk
import logging

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.sixth_form.domain.learners.bulk_operations import base as bulk_base
from education_system.systems.sixth_form.domain.learners.bulk_operations import ops_academic as bulk_ops_academic
from education_system.systems.sixth_form.domain.learners.bulk_operations import ops_attendance as bulk_ops_attendance
from education_system.systems.sixth_form.domain.learners.bulk_operations import ops_behaviour as bulk_ops_behaviour
from education_system.systems.sixth_form.domain.learners.bulk_operations import ops_comms as bulk_ops_comms
from education_system.systems.sixth_form.domain.learners.bulk_operations import ops_finance as bulk_ops_finance
from education_system.systems.sixth_form.domain.learners.bulk_operations import ops_records as bulk_ops_records
from education_system.systems.sixth_form.domain.learners.bulk_operations.base import BulkResult
from education_system.systems.sixth_form.domain.learners.bulk_operations.base import ValidationError

from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.view_common import (
    logger,
    _NO_STUDENTS_OPS,
    _today,
)
from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.dialogs import (
    _ResultDialog,
)


class RunnerMixin:
    """Runs, previews and reports the selected bulk operation."""

    # ── Run ───────────────────────────────────────────────────────
    def _run(self, *, _preview_dialog: bool = False) -> None:
        sids = self._selected_ids()
        dry = self.dry_var.get()
        op = self._op_key
        if op not in _NO_STUDENTS_OPS and not sids:
            messagebox.showinfo("Run", "Select at least one student.")
            return
        try:
            if op == "log_behaviour":
                r = bulk_ops_behaviour.bulk_log_behaviour(
                    sids,
                    entry_date=self.p_date.get().strip() or _today(),
                    entry_type=self.p_type.get(),
                    category=self.p_cat.get().strip(),
                    description=self.p_desc.get().strip(),
                    severity=self.p_sev.get() or None,
                    location=self.p_loc.get().strip() or None,
                    recorded_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "add_accommodation":
                r = bulk_ops_behaviour.bulk_add_accommodation(
                    sids,
                    name=self.p_name.get().strip(),
                    category=self.p_cat.get().strip() or "Exam Access",
                    description=self.p_desc.get().strip() or None,
                    status=self.p_status.get().strip() or "Active",
                    start_date=self.p_start.get().strip() or None,
                    end_date=self.p_end.get().strip() or None,
                    approved_by=self.p_appby.get().strip() or None,
                    approved_date=self.p_appdate.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "update_student":
                r = bulk_ops_behaviour.bulk_update_student(
                    sids,
                    field=self.p_field.get(),
                    value=self.p_value.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "message":
                if not dry and not messagebox.askyesno(
                        "Send", f"Send to {len(sids)} student(s)?"):
                    return
                r = bulk_ops_comms.bulk_message(
                    sids,
                    subject=self.p_subject.get().strip(),
                    body=self.p_body.get("1.0", "end").strip(),
                    channel=self.p_channel.get(),
                    category=self.p_msg_cat.get().strip() or "General",
                    priority=self.p_pri.get(),
                    status=self.p_status.get(),
                    dry_run=dry,
                )
            elif op == "archive_to_alumni":
                delete = self.p_delete.get()
                if not dry and delete and not messagebox.askyesno(
                        "Archive",
                        f"This will DELETE {len(sids)} student row(s). "
                        "Continue?"):
                    return
                r = bulk_ops_records.bulk_archive_to_alumni(
                    sids,
                    leaving_year=self.p_year.get().strip() or None,
                    leaving_date=self.p_date.get().strip() or None,
                    leaving_reason=self.p_reason.get() or None,
                    destination_type=self.p_dest.get(),
                    delete_students=delete,
                    dry_run=dry,
                )
            elif op == "mark_attendance":
                slot_id = self._slot_label_to_id.get(self.p_slot.get())
                if slot_id is None:
                    messagebox.showerror("Run", "Pick a slot.")
                    return
                minutes_raw = self.p_minutes.get().strip()
                minutes = int(minutes_raw) if minutes_raw else None
                r = bulk_ops_attendance.bulk_mark_attendance(
                    sids, slot_id=slot_id,
                    date=self.p_date.get().strip() or _today(),
                    status=self.p_status.get(),
                    minutes_late=minutes,
                    notes=self.p_notes.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "authorise_absences":
                r = bulk_ops_attendance.bulk_authorise_absences(
                    sids,
                    date_from=self.p_date_from.get().strip(),
                    date_to=self.p_date_to.get().strip() or _today(),
                    target_status=self.p_target.get(),
                    reason=self.p_reason.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "apply_lateness":
                slot_id = self._slot_label_to_id.get(self.p_slot.get())
                if slot_id is None:
                    messagebox.showerror("Run", "Pick a slot.")
                    return
                threshold_raw = self.p_threshold.get().strip()
                threshold = int(threshold_raw) if threshold_raw else None
                r = bulk_ops_attendance.bulk_apply_lateness(
                    sids, slot_id=slot_id,
                    date=self.p_date.get().strip() or _today(),
                    minutes_late=int(self.p_minutes.get().strip() or 0),
                    auto_log_behaviour_over=threshold,
                    behaviour_recorded_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "import_attendance_csv":
                path = self.p_csv.get().strip()
                if not path:
                    messagebox.showerror("Run", "Pick a CSV file.")
                    return
                r = bulk_ops_attendance.bulk_import_attendance_csv(path, dry_run=dry)
            elif op == "recalc_attendance":
                r = bulk_ops_attendance.bulk_recalc_attendance(
                    sids,
                    date_from=self.p_date_from.get().strip() or None,
                    date_to=self.p_date_to.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "flag_low_attendance":
                r = bulk_ops_attendance.bulk_flag_low_attendance(
                    sids,
                    threshold_pct=float(
                        self.p_threshold.get().strip() or "90"),
                    window_days=int(
                        self.p_window.get().strip() or "28"),
                    level=self.p_level.get(),
                    reason=(self.p_reason.get().strip()
                            or "Low overall attendance"),
                    raised_by=self.p_by.get().strip() or None,
                    skip_if_open_concern=bool(self.p_skip_open.get()),
                    dry_run=dry,
                )
            elif op == "signoff_register":
                picks = self.p_slots_lb.curselection()
                if not picks:
                    messagebox.showerror("Run", "Pick at least one slot.")
                    return
                slot_ids = [self._signoff_slot_map[str(i)] for i in picks]
                r = bulk_ops_attendance.bulk_signoff_register(
                    slot_ids,
                    date=self.p_date.get().strip() or _today(),
                    default_status=self.p_default.get(),
                    dry_run=dry,
                )
            elif op == "enrol":
                r = bulk_ops_academic.bulk_enrol(
                    sids,
                    academic_year=self.p_year.get().strip(),
                    year_group=int(self.p_yg.get() or "12"),
                    tutor_group=self.p_tutor.get().strip() or None,
                    start_date=self.p_start.get().strip() or None,
                    status=self.p_status.get(),
                    notes=self.p_notes.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "move_class_group":
                from_map = getattr(self, self.p_from._map_attr)
                to_map = getattr(self, self.p_to._map_attr)
                from_id = from_map.get(self.p_from.get())
                to_id = to_map.get(self.p_to.get())
                r = bulk_ops_academic.bulk_move_class_group(
                    sids, from_group_id=from_id, to_group_id=to_id,
                    dry_run=dry,
                )
            elif op == "assign_predicted_grades":
                fb = bool(self.p_from_baseline.get())
                r = bulk_ops_academic.bulk_assign_predicted_grades(
                    sids,
                    subject=self.p_subject.get(),
                    grade=(None if fb else
                            (self.p_grade.get() or None)),
                    from_baseline=fb,
                    confidence=self.p_conf.get(),
                    predicted_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "import_assessment_marks":
                path = self.p_csv.get().strip()
                if not path:
                    messagebox.showerror("Run", "Pick a CSV file.")
                    return
                r = bulk_ops_academic.bulk_import_assessment_marks(path, dry_run=dry)
            elif op == "recalc_grade_reports":
                r = bulk_ops_academic.bulk_recalc_grade_reports(sids, dry_run=dry)
            elif op == "export_progress_reports":
                out_dir = self.p_outdir.get().strip()
                if not out_dir:
                    messagebox.showerror("Run", "Pick an output dir.")
                    return
                r = bulk_ops_academic.bulk_export_progress_reports(
                    sids, output_dir=out_dir, dry_run=dry)
            elif op == "publish_report_cards":
                r = bulk_ops_academic.bulk_publish_report_cards(
                    sids,
                    period=self.p_period.get().strip(),
                    publish=bool(self.p_publish.get()),
                    published_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "apply_grade_boundaries":
                raw_ids = self.p_assn.get().strip()
                try:
                    ids = [int(t) for t in
                            raw_ids.replace(" ", ",").split(",") if t]
                except ValueError:
                    messagebox.showerror(
                        "Run", "Assignment ids must be integers.")
                    return
                def _n(w: ttk.Entry) -> int | None:
                    s = w.get().strip()
                    return int(s) if s else None
                r = bulk_ops_academic.bulk_apply_grade_boundaries(
                    ids,
                    a_star=_n(self.p_a_star), a=_n(self.p_a),
                    b=_n(self.p_b), c=_n(self.p_c),
                    d=_n(self.p_d), e=_n(self.p_e),
                    dry_run=dry,
                )
            elif op == "issue_detentions":
                r = bulk_ops_behaviour.bulk_issue_detentions(
                    sids,
                    date=self.p_date.get().strip() or _today(),
                    reason=self.p_reason.get().strip(),
                    duration_minutes=int(
                        self.p_duration.get().strip() or "30"),
                    room=self.p_room.get().strip() or None,
                    severity=self.p_severity.get(),
                    recorded_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "award_merits":
                r = bulk_ops_behaviour.bulk_award_merits(
                    sids,
                    date=self.p_date.get().strip() or _today(),
                    category=self.p_category.get(),
                    description=self.p_desc.get().strip(),
                    points=int(self.p_points.get().strip() or "5"),
                    recorded_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "escalate_behaviour":
                r = bulk_ops_behaviour.bulk_escalate_behaviour(
                    sids,
                    date=self.p_date.get().strip() or _today(),
                    reason=self.p_reason.get().strip(),
                    escalate_to=(self.p_to.get().strip()
                                  or "Senior Tutor"),
                    follow_up_date=self.p_followup.get().strip() or None,
                    recorded_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "safeguarding_flag":
                dsl = bool(self.p_dsl.get())
                r = bulk_ops_behaviour.bulk_safeguarding_flag(
                    sids,
                    concern_date=self.p_cdate.get().strip() or _today(),
                    reported_date=self.p_rdate.get().strip() or _today(),
                    concern_type=self.p_ctype.get(),
                    category=self.p_category.get(),
                    risk_level=self.p_risk.get(),
                    reported_by=self.p_by.get().strip(),
                    description=self.p_desc.get().strip(),
                    dsl_notified=dsl,
                    dsl_name=(self.p_dsl_name.get().strip()
                                if dsl else None) or None,
                    dry_run=dry,
                )
            elif op == "reset_behaviour_points":
                r = bulk_ops_behaviour.bulk_reset_behaviour_points(
                    sids,
                    date_from=self.p_date_from.get().strip(),
                    date_to=self.p_date_to.get().strip() or _today(),
                    reset_date=self.p_reset_date.get().strip() or _today(),
                    note=self.p_note.get().strip() or "Term reset",
                    recorded_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "send_sms":
                r = bulk_ops_comms.bulk_send_sms(
                    sids,
                    body=self.p_body.get("1.0", "end").strip(),
                    subject=self.p_subject.get().strip() or "SMS",
                    sender_staff_id=self.p_sender.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "send_letters":
                tid = self._template_map.get(self.p_template.get())
                if tid is None:
                    messagebox.showerror("Run", "Pick a template.")
                    return
                ctx: dict[str, str] = {}
                for pair in self.p_ctx.get().split(","):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        ctx[k.strip()] = v.strip()
                r = bulk_ops_comms.bulk_send_letters(
                    sids, template_id=tid,
                    extra_context=ctx, dry_run=dry,
                )
            elif op == "meeting_invites":
                eid = self._event_map.get(self.p_event.get())
                if eid is None:
                    messagebox.showerror("Run", "Pick an event.")
                    return
                r = bulk_ops_comms.bulk_meeting_invites(
                    sids, event_id=eid,
                    booking_link=self.p_link.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "ucas_reference_reminders":
                r = bulk_ops_comms.bulk_ucas_reference_reminders(
                    sids,
                    referee_email=self.p_referee.get().strip() or None,
                    deadline=self.p_deadline.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "password_reset_emails":
                r = bulk_ops_comms.bulk_password_reset_emails(
                    sids,
                    reset_url=self.p_url.get().strip() or None,
                    mfa_enrolment=bool(self.p_mfa.get()),
                    dry_run=dry,
                )
            elif op == "schedule_message":
                r = bulk_ops_comms.bulk_schedule_message(
                    sids,
                    subject=self.p_subject.get().strip(),
                    body=self.p_body.get("1.0", "end").strip(),
                    send_at=self.p_send_at.get().strip(),
                    channel=self.p_channel.get(),
                    category=self.p_msg_cat.get().strip() or "General",
                    priority=self.p_pri.get(),
                    dry_run=dry,
                )
            elif op == "bursary_award":
                r = bulk_ops_finance.bulk_bursary_award(
                    sids,
                    bursary_type=self.p_btype.get(),
                    amount_awarded=float(
                        self.p_amount.get().strip() or "0"),
                    academic_year=self.p_year.get().strip() or None,
                    eligibility_basis=(
                        self.p_basis.get().strip() or None),
                    decision_note=self.p_note.get().strip() or None,
                    assessed_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "raise_invoices":
                r = bulk_ops_finance.bulk_raise_invoices(
                    sids,
                    description=self.p_desc.get().strip(),
                    category=self.p_cat.get(),
                    amount=float(self.p_amount.get().strip() or "0"),
                    issued_date=self.p_issued.get().strip() or None,
                    due_date=self.p_due.get().strip() or None,
                    academic_year=self.p_year.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "fee_discount":
                r = bulk_ops_finance.bulk_fee_discount(
                    sids,
                    description=self.p_desc.get().strip(),
                    amount=float(self.p_amount.get().strip() or "0"),
                    category=self.p_cat.get(),
                    issued_date=self.p_issued.get().strip() or None,
                    academic_year=self.p_year.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "import_payments":
                path = self.p_csv.get().strip()
                if not path:
                    messagebox.showerror("Run", "Pick a CSV file.")
                    return
                r = bulk_ops_finance.bulk_import_payments(path, dry_run=dry)
            elif op == "financial_statements":
                out_dir = self.p_outdir.get().strip()
                if not out_dir:
                    messagebox.showerror("Run", "Pick an output dir.")
                    return
                r = bulk_ops_finance.bulk_financial_statements(
                    sids, output_dir=out_dir,
                    academic_year=self.p_year.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "exam_entries":
                fee_raw = self.p_fee.get().strip()
                fee = float(fee_raw) if fee_raw else None
                r = bulk_ops_records.bulk_exam_entries(
                    sids,
                    subject=self.p_subject.get(),
                    exam_board=self.p_board.get().strip(),
                    paper_code=self.p_code.get().strip(),
                    season=self.p_season.get(),
                    year=int(self.p_year.get().strip() or
                              str(_date.today().year)),
                    tier=(self.p_tier.get().strip() or None),
                    fee=fee,
                    candidate_no_prefix=(
                        self.p_prefix.get().strip() or None),
                    dry_run=dry,
                )
            elif op == "exam_access_arrangements":
                r = bulk_ops_records.bulk_exam_access_arrangements(
                    sids,
                    arrangement=self.p_arrangement.get(),
                    description=self.p_desc.get().strip() or None,
                    start_date=self.p_start.get().strip() or None,
                    end_date=self.p_end.get().strip() or None,
                    approved_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "exam_timetables":
                out_dir = self.p_outdir.get().strip()
                if not out_dir:
                    messagebox.showerror("Run", "Pick an output dir.")
                    return
                year_raw = self.p_year.get().strip()
                year = int(year_raw) if year_raw else None
                r = bulk_ops_records.bulk_export_exam_timetables(
                    sids, output_dir=out_dir, year=year,
                    season=self.p_season.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "ucas_export_predictions":
                path = self.p_outpath.get().strip()
                if not path:
                    messagebox.showerror("Run", "Pick an output path.")
                    return
                r = bulk_ops_records.bulk_ucas_export_predictions(
                    sids, output_path=path, dry_run=dry)
            elif op == "ucas_update_status":
                r = bulk_ops_records.bulk_ucas_update_status(
                    sids, status=self.p_status.get(), dry_run=dry)
            elif op == "promote_year_group":
                r = bulk_ops_records.bulk_promote_year_group(
                    sids,
                    new_academic_year=self.p_year.get().strip(),
                    bump_year_group=bool(self.p_bump.get()),
                    dry_run=dry,
                )
            elif op == "mark_leavers":
                r = bulk_ops_records.bulk_mark_leavers(
                    sids,
                    leaving_date=self.p_date.get().strip() or _today(),
                    leaving_reason=self.p_reason.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "reinstate_alumni":
                raw = self.p_ids.get().strip()
                try:
                    ids = [int(t) for t in
                            raw.replace(" ", ",").split(",") if t]
                except ValueError:
                    messagebox.showerror(
                        "Run", "Alumni ids must be integers.")
                    return
                r = bulk_ops_records.bulk_reinstate_alumni(ids, dry_run=dry)
            elif op == "gdpr_redact":
                raw = self.p_fields.get().strip()
                fields = ([f.strip() for f in raw.split(",")
                            if f.strip()] or None)
                r = bulk_ops_records.bulk_gdpr_redact(
                    sids, fields=fields, dry_run=dry)
            elif op == "export_student_records":
                path = self.p_outpath.get().strip()
                if not path:
                    messagebox.showerror("Run", "Pick an output path.")
                    return
                r = bulk_ops_records.bulk_export_student_records(
                    sids, output_path=path, dry_run=dry)
            elif op == "anonymise_alumni":
                raw = self.p_ids.get().strip()
                try:
                    ids = [int(t) for t in
                            raw.replace(" ", ",").split(",") if t]
                except ValueError:
                    messagebox.showerror(
                        "Run", "Alumni ids must be integers.")
                    return
                r = bulk_ops_records.bulk_anonymise_alumni(ids, dry_run=dry)
            elif op == "assign_inventory":
                r = bulk_ops_records.bulk_assign_inventory(
                    sids,
                    kind=self.p_kind.get(),
                    starting_number=int(
                        self.p_start.get().strip() or "1"),
                    prefix=self.p_prefix.get().strip(),
                    pad=int(self.p_pad.get().strip() or "4"),
                    assigned_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "upload_photos":
                zip_path = self.p_zip.get().strip()
                out_dir = self.p_outdir.get().strip()
                if not zip_path or not out_dir:
                    messagebox.showerror(
                        "Run", "ZIP and output dir required.")
                    return
                r = bulk_ops_records.bulk_upload_photos(
                    zip_path, output_dir=out_dir, dry_run=dry)
            elif op == "import_contacts_csv":
                path = self.p_csv.get().strip()
                if not path:
                    messagebox.showerror("Run", "Pick a CSV file.")
                    return
                r = bulk_ops_records.bulk_import_contacts_csv(path, dry_run=dry)
            elif op == "force_password_reset":
                r = bulk_ops_records.bulk_force_password_reset(
                    sids,
                    reason=self.p_reason.get().strip() or None,
                    flagged_by=self.p_by.get().strip() or None,
                    clear=bool(self.p_clear.get()),
                    dry_run=dry,
                )
            elif op == "undo_job":
                try:
                    jid = int(self.p_jid.get().strip())
                except ValueError:
                    messagebox.showerror(
                        "Run", "Job id must be an integer.")
                    return
                r = bulk_ops_records.bulk_undo_job(jid, dry_run=dry)
            elif op == "schedule_recurring":
                params: dict[str, str] = {}
                for pair in self.p_params.get().split(","):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        params[k.strip()] = v.strip()
                r = bulk_ops_records.bulk_schedule_recurring(
                    name=self.p_name.get().strip(),
                    operation=self.p_op.get(),
                    cron_expr=self.p_cron.get().strip(),
                    parameters=params,
                    next_run_at=self.p_next.get().strip() or None,
                    created_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "assign_mentors":
                sessions_raw = self.p_sessions.get().strip()
                sessions = int(sessions_raw) if sessions_raw else None
                r = bulk_ops_behaviour.bulk_assign_mentors(
                    sids,
                    mentor_id=self.p_mentor.get().strip(),
                    programme=self.p_programme.get(),
                    start_date=self.p_start.get().strip() or _today(),
                    frequency=self.p_frequency.get(),
                    coordinator=self.p_coord.get().strip() or None,
                    planned_end=self.p_planned.get().strip() or None,
                    sessions_planned=sessions,
                    dry_run=dry,
                )
            elif op == "mark_holiday":
                r = bulk_ops_attendance.bulk_mark_holiday(
                    sids,
                    date_from=self.p_date_from.get().strip(),
                    date_to=self.p_date_to.get().strip(),
                    reason=self.p_reason.get().strip()
                           or "Authorised holiday",
                    dry_run=dry,
                )
            elif op == "clear_attendance":
                only = self.p_only_status.get().strip() or None
                if not dry and not messagebox.askyesno(
                        "Clear attendance",
                        f"This will DELETE attendance rows for "
                        f"{len(sids)} student(s). Continue?"):
                    return
                r = bulk_ops_attendance.bulk_clear_attendance(
                    sids,
                    date_from=self.p_date_from.get().strip(),
                    date_to=self.p_date_to.get().strip(),
                    only_status=only,
                    dry_run=dry,
                )
            elif op == "late_to_unauth":
                over_raw = self.p_over.get().strip() or "15"
                try:
                    over = int(over_raw)
                except ValueError:
                    messagebox.showerror(
                        "Run", "Threshold minutes must be an integer.")
                    return
                r = bulk_ops_attendance.bulk_late_to_unauth(
                    sids,
                    date_from=self.p_date_from.get().strip(),
                    date_to=self.p_date_to.get().strip(),
                    over_minutes=over,
                    reason=self.p_reason.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "attendance_letters":
                try:
                    window = int(self.p_window.get().strip() or "28")
                    s1 = float(self.p_s1.get().strip() or "95")
                    s2 = float(self.p_s2.get().strip() or "90")
                    s3 = float(self.p_s3.get().strip() or "85")
                except ValueError:
                    messagebox.showerror(
                        "Run",
                        "Window and thresholds must be numeric.")
                    return
                tiers = (
                    (s1, "Stage 1"), (s2, "Stage 2"), (s3, "Stage 3"),
                )
                r = bulk_ops_attendance.bulk_attendance_letters(
                    sids,
                    window_days=window,
                    stages=tiers,
                    send=self.p_send.get(),
                    sender_staff_id=self.p_sender.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "punctuality_report":
                r = bulk_ops_attendance.bulk_punctuality_report(
                    sids,
                    date_from=self.p_date_from.get().strip(),
                    date_to=self.p_date_to.get().strip() or _today(),
                    sender_staff_id=self.p_sender.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "register_closure":
                picks = self.p_closure_slots_lb.curselection()
                if not picks:
                    messagebox.showerror(
                        "Run", "Pick at least one slot.")
                    return
                slot_ids = [self._closure_slot_map[str(i)] for i in picks]
                r = bulk_ops_attendance.bulk_register_closure(
                    slot_ids,
                    date_from=self.p_date_from.get().strip(),
                    date_to=self.p_date_to.get().strip(),
                    default_status=self.p_default.get(),
                    notes=self.p_notes.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "assign_subjects":
                picks = self.p_subjects_lb.curselection()
                subjects = [self.p_subjects_lb.get(i) for i in picks]
                if not subjects:
                    messagebox.showerror(
                        "Run", "Pick at least one subject.")
                    return
                r = bulk_ops_academic.bulk_assign_subjects(
                    sids, subjects=subjects,
                    overwrite=self.p_overwrite.get(),
                    dry_run=dry,
                )
            elif op == "withdraw_subjects":
                picks = self.p_subjects_lb.curselection()
                subjects = [self.p_subjects_lb.get(i) for i in picks]
                if not subjects:
                    messagebox.showerror(
                        "Run", "Pick at least one subject to withdraw.")
                    return
                r = bulk_ops_academic.bulk_withdraw_subjects(
                    sids, subjects=subjects, dry_run=dry,
                    effective_date=self.p_withdraw_date.get().strip() or None,
                    reason=self.p_withdraw_reason.get().strip() or None,
                    approved_by=self.p_withdraw_approver.get().strip() or None,
                )
            elif op == "set_teaching_set":
                target_label = self.p_set_target.get().strip()
                target_id = self._set_group_map.get(target_label)
                if target_id is None:
                    messagebox.showerror(
                        "Run", "Pick a target group.")
                    return
                r = bulk_ops_academic.bulk_set_teaching_set(
                    sids, target_group_id=target_id, dry_run=dry,
                )
            elif op == "import_timetable_csv":
                path = self.p_csv.get().strip()
                if not path:
                    messagebox.showerror("Run", "Pick a CSV file.")
                    return
                r = bulk_ops_academic.bulk_import_timetable_csv(
                    path, dry_run=dry,
                )
            else:
                messagebox.showerror("Run", f"Unknown operation {op!r}")
                return
        except ValidationError as e:
            bulk_base.log_event(logging.WARNING,
                            f"GUI validation error in {op!r}: {e}",
                            operation=op)
            messagebox.showerror("Run", str(e))
            return
        except Exception as e:  # noqa: BLE001
            bulk_base.log_event(logging.ERROR,
                            f"GUI run for {op!r} crashed: {e}",
                            operation=op, exc_info=True)
            logger.exception("Bulk-ops GUI run crashed")
            messagebox.showerror("Run", f"Unexpected error: {e}")
            return
        self._show_result(r, dry_run=dry,
                            _preview_dialog=_preview_dialog)

    def _preview(self) -> None:
        """Force dry-run + show a detailed diff dialog."""
        prev = self.dry_var.get()
        self.dry_var.set(True)
        try:
            self._run(_preview_dialog=True)
        finally:
            self.dry_var.set(prev)

    def _show_result(self, r: BulkResult, *, dry_run: bool,
                       _preview_dialog: bool = False) -> None:
        prefix = "[preview] " if dry_run else ""
        msg = (f"{prefix}{r.operation}: "
               f"{r.success_count}/{r.target_count} ok, "
               f"{r.failure_count} failed")
        if r.job_id:
            msg += f"  (job #{r.job_id})"
        self.result_var.set(msg)
        # In dry-run with no operation-specific diff, fall back to showing
        # the resolved target list so the user can sanity-check scope.
        diff_lines: list[str] = []
        if r.success_ids:
            diff_lines = list(r.success_ids[:50])
            if len(r.success_ids) > 50:
                diff_lines.append(
                    f"... +{len(r.success_ids) - 50} more")
        elif dry_run and r.target_count and not r.failures:
            diff_lines = [f"Would touch {r.target_count} target(s)."]

        if r.failures:
            preview = "\n".join(f"{sid}: {reason}"
                                  for sid, reason in r.failures[:10])
            if len(r.failures) > 10:
                preview += f"\n... +{len(r.failures) - 10} more"
            messagebox.showwarning(
                "Run complete (with failures)",
                f"{msg}\n\nFailures:\n{preview}")
        elif _preview_dialog or (dry_run and diff_lines):
            _ResultDialog(self.frame.winfo_toplevel(), msg, diff_lines)
        else:
            messagebox.showinfo("Run complete", msg)
