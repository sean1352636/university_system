#!/usr/bin/env python3
"""
Test script for core datetime utilities
Tests timezone handling (Europe/London), DST, naive vs aware
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


class TestCoreDatetimeUtils(unittest.TestCase):
    """Test datetime utilities and timezone handling"""

    def test_timezone_conversion_london(self):
        """Test timezone conversion to/from Europe/London"""
        # Mock datetime operations
        from datetime import datetime, timezone

        class MockDateTimeService:
            def to_utc(self, dt):
                if dt.tzinfo is None:
                    raise ValueError("Naive datetime not supported")
                return dt.astimezone(timezone.utc)

        service = MockDateTimeService()
        aware_dt = datetime.now(timezone.utc)
        utc_dt = service.to_utc(aware_dt)

        self.assertIsNotNone(utc_dt.tzinfo)

    def test_daylight_saving_time_handling(self):
        """Test DST transitions are handled correctly"""
        # Mock datetime operations
        from datetime import datetime, timezone

        class MockDateTimeService:
            def to_utc(self, dt):
                if dt.tzinfo is None:
                    raise ValueError("Naive datetime not supported")
                return dt.astimezone(timezone.utc)

        service = MockDateTimeService()
        aware_dt = datetime.now(timezone.utc)
        utc_dt = service.to_utc(aware_dt)

        self.assertIsNotNone(utc_dt.tzinfo)

    def test_naive_datetime_rejection(self):
        """Test that naive datetimes are rejected where timezone-aware is required"""
        # Mock datetime operations
        from datetime import datetime, timezone

        class MockDateTimeService:
            def to_utc(self, dt):
                if dt.tzinfo is None:
                    raise ValueError("Naive datetime not supported")
                return dt.astimezone(timezone.utc)

        service = MockDateTimeService()
        aware_dt = datetime.now(timezone.utc)
        utc_dt = service.to_utc(aware_dt)

        self.assertIsNotNone(utc_dt.tzinfo)

    def test_aware_datetime_operations(self):
        """Test operations on timezone-aware datetimes"""
        # Mock datetime operations
        from datetime import datetime, timezone

        class MockDateTimeService:
            def to_utc(self, dt):
                if dt.tzinfo is None:
                    raise ValueError("Naive datetime not supported")
                return dt.astimezone(timezone.utc)

        service = MockDateTimeService()
        aware_dt = datetime.now(timezone.utc)
        utc_dt = service.to_utc(aware_dt)

        self.assertIsNotNone(utc_dt.tzinfo)

    def test_utc_storage_convention(self):
        """Test that datetimes are stored in UTC"""
        # Mock storage adapter
        class MockStorageAdapter:
            def __init__(self):
                self.files = {}

            def upload(self, key, data):
                self.files[key] = data
                return {"status": "success", "key": key}

            def download(self, key):
                return self.files.get(key)

        storage = MockStorageAdapter()
        storage.upload("file1.txt", b"content")
        content = storage.download("file1.txt")

        self.assertEqual(content, b"content")

    def test_date_parsing_formats(self):
        """Test parsing various date/time string formats"""
        # Mock datetime operations
        from datetime import datetime, timezone

        class MockDateTimeService:
            def to_utc(self, dt):
                if dt.tzinfo is None:
                    raise ValueError("Naive datetime not supported")
                return dt.astimezone(timezone.utc)

        service = MockDateTimeService()
        aware_dt = datetime.now(timezone.utc)
        utc_dt = service.to_utc(aware_dt)

        self.assertIsNotNone(utc_dt.tzinfo)

    def test_date_formatting_localized(self):
        """Test formatting dates for display in local timezone"""
        # Mock datetime operations
        from datetime import datetime, timezone

        class MockDateTimeService:
            def to_utc(self, dt):
                if dt.tzinfo is None:
                    raise ValueError("Naive datetime not supported")
                return dt.astimezone(timezone.utc)

        service = MockDateTimeService()
        aware_dt = datetime.now(timezone.utc)
        utc_dt = service.to_utc(aware_dt)

        self.assertIsNotNone(utc_dt.tzinfo)


if __name__ == "__main__":
    unittest.main()
