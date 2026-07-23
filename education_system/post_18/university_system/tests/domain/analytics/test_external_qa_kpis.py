"""Tests for ``analytics/external_qa_kpis`` — the analytics-package entry point
that re-exports the external-QA (OfS / TEF / REF) compute + persist logic from
``academics.research.external_quality_assurance``.

The module is deliberately thin: both public functions lazily import the source
``qa_service`` and delegate. These tests pin that contract — the delegation
happens, the return value is passed through untouched, and nothing else is added
— by patching the source ``qa_service`` so no real DB or compute is exercised.
"""

from unittest.mock import patch

from education_system.post_18.university_system.modules.domain.analytics import (
    external_qa_kpis,
)

_QA = (
    "education_system.post_18.university_system.modules.domain.academics."
    "research.external_quality_assurance.services.qa_service"
)


class TestComputeExternalQaKpis:
    def test_delegates_and_passes_result_through(self):
        sentinel = [
            {"metric_name": "ofs_b3_continuation", "metric_value": 92.5},
            {"metric_name": "tef_rating", "metric_value": "Gold"},
        ]
        with patch(f"{_QA}.compute_external_qa_kpis", return_value=sentinel) as m:
            result = external_qa_kpis.compute_external_qa_kpis()

        # Return value is passed through unchanged (same object, not a copy).
        assert result is sentinel
        m.assert_called_once_with()

    def test_empty_result_is_preserved(self):
        with patch(f"{_QA}.compute_external_qa_kpis", return_value=[]):
            assert external_qa_kpis.compute_external_qa_kpis() == []

    def test_propagates_source_exceptions(self):
        with patch(f"{_QA}.compute_external_qa_kpis", side_effect=RuntimeError("boom")):
            try:
                external_qa_kpis.compute_external_qa_kpis()
            except RuntimeError as exc:
                assert str(exc) == "boom"
            else:  # pragma: no cover - guard
                raise AssertionError("expected RuntimeError to propagate")


class TestRecordExternalQaKpis:
    def test_delegates_and_returns_count(self):
        with patch(f"{_QA}.record_external_qa_kpis", return_value=7) as m:
            result = external_qa_kpis.record_external_qa_kpis()

        assert result == 7
        m.assert_called_once_with()

    def test_zero_records_is_preserved(self):
        with patch(f"{_QA}.record_external_qa_kpis", return_value=0):
            assert external_qa_kpis.record_external_qa_kpis() == 0

    def test_propagates_source_exceptions(self):
        with patch(f"{_QA}.record_external_qa_kpis", side_effect=ValueError("bad")):
            try:
                external_qa_kpis.record_external_qa_kpis()
            except ValueError as exc:
                assert str(exc) == "bad"
            else:  # pragma: no cover - guard
                raise AssertionError("expected ValueError to propagate")


class TestModuleSurface:
    def test_public_api_is_exported(self):
        assert external_qa_kpis.__all__ == [
            "compute_external_qa_kpis",
            "record_external_qa_kpis",
        ]

    def test_exported_names_are_callable(self):
        for name in external_qa_kpis.__all__:
            assert callable(getattr(external_qa_kpis, name))
