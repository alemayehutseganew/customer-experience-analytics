"""
Unit tests for core data processing functions.
"""
import unittest
import sys
import os
from datetime import datetime

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from scrape_reviews import _serialize_review
from preprocess import is_english

class TestScraping(unittest.TestCase):
    def test_serialize_review(self):
        payload = {
            'content': 'Great app!',
            'score': 5,
            'at': datetime(2023, 1, 1, 12, 0, 0),
            'replyContent': None
        }
        result = _serialize_review('CBE', 'com.combanketh', payload)
        self.assertEqual(result['bank_code'], 'CBE')
        self.assertEqual(result['review'], 'Great app!')
        self.assertEqual(result['rating'], 5)
        self.assertEqual(result['date'], '2023-01-01')

class TestPreprocessing(unittest.TestCase):
    def test_is_english_basic(self):
        self.assertTrue(is_english("This is a good banking app."))
        self.assertFalse(is_english("ይህ በጣም ጥሩ ባንክ ነው።")) # Amharic
    
    def test_is_english_mixed(self):
        # Mostly English should pass
        self.assertTrue(is_english("The app is good but sometimes slow. አመሰግናለሁ"))
        # Mostly non-English should fail
        self.assertFalse(is_english("አመሰግናለሁ for the app."))

if __name__ == '__main__':
    unittest.main()
