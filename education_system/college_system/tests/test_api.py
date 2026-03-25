"""Tests for the REST API."""

import pytest


class TestHealthCheck:
    def test_health(self, api_client):
        resp = api_client.get("/api/system/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"


class TestAuthAPI:
    def test_login(self, api_client):
        resp = api_client.post("/api/auth/login", json={
            "username": "admin1", "password": "admin1234",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data
        assert data["user"]["username"] == "admin1"

    def test_login_wrong_password(self, api_client):
        resp = api_client.post("/api/auth/login", json={
            "username": "admin1", "password": "wrong",
        })
        assert resp.status_code == 401

    def test_register(self, api_client, auth_headers):
        resp = api_client.post("/api/auth/register", json={
            "username": "newstudent", "password": "Student@12345",
            "systems": [{"system_key": "college", "role": "student"}],
        }, headers=auth_headers)
        assert resp.status_code == 201

    def test_me(self, api_client, auth_headers):
        resp = api_client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["user"]["username"] == "admin1"

    def test_unauthorized(self, api_client):
        resp = api_client.get("/api/auth/me")
        assert resp.status_code == 401


class TestStudentAPI:
    def test_create_student(self, api_client, auth_headers):
        resp = api_client.post("/api/students", headers=auth_headers, json={
            "first_name": "Alice", "last_name": "Smith",
            "year_group": "12", "form_group": "12A",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["data"]["first_name"] == "Alice"

    def test_list_students(self, api_client, auth_headers):
        api_client.post("/api/students", headers=auth_headers, json={
            "first_name": "A", "last_name": "B",
        })
        resp = api_client.get("/api/students", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["pagination"]["total"] >= 1

    def test_get_student(self, api_client, auth_headers):
        create = api_client.post("/api/students", headers=auth_headers, json={
            "first_name": "Bob", "last_name": "Jones",
        })
        pk = create.get_json()["data"]["id"]
        resp = api_client.get(f"/api/students/{pk}", headers=auth_headers)
        assert resp.status_code == 200

    def test_update_student(self, api_client, auth_headers):
        create = api_client.post("/api/students", headers=auth_headers, json={
            "first_name": "C", "last_name": "D",
        })
        pk = create.get_json()["data"]["id"]
        resp = api_client.put(f"/api/students/{pk}", headers=auth_headers, json={
            "year_group": "13",
        })
        assert resp.status_code == 200
        assert resp.get_json()["data"]["year_group"] == "13"


class TestCourseAPI:
    def test_create_course(self, api_client, auth_headers):
        resp = api_client.post("/api/courses", headers=auth_headers, json={
            "course_code": "TEST901", "title": "Intro to CS",
        })
        assert resp.status_code == 201

    def test_get_course_by_code(self, api_client, auth_headers):
        api_client.post("/api/courses", headers=auth_headers, json={
            "course_code": "TEST902", "title": "Calculus",
        })
        resp = api_client.get("/api/courses/by-code/TEST902", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["title"] == "Calculus"


class TestEnrollmentAPI:
    def test_enroll_student(self, api_client, auth_headers):
        s = api_client.post("/api/students", headers=auth_headers, json={
            "first_name": "E", "last_name": "F",
        }).get_json()["data"]
        c = api_client.post("/api/courses", headers=auth_headers, json={
            "course_code": "TEST901", "title": "CS",
        }).get_json()["data"]

        resp = api_client.post("/api/enrollments/enroll", headers=auth_headers, json={
            "student_id": s["id"], "course_id": c["id"],
        })
        assert resp.status_code == 201


class TestGradeAPI:
    def test_record_grade(self, api_client, auth_headers):
        s = api_client.post("/api/students", headers=auth_headers, json={
            "first_name": "G", "last_name": "H",
        }).get_json()["data"]
        c = api_client.post("/api/courses", headers=auth_headers, json={
            "course_code": "TEST901", "title": "CS",
        }).get_json()["data"]
        api_client.post("/api/enrollments/enroll", headers=auth_headers, json={
            "student_id": s["id"], "course_id": c["id"],
        })

        resp = api_client.post("/api/grades/record", headers=auth_headers, json={
            "student_id": s["id"], "course_id": c["id"], "score": 88,
        })
        assert resp.status_code == 201
        assert resp.get_json()["data"]["letter_grade"] == "A"

    def test_get_ucas_points(self, api_client, auth_headers):
        s = api_client.post("/api/students", headers=auth_headers, json={
            "first_name": "I", "last_name": "J",
        }).get_json()["data"]
        c = api_client.post("/api/courses", headers=auth_headers, json={
            "course_code": "TEST902", "title": "Math",
        }).get_json()["data"]
        api_client.post("/api/enrollments/enroll", headers=auth_headers, json={
            "student_id": s["id"], "course_id": c["id"],
        })
        api_client.post("/api/grades/record", headers=auth_headers, json={
            "student_id": s["id"], "course_id": c["id"], "score": 95,
        })

        resp = api_client.get(f"/api/grades/student/{s['id']}/ucas-points", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["ucas_points"] == 56


class TestAttendanceAPI:
    def test_create_session(self, api_client, auth_headers):
        c = api_client.post("/api/courses", headers=auth_headers, json={
            "course_code": "TEST901", "title": "CS",
        }).get_json()["data"]

        resp = api_client.post("/api/attendance/sessions", headers=auth_headers, json={
            "course_id": c["id"], "session_date": "2026-01-15",
        })
        assert resp.status_code == 201

    def test_record_attendance(self, api_client, auth_headers):
        s = api_client.post("/api/students", headers=auth_headers, json={
            "first_name": "K", "last_name": "L",
        }).get_json()["data"]
        c = api_client.post("/api/courses", headers=auth_headers, json={
            "course_code": "TEST901", "title": "CS",
        }).get_json()["data"]
        api_client.post("/api/enrollments/enroll", headers=auth_headers, json={
            "student_id": s["id"], "course_id": c["id"],
        })
        session = api_client.post("/api/attendance/sessions", headers=auth_headers, json={
            "course_id": c["id"],
        }).get_json()["data"]

        resp = api_client.post("/api/attendance/record", headers=auth_headers, json={
            "session_id": session["id"], "student_id": s["id"], "status": "present",
        })
        assert resp.status_code == 201
