from __future__ import annotations

import sqlite3

import pytest

from education_system.platform.governance.security.sensitive_access import (
    approve_break_glass,
    authorize_sensitive_fields,
    request_break_glass,
    review_break_glass,
)
from education_system.platform.identity.auth.schema import initialise_auth_db


def test_allow_and_deny_are_both_audited(tmp_path) -> None:
    path = str(tmp_path / "auth.db")
    initialise_auth_db(path)

    allowed = authorize_sensitive_fields(
        actor_id="dsl-1",
        actor_role="dsl",
        domain="safeguarding",
        subject_id="S1",
        fields={"case_summary"},
        purpose="safeguarding_casework",
        db_path=path,
    )
    denied = authorize_sensitive_fields(
        actor_id="registry-1",
        actor_role="staff",
        domain="health",
        subject_id="S1",
        fields={"diagnosis"},
        purpose="quality_audit",
        db_path=path,
    )
    assert allowed.allowed
    assert not denied.allowed

    with sqlite3.connect(path) as conn:
        audit_id = conn.execute(
            "SELECT audit_id FROM sensitive_access_audit LIMIT 1"
        ).fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            conn.execute(
                "UPDATE sensitive_access_audit SET reason = ? WHERE audit_id = ?",
                ("tampered", audit_id),
            )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            conn.execute(
                "DELETE FROM sensitive_access_audit WHERE audit_id = ?",
                (audit_id,),
            )


def test_break_glass_requires_independent_approval_and_review(tmp_path) -> None:
    path = str(tmp_path / "auth.db")
    initialise_auth_db(path)
    grant = request_break_glass(
        actor_id="registry-1",
        domain="health",
        subject_id="S1",
        purpose="direct_care",
        reason="Immediate care while clinician is unavailable",
        db_path=path,
    )
    assert approve_break_glass(grant, approved_by="clinical-lead", db_path=path)
    decision = authorize_sensitive_fields(
        actor_id="registry-1",
        actor_role="staff",
        domain="health",
        subject_id="S1",
        fields={"diagnosis"},
        purpose="direct_care",
        db_path=path,
    )
    assert decision.allowed
    assert decision.grant_id == grant
    assert review_break_glass(
        grant,
        reviewed_by="privacy-officer",
        outcome="appropriate",
        db_path=path,
    )
