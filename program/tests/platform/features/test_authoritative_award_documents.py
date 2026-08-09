from __future__ import annotations

import sqlite3

import pytest

from education_system.platform.features.certificates.certificate_service import (
    CertificateService,
)
from education_system.platform.features.certificates.transcript_service import (
    TranscriptService,
)


def _award_db(path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE students (
            student_id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT
        );
        CREATE TABLE ratified_student_awards (
            award_id INTEGER PRIMARY KEY, student_id TEXT, award_name TEXT,
            classification TEXT, programme_code TEXT, academic_year TEXT,
            ratified_at TEXT, status TEXT, release_authorised INTEGER
        );
        INSERT INTO students VALUES ('S1', 'Ada', 'Lovelace');
    """)
    connection.commit()
    connection.close()


def test_documents_reject_mutable_results_without_ratified_award(tmp_path) -> None:
    path = tmp_path / "student_records.db"
    _award_db(path)
    with pytest.raises(PermissionError):
        TranscriptService(str(path)).generate_transcript("S1")
    with pytest.raises(RuntimeError, match="ratified and released"):
        CertificateService(str(path)).generate_certificate(
            "S1", "completion", "Caller supplied title", "2026-07-01"
        )


def test_certificate_uses_ratified_outcome_not_caller_values(tmp_path) -> None:
    path = tmp_path / "student_records.db"
    _award_db(path)
    connection = sqlite3.connect(path)
    connection.execute(
        """INSERT INTO ratified_student_awards VALUES
           (1, 'S1', 'BSc Computing', 'First Class', 'CS', '2026/27',
            '2027-07-15T12:00:00', 'ratified', 1)"""
    )
    connection.commit()
    connection.close()

    certificate = CertificateService(str(path)).generate_certificate(
        "S1", "completion", "Wrong title", "1900-01-01", grade="Wrong grade"
    )
    assert certificate["course_name"] == "BSc Computing"
    assert certificate["grade"] == "First Class"
    assert certificate["award_date"] == "2027-07-15"
