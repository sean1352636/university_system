"""Tests for ReportService, ReportFormat, ReportResult, and MetricSnapshot."""

import json
import pytest

from education_system.shared.analytics.models import (
    MetricSnapshot,
    ReportFormat,
    ReportResult,
)
from education_system.shared.analytics.report_service import ReportService


# ── model basics ─────────────────────────────────────────────────────

def test_report_format_enum():
    assert ReportFormat.JSON.value == "json"
    assert ReportFormat.CSV.value == "csv"
    assert ReportFormat.HTML.value == "html"


def test_metric_snapshot():
    m = MetricSnapshot(name="attendance", value=92.5, category="kpi")
    assert m.name == "attendance"
    assert m.value == 92.5
    assert m.category == "kpi"
    assert m.timestamp is not None


def test_report_result_to_dict():
    r = ReportResult(title="Monthly", system_key="sixth_form",
                     period_start="2026-03-01", period_end="2026-03-31")
    r.sections["summary"] = {"total": 100}
    r.metrics.append(MetricSnapshot(name="rate", value=95.0))

    d = r.to_dict()
    assert d["title"] == "Monthly"
    assert d["sections"]["summary"]["total"] == 100
    assert len(d["metrics"]) == 1
    assert d["metrics"][0]["name"] == "rate"


# ── collector registration ───────────────────────────────────────────

def test_register_collector():
    svc = ReportService(system_key="test")

    def dummy_collector(conn, start, end):
        return {"count": 42}, [MetricSnapshot(name="x", value=1.0)]

    svc.register_collector("dummy", dummy_collector)
    assert "dummy" in svc._collectors


# ── generate with mock collectors ────────────────────────────────────

def _enrollment_collector(conn, start, end):
    return {"new_students": 15, "period": f"{start} to {end}"}, [
        MetricSnapshot(name="enrollment_count", value=15, category="enrollment"),
    ]


def _attendance_collector(conn, start, end):
    return {"rate": 94.2}, [
        MetricSnapshot(name="attendance_rate", value=94.2, category="attendance"),
    ]


def test_generate_all_collectors():
    svc = ReportService(system_key="sixth_form")
    svc.register_collector("enrollment", _enrollment_collector)
    svc.register_collector("attendance", _attendance_collector)

    result = svc.generate(
        title="Term Report",
        period="monthly",
        start_date="2026-03-01",
        end_date="2026-03-31",
    )
    assert result.title == "Term Report"
    assert "enrollment" in result.sections
    assert "attendance" in result.sections
    assert result.sections["enrollment"]["new_students"] == 15
    assert len(result.metrics) == 2


def test_generate_subset_collectors():
    svc = ReportService(system_key="sixth_form")
    svc.register_collector("enrollment", _enrollment_collector)
    svc.register_collector("attendance", _attendance_collector)

    result = svc.generate(
        title="Enroll Only",
        collectors=["enrollment"],
        start_date="2026-03-01",
        end_date="2026-03-31",
    )
    assert "enrollment" in result.sections
    assert "attendance" not in result.sections


def test_generate_unknown_collector_skipped():
    svc = ReportService(system_key="sixth_form")
    result = svc.generate(
        title="Empty",
        collectors=["nonexistent"],
        start_date="2026-03-01",
        end_date="2026-03-31",
    )
    assert result.sections == {}


def test_generate_default_dates():
    svc = ReportService(system_key="sixth_form")
    svc.register_collector("enrollment", _enrollment_collector)
    result = svc.generate(title="Auto Dates", period="weekly")
    assert result.period_start is not None
    assert result.period_end is not None


# ── export JSON ──────────────────────────────────────────────────────

def test_export_json():
    svc = ReportService(system_key="sixth_form")
    svc.register_collector("enrollment", _enrollment_collector)
    report = svc.generate(title="JSON Test", start_date="2026-03-01", end_date="2026-03-31")

    output = svc.export(report, ReportFormat.JSON)
    data = json.loads(output)
    assert data["title"] == "JSON Test"
    assert "enrollment" in data["sections"]


# ── export CSV ───────────────────────────────────────────────────────

def test_export_csv():
    svc = ReportService(system_key="sixth_form")
    svc.register_collector("attendance", _attendance_collector)
    report = svc.generate(title="CSV Test", start_date="2026-03-01", end_date="2026-03-31")

    csv_str = svc.export(report, ReportFormat.CSV)
    assert "section,metric,value" in csv_str
    assert "attendance,rate,94.2" in csv_str


# ── export HTML ──────────────────────────────────────────────────────

def test_export_html():
    svc = ReportService(system_key="sixth_form")
    svc.register_collector("attendance", _attendance_collector)
    report = svc.generate(title="HTML Test", start_date="2026-03-01", end_date="2026-03-31")

    html = svc.export(report, ReportFormat.HTML)
    assert "<html>" in html
    assert "HTML Test" in html
    assert "<table>" in html


# ── collector error handling ─────────────────────────────────────────

def test_collector_error_captured():
    def broken_collector(conn, start, end):
        raise RuntimeError("boom")

    svc = ReportService(system_key="sixth_form")
    svc.register_collector("broken", broken_collector)

    result = svc.generate(title="Error Test", start_date="2026-03-01", end_date="2026-03-31")
    assert "broken" in result.sections
    assert "error" in result.sections["broken"]
    assert "boom" in result.sections["broken"]["error"]
