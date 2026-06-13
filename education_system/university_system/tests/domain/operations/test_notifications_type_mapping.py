"""Tests for the legacy notification_type → (channel, priority) mapping
and the public enums exposed by the notifications service.

These functions are pure (no DB / no I/O), so no fixture is needed.
"""

from __future__ import annotations

import pytest

from education_system.university_system.modules.domain.operations.communications.notifications.services.notifications_service import (
    DeliveryMethod,
    NotificationChannel,
    NotificationPriority,
    map_notification_type_to_channel_priority,
)


class TestEnumValues:
    def test_priority_values(self):
        assert {p.value for p in NotificationPriority} == {"low", "medium", "high", "urgent"}

    def test_channel_values(self):
        assert {c.value for c in NotificationChannel} == {
            "academic", "social", "financial", "health",
            "housing", "events", "system",
        }

    def test_delivery_method_values(self):
        assert {d.value for d in DeliveryMethod} == {"push", "email", "sms"}


class TestTypeMapping:
    @pytest.mark.parametrize(
        "ntype,channel,priority",
        [
            ("assignment", "academic", "medium"),
            ("assignment_due", "academic", "high"),
            ("grade_posted", "academic", "medium"),
            ("schedule_change", "academic", "high"),
            ("exam_reminder", "academic", "high"),
            ("payment_due", "financial", "high"),
            ("payment_received", "financial", "low"),
            ("invoice", "financial", "medium"),
            ("health_alert", "health", "high"),
            ("appointment_reminder", "health", "medium"),
            ("housing_update", "housing", "medium"),
            ("maintenance_request", "housing", "low"),
            ("event_reminder", "events", "low"),
            ("event_cancelled", "events", "medium"),
            ("message", "social", "low"),
            ("friend_request", "social", "low"),
            ("document_uploaded", "system", "low"),
            ("document_rejected", "system", "medium"),
            ("urgent", "system", "urgent"),
            ("critical", "system", "urgent"),
            ("info", "system", "low"),
        ],
    )
    def test_known_mappings(self, ntype, channel, priority):
        assert map_notification_type_to_channel_priority(ntype) == (channel, priority)

    def test_case_insensitive(self):
        assert map_notification_type_to_channel_priority("PAYMENT_DUE") == ("financial", "high")
        assert map_notification_type_to_channel_priority("Exam_Reminder") == ("academic", "high")

    def test_unknown_type_defaults_to_system_medium(self):
        assert map_notification_type_to_channel_priority("totally-unknown-type") == ("system", "medium")
        assert map_notification_type_to_channel_priority("") == ("system", "medium")

    def test_mapping_outputs_align_with_enum_values(self):
        valid_channels = {c.value for c in NotificationChannel}
        valid_priorities = {p.value for p in NotificationPriority}
        for ntype in ("assignment", "payment_due", "event_reminder",
                      "message", "urgent", "unknown"):
            channel, priority = map_notification_type_to_channel_priority(ntype)
            assert channel in valid_channels
            assert priority in valid_priorities
