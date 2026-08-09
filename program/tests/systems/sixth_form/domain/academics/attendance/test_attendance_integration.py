"""Tests for integration, subject access and retention.

Nothing is ever posted on import: delivery only happens when
:func:`deliver_pending` is called, so a test database cannot fire a
term's worth of events at somebody's live endpoint.
"""

from __future__ import annotations

import datetime as _dt
import json

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_integration as integration,
)


# ── 1. Payload shapes ──────────────────────────────────────────────

class TestPayloads:

    def test_a_mark_payload_carries_its_meaning(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "I"}})
        record = core.get_record_for(attdb.slot, attdb.s1,
                                     attdb.prev_monday)
        payload = integration.mark_payload(record)
        assert payload["code"] == "I"
        assert payload["meaning"] == "Authorised"
        assert payload["counts_as_present"] is False

    def test_a_student_payload_carries_figure_and_detail(self, attdb):
        # A portal showing a percentage with no way to see the lessons
        # behind it generates a phone call every time.
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "/"}})
        payload = integration.student_payload(attdb.s1)
        assert payload["summary"]["percentage"] == 100.0
        assert len(payload["marks"]) == 1

    def test_a_register_payload_carries_the_digest(self, attdb):
        payload = integration.register_payload(attdb.slot, attdb.monday)
        assert payload["state"] == "Not started"
        assert len(payload["entries"]) == 3
        assert payload["digest"]

    def test_a_summary_payload_carries_the_cohorts(self, attdb):
        payload = integration.summary_payload(date_from=attdb.prev_monday,
                                              date_to=attdb.monday)
        assert "cohorts" in payload
        assert payload["window"]["from"] == attdb.prev_monday

    def test_payloads_serialise(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "/"}})
        assert json.dumps(integration.student_payload(attdb.s1))


# ── 2. Webhooks ────────────────────────────────────────────────────

class TestWebhooks:

    def test_a_subscriber_can_register(self, attdb):
        subscription = integration.subscribe(
            "portal", "https://example.test/hook",
            events=[integration.MARK_RECORDED], secret="s3cret")
        assert subscription.active is True
        assert subscription.events == (integration.MARK_RECORDED,)

    def test_a_non_http_url_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="must be http"):
            integration.subscribe("portal", "ftp://example.test")

    def test_a_name_and_url_are_required(self, attdb):
        with pytest.raises(core.ValidationError, match="needs a name"):
            integration.subscribe("  ", "https://example.test")

    def test_an_unknown_event_type_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Event type must be"):
            integration.subscribe("portal", "https://example.test",
                                  events=["mark.vibed"])

    def test_emitting_queues_without_sending(self, attdb):
        integration.subscribe("portal", "https://example.test/hook")
        assert integration.emit(integration.MARK_RECORDED,
                                {"student_id": attdb.s1}) == 1
        assert len(integration.list_events(state=integration.PENDING)) == 1

    def test_a_subscriber_only_gets_what_it_asked_for(self, attdb):
        integration.subscribe("portal", "https://example.test/hook",
                              events=[integration.REGISTER_SUBMITTED])
        assert integration.emit(integration.MARK_RECORDED, {}) == 0

    def test_no_events_means_everything(self, attdb):
        integration.subscribe("portal", "https://example.test/hook")
        assert integration.emit(integration.SAFEGUARDING_ALERT, {}) == 1

    def test_a_signature_is_reproducible(self, attdb):
        assert integration.sign("body", "secret") == \
            integration.sign("body", "secret")
        assert integration.sign("body", "secret") != \
            integration.sign("body", "other")

    def test_delivery_uses_the_supplied_sender(self, attdb):
        posted: list[str] = []
        integration.subscribe("portal", "https://example.test/hook",
                              secret="s3cret")
        integration.emit(integration.MARK_RECORDED, {"student_id": attdb.s1})
        result = integration.deliver_pending(
            sender=lambda url, body, headers: posted.append(url))
        assert result.delivered == 1
        assert posted == ["https://example.test/hook"]

    def test_the_signature_header_is_sent(self, attdb):
        captured: list[dict] = []
        integration.subscribe("portal", "https://example.test/hook",
                              secret="s3cret")
        integration.emit(integration.MARK_RECORDED, {})
        integration.deliver_pending(
            sender=lambda url, body, headers: captured.append(headers))
        assert "X-Attendance-Signature" in captured[0]

    def test_no_sender_is_a_failure_not_a_success(self, attdb):
        # An installation with no transport must not look like one that
        # is delivering.
        integration.subscribe("portal", "https://example.test/hook")
        integration.emit(integration.MARK_RECORDED, {})
        result = integration.deliver_pending()
        assert result.delivered == 0
        assert result.failed == 1

    def test_repeated_failure_dead_letters_the_event(self, attdb):
        def explode(_url, _body, _headers):
            raise RuntimeError("connection refused")

        integration.subscribe("portal", "https://example.test/hook")
        integration.emit(integration.MARK_RECORDED, {})
        for _ in range(integration.MAX_ATTEMPTS):
            integration.deliver_pending(sender=explode)
        assert len(integration.dead_letters()) == 1

    def test_dead_letters_can_be_retried(self, attdb):
        def explode(_url, _body, _headers):
            raise RuntimeError("connection refused")

        integration.subscribe("portal", "https://example.test/hook")
        integration.emit(integration.MARK_RECORDED, {})
        for _ in range(integration.MAX_ATTEMPTS):
            integration.deliver_pending(sender=explode)
        assert integration.retry_dead() == 1
        assert integration.deliver_pending(
            sender=lambda *_: None).delivered == 1

    def test_unsubscribing_stops_delivery(self, attdb):
        subscription = integration.subscribe("portal",
                                             "https://example.test/hook")
        integration.emit(integration.MARK_RECORDED, {})
        integration.unsubscribe(subscription.subscription_id)
        result = integration.deliver_pending(sender=lambda *_: None)
        assert result.dead == 1
        assert result.delivered == 0

    def test_a_mark_can_be_emitted_directly(self, attdb):
        integration.subscribe("portal", "https://example.test/hook")
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "/"}})
        record = core.get_record_for(attdb.slot, attdb.s1,
                                     attdb.prev_monday)
        assert integration.emit_mark(record) == 1


