"""Horizontal object-scope regression tests for university API boundaries."""

from flask import Flask, g, jsonify

from education_system.platform.delivery.api.university.auth import (
    authorize_object,
)


def _app(user):
    app = Flask(__name__)

    @app.get('/student/<student_id>')
    def student(student_id):
        g.current_user = user
        denied = authorize_object(student_id)
        if denied is not None:
            return denied
        return jsonify(ok=True)

    return app


def test_student_cannot_read_another_students_record():
    client = _app({'sub': 'student-a', 'user_id': 1, 'role': 'student'}).test_client()
    assert client.get('/student/student-b').status_code == 403


def test_student_can_read_own_record():
    client = _app({'sub': 'student-a', 'user_id': 1, 'role': 'student'}).test_client()
    assert client.get('/student/student-a').status_code == 200


def test_unknown_role_is_denied_even_with_matching_subject():
    client = _app({'sub': 'student-a', 'user_id': 1, 'role': 'unknown'}).test_client()
    assert client.get('/student/student-a').status_code == 403
