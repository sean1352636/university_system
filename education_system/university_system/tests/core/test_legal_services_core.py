"""Tests for modules.domain.operations.legal.services.legal_services_core.

Focuses on the pure-logic surface: module constants, fee calculation,
case-number generation, invoice rendering, and the email send-helper's
branching (recipient-empty, infra-missing, render failure).
"""
import re
from unittest.mock import patch

import pytest

from education_system.university_system.modules.domain.operations.legal.services import (
    legal_services_core as core,
)


class TestServiceFeeConstants:
    def test_pro_bono_is_free(self):
        assert core.SERVICE_FEES["pro_bono"] == 0.00

    def test_30min_cheaper_than_60min(self):
        assert core.SERVICE_FEES["consultation_30min"] < core.SERVICE_FEES["consultation_60min"]

    def test_all_fees_non_negative(self):
        for name, fee in core.SERVICE_FEES.items():
            assert fee >= 0, f"{name} fee should be non-negative"


class TestEnumConstants:
    def test_case_types_contains_pro_bono(self):
        assert "pro_bono" in core.CASE_TYPES

    def test_case_statuses(self):
        assert set(core.CASE_STATUSES) == {"open", "in_progress", "pending_review", "closed"}

    def test_consultation_statuses(self):
        assert set(core.CONSULTATION_STATUSES) == {"scheduled", "completed", "cancelled", "no_show"}

    def test_payment_statuses(self):
        assert set(core.PAYMENT_STATUSES) == {"pending", "paid", "refunded"}


class TestGenerateCaseNumber:
    def test_format(self):
        n = core.generate_case_number()
        # CASE-YYYYMMDD-XXXXXX (6 hex chars upper)
        assert re.match(r"^CASE-\d{8}-[0-9A-F]{6}$", n), n

    def test_unique_across_calls(self):
        numbers = {core.generate_case_number() for _ in range(20)}
        assert len(numbers) == 20  # all distinct


class TestCalculateServiceFee:
    def test_pro_bono_returns_zero(self):
        assert core.calculate_service_fee("pro_bono") == 0.00

    def test_specific_service_with_known_fee(self):
        # immigration_consultation = 60.00
        assert core.calculate_service_fee("immigration", 30) == 60.00

    def test_unknown_service_short_duration_uses_30min_default(self):
        assert core.calculate_service_fee("mystery", 20) == core.SERVICE_FEES["consultation_30min"]

    def test_unknown_service_long_duration_uses_60min_default(self):
        assert core.calculate_service_fee("mystery", 60) == core.SERVICE_FEES["consultation_60min"]

    def test_overtime_adds_blocks(self):
        # 90 min = 1 extra 30-min block at 0.75 × 30-min fee
        expected = core.SERVICE_FEES["consultation_60min"] + core.SERVICE_FEES["consultation_30min"] * 0.75
        # mystery service, > 60 min → starts from 60min fee, then adds blocks
        assert core.calculate_service_fee("mystery", 90) == round(expected, 2)

    def test_two_extra_blocks(self):
        # 120 min = 2 extra 30-min blocks
        base = core.SERVICE_FEES["consultation_60min"]
        extra = 2 * core.SERVICE_FEES["consultation_30min"] * 0.75
        assert core.calculate_service_fee("mystery", 120) == round(base + extra, 2)


class TestGenerateInvoiceText:
    def _case(self, **overrides):
        base = {
            "case_number": "CASE-001",
            "client_name": "Alice",
            "client_email": "alice@x",
            "total_fees": 100.0,
        }
        base.update(overrides)
        return base

    def test_includes_case_basics(self):
        text = core.generate_invoice_text(self._case(), [], ["consultation"])
        assert "CASE-001" in text
        assert "Alice" in text
        assert "alice@x" in text
        assert "consultation" in text

    def test_handles_missing_client_email(self):
        case = self._case()
        del case["client_email"]
        text = core.generate_invoice_text(case, [], ["x"])
        assert "N/A" in text

    def test_balance_computed_from_completed_payments(self):
        case = self._case(total_fees=200.0)
        payments = [
            {"amount": 50, "status": "completed", "created_at": "2026-01-01T00:00:00", "payment_type": "card"},
            {"amount": 30, "status": "completed", "created_at": "2026-01-02T00:00:00", "payment_type": "card"},
            {"amount": 100, "status": "pending", "created_at": "2026-01-03T00:00:00", "payment_type": "card"},  # excluded from total
        ]
        text = core.generate_invoice_text(case, payments, ["service-A"])
        assert "200.00" in text
        assert "80.00" in text  # total paid
        assert "120.00" in text  # balance due

    def test_lists_each_service(self):
        text = core.generate_invoice_text(self._case(), [], ["a", "b", "c"])
        assert "- a" in text and "- b" in text and "- c" in text


