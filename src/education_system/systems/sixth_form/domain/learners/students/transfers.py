"""Onward transfer of a sixth form student to another system.

:func:`mark_transferred` is the leaving route for a learner handed over to
the university, an FE college or an apprenticeship (the withdrawal route
is :func:`students.withdraw_student`); :func:`list_incomplete_transfers`
finds the ones whose announcement did not land. Moved out of
``students.py`` so the record module stays under the size limit.

The record functions are reached through the module (``_s.get_student``)
rather than imported by name, so a test that rebinds them on
``students`` redirects these calls too.
"""

from __future__ import annotations

import datetime as _dt
import logging

from education_system.systems.sixth_form.domain.learners.students import students as _s

logger = logging.getLogger(__name__)


def mark_transferred(student_id: str,
                      *, moved_by: str | None = None) -> _s.Student:
    """Mark a sixth-form student as transferred to another system.

    Composite, idempotent-ish operation:

      1. Updates the student row's ``status`` to ``'Left'``.
      2. Removes the ``sixth_form`` membership from the shared-auth
         account and revokes live sessions. The account itself stays
         active with its MFA and credentials intact — it is the person,
         who may hold other roles and who keeps one identity across a
         change of education phase.
      3. Anchors the canonical cross-system journey, records the
         ``sixth_form -> <destination>`` transition on it, and — when the
         destination is this university — publishes the handover onto the
         durable bus for the admissions intake to pick up.
      4. Sends an email to the sixth-form admin inbox via the
         ``student_transferred_to_university`` template, naming the
         student and quoting their id.

    Each step logs progress and failure individually. The auth and
    email steps are best-effort: failures are logged but do not block
    the status update or each other, so a successful import in the
    university system can never be left half-applied.

    **Safe to call again.** Completion is recorded in ``transferred_at``,
    not in ``status``, and the announcement carries a deterministic
    idempotency key. A call that failed part-way leaves ``transferred_at``
    unset and can simply be repeated; a call that already succeeded
    re-announces into a no-op. Use :func:`list_incomplete_transfers` to
    find students left in that state.

    Needs ``students.manage`` or ``admissions``; a drainer or job with
    nobody signed in runs it inside ``_guard.system_actor``.
    """
    _s._require_writer("transferring students", lifecycle=True)
    _s.init_db()
    student = _s.get_student(student_id)
    if student is None:
        raise _s.ValidationError(f"No student with id {student_id}")

    # Has *this transfer* already completed? Keyed on ``transferred_at``,
    # never on ``status``: 'Left' is also what a withdrawal and a completed
    # course leave behind, so it cannot distinguish "already announced"
    # from "gone for some other reason". It used to gate the announcement,
    # which meant a failed publish stranded the student — the status was
    # already 'Left', so the retry skipped the very step that had failed
    # and they vanished from the sixth form without reaching the
    # university. The announcement is now always attempted and is
    # idempotent on the bus; only the non-idempotent email is gated.
    already_transferred = student.transfer_complete

    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        leaving as _leaving,
    )
    _leaving.check_allowed()   # before anything changes

    # 1) Flip status to Left — independent of any side-effects below.
    with _s._connect() as conn:
        conn.execute(
            "UPDATE students SET status = 'Left' WHERE student_id = ?",
            (student_id,),
        )
        conn.commit()
    logger.info(
        "Marked student %s (%s) as Left (transferred)",
        student_id, student.full_name,
    )
    if student.status != "Left":
        _s.record_history(student_id, "Status", student.status, "Left",
                       changed_by=moved_by, note="Transferred onward")
    if not student.leaving_date:
        _s._set_leaving(student, _dt.date.today().isoformat(),
                     "Transferred onward", moved_by)

    # 1a) Close the local enrolments: a Year 13 leaving in the summer term
    #     completes, anyone else is withdrawn (ILR 2, transferred to
    #     another provider) so their learning aims end.
    closed = _leaving.learner_left(
        student_id, leaving_date=student.leaving_date
        or _dt.date.today().isoformat(),
        reason_code=_leaving.TRANSFERRED_REASON,
        detail="Transferred onward")
    for line in closed.lines():
        _s.record_history(student_id, "Enrolment", None, None,
                          changed_by=moved_by, note=line)

    # 2) End the sixth-form membership. Not the account — shared auth means
    #    the account is the person, who may hold other roles entirely.
    _s._revoke_sixth_form_access(student_id)

    # 2a) Close the account down once nothing is left on it, and take
    #     any parent logins that existed only for this learner with it.
    _s.disable_leaver_login(student_id)
    _s.disable_orphaned_parent_logins(student_id)
    _s._close_sixth_form_enrolment(student_id, moved_by)

    # 2b) Register the canonical cross-system identity and route the
    #     leaver: a progression event onto the durable bus when they are
    #     coming to this university, an ``external`` transition when they
    #     are not. Always attempted — the announcement is idempotent, so a
    #     repeat call is a no-op when it previously succeeded and a genuine
    #     retry when it did not.
    announced = _publish_progression(student, moved_by)

    # 2c) Stamp completion only on a successful announcement. This is what
    #     makes the operation retryable: a failure leaves transferred_at
    #     unset, so the student shows up in list_incomplete_transfers() and
    #     the next call redoes the work.
    if announced and not already_transferred:
        with _s._connect() as conn:
            conn.execute(
                "UPDATE students SET transferred_at = datetime('now') "
                "WHERE student_id = ?",
                (student_id,),
            )
            conn.commit()

    # 3) Notify the sixth-form admin inbox — only on the first completed
    #    transfer, since the email is the one step that is not idempotent.
    if already_transferred:
        logger.info(
            "Transfer for %s already completed at %s — skipping duplicate "
            "notification email", student_id, student.transferred_at,
        )
    elif not announced:
        logger.warning(
            "Not sending a transfer notification for %s — the announcement "
            "failed, so there is nothing to notify anyone about yet",
            student_id,
        )
    else:
        try:
            from education_system.systems.sixth_form.domains.communications.domain.messages import (
                email_templates,
            )
            admin_email = _s._sixthform_admin_email()
            context = {
                "student_id":     student.student_id,
                "full_name":      student.full_name,
                "first_name":     student.first_name,
                "last_name":      student.last_name,
                "date_of_birth":  student.date_of_birth or "—",
                "transferred_at": _dt.datetime.utcnow().strftime(
                    "%Y-%m-%d %H:%M UTC"),
                "moved_by":       (moved_by or "university system").strip()
                                  or "university system",
            }
            email_templates.send_from_template(
                "student_transferred_to_university",
                context,
                to_name="Sixth Form Admin",
                to_address=admin_email,
                student_id=student.student_id,
            )
            logger.info(
                "Transfer notification email queued for %s to %s",
                student_id, admin_email,
            )
        except Exception:
            logger.exception(
                "Transfer notification email failed for %s "
                "(student row was still marked Left)", student_id,
            )

    # Return the refreshed Student row so callers can see the new
    # status and transferred_at without an extra fetch.
    out = _s.get_student(student_id)
    assert out is not None
    return out