# ── 3. Subject access ──────────────────────────────────────────────

class TestSubjectAccess:

    def test_the_export_includes_the_marks(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "O"}})
        export = integration.subject_access_export(attdb.s1)
        assert export["student_id"] == attdb.s1
        assert len(export["attendance_marks"]) == 1

    def test_voided_marks_are_included(self, attdb):
        # The honest answer to "what do you hold" includes these.
        from education_system.systems.sixth_form.domain.academics.attendance \
            import attendance_audit as audit
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "O"}})
        record = core.get_record_for(attdb.slot, attdb.s1,
                                     attdb.prev_monday)
        audit.void_record(record.record_id, reason="Wrong learner")
        export = integration.subject_access_export(attdb.s1)
        assert export["attendance_marks"]

    def test_the_awkward_parts_are_included(self, attdb):
        from education_system.systems.sixth_form.domain.academics.attendance \
            import attendance_absence_reports as reports
        reports.report_absence(attdb.s1, attdb.prev_monday,
                               reason_text="Flu")
        export = integration.subject_access_export(attdb.s1)
        assert "absence_reports" in export

    def test_the_export_serialises_to_json(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "O"}})
        assert json.loads(integration.subject_access_json(attdb.s1))

    def test_erasure_needs_the_id_confirmed(self, attdb):
        with pytest.raises(core.ValidationError, match="confirm"):
            integration.erase_student(attdb.s1, confirm="wrong",
                                      actor="head")

    def test_erasure_needs_an_actor(self, attdb):
        with pytest.raises(core.ValidationError, match="who authorised"):
            integration.erase_student(attdb.s1, confirm=attdb.s1, actor="  ")

    def test_erasure_removes_the_marks(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "O"}})
        removed = integration.erase_student(attdb.s1, confirm=attdb.s1,
                                            actor="head")
        assert removed.get("attendance_records") == 1
        assert core.list_records(student_id=attdb.s1) == []


# ── 4. Retention ───────────────────────────────────────────────────

class TestRetention:

    def test_the_cutoff_is_years_back(self, attdb):
        cutoff = integration.retention_cutoff(years=7)
        assert int(cutoff[:4]) == _dt.date.today().year - 7

    def test_a_purge_defaults_to_a_dry_run(self, attdb):
        core.save_register(attdb.slot, attdb.ancient,
                           {attdb.s1: {"code": "O"}}, allow_retro=True)
        result = integration.purge(years=1)
        assert result.dry_run is True
        assert core.list_records(student_id=attdb.s1)

    def test_a_real_purge_deletes_old_marks(self, attdb):
        core.save_register(attdb.slot, attdb.ancient,
                           {attdb.s1: {"code": "O"}}, allow_retro=True)
        result = integration.purge(years=1, dry_run=False, actor="head")
        assert result.records == 1
        assert core.list_records(student_id=attdb.s1) == []

    def test_recent_marks_survive_a_purge(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "O"}})
        integration.purge(years=1, dry_run=False)
        assert core.list_records(student_id=attdb.s1)

    def test_the_retention_report_says_what_would_go(self, attdb):
        core.save_register(attdb.slot, attdb.ancient,
                           {attdb.s1: {"code": "O"}}, allow_retro=True)
        report = integration.retention_report(years=1)
        assert report["attendance_marks"] == 1
        assert "purge" in report["action"]

    def test_a_clean_college_has_nothing_to_purge(self, attdb):
        report = integration.retention_report()
        assert report["total"] == 0
        assert report["action"] == "Nothing to purge"
