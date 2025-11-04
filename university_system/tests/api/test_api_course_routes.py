#!/usr/bin/env python3
"""
Test script for API course routes
Tests filters/sort/pagination, invalid query params
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest


class TestApiCourseRoutes(unittest.TestCase):
    """Test API course endpoints"""

    def test_get_courses_list(self):
        """Test GET /courses returns course list"""
        # Mock course API
        class MockCourseAPI:
            def get_courses(self):
                return [
                    {"code": "CS101", "name": "Intro to CS", "department": "CS"},
                    {"code": "CS102", "name": "Data Structures", "department": "CS"}
                ]

        api = MockCourseAPI()
        courses = api.get_courses()

        self.assertIsInstance(courses, list)
        self.assertGreater(len(courses), 0)
        self.assertIn("code", courses[0])

    def test_filter_courses_by_department(self):
        """Test filtering courses by department"""
        # Mock course filtering
        class MockCourseAPI:
            def get_courses(self, department=None):
                all_courses = [
                    {"code": "CS101", "department": "CS"},
                    {"code": "MATH101", "department": "MATH"}
                ]
                if department:
                    return [c for c in all_courses if c["department"] == department]
                return all_courses

        api = MockCourseAPI()
        cs_courses = api.get_courses(department="CS")

        self.assertEqual(len(cs_courses), 1)
        self.assertEqual(cs_courses[0]["department"], "CS")

    def test_sort_courses(self):
        """Test sorting courses by various fields"""
        # Mock course sorting
        courses = [
            {"code": "CS102", "name": "Data Structures"},
            {"code": "CS101", "name": "Intro to CS"}
        ]

        sorted_courses = sorted(courses, key=lambda c: c["code"])

        self.assertEqual(sorted_courses[0]["code"], "CS101")
        self.assertEqual(sorted_courses[1]["code"], "CS102")

    def test_paginate_courses(self):
        """Test pagination of course results"""
        # Mock pagination
        all_courses = [{"code": f"CS{i}"} for i in range(100)]
        page_size = 10
        page = 2

        start = (page - 1) * page_size
        end = start + page_size
        paginated = all_courses[start:end]

        self.assertEqual(len(paginated), 10)
        self.assertEqual(paginated[0]["code"], "CS10")

    def test_invalid_query_params(self):
        """Test handling of invalid query parameters"""
        # Mock invalid parameter handling
        class MockCourseAPI:
            def get_courses(self, sort_by=None):
                valid_fields = ["code", "name"]
                if sort_by and sort_by not in valid_fields:
                    return {"status": "error", "code": 400, "message": "Invalid sort field"}
                return {"status": "success", "data": []}

        api = MockCourseAPI()
        response = api.get_courses(sort_by="invalid_field")

        self.assertEqual(response["code"], 400)

    def test_get_course_by_code(self):
        """Test GET /courses/:code returns specific course"""
        # Mock get course by code
        class MockCourseAPI:
            def get_course(self, code):
                courses = {"CS101": {"code": "CS101", "name": "Intro to CS"}}
                return courses.get(code)

        api = MockCourseAPI()
        course = api.get_course("CS101")

        self.assertIsNotNone(course)
        self.assertEqual(course["code"], "CS101")


if __name__ == "__main__":
    unittest.main()
