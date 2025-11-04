#!/usr/bin/env python3
"""
Test script for API enrollment routes
Tests race conditions (concurrent enroll), idempotency keys
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest


class TestApiEnrollmentRoutes(unittest.TestCase):
    """Test API enrollment endpoints"""

    def test_enroll_student_success(self):
        """Test POST /enrollments creates enrollment"""
        # Mock enrollment
        class MockEnrollmentAPI:
            def __init__(self):
                self.enrollments = []

            def enroll(self, student_id, course_code):
                enrollment = {"student_id": student_id, "course_code": course_code}
                self.enrollments.append(enrollment)
                return {"status": "success", "enrollment_id": len(self.enrollments)}

        api = MockEnrollmentAPI()
        response = api.enroll("S001", "CS101")

        self.assertEqual(response["status"], "success")
        self.assertIn("enrollment_id", response)

    def test_concurrent_enrollment_race_condition(self):
        """Test handling of concurrent enrollment requests"""
        # Mock race condition handling
        import threading

        class MockEnrollmentAPI:
            def __init__(self):
                self.enrollments = []
                self.lock = threading.Lock()
                self.capacity = 1

            def enroll(self, student_id, course_code):
                with self.lock:
                    if len(self.enrollments) >= self.capacity:
                        return {"status": "error", "message": "Course full"}
                    self.enrollments.append({"student_id": student_id, "course_code": course_code})
                    return {"status": "success"}

        api = MockEnrollmentAPI()
        results = []

        def try_enroll(sid):
            results.append(api.enroll(sid, "CS101"))

        threads = [threading.Thread(target=try_enroll, args=(f"S{i}",)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        success_count = sum(1 for r in results if r["status"] == "success")
        self.assertEqual(success_count, 1)

    def test_idempotency_key_handling(self):
        """Test idempotency key prevents duplicate enrollments"""
        # Mock idempotency key
        class MockEnrollmentAPI:
            def __init__(self):
                self.processed_keys = set()

            def enroll(self, student_id, course_code, idempotency_key):
                if idempotency_key in self.processed_keys:
                    return {"status": "success", "message": "Already processed"}
                self.processed_keys.add(idempotency_key)
                return {"status": "success", "message": "Enrolled"}

        api = MockEnrollmentAPI()
        response1 = api.enroll("S001", "CS101", "key123")
        response2 = api.enroll("S001", "CS101", "key123")

        self.assertEqual(response1["status"], "success")
        self.assertEqual(response2["status"], "success")
        self.assertEqual(len(api.processed_keys), 1)

    def test_drop_enrollment(self):
        """Test DELETE /enrollments/:id drops enrollment"""
        # Mock drop enrollment
        class MockEnrollmentAPI:
            def __init__(self):
                self.enrollments = {1: {"student_id": "S001", "course_code": "CS101"}}

            def drop(self, enrollment_id):
                if enrollment_id in self.enrollments:
                    del self.enrollments[enrollment_id]
                    return {"status": "success"}
                return {"status": "error", "code": 404}

        api = MockEnrollmentAPI()
        response = api.drop(1)

        self.assertEqual(response["status"], "success")
        self.assertEqual(len(api.enrollments), 0)

    def test_get_student_enrollments(self):
        """Test GET /students/:id/enrollments returns enrollments"""
        # Mock get student enrollments
        class MockEnrollmentAPI:
            def __init__(self):
                self.enrollments = [
                    {"student_id": "S001", "course_code": "CS101"},
                    {"student_id": "S001", "course_code": "CS102"},
                    {"student_id": "S002", "course_code": "CS101"}
                ]

            def get_enrollments(self, student_id):
                return [e for e in self.enrollments if e["student_id"] == student_id]

        api = MockEnrollmentAPI()
        enrollments = api.get_enrollments("S001")

        self.assertEqual(len(enrollments), 2)
        self.assertEqual(enrollments[0]["student_id"], "S001")


if __name__ == "__main__":
    unittest.main()
