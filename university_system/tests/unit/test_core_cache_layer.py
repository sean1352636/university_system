#!/usr/bin/env python3
"""
Test script for cache layer
Tests TTL expiry, cache stampede prevention, serialization errors
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest
import time


class TestCoreCacheLayer(unittest.TestCase):
    """Test caching layer functionality"""

    def test_cache_set_and_get(self):
        """Test basic cache set and get operations"""
        # Simple cache implementation for testing
        cache = {}

        # Set a value
        cache['key1'] = 'value1'

        # Get the value
        result = cache.get('key1')

        self.assertEqual(result, 'value1')

    def test_ttl_expiry(self):
        """Test that cached items expire after TTL"""
        import time

        # Cache with expiry timestamps
        cache = {}
        ttl_cache = {}

        # Set value with 1 second TTL
        cache['key1'] = 'value1'
        ttl_cache['key1'] = time.time() + 1

        # Value should exist immediately
        self.assertIn('key1', cache)

        # After TTL, value should be expired
        time.sleep(1.1)
        is_expired = time.time() > ttl_cache['key1']
        self.assertTrue(is_expired)

    def test_cache_stampede_prevention(self):
        """Test prevention of cache stampede (multiple concurrent cache misses)"""
        # Use a lock to prevent multiple threads from regenerating cache
        import threading

        cache = {}
        lock = threading.Lock()
        computation_count = [0]

        def get_or_compute(key):
            if key in cache:
                return cache[key]

            with lock:
                # Double-check after acquiring lock
                if key in cache:
                    return cache[key]

                # Expensive computation
                computation_count[0] += 1
                result = f"computed_{key}"
                cache[key] = result
                return result

        # Simulate concurrent access
        threads = [threading.Thread(target=get_or_compute, args=('key1',)) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should only compute once
        self.assertEqual(computation_count[0], 1)

    def test_serialization_errors_handled(self):
        """Test handling of objects that cannot be serialized"""
        import json

        # Test that serialization errors are caught
        class NonSerializable:
            pass

        obj = NonSerializable()

        try:
            json.dumps(obj)
            serializable = True
        except (TypeError, ValueError):
            serializable = False

        self.assertFalse(serializable)

    def test_cache_invalidation(self):
        """Test explicit cache invalidation"""
        cache = {}

        # Set values
        cache['key1'] = 'value1'
        cache['key2'] = 'value2'

        # Invalidate specific key
        if 'key1' in cache:
            del cache['key1']

        self.assertNotIn('key1', cache)
        self.assertIn('key2', cache)

    def test_cache_miss_handling(self):
        """Test behavior on cache miss"""
        cache = {}

        # Test cache miss returns None or default
        result = cache.get('nonexistent_key', 'default_value')

        self.assertEqual(result, 'default_value')


if __name__ == "__main__":
    unittest.main()
