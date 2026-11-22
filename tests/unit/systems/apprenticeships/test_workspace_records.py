"""Signatures and documents reaching the workspace.

A plan waiting for signatures lands on each party until they sign; an
upload lands on the people who approve it; an expiring document lands on
the person it belongs to. Files go to a temporary directory, never the
real var tree.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system import paths
from education_system.systems.apprenticeships.application.learning import learning_plan_service
from education_system.systems.apprenticeships.application.records import document_service
from education_system.systems.apprenticeships.application.workspace import (
    calendar_service,
    reporting_service,
    search_service,
    task_service,
)

PDF = b"%PDF-1.4\n% test document\n"


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    data = tmp_path / "var"
    monkeypatch.setattr(paths, "APPRENTICESHIPS_DATA_DIR", data)
    monkeypatch.setattr(paths, "APPRENTICESHIPS_EVIDENCE_DIR", data / "evidence")
    monkeypatch.setattr(paths, "APPRENTICESHIPS_EXPORTS_DIR", data / "exports")
    monkeypatch.setattr(paths, "APPRENTICESHIPS_DOCUMENTS_DIR", data / "documents")
    return data / "documents"


def _in(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _upload(actor, cohort, tmp_path, **kwargs):
    source = tmp_path / "passport.pdf"
    source.write_bytes(PDF)
    return document_service.upload_document(
        actor, source, category="Identity", apprentice_id=cohort["apprentice_id"],
        title="Passport", **kwargs,
    )


def _tasks(actor, category: str) -> list[str]:
    return [t.title for t in task_service.my_tasks(actor) if t.category == category]


class TestPlanSignatures:
    def test_each_party_is_asked_until_they_sign(self, cohort, admin):
        learning_plan_service.add_objective(admin, cohort["apprentice_id"], {
            "title": "Wire a consumer unit", "target_date": _in(60),
        })
        assert _tasks(cohort["learner"], "Signatures")
        assert _tasks(cohort["employer_actor"], "Signatures")
        kpis = dict(reporting_service.apprentice_dashboard(cohort["learner"])["kpis"])
        assert kpis["Awaiting my signature"] >= 1

        learning_plan_service.sign_plan(cohort["learner"], cohort["apprentice_id"])
        assert not _tasks(cohort["learner"], "Signatures")
        assert _tasks(cohort["employer_actor"], "Signatures")

    def test_another_employer_is_never_asked(self, cohort, admin):
        learning_plan_service.add_objective(admin, cohort["apprentice_id"], {
            "title": "Wire a consumer unit",
        })
        assert not _tasks(cohort["outsider"], "Signatures")


class TestDocuments:
    def test_an_apprentice_upload_waits_on_the_tutor(self, cohort, tmp_path):
        _upload(cohort["learner"], cohort, tmp_path)
        assert "Approve document: Passport" in _tasks(cohort["tutor"], "Documents")
        assert not _tasks(cohort["employer_actor"], "Documents")

    def test_an_expiring_document_warns_its_owner_and_shows_in_the_diary(
        self, cohort, admin, tmp_path
    ):
        _upload(admin, cohort, tmp_path, expiry_date=_in(10))
        assert "Document expiring: Passport" in _tasks(cohort["learner"], "Documents")
        diary = calendar_service.events(
            cohort["learner"], date_from=date.today(), date_to=date.today() + timedelta(days=14)
        )
        assert "Expires: Passport" in [e.title for e in diary]

    def test_found_by_search_within_scope(self, cohort, tmp_path):
        _upload(cohort["learner"], cohort, tmp_path)
        assert "Passport" in [r.title for r in search_service.search(cohort["learner"], "passport")]
        assert not [r for r in search_service.search(cohort["outsider"], "passport")
                    if r.kind == "Document"]
