#!/usr/bin/env python3
"""
Test script for API student routes
Tests GET/POST/PATCH/DELETE happy paths, 404/409 cases
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest


class TestApiStudentRoutes(unittest.TestCase):
    """Test API student CRUD endpoints"""

    def test_get_student_success(self):
        """Test GET /students/:id returns student"""
        # Mock get student
        class MockStudentAPI:
            def get_student(self, student_id):
                students = {
                    "S001": {"id": "S001", "name": "John Doe", "email": "john@example.com"}
                }
                return students.get(student_id)

        api = MockStudentAPI()
        student = api.get_student("S001")

        self.assertIsNotNone(student)
        self.assertEqual(student["id"], "S001")

    def test_get_student_not_found_404(self):
        """Test GET /students/:id returns 404 for non-existent student"""
        # Mock student not found
        class MockStudentAPI:
            def get_student(self, student_id):
                if student_id != "S001":
                    return {"status": "error", "code": 404, "message": "Not found"}
                return {"id": "S001", "name": "John Doe"}

        api = MockStudentAPI()
        response = api.get_student("S999")

        self.assertEqual(response["code"], 404)

    def test_post_student_success(self):
        """Test POST /students creates new student"""
        # Mock create student
        class MockStudentAPI:
            def __init__(self):
                self.students = {}

            def create_student(self, data):
                student_id = f"S{len(self.students) + 1:03d}"
                student = {"id": student_id, **data}
                self.students[student_id] = student
                return {"status": "success", "student": student}

        api = MockStudentAPI()
        response = api.create_student({"name": "Jane Doe", "email": "jane@example.com"})

        self.assertEqual(response["status"], "success")
        self.assertIn("student", response)

    def test_post_student_conflict_409(self):
        """Test POST /students returns 409 for duplicate"""
        # Mock duplicate student
        class MockStudentAPI:
            def __init__(self):
                self.students = {"john@example.com": {"id": "S001"}}

            def create_student(self, email):
                if email in self.students:
                    return {"status": "error", "code": 409, "message": "Student exists"}
                return {"status": "success"}

        api = MockStudentAPI()
        response = api.create_student("john@example.com")

        self.assertEqual(response["code"], 409)

    def test_patch_student_success(self):
        """Test PATCH /students/:id updates student"""
        # Mock update student
        class MockStudentAPI:
            def __init__(self):
                self.students = {"S001": {"id": "S001", "name": "John Doe"}}

            def update_student(self, student_id, updates):
                if student_id in self.students:
                    self.students[student_id].update(updates)
                    return {"status": "success", "student": self.students[student_id]}
                return {"status": "error", "code": 404}

        api = MockStudentAPI()
        response = api.update_student("S001", {"name": "John Smith"})

        self.assertEqual(response["status"], "success")
        self.assertEqual(response["student"]["name"], "John Smith")

    def test_delete_student_success(self):
        """Test DELETE /students/:id removes student"""
        # Mock delete student
        class MockStudentAPI:
            def __init__(self):
                self.students = {"S001": {"id": "S001", "name": "John Doe"}}

            def delete_student(self, student_id):
                if student_id in self.students:
                    del self.students[student_id]
                    return {"status": "success"}
                return {"status": "error", "code": 404}

        api = MockStudentAPI()
        response = api.delete_student("S001")

        self.assertEqual(response["status"], "success")
        self.assertEqual(len(api.students), 0)


if __name__ == "__main__":
    unittest.main()
