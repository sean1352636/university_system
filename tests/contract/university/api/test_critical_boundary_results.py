import sqlite3

import pytest

from education_system.systems.university.domains.finance.domain.services import (
    enrolment_fees,
)
from education_system.systems.university.domains.safeguarding.application.services import webhooks
from education_system.systems.university.services.boundary_errors import (
    ExportBoundaryError,
    FinanceBoundaryError,
)
from education_system.systems.university.services.data_exporter import (
    DataExportService,
)
from education_system.systems.university.services.operations import OperationStatus


def test_finance_boundary_does_not_report_database_failure_as_no_fees(
    monkeypatch,
):
    def unavailable():
        raise RuntimeError("database offline")

    monkeypatch.setattr(
        "education_system.systems.university.infrastructure.database.db."
        "get_connection",
        unavailable,
    )

    with pytest.raises(FinanceBoundaryError) as caught:
        enrolment_fees.assess_module_enrolment_fee("S1", "CS101")

    assert caught.value.code == "FINANCE_DATABASE_UNAVAILABLE"


def test_safeguarding_boundary_reports_retryable_registry_failure(monkeypatch):
    monkeypatch.setattr(
        webhooks,
        "_connect",
        lambda: (_ for _ in ()).throw(sqlite3.OperationalError("locked")),
    )

    result = webhooks.emit_webhook_event("case.created", {"case_id": 7})

    assert result.status is OperationStatus.RETRYING
    assert result.retryable
    assert result.issues[0].component == "safeguarding_webhook_registry"


def test_export_boundary_returns_machine_readable_issue(tmp_path):
    service = DataExportService(
        db_path=str(tmp_path / "missing.db"),
        export_dir=str(tmp_path / "exports"),
    )

    result = service.export_student_data("S1", format="xml")

    assert not result.success
    assert result.format is None
    assert result.issue is not None
    assert result.issue.code == "UNSUPPORTED_EXPORT_FORMAT"
    assert isinstance(
        ExportBoundaryError("failed"), ValueError
    )  # compatibility for existing callers