def list_incomplete_transfers() -> list[_s.Student]:
    """Students marked Left whose transfer never completed.

    A row appears here when :func:`mark_transferred` flipped the status
    but the announcement failed — the student has gone from the sixth-form
    workflow without reaching anywhere. Calling ``mark_transferred`` again
    for each one retries the announcement; it is safe whether the earlier
    attempt failed before or after the bus write.

    Rows predating the ``transferred_at`` column also surface here, since
    their marker is NULL. That is the honest answer — nothing recorded
    whether their announcement landed — and re-running them is harmless.
    """
    _s.init_db()
    with _s._connect() as conn:
        rows = conn.execute(
            "SELECT * FROM students WHERE status = 'Left' "
            "AND transferred_at IS NULL ORDER BY student_id"
        ).fetchall()
    return [_s._row_to_student(r) for r in rows]


def _publish_progression(student, moved_by: str | None) -> None:
    """Best-effort: register the canonical journey, then route the leaver.

    A ``student.progression.completed`` event is published for the
    university only when that is where the learner is actually going —
    see :func:`university_handover.resolve`. A leaver whose Firm choice
    is an institution this platform does not run gets a transition
    recorded against ``external`` instead, so the journey says where they
    went without announcing an arrival nobody is expecting.

    Requires name + DOB to anchor the canonical identity; if the
    sixth-form record is missing a DOB we skip the bus (the status
    flip / email still apply) rather than create an unmatchable journey.

    Either route anchors the canonical journey and records the hop on it
    (idempotently — this function is re-entered on every retry). Only the
    home route also publishes; ``external`` has no consumer to publish to.

    Returns True only when the learner was actually announced — either
    published to the university or recorded as having gone elsewhere.
    The caller stamps ``transferred_at`` on that answer, so a False here
    leaves the transfer visibly unfinished and retryable rather than
    silently swallowed.
    """
    if not (student.first_name and student.last_name
            and student.date_of_birth):
        logger.warning(
            "Cannot announce transfer for %s — needs name + DOB to anchor "
            "a canonical identity. The status flip and login deactivation "
            "still apply; the transfer stays incomplete and retryable.",
            student.student_id)
        return False
    try:
        from education_system.platform.cross_system import identity_service
        from education_system.platform.integrations.external import cross_system_bus
        from education_system.systems.sixth_form.domain.progression import (
            university_handover,
        )
        journey_id = identity_service.get_or_create_journey(
            first_name=student.first_name,
            last_name=student.last_name,
            date_of_birth=student.date_of_birth,
            system="sixth_form", student_id=student.student_id)
        # Only a Firm choice at this university is an arrival here. An
        # Insurance choice, a declined offer or a place elsewhere used to
        # publish all the same, creating an applicant in a university the
        # learner never accepted.
        destination = university_handover.resolve(student)
        journey = identity_service.get(journey_id) or {}
        _pk_col, uni_id_col = identity_service.SYSTEM_SLOTS[
            university_handover.DESTINATION_SYSTEM]
        already_admitted = journey.get(uni_id_col)

        if not destination.is_home:
            if already_admitted:
                # A completed admission outranks the UCAS record: the
                # university's import picker fills this slot before calling
                # us, and a learner demonstrably enrolled here did not go
                # somewhere else, whatever their choices say.
                logger.info(
                    "Firm choice for %s names %s, but they are already "
                    "university student %s — publishing as normal",
                    student.student_id,
                    destination.institution or "another institution",
                    already_admitted)
            else:
                identity_service.record_transition_once(
                    journey_id, from_system="sixth_form",
                    to_system=destination.system,
                    reason=destination.reason, actor_user_id=None)
                logger.info(
                    "Sixth-form leaver %s recorded as %s (%s) — no "
                    "university progression event published",
                    student.student_id, destination.system,
                    destination.institution or "institution not named")
                _emit_transfer_webhook(student, journey_id, moved_by)
                return True

        released = university_handover.build(student)
        # Two layers travel together, and they are not competing
        # vocabularies. The flat identity keys are the platform's envelope
        # convention — ProgressionIntake matches on them and adapter_intake
        # back-fills them from the journey when a producer omits them. The
        # spec-keyed fields are this boundary's own dataset, filtered by
        # SIXTH_FORM_TO_UNIVERSITY. Merged into one dict rather than
        # double-splatted so a future spec field named like an envelope key
        # is an override, not a TypeError at the transfer.
        payload = {
            "sf_student_id": student.student_id,
            "first_name": student.first_name,
            "middle_name": student.middle_name,
            "last_name": student.last_name,
            "date_of_birth": student.date_of_birth,
            "gender": student.gender,
            "title": student.title,
            "moved_by": moved_by,
            "handover_boundary": released.boundary,
            "handover_missing": released.missing_required,
        }
        payload.update(released.payload)
        # A deterministic key makes re-publication a no-op: the outbox is
        # ON CONFLICT(idempotency_key) DO NOTHING and hands back the
        # original event_id. That is what lets a failed transfer be retried
        # by simply calling mark_transferred() again — without it, every
        # attempt minted a fresh uuid and a second call would double-admit,
        # which is why publication used to be gated on the student not
        # already being 'Left'.
        cross_system_bus.publish_cross_system(
            cross_system_bus.EVENT_STUDENT_PROGRESSION_COMPLETED,
            source_system="sixth_form",
            source_module="sixthform_system.students",
            journey_id=journey_id, target_system="university",
            idempotency_key=f"sixth_form:progression:{student.student_id}",
            **payload)
        # Record the hop on the journey itself, exactly as the external
        # branch above does. The home route used to publish and stop
        # there: a learner coming to *this* university left no transition
        # at all, so their cross-system history said "sixth form" and
        # then nothing, while a leaver who went somewhere else — the case
        # the platform knows least about — was properly recorded. Once,
        # because mark_transferred() is deliberately re-callable.
        identity_service.record_transition_once(
            journey_id, from_system="sixth_form", to_system="university",
            reason=destination.reason, actor_user_id=None)
        logger.info(
            "Published progression event for %s (journey %s) to university "
            "with %d handover field(s): %s", student.student_id, journey_id,
            len(released.included), ", ".join(released.included) or "none")
        _emit_transfer_webhook(student, journey_id, moved_by)
        return True
    except Exception:
        logger.exception(
            "Transfer announcement failed for %s — the student is marked "
            "Left with their login disabled but has NOT reached the "
            "university. transferred_at stays unset, so calling "
            "mark_transferred() again will retry the announcement.",
            student.student_id)
        return False


def _emit_transfer_webhook(student, journey_id: str,
                           moved_by: str | None) -> None:
    """Best-effort: notify external subscribers of the transfer."""
    try:
        from education_system.platform.integrations.webhooks.webhook_service import (
            WebhookService,
        )
        WebhookService().dispatch(
            "student.transferred",
            {
                "journey_id": journey_id,
                "sf_student_id": student.student_id,
                "full_name": student.full_name,
                "date_of_birth": student.date_of_birth,
                "moved_by": moved_by or "university system",
            },
            system_key="sixth_form")
    except Exception:
        logger.debug("Transfer webhook dispatch skipped for %s",
                     student.student_id, exc_info=True)