class TestSendLegalEmail:
    """The internal _send_legal_email helper governs all email send paths."""

    def test_empty_recipient_returns_false(self):
        assert core._send_legal_email("any_template", "", {"x": 1}) is False

    def test_returns_false_when_infrastructure_unavailable(self):
        # Patch the import inside the helper to raise — simulates infra missing
        with patch.dict(
            "sys.modules",
            {"education_system.university_system.infrastructure.email.template_utils": None,
             "education_system.university_system.infrastructure.email.email_service": None},
        ):
            # When the lookup yields None for the submodule, `from ... import ...`
            # raises ImportError → caught by helper → returns False
            assert core._send_legal_email("template", "to@x", {}) is False

    def test_returns_false_when_render_yields_empty(self):
        fake_template_utils = type("M", (), {"render_template": staticmethod(lambda *a, **kw: ("", ""))})
        fake_email_service = type("M", (), {"send_email": staticmethod(lambda **kw: True)})
        with patch.dict(
            "sys.modules",
            {"education_system.university_system.infrastructure.email.template_utils": fake_template_utils,
             "education_system.university_system.infrastructure.email.email_service": fake_email_service},
        ):
            assert core._send_legal_email("template", "to@x", {}) is False

    def test_returns_true_on_successful_send(self):
        fake_template_utils = type("M", (), {
            "render_template": staticmethod(lambda *a, **kw: ("subject", "body")),
        })
        sent = {}
        def _send(**kw):
            sent.update(kw)
            return True
        fake_email_service = type("M", (), {"send_email": staticmethod(_send)})
        with patch.dict(
            "sys.modules",
            {"education_system.university_system.infrastructure.email.template_utils": fake_template_utils,
             "education_system.university_system.infrastructure.email.email_service": fake_email_service},
        ):
            assert core._send_legal_email("template", "to@x", {"k": "v"}) is True
        assert sent["recipient_email"] == "to@x"
        assert sent["subject"] == "subject"


class TestSendPolicyAcknowledgement:
    def test_delegates_to_send_legal_email_with_template_name(self):
        with patch.object(core, "_send_legal_email", return_value=True) as send:
            assert core.send_policy_acknowledgement(
                "to@x", "Alice", "Code of Conduct", "v1",
                "2026-01-01", "2026-01-31",
            ) is True
        template_name, recipient, vars_ = send.call_args.args
        assert template_name == "policy_acknowledgement"
        assert recipient == "to@x"
        assert vars_["policy_name"] == "Code of Conduct"
        assert vars_["recipient_name"] == "Alice"

    def test_generates_reference_id_when_blank(self):
        with patch.object(core, "_send_legal_email", return_value=True) as send:
            core.send_policy_acknowledgement(
                "to@x", "Alice", "p", "v", "d1", "d2", reference_id="",
            )
        vars_ = send.call_args.args[2]
        assert vars_["reference_id"].startswith("POL-")

    def test_preserves_provided_reference_id(self):
        with patch.object(core, "_send_legal_email", return_value=True) as send:
            core.send_policy_acknowledgement(
                "to@x", "Alice", "p", "v", "d1", "d2", reference_id="EXPLICIT-1",
            )
        assert send.call_args.args[2]["reference_id"] == "EXPLICIT-1"


class TestSendComplianceNotice:
    def test_delegates_with_template_name(self):
        with patch.object(core, "_send_legal_email", return_value=True) as send:
            core.send_compliance_notice(
                "to@x", "Alice", "Subject", "Body", "Do X",
            )
        template_name, recipient, vars_ = send.call_args.args
        assert template_name == "compliance_notice"
        assert recipient == "to@x"
        assert vars_["notice_subject"] == "Subject"

    def test_generates_notice_reference_when_blank(self):
        with patch.object(core, "_send_legal_email", return_value=True) as send:
            core.send_compliance_notice("to@x", "A", "s", "b", "act")
        assert send.call_args.args[2]["notice_reference"].startswith("COMP-")

    def test_preserves_provided_notice_reference(self):
        with patch.object(core, "_send_legal_email", return_value=True) as send:
            core.send_compliance_notice(
                "to@x", "A", "s", "b", "act", notice_reference="NREF-9",
            )
        assert send.call_args.args[2]["notice_reference"] == "NREF-9"

    def test_default_effective_date_is_today(self):
        with patch.object(core, "_send_legal_email", return_value=True) as send:
            core.send_compliance_notice("to@x", "A", "s", "b", "act")
        # default branch substitutes today's YYYY-MM-DD
        vars_ = send.call_args.args[2]
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", vars_["effective_date"])
