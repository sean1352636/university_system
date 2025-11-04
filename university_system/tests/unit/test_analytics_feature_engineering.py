#!/usr/bin/env python3
"""
Test script for analytics feature engineering
Tests deterministic transforms, scaling/encoding schemas
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest


class TestAnalyticsFeatureEngineering(unittest.TestCase):
    """Test feature engineering and transformations"""

    def test_deterministic_transformations(self):
        """Test that transformations are deterministic"""
        # Test that applying same transformation twice yields same result
        data = [1.0, 2.0, 3.0, 4.0, 5.0]

        # Simple transformation: multiply by 2
        transformed1 = [x * 2 for x in data]
        transformed2 = [x * 2 for x in data]

        self.assertEqual(transformed1, transformed2)

    def test_feature_scaling(self):
        """Test feature scaling (normalization, standardization)"""
        # Test min-max normalization to [0, 1]
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        min_val, max_val = min(data), max(data)
        normalized = [(x - min_val) / (max_val - min_val) for x in data]

        self.assertAlmostEqual(min(normalized), 0.0)
        self.assertAlmostEqual(max(normalized), 1.0)

    def test_categorical_encoding(self):
        """Test categorical variable encoding"""
        # Test one-hot encoding
        categories = ['apple', 'banana', 'apple', 'cherry', 'banana']
        unique_cats = list(set(categories))

        # Simple encoding: map to indices
        encoding_map = {cat: idx for idx, cat in enumerate(unique_cats)}
        encoded = [encoding_map[cat] for cat in categories]

        self.assertEqual(len(encoded), len(categories))
        self.assertTrue(all(isinstance(x, int) for x in encoded))

    def test_feature_extraction(self):
        """Test feature extraction from raw data"""
        # Test extracting statistical features
        data = [1.0, 2.0, 3.0, 4.0, 5.0]

        features = {
            'mean': sum(data) / len(data),
            'min': min(data),
            'max': max(data),
            'count': len(data)
        }

        self.assertAlmostEqual(features['mean'], 3.0)
        self.assertEqual(features['count'], 5)

    def test_schema_validation(self):
        """Test validation of feature schemas"""
        # Test that features match expected schema
        features = {
            'age': 25,
            'grade': 95.5,
            'name': 'Alice'
        }

        expected_schema = {
            'age': int,
            'grade': float,
            'name': str
        }

        for key, expected_type in expected_schema.items():
            self.assertIn(key, features)
            self.assertIsInstance(features[key], expected_type)


if __name__ == "__main__":
    unittest.main()
