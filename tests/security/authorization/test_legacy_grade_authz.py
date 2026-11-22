"""Legacy grade dialogs must fail closed on grade/enrolment writes (task 11).

The dialogs under grade_tracking/dialogs/ historically wrote grades with no
permission, ownership, or enrolment check. These tests pin the standalone
authorizer they now call.
"""

from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest

from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking.grades import (
    authz,
)

pytestmark = pytest.mark.security


@pytest.fixture
def cur():
    c = sqlite3.connect(":memory:")
    c.executescript(
        """
        CREATE TABLE assessments(assessment_id INTEGER PRIMARY KEY, module_code TEXT, max_points REAL);
        CREATE TABLE grades(grade_id INTEGER PRIMARY KEY, assessment_id INTEGER);
        CREATE TABLE modules(module_code TEXT, instructor TEXT);
        CREATE TABLE module_schedule(module_code TEXT, instructor_id TEXT);
        CREATE TABLE student_modules(student_id TEXT, module_code TEXT, status TEXT);
        INSERT INTO assessments VALUES (1, 'CS101', 100);
        INSERT INTO grades VALUES (10, 1);
        INSERT INTO modules VALUES ('CS101', 'prof_smith');
        INSERT INTO student_modules VALUES ('S1', 'CS101', 'Enrolled');
        INSERT INTO student_modules VALUES ('S2', 'CS101', 'withdrawn');
        """
    )
    return c.cursor()


def test_no_auth_context_denies(cur):
    with patch.object(authz, "_current_user", return_value=None):
        assert authz.authorize_grade_mutation("update", cursor=cur, grade_id=10) is False


def test_admin_allowed(cur):
    with patch.object(authz, "_current_user", return_value={"role": "admin"}):
        assert authz.authorize_grade_mutation("update", cursor=cur, grade_id=10) is True


def test_owning_instructor_with_permission_allowed(cur):
    with patch.object(authz, "_current_user",
                      return_value={"role": "instructor", "username": "prof_smith", "id": "7"}), \
         patch.object(authz, "_check_permission", return_value=True):
        assert authz.authorize_grade_mutation("update", cursor=cur, grade_id=10) is True


def test_non_owning_instructor_denied(cur):
    with patch.object(authz, "_current_user",
                      return_value={"role": "instructor", "username": "other", "id": "9"}), \
         patch.object(authz, "_check_permission", return_value=True):
        assert authz.authorize_grade_mutation("update", cursor=cur, grade_id=10) is False


def test_missing_permission_denied_even_for_owner(cur):
    with patch.object(authz, "_current_user",
                      return_value={"role": "instructor", "username": "prof_smith", "id": "7"}), \
         patch.object(authz, "_check_permission", return_value=False):
        assert authz.authorize_grade_mutation("update", cursor=cur, grade_id=10) is False


def test_enrolment_change_owner_vs_non_owner(cur):
    with patch.object(authz, "_current_user",
                      return_value={"role": "instructor", "username": "prof_smith", "id": "7"}):
        assert authz.authorize_module_change(cursor=cur, module_code="CS101") is True
    with patch.object(authz, "_current_user",
                      return_value={"role": "student", "username": "s", "id": "1"}):
        assert authz.authorize_module_change(cursor=cur, module_code="CS101") is False


def test_is_student_enrolled(cur):
    assert authz.is_student_enrolled(cur, "S1", "CS101") is True     # enrolled
    assert authz.is_student_enrolled(cur, "S2", "CS101") is False    # withdrawn
    assert authz.is_student_enrolled(cur, "S3", "CS101") is False    # not in module
    assert authz.is_student_enrolled(cur, "S1", None) is False       # no module


def test_grade_write_requires_enrolment(cur):
    with patch.object(authz, "_current_user",
                      return_value={"role": "instructor", "username": "prof_smith", "id": "7"}), \
         patch.object(authz, "_check_permission", return_value=True):
        # Enrolled student -> allowed; withdrawn student -> denied even for the owner.
        assert authz.authorize_grade_mutation(
            "create", cursor=cur, assessment_id=1, student_id="S1") is True
        assert authz.authorize_grade_mutation(
            "create", cursor=cur, assessment_id=1, student_id="S2") is False
