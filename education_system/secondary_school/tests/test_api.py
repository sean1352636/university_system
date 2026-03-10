"""Tests for the Secondary School REST API."""

import pytest


class TestHealthEndpoint:
    def test_health_check(self, api_client):
        response = api_client.get("/api/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "healthy"

    def test_system_info(self, api_client):
        response = api_client.get("/api/info")
        assert response.status_code == 200
        data = response.get_json()
        assert "Secondary School" in data["name"]


class TestAuthAPI:
    def test_login(self, api_client):
        response = api_client.post("/api/auth/login", json={
            "username": "admin2",
            "password": "admin1234",
        })
        assert response.status_code == 200
        data = response.get_json()
        assert "token" in data
        assert any(
            s["role"] == "admin"
            for s in data["user"]["systems"]
        )

    def test_login_invalid(self, api_client):
        response = api_client.post("/api/auth/login", json={
            "username": "admin2",
            "password": "WrongPass@1",
        })
        assert response.status_code == 401

    def test_login_missing_fields(self, api_client):
        response = api_client.post("/api/auth/login", json={"username": "admin2"})
        assert response.status_code == 400

    def test_register(self, api_client):
        response = api_client.post("/api/auth/register", json={
            "username": "newteacher",
            "password": "Teacher@456",
            "role": "teacher",
        })
        assert response.status_code == 201


class TestStudentAPI:
    def test_list_students_requires_auth(self, api_client):
        response = api_client.get("/api/students")
        assert response.status_code == 401

    def test_create_and_list_students(self, api_client, auth_headers):
        # Create
        response = api_client.post("/api/students", json={
            "first_name": "Test", "last_name": "Student", "year_group": "9",
        }, headers=auth_headers)
        assert response.status_code == 201
        student = response.get_json()["data"]
        assert student["first_name"] == "Test"

        # List
        response = api_client.get("/api/students", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["pagination"]["total"] >= 1

    def test_get_student(self, api_client, auth_headers):
        create = api_client.post("/api/students", json={
            "first_name": "Get", "last_name": "Me",
        }, headers=auth_headers)
        pk = create.get_json()["data"]["id"]

        response = api_client.get(f"/api/students/{pk}", headers=auth_headers)
        assert response.status_code == 200
        assert response.get_json()["data"]["first_name"] == "Get"

    def test_get_student_not_found(self, api_client, auth_headers):
        response = api_client.get("/api/students/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_update_student(self, api_client, auth_headers):
        create = api_client.post("/api/students", json={
            "first_name": "Old", "last_name": "Name",
        }, headers=auth_headers)
        pk = create.get_json()["data"]["id"]

        response = api_client.put(f"/api/students/{pk}", json={
            "first_name": "New",
        }, headers=auth_headers)
        assert response.status_code == 200
        assert response.get_json()["data"]["first_name"] == "New"

    def test_delete_student(self, api_client, auth_headers):
        create = api_client.post("/api/students", json={
            "first_name": "Del", "last_name": "Ete",
        }, headers=auth_headers)
        pk = create.get_json()["data"]["id"]

        response = api_client.delete(f"/api/students/{pk}", headers=auth_headers)
        assert response.status_code == 200


class TestSubjectAPI:
    def test_create_and_get_subject(self, api_client, auth_headers):
        response = api_client.post("/api/subjects", json={
            "subject_code": "ENG01", "title": "English Literature",
            "department": "English", "key_stage": "KS4",
        }, headers=auth_headers)
        assert response.status_code == 201
        subject = response.get_json()["data"]
        assert subject["subject_code"] == "ENG01"

        response = api_client.get(f"/api/subjects/{subject['id']}", headers=auth_headers)
        assert response.status_code == 200

    def test_get_subject_by_code(self, api_client, auth_headers):
        api_client.post("/api/subjects", json={
            "subject_code": "HIS01", "title": "History",
        }, headers=auth_headers)

        response = api_client.get("/api/subjects/by-code/HIS01", headers=auth_headers)
        assert response.status_code == 200
        assert response.get_json()["data"]["title"] == "History"


class TestEnrollmentAPI:
    def test_enroll_and_list(self, api_client, auth_headers):
        # Create student and subject
        s_resp = api_client.post("/api/students", json={
            "first_name": "Enr", "last_name": "Oll",
        }, headers=auth_headers)
        student_pk = s_resp.get_json()["data"]["id"]

        sub_resp = api_client.post("/api/subjects", json={
            "subject_code": "ART01", "title": "Art",
        }, headers=auth_headers)
        subject_pk = sub_resp.get_json()["data"]["id"]

        # Enroll
        response = api_client.post("/api/enrollments", json={
            "student_id": student_pk, "subject_id": subject_pk,
        }, headers=auth_headers)
        assert response.status_code == 201

        # List student enrollments
        response = api_client.get(f"/api/enrollments/student/{student_pk}", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.get_json()["data"]) == 1


class TestGradeAPI:
    def test_add_and_get_grades(self, api_client, auth_headers):
        s = api_client.post("/api/students", json={
            "first_name": "Gr", "last_name": "Ade",
        }, headers=auth_headers).get_json()["data"]
        sub = api_client.post("/api/subjects", json={
            "subject_code": "SCI01", "title": "Science",
        }, headers=auth_headers).get_json()["data"]
        api_client.post("/api/enrollments", json={
            "student_id": s["id"], "subject_id": sub["id"],
        }, headers=auth_headers)

        response = api_client.post("/api/grades", json={
            "student_id": s["id"], "subject_id": sub["id"],
            "score": 85.0, "grade": "8", "term": "Autumn",
        }, headers=auth_headers)
        assert response.status_code == 201

        response = api_client.get(f"/api/grades/student/{s['id']}", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.get_json()["data"]) == 1


class TestAttendanceAPI:
    def test_record_and_get_attendance(self, api_client, auth_headers):
        s = api_client.post("/api/students", json={
            "first_name": "Att", "last_name": "End",
        }, headers=auth_headers).get_json()["data"]

        response = api_client.post("/api/attendance", json={
            "student_id": s["id"], "date": "2026-01-15",
            "status": "present", "period": "AM",
        }, headers=auth_headers)
        assert response.status_code == 201

        response = api_client.get(f"/api/attendance/student/{s['id']}", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.get_json()["data"]) == 1

    def test_attendance_summary(self, api_client, auth_headers):
        s = api_client.post("/api/students", json={
            "first_name": "Sum", "last_name": "Mary",
        }, headers=auth_headers).get_json()["data"]

        response = api_client.get(f"/api/attendance/student/{s['id']}/summary", headers=auth_headers)
        assert response.status_code == 200
        assert response.get_json()["data"]["total"] == 0
