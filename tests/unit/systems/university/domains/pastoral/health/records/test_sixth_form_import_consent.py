"""Tests for the consent gate on ``health.records.sixth_form_import``.

Health data is special category. ``handover.SIXTH_FORM_TO_UNIVERSITY``
marks its sensitive fields as needing consent, the sixth form records
that consent under ``university_handover``, and this module is the single
seam through which the record crosses — so this is where the gate lives
and where it has to be pinned down.

Only :func:`check_release` is exercised here, plus the refusal path
through :func:`import_from_sixth_form`. The copying itself needs both
databases and belongs to an integration test; what must never regress is
the *decision*, and the decision is pure.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.university.domains.pastoral.domain.health.records import (
    sixth_form_import as sfi,
)


@pytest.fixture()
def consent(monkeypatch):
    """Control what the sixth form's consent register answers."""
    def _set(value, *, raises=False):
        from education_system.systems.sixth_form.domain.progression import (
            university_handover,
        )

        def _consent_for(_student_id):
            if raises:
                raise RuntimeError("consent register unavailable")
            return value

        monkeypatch.setattr(university_handover, "consent_for", _consent_for)
    return _set


class TestCheckRelease:
    def test_active_consent_releases_the_full_record(self, consent):
        consent({"consent_id": 7, "granted_date": "2027-05-01",
                 "expires_date": None})
        decision = sfi.check_release("SF-1")
        assert decision.allowed
        assert decision.basis == sfi.CONSENT
        assert decision.scope == sfi.SCOPE_FULL
        assert decision.full_record
        assert decision.consent_reference == "7"

    def test_no_consent_refuses(self, consent):
        consent(None)
        decision = sfi.check_release("SF-1")
        assert not decision.allowed
        assert decision.basis == ""
        assert "university_handover" in decision.detail

    def test_expired_consent_refuses(self, consent):
        yesterday = (_dt.date.today() - _dt.timedelta(days=1)).isoformat()
        consent({"consent_id": 7, "granted_date": "2020-01-01",
                 "expires_date": yesterday})
        decision = sfi.check_release("SF-1")
        assert not decision.allowed

    def test_vital_interests_narrows_rather_than_widens(self, consent):
        """An asserted basis is a reason to carry the allergy that could
        kill somebody, not a way around the consent that was not given."""
        consent(None)
        decision = sfi.check_release("SF-1",
                                     lawful_basis=sfi.VITAL_INTERESTS)
        assert decision.allowed
        assert decision.basis == sfi.VITAL_INTERESTS
        assert decision.scope == sfi.SCOPE_SAFETY_CRITICAL
        assert decision.full_record is False

    def test_consent_outranks_an_asserted_basis(self, consent):
        """With real consent there is no reason to fall back to the narrow
        subset — the learner agreed to the whole thing."""
        consent({"consent_id": 7, "granted_date": "2027-05-01"})
        decision = sfi.check_release("SF-1",
                                     lawful_basis=sfi.VITAL_INTERESTS)
        assert decision.basis == sfi.CONSENT
        assert decision.full_record

    def test_an_invented_basis_is_not_a_basis(self, consent):
        consent(None)
        decision = sfi.check_release("SF-1",
                                     lawful_basis="the registrar said so")
        assert not decision.allowed
        assert "not a lawful basis" in decision.detail

    def test_an_unreadable_register_is_not_a_grant(self, consent):
        consent(None, raises=True)
        decision = sfi.check_release("SF-1")
        assert not decision.allowed

    def test_an_unreadable_register_still_allows_vital_interests(self, consent):
        consent(None, raises=True)
        decision = sfi.check_release("SF-1",
                                     lawful_basis=sfi.VITAL_INTERESTS)
        assert decision.allowed
        assert decision.scope == sfi.SCOPE_SAFETY_CRITICAL


class TestRefusalPath:
    def test_import_raises_and_writes_nothing_without_a_basis(
        self, consent, monkeypatch
    ):
        consent(None)
        audited = []
        monkeypatch.setattr(
            sfi, "_audit_release",
            lambda **kw: audited.append(kw))

        # If the gate leaked, this would be the next thing called.
        def _must_not_run(*_a, **_k):  # pragma: no cover - guard
            raise AssertionError("read the medical record despite refusal")

        monkeypatch.setattr(sfi, "get_connection", _must_not_run)

        with pytest.raises(sfi.MedicalHandoverRefused):
            sfi.import_from_sixth_form(
                uni_student_id="1234567", sf_student_id="SF-1")

        assert len(audited) == 1
        assert audited[0]["outcome"] == "refused"

    def test_a_refusal_is_audited_even_when_it_denies_access(
        self, consent, monkeypatch
    ):
        """The access record has to be complete, which means the refusals
        are in it too — otherwise "no row" is ambiguous between "never
        asked" and "asked and was told no"."""
        consent(None)
        logged = []
        monkeypatch.setattr(sfi, "_audit_release",
                            lambda **kw: logged.append(kw))
        with pytest.raises(sfi.MedicalHandoverRefused):
            sfi.import_from_sixth_form(
                uni_student_id="1234567", sf_student_id="SF-1",
                actor="registrar", received_by="student records")
        assert logged[0]["actor"] == "registrar"
        assert logged[0]["received_by"] == "student records"
