# Standard library imports
import os
import re
import time
import hashlib
import json
import random
import pickle
import uuid
import base64
import logging
import traceback
import threading
import statistics
import math
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from logging.handlers import RotatingFileHandler
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

# Configure logging first using the centralized logging config
from university_system.utils.logging.log_config import configure_logging

# Setup logger using the centralized configuration
logger = configure_logging(name="ai_detector")

# Application imports
from university_system.infrastructure.database.db import sqlite3, DatabaseManager
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from university_system.infrastructure.auth.user_authentication import UserAuth

# Handle optional dependencies with proper error handling
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("requests library not available. External API features will be disabled.")

try:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.ensemble import RandomForestClassifier, IsolationForest
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, classification_report
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("scikit-learn not available. ML features will be disabled.")

try:
    import langdetect
    from langdetect import detect_langs
    LANG_DETECT_AVAILABLE = True
except ImportError:
    LANG_DETECT_AVAILABLE = False
    logger.warning("langdetect not available. Language detection will be disabled.")

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    logger.warning("spaCy not available. Advanced NLP features will be disabled.")

try:
    import transformers
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("transformers not available. Advanced AI detection will be disabled.")

try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("OCR libraries not available. Image analysis will be disabled.")

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    logger.warning("OpenCV not available. Advanced image analysis will be disabled.")

# Enums and Data Classes
class DetectionMethod(Enum):
    PATTERN_MATCHING = "pattern_matching"
    STATISTICAL_ANALYSIS = "statistical_analysis"
    BEHAVIORAL_ANALYSIS = "behavioral_analysis"
    TEMPORAL_ANALYSIS = "temporal_analysis"
    CITATION_VERIFICATION = "citation_verification"
    MULTI_MODAL = "multi_modal"
    ENSEMBLE_API = "ensemble_api"
    ML_MODEL = "ml_model"
    STYLE_DEVIATION = "style_deviation"
    SENTENCE_ANALYSIS = "sentence_analysis"
    ADVERSARIAL_DETECTION = "adversarial_detection"

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ViolationType(Enum):
    AI_GENERATED = "ai_generated_content"
    SUSPICIOUS_BEHAVIOR = "suspicious_behavior"
    CITATION_FRAUD = "citation_fraud"
    TEMPORAL_ANOMALY = "temporal_anomaly"
    COLLABORATION = "unauthorized_collaboration"

@dataclass
class DetectionResult:
    method: DetectionMethod
    score: float
    confidence: float
    evidence: Dict[str, Any]
    risk_level: RiskLevel

@dataclass
class SubmissionMetadata:
    timestamp: datetime
    time_taken: Optional[int]  # seconds
    browser_info: Optional[Dict]
    device_fingerprint: Optional[str]
    ip_address: Optional[str]
    location: Optional[Dict]

# Exception Classes
class AIDetectionError(Exception):
    """Base exception for AI detection errors"""
    def __init__(self, message="An error occurred in the AI detection system"):
        self.message = message
        super().__init__(self.message)

class DatabaseError(AIDetectionError):
    """Exception raised for database connection/query errors"""
    def __init__(self, message="Database error occurred", query=None):
        self.query = query
        if query:
            message = f"{message} (Query: {query})"
        super().__init__(message)

class APIError(AIDetectionError):
    """Exception raised for API-related errors"""
    def __init__(self, message="API error occurred", status_code=None):
        self.status_code = status_code
        if status_code:
            message = f"{message} (Status code: {status_code})"
        super().__init__(message)

class ConfigurationError(AIDetectionError):
    """Exception raised for configuration errors"""
    def __init__(self, message="Configuration error occurred", setting=None):
        self.setting = setting
        if setting:
            message = f"{message} (Setting: {setting})"
        super().__init__(message)

class PrivacyError(AIDetectionError):
    """Exception raised for privacy violations"""
    pass

# Advanced Analysis Classes

class TemporalAnalyzer:
    """Analyzes temporal patterns in submissions"""
    
    def __init__(self, detector_instance):
        self.detector = detector_instance
    
    def analyze_writing_speed(self, text: str, time_taken: Optional[int]) -> DetectionResult:
        """Analyze writing speed vs complexity"""
        if not time_taken or time_taken <= 0:
            return DetectionResult(
                method=DetectionMethod.TEMPORAL_ANALYSIS,
                score=0,
                confidence=0,
                evidence={'reason': 'No timing data available'},
                risk_level=RiskLevel.LOW
            )
        
        word_count = len(text.split())
        wpm = (word_count / time_taken) * 60
        
        # Calculate text complexity
        complexity = self._calculate_complexity(text)
        
        # Expected WPM ranges based on complexity
        if complexity < 0.3:  # Simple text
            expected_wpm = (20, 60)
        elif complexity < 0.6:  # Medium complexity
            expected_wpm = (15, 45)
        else:  # High complexity
            expected_wpm = (10, 30)
        
        score = 0
        evidence = {
            'words_per_minute': wpm,
            'complexity_score': complexity,
            'expected_wpm_range': expected_wpm
        }
        
        if wpm > expected_wpm[1] * 2:  # Significantly faster than expected
            score = min(1.0, (wpm - expected_wpm[1]) / expected_wpm[1])
            evidence['anomaly'] = 'Writing speed too fast for complexity level'
        
        risk_level = RiskLevel.HIGH if score > 0.7 else RiskLevel.MEDIUM if score > 0.4 else RiskLevel.LOW
        
        return DetectionResult(
            method=DetectionMethod.TEMPORAL_ANALYSIS,
            score=score,
            confidence=0.8 if time_taken > 300 else 0.5,  # More confident with longer timing data
            evidence=evidence,
            risk_level=risk_level
        )
    
    def analyze_submission_patterns(self, student_id: str) -> Dict[str, Any]:
        """Analyze student's submission time patterns"""
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT submission_date, word_count 
            FROM ai_detector_submissions 
            WHERE student_id = ?
            ORDER BY submission_date DESC
            LIMIT 20
            ''', (student_id,))
            
            submissions = cursor.fetchall()
            conn.close()
            
            if len(submissions) < 3:
                return {'insufficient_data': True}
            
            # Analyze time patterns
            hours = []
            intervals = []
            
            for i, sub in enumerate(submissions):
                dt = datetime.fromisoformat(sub['submission_date'])
                hours.append(dt.hour)
                
                if i > 0:
                    prev_dt = datetime.fromisoformat(submissions[i-1]['submission_date'])
                    interval = (dt - prev_dt).total_seconds() / 3600  # hours
                    intervals.append(interval)
            
            # Check for suspicious patterns
            suspicious_hours = sum(1 for h in hours if h < 6 or h > 23)  # Late night submissions
            regular_intervals = len([i for i in intervals if 23.5 <= i <= 24.5])  # Exactly 24h apart
            
            return {
                'total_submissions': len(submissions),
                'suspicious_hour_ratio': suspicious_hours / len(submissions),
                'regular_interval_count': regular_intervals,
                'avg_hour': sum(hours) / len(hours),
                'hour_variance': statistics.variance(hours) if len(hours) > 1 else 0
            }
            
        except Exception as e:
            logger.error(f"Error analyzing submission patterns: {e}")
            return {'error': str(e)}
    
    def _calculate_complexity(self, text: str) -> float:
        """Calculate text complexity score"""
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return 0
        
        words = text.split()
        
        # Average sentence length
        avg_sentence_length = len(words) / len(sentences)
        
        # Syllable complexity
        complex_words = sum(1 for word in words if self._count_syllables(word) > 2)
        complex_ratio = complex_words / len(words) if words else 0
        
        # Punctuation complexity
        punctuation_count = len(re.findall(r'[,;:()"]', text))
        punctuation_ratio = punctuation_count / len(text)
        
        # Combine metrics
        complexity = (
            min(1, avg_sentence_length / 20) * 0.4 +
            complex_ratio * 0.4 +
            min(1, punctuation_ratio * 100) * 0.2
        )
        
        return complexity
    
    def _count_syllables(self, word: str) -> int:
        """Count syllables in a word"""
        word = word.lower()
        vowels = 'aeiouy'
        syllable_count = 0
        prev_was_vowel = False
        
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_was_vowel:
                syllable_count += 1
            prev_was_vowel = is_vowel
        
        if word.endswith('e'):
            syllable_count -= 1
        
        return max(1, syllable_count)

class CitationVerifier:
    """Verifies citations and references"""
    
    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.api_endpoints = {
            'crossref': 'https://api.crossref.org/works',
            'openalex': 'https://api.openalex.org/works',
            'semantic_scholar': 'https://api.semanticscholar.org/graph/v1/paper/search'
        }
    
    def verify_citations(self, text: str) -> DetectionResult:
        """Verify citations in text"""
        citations = self._extract_citations(text)
        
        if not citations:
            return DetectionResult(
                method=DetectionMethod.CITATION_VERIFICATION,
                score=0,
                confidence=0.3,
                evidence={'reason': 'No citations found'},
                risk_level=RiskLevel.LOW
            )
        
        verification_results = []
        suspicious_count = 0
        
        for citation in citations:
            result = self._verify_single_citation(citation)
            verification_results.append(result)
            
            if not result['exists'] or result['suspicious']:
                suspicious_count += 1
        
        # Calculate score based on suspicious citations
        suspicious_ratio = suspicious_count / len(citations)
        score = suspicious_ratio
        
        risk_level = (RiskLevel.HIGH if suspicious_ratio > 0.5 else 
                     RiskLevel.MEDIUM if suspicious_ratio > 0.2 else 
                     RiskLevel.LOW)
        
        return DetectionResult(
            method=DetectionMethod.CITATION_VERIFICATION,
            score=score,
            confidence=0.9,
            evidence={
                'total_citations': len(citations),
                'suspicious_citations': suspicious_count,
                'suspicious_ratio': suspicious_ratio,
                'citation_details': verification_results
            },
            risk_level=risk_level
        )
    
    def _extract_citations(self, text: str) -> List[str]:
        """Extract citations from text"""
        # Pattern for common citation formats
        patterns = [
            r'\([^)]*\d{4}[^)]*\)',  # (Author, 2023)
            r'\[[^\]]*\d{4}[^\]]*\]',  # [Author, 2023]
            r'(?:doi:|DOI:)\s*[\w\./\-]+',  # DOI references
            r'https?://[^\s]+',  # URLs
        ]
        
        citations = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            citations.extend(matches)
        
        return list(set(citations))  # Remove duplicates
    
    def _verify_single_citation(self, citation: str) -> Dict[str, Any]:
        """Verify a single citation"""
        result = {
            'citation': citation,
            'exists': False,
            'suspicious': False,
            'details': {}
        }
        
        if not REQUESTS_AVAILABLE:
            result['details']['error'] = 'Requests library not available'
            return result
        
        try:
            # Extract potential DOI
            doi_match = re.search(r'10\.\d+/[^\s]+', citation)
            if doi_match:
                doi = doi_match.group()
                result['exists'] = self._verify_doi(doi)
                return result
            
            # Extract year
            year_match = re.search(r'\b(19|20)\d{2}\b', citation)
            if year_match:
                year = year_match.group()
                
                # Check if year is in the future
                current_year = datetime.now().year
                if int(year) > current_year:
                    result['suspicious'] = True
                    result['details']['reason'] = 'Future publication date'
            
            # For now, assume other citations exist (would need specific API implementations)
            result['exists'] = True
            
        except Exception as e:
            result['details']['error'] = str(e)
        
        return result
    
    def _verify_doi(self, doi: str) -> bool:
        """Verify DOI exists"""
        try:
            response = requests.get(f"https://doi.org/{doi}", timeout=10, allow_redirects=False)
            return response.status_code in [200, 301, 302]
        except:
            return False

class BehavioralAnalyzer:
    """Analyzes behavioral patterns during submission"""
    
    def __init__(self, detector_instance):
        self.detector = detector_instance
    
    def analyze_submission_behavior(self, metadata: SubmissionMetadata, text: str) -> DetectionResult:
        """Analyze behavioral patterns"""
        score = 0
        evidence = {}
        
        # Analyze browser behavior if available
        if metadata.browser_info:
            browser_score = self._analyze_browser_behavior(metadata.browser_info)
            score += browser_score * 0.3
            evidence['browser_analysis'] = browser_score
        
        # Analyze device patterns
        if metadata.device_fingerprint:
            device_score = self._analyze_device_patterns(metadata.device_fingerprint)
            score += device_score * 0.2
            evidence['device_analysis'] = device_score
        
        # Analyze timing patterns
        if metadata.timestamp:
            timing_score = self._analyze_timing_patterns(metadata.timestamp)
            score += timing_score * 0.3
            evidence['timing_analysis'] = timing_score
        
        # Analyze text entry patterns
        text_entry_score = self._analyze_text_entry_patterns(text)
        score += text_entry_score * 0.2
        evidence['text_entry_analysis'] = text_entry_score
        
        risk_level = (RiskLevel.HIGH if score > 0.7 else 
                     RiskLevel.MEDIUM if score > 0.4 else 
                     RiskLevel.LOW)
        
        return DetectionResult(
            method=DetectionMethod.BEHAVIORAL_ANALYSIS,
            score=min(1.0, score),
            confidence=0.6,
            evidence=evidence,
            risk_level=risk_level
        )
    
    def _analyze_browser_behavior(self, browser_info: Dict) -> float:
        """Analyze browser behavior patterns"""
        score = 0
        
        # Check for tab switching patterns
        if 'tab_switches' in browser_info:
            tab_switches = browser_info['tab_switches']
            if tab_switches > 50:  # Excessive tab switching
                score += 0.3
        
        # Check for copy-paste events
        if 'paste_events' in browser_info:
            paste_events = browser_info['paste_events']
            text_length = browser_info.get('text_length', 1)
            paste_ratio = paste_events / max(1, text_length / 100)
            if paste_ratio > 0.5:  # High paste to text ratio
                score += 0.4
        
        # Check for suspicious extensions
        if 'extensions' in browser_info:
            suspicious_extensions = ['ai-assistant', 'grammarly', 'chatgpt']
            for ext in browser_info['extensions']:
                if any(sus in ext.lower() for sus in suspicious_extensions):
                    score += 0.2
        
        return min(1.0, score)
    
    def _analyze_device_patterns(self, device_fingerprint: str) -> float:
        """Analyze device usage patterns"""
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()
            
            # Check if device is used by multiple students
            cursor.execute('''
            SELECT COUNT(DISTINCT student_id) as student_count
            FROM ai_detector_submissions s
            JOIN ai_detector_metadata m ON s.id = m.submission_id
            WHERE m.device_fingerprint = ?
            ''', (device_fingerprint,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result and result['student_count'] > 3:
                return 0.6  # Multiple students using same device
            
        except Exception as e:
            logger.debug(f"Error analyzing device patterns: {e}")
        
        return 0
    
    def _analyze_timing_patterns(self, timestamp: datetime) -> float:
        """Analyze submission timing patterns"""
        hour = timestamp.hour
        
        # Suspicious hours (very late night/early morning)
        if hour < 5 or hour > 23:
            return 0.3
        
        # Check if it's a weekend (might be suspicious for assignments)
        if timestamp.weekday() >= 5:  # Saturday or Sunday
            return 0.1
        
        return 0
    
    def _analyze_text_entry_patterns(self, text: str) -> float:
        """Analyze text entry patterns"""
        # Look for perfect formatting (no typos, perfect spacing)
        words = text.split()
        
        # Check for absence of common typos
        typo_indicators = ['teh', 'adn', 'youre', 'its']  # Would be more comprehensive
        typo_count = sum(1 for word in words if word.lower() in typo_indicators)
        
        # Very long text with no typos might be suspicious
        if len(words) > 500 and typo_count == 0:
            return 0.2
        
        return 0

class MultiModalAnalyzer:
    """Analyzes submissions with multiple content types"""
    
    def __init__(self, detector_instance):
        self.detector = detector_instance
    
    def analyze_image_text_consistency(self, text: str, images: List[bytes]) -> DetectionResult:
        """Analyze consistency between text and images"""
        if not OCR_AVAILABLE or not images:
            return DetectionResult(
                method=DetectionMethod.MULTI_MODAL,
                score=0,
                confidence=0,
                evidence={'reason': 'OCR not available or no images'},
                risk_level=RiskLevel.LOW
            )
        
        try:
            extracted_texts = []
            for img_data in images:
                img_text = self._extract_text_from_image(img_data)
                if img_text:
                    extracted_texts.append(img_text)
            
            if not extracted_texts:
                return DetectionResult(
                    method=DetectionMethod.MULTI_MODAL,
                    score=0,
                    confidence=0.3,
                    evidence={'reason': 'No text found in images'},
                    risk_level=RiskLevel.LOW
                )
            
            # Compare extracted text with submission text
            consistency_score = self._calculate_text_similarity(text, ' '.join(extracted_texts))
            
            # Low consistency might indicate copy-paste from images
            score = 1 - consistency_score if consistency_score < 0.3 else 0
            
            risk_level = RiskLevel.HIGH if score > 0.7 else RiskLevel.MEDIUM if score > 0.4 else RiskLevel.LOW
            
            return DetectionResult(
                method=DetectionMethod.MULTI_MODAL,
                score=score,
                confidence=0.7,
                evidence={
                    'extracted_texts': extracted_texts,
                    'consistency_score': consistency_score,
                    'image_count': len(images)
                },
                risk_level=risk_level
            )
            
        except Exception as e:
            logger.error(f"Error in multi-modal analysis: {e}")
            return DetectionResult(
                method=DetectionMethod.MULTI_MODAL,
                score=0,
                confidence=0,
                evidence={'error': str(e)},
                risk_level=RiskLevel.LOW
            )
    
    def analyze_code_submission(self, code: str, language: str) -> DetectionResult:
        """Analyze code submissions for AI patterns"""
        # AI-generated code patterns
        ai_patterns = {
            'python': [
                r'# This is a comment explaining the code',
                r'def main\(\):',
                r'if __name__ == "__main__":',
                r'# TODO: implement this function',
                r'# Example usage:'
            ],
            'java': [
                r'// This is a comment explaining the code',
                r'public static void main\(String\[\] args\)',
                r'// TODO: implement this method'
            ]
        }
        
        score = 0
        patterns_found = []
        
        if language.lower() in ai_patterns:
            for pattern in ai_patterns[language.lower()]:
                if re.search(pattern, code):
                    score += 0.2
                    patterns_found.append(pattern)
        
        # Check for overly perfect formatting
        lines = code.split('\n')
        empty_lines = sum(1 for line in lines if not line.strip())
        if empty_lines / len(lines) > 0.3:  # Too many empty lines (AI formatting)
            score += 0.3
            patterns_found.append('excessive_formatting')
        
        # Check for generic variable names
        generic_vars = ['temp', 'result', 'output', 'input_data', 'processed_data']
        for var in generic_vars:
            if var in code:
                score += 0.1
                patterns_found.append(f'generic_variable_{var}')
        
        score = min(1.0, score)
        risk_level = RiskLevel.HIGH if score > 0.7 else RiskLevel.MEDIUM if score > 0.4 else RiskLevel.LOW
        
        return DetectionResult(
            method=DetectionMethod.MULTI_MODAL,
            score=score,
            confidence=0.6,
            evidence={
                'language': language,
                'patterns_found': patterns_found,
                'line_count': len(lines)
            },
            risk_level=risk_level
        )
    
    def _extract_text_from_image(self, img_data: bytes) -> str:
        """Extract text from image using OCR"""
        try:
            # Convert bytes to PIL Image
            from io import BytesIO
            img = Image.open(BytesIO(img_data))
            
            # Extract text using pytesseract
            text = pytesseract.image_to_string(img)
            return text.strip()
            
        except Exception as e:
            logger.debug(f"OCR extraction error: {e}")
            return ""
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts"""
        if not ML_AVAILABLE:
            # Simple word overlap similarity
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            
            if not words1 or not words2:
                return 0
            
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            
            return len(intersection) / len(union)
        
        try:
            # Use TF-IDF for better similarity
            vectorizer = TfidfVectorizer()
            tfidf_matrix = vectorizer.fit_transform([text1, text2])
            
            # Calculate cosine similarity
            from sklearn.metrics.pairwise import cosine_similarity
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            
            return similarity
            
        except Exception:
            # Fallback to simple method
            return self._calculate_text_similarity(text1, text2)

class AdversarialDetector:
    """Detects attempts to fool the detection system"""
    
    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.adversarial_patterns = [
            r'[a-zA-Z]\u200b[a-zA-Z]',  # Zero-width space
            r'[а-я]',  # Cyrillic characters that look like Latin
            r'[αβγδε]',  # Greek characters
            r'[０-９]',  # Full-width numbers
        ]
    
    def detect_evasion_attempts(self, text: str) -> DetectionResult:
        """Detect attempts to evade AI detection"""
        score = 0
        evidence = {}
        evasion_techniques = []
        
        # Check for invisible characters
        invisible_chars = self._count_invisible_characters(text)
        if invisible_chars > 0:
            score += min(0.5, invisible_chars / 100)
            evasion_techniques.append('invisible_characters')
            evidence['invisible_chars'] = invisible_chars
        
        # Check for character substitution
        substitutions = self._detect_character_substitution(text)
        if substitutions > 0:
            score += min(0.4, substitutions / 50)
            evasion_techniques.append('character_substitution')
            evidence['substitutions'] = substitutions
        
        # Check for unusual spacing patterns
        spacing_anomalies = self._detect_spacing_anomalies(text)
        if spacing_anomalies:
            score += 0.3
            evasion_techniques.append('spacing_manipulation')
            evidence['spacing_anomalies'] = spacing_anomalies
        
        # Check for format manipulation
        format_manipulation = self._detect_format_manipulation(text)
        if format_manipulation:
            score += 0.2
            evasion_techniques.append('format_manipulation')
            evidence['format_issues'] = format_manipulation
        
        score = min(1.0, score)
        risk_level = RiskLevel.CRITICAL if score > 0.8 else RiskLevel.HIGH if score > 0.5 else RiskLevel.LOW
        
        return DetectionResult(
            method=DetectionMethod.ADVERSARIAL_DETECTION,
            score=score,
            confidence=0.9,
            evidence={
                'evasion_techniques': evasion_techniques,
                'details': evidence
            },
            risk_level=risk_level
        )
    
    def _count_invisible_characters(self, text: str) -> int:
        """Count invisible Unicode characters"""
        invisible_chars = [
            '\u200b',  # Zero width space
            '\u200c',  # Zero width non-joiner
            '\u200d',  # Zero width joiner
            '\u2060',  # Word joiner
            '\ufeff',  # Zero width no-break space
        ]
        
        count = 0
        for char in invisible_chars:
            count += text.count(char)
        
        return count
    
    def _detect_character_substitution(self, text: str) -> int:
        """Detect character substitution (e.g., Cyrillic for Latin)"""
        suspicious_count = 0
        
        for pattern in self.adversarial_patterns:
            matches = re.findall(pattern, text)
            suspicious_count += len(matches)
        
        return suspicious_count
    
    def _detect_spacing_anomalies(self, text: str) -> List[str]:
        """Detect unusual spacing patterns"""
        anomalies = []
        
        # Check for excessive spaces
        if '  ' in text:
            anomalies.append('multiple_spaces')
        
        # Check for unusual line breaks
        if '\n\n\n' in text:
            anomalies.append('excessive_line_breaks')
        
        # Check for tabs mixed with spaces
        if '\t' in text and ' ' in text:
            anomalies.append('mixed_whitespace')
        
        return anomalies
    
    def _detect_format_manipulation(self, text: str) -> List[str]:
        """Detect format manipulation attempts"""
        issues = []
        
        # Check for unusual Unicode normalization
        import unicodedata
        if unicodedata.normalize('NFC', text) != text:
            issues.append('unicode_normalization')
        
        # Check for RTL/LTR marks
        if '\u202e' in text or '\u202d' in text:
            issues.append('direction_marks')
        
        return issues

class FederatedLearning:
    """Implements federated learning for AI detection models"""
    
    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.model_updates = []
        self.institution_id = None
    
    def initialize_federation(self, institution_id: str, federation_config: Dict):
        """Initialize federated learning setup"""
        self.institution_id = institution_id
        self.federation_config = federation_config
        
        # Create federated learning table
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS federated_learning (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                institution_id TEXT NOT NULL,
                model_update BLOB NOT NULL,
                update_round INTEGER NOT NULL,
                accuracy_metric REAL,
                privacy_budget REAL,
                created_at TEXT NOT NULL
            )
            ''')
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error initializing federated learning: {e}")
    
    def contribute_model_update(self, local_model_weights: np.ndarray, privacy_budget: float = 1.0):
        """Contribute model update while preserving privacy"""
        if not ML_AVAILABLE:
            return
        
        # Add differential privacy noise
        noise_scale = 1.0 / privacy_budget
        noisy_weights = local_model_weights + np.random.laplace(0, noise_scale, local_model_weights.shape)
        
        # Serialize weights
        weights_blob = pickle.dumps(noisy_weights)
        
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()
            
            # Get current round
            cursor.execute('SELECT MAX(update_round) FROM federated_learning WHERE institution_id = ?', 
                          (self.institution_id,))
            result = cursor.fetchone()
            current_round = (result[0] or 0) + 1
            
            # Store update
            cursor.execute('''
            INSERT INTO federated_learning 
            (institution_id, model_update, update_round, privacy_budget, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (self.institution_id, weights_blob, current_round, privacy_budget, 
                  datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error contributing model update: {e}")
    
    def aggregate_model_updates(self, round_number: int) -> Optional[np.ndarray]:
        """Aggregate model updates from different institutions"""
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT model_update, privacy_budget 
            FROM federated_learning 
            WHERE update_round = ?
            ''', (round_number,))
            
            updates = cursor.fetchall()
            conn.close()
            
            if not updates:
                return None
            
            # Weighted average based on privacy budget
            total_weights = None
            total_budget = 0
            
            for update_blob, budget in updates:
                weights = pickle.loads(update_blob)
                
                if total_weights is None:
                    total_weights = weights * budget
                else:
                    total_weights += weights * budget
                
                total_budget += budget
            
            if total_budget > 0:
                return total_weights / total_budget
            
            return None
            
        except Exception as e:
            logger.error(f"Error aggregating model updates: {e}")
            return None

class PrivacyManager:
    """Manages privacy controls and compliance"""
    
    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.consent_records = {}
    
    def initialize_privacy_tables(self):
        """Initialize privacy-related database tables"""
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()
            
            # Privacy consent table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS privacy_consent (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                consent_type TEXT NOT NULL,
                granted INTEGER NOT NULL,
                granted_at TEXT NOT NULL,
                expires_at TEXT,
                version TEXT NOT NULL,
                UNIQUE(student_id, consent_type)
            )
            ''')
            
            # Data retention table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_retention (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_type TEXT NOT NULL,
                retention_period INTEGER NOT NULL,
                deletion_date TEXT,
                status TEXT DEFAULT 'active'
            )
            ''')
            
            # Audit log table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS privacy_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                student_id TEXT,
                user_id INTEGER,
                data_accessed TEXT,
                timestamp TEXT NOT NULL,
                ip_address TEXT
            )
            ''')
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error initializing privacy tables: {e}")
    
    def check_consent(self, student_id: str, consent_type: str) -> bool:
        """Check if student has given consent for specific data processing"""
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT granted, expires_at 
            FROM privacy_consent 
            WHERE student_id = ? AND consent_type = ?
            ''', (student_id, consent_type))
            
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                return False
            
            granted, expires_at = result
            
            if not granted:
                return False
            
            # Check if consent has expired
            if expires_at:
                expiry_date = datetime.fromisoformat(expires_at)
                if datetime.now() > expiry_date:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking consent: {e}")
            return False
    
    def record_data_access(self, action: str, student_id: str = None, data_accessed: str = None):
        """Record data access for audit purposes"""
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()
            
            user_id = self.detector.current_user.get('id') if self.detector.current_user else None
            
            cursor.execute('''
            INSERT INTO privacy_audit_log 
            (action, student_id, user_id, data_accessed, timestamp)
            VALUES (?, ?, ?, ?, ?)
            ''', (action, student_id, user_id, data_accessed, datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error recording data access: {e}")
    
    def anonymize_data(self, data: Dict, fields_to_anonymize: List[str]) -> Dict:
        """Anonymize sensitive data fields"""
        anonymized = data.copy()
        
        for field in fields_to_anonymize:
            if field in anonymized:
                if field == 'student_id':
                    # Hash student ID
                    anonymized[field] = hashlib.sha256(str(data[field]).encode()).hexdigest()[:8]
                elif field in ['ip_address', 'device_fingerprint']:
                    # Partial anonymization
                    value = str(data[field])
                    if len(value) > 4:
                        anonymized[field] = value[:4] + '*' * (len(value) - 4)
                else:
                    # Full anonymization
                    anonymized[field] = '[ANONYMIZED]'
        
        return anonymized

class BiasDetector:
    """Detects and mitigates bias in AI detection"""
    
    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.bias_metrics = {}
    
    def analyze_detection_bias(self, demographic_data: Dict[str, str]) -> Dict[str, Any]:
        """Analyze bias in detection across demographic groups"""
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()
            
            # Analyze detection rates by demographic groups
            bias_analysis = {}
            
            for demographic, value in demographic_data.items():
                cursor.execute('''
                SELECT AVG(r.ai_score), COUNT(*) as total_submissions,
                       SUM(CASE WHEN r.ai_score >= 0.7 THEN 1 ELSE 0 END) as flagged_submissions
                FROM ai_detector_results r
                JOIN ai_detector_submissions s ON r.submission_id = s.id
                JOIN student_demographics d ON s.student_id = d.student_id
                WHERE d.{} = ?
                '''.format(demographic), (value,))
                
                result = cursor.fetchone()
                if result and result['total_submissions'] > 0:
                    bias_analysis[f"{demographic}_{value}"] = {
                        'avg_ai_score': result[0],
                        'total_submissions': result['total_submissions'],
                        'flagged_rate': result['flagged_submissions'] / result['total_submissions']
                    }
            
            conn.close()
            
            # Calculate bias metrics
            flagged_rates = [data['flagged_rate'] for data in bias_analysis.values()]
            if len(flagged_rates) > 1:
                bias_variance = statistics.variance(flagged_rates)
                bias_analysis['bias_variance'] = bias_variance
                bias_analysis['needs_calibration'] = bias_variance > 0.1
            
            return bias_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing detection bias: {e}")
            return {}
    
    def apply_bias_correction(self, ai_score: float, student_demographics: Dict) -> float:
        """Apply bias correction to AI score"""
        # Implement fairness through demographic parity or equalized odds
        correction_factor = 1.0
        
        # This would be calibrated based on historical bias analysis
        # For now, implementing a simple correction
        
        return min(1.0, ai_score * correction_factor)

class BlockchainAuditTrail:
    """Implements blockchain-based audit trail for academic integrity"""
    
    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.blockchain = []
        self.pending_transactions = []
    
    def create_detection_record(self, submission_id: int, detection_result: Dict) -> str:
        """Create immutable detection record"""
        # Create transaction
        transaction = {
            'type': 'ai_detection',
            'submission_id': submission_id,
            'detection_hash': hashlib.sha256(json.dumps(detection_result, sort_keys=True).encode()).hexdigest(),
            'timestamp': datetime.now().isoformat(),
            'analyzer_id': self.detector.current_user.get('id') if self.detector.current_user else None
        }
        
        # Add to pending transactions
        self.pending_transactions.append(transaction)
        
        # Mine block if enough transactions
        if len(self.pending_transactions) >= 5:
            self._mine_block()
        
        return transaction['detection_hash']
    
    def verify_detection_integrity(self, submission_id: int, claimed_hash: str) -> bool:
        """Verify integrity of detection record"""
        # Search blockchain for record
        for block in self.blockchain:
            for transaction in block.get('transactions', []):
                if (transaction.get('submission_id') == submission_id and 
                    transaction.get('detection_hash') == claimed_hash):
                    return True
        
        return False
    
    def _mine_block(self):
        """Mine a new block with pending transactions"""
        previous_hash = self.blockchain[-1]['hash'] if self.blockchain else '0' * 64
        
        block = {
            'index': len(self.blockchain),
            'timestamp': datetime.now().isoformat(),
            'transactions': self.pending_transactions.copy(),
            'previous_hash': previous_hash,
            'nonce': 0
        }
        
        # Simple proof of work (in production, use proper PoW algorithm)
        while True:
            block_string = json.dumps(block, sort_keys=True)
            block_hash = hashlib.sha256(block_string.encode()).hexdigest()
            
            if block_hash.startswith('0000'):  # Difficulty = 4 leading zeros
                block['hash'] = block_hash
                break
            
            block['nonce'] += 1
        
        self.blockchain.append(block)
        self.pending_transactions = []
        
        logger.info(f"New block mined: {block['hash']}")

class PredictiveAnalytics:
    """Predictive analytics for academic integrity risks"""
    
    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.risk_model = None
    
    def train_risk_prediction_model(self):
        """Train model to predict students at risk of academic dishonesty"""
        if not ML_AVAILABLE:
            return
        
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()
            
            # Get training data
            cursor.execute('''
            SELECT 
                s.student_id,
                COUNT(*) as submission_count,
                AVG(r.ai_score) as avg_ai_score,
                MAX(r.ai_score) as max_ai_score,
                AVG(s.word_count) as avg_word_count,
                COUNT(CASE WHEN r.ai_score >= 0.7 THEN 1 END) as violations,
                AVG(CAST(strftime('%H', s.submission_date) AS INTEGER)) as avg_submission_hour
            FROM ai_detector_submissions s
            JOIN ai_detector_results r ON s.id = r.submission_id
            GROUP BY s.student_id
            HAVING submission_count >= 3
            ''')
            
            data = cursor.fetchall()
            conn.close()
            
            if len(data) < 20:
                logger.warning("Insufficient data for risk prediction model")
                return
            
            # Prepare features and labels
            features = []
            labels = []
            
            for row in data:
                feature_vector = [
                    row['submission_count'],
                    row['avg_ai_score'],
                    row['max_ai_score'],
                    row['avg_word_count'],
                    row['avg_submission_hour']
                ]
                features.append(feature_vector)
                
                # Label as high risk if they have violations
                labels.append(1 if row['violations'] > 0 else 0)
            
            # Train model
            X = np.array(features)
            y = np.array(labels)
            
            self.risk_model = RandomForestClassifier(n_estimators=100, random_state=42)
            self.risk_model.fit(X, y)
            
            logger.info("Risk prediction model trained successfully")
            
        except Exception as e:
            logger.error(f"Error training risk prediction model: {e}")
    
    def predict_student_risk(self, student_id: str) -> Dict[str, Any]:
        """Predict risk level for a student"""
        if not self.risk_model or not ML_AVAILABLE:
            return {'risk_score': 0, 'risk_level': 'unknown'}
        
        try:
            # Get student features
            features = self._extract_student_features(student_id)
            if not features:
                return {'risk_score': 0, 'risk_level': 'insufficient_data'}
            
            # Predict
            risk_prob = self.risk_model.predict_proba([features])[0][1]
            
            if risk_prob > 0.8:
                risk_level = 'high'
            elif risk_prob > 0.5:
                risk_level = 'medium'
            else:
                risk_level = 'low'
            
            return {
                'risk_score': risk_prob,
                'risk_level': risk_level,
                'features_used': features
            }
            
        except Exception as e:
            logger.error(f"Error predicting student risk: {e}")
            return {'risk_score': 0, 'risk_level': 'error'}
    
    def _extract_student_features(self, student_id: str) -> Optional[List[float]]:
        """Extract features for risk prediction"""
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT 
                COUNT(*) as submission_count,
                AVG(r.ai_score) as avg_ai_score,
                MAX(r.ai_score) as max_ai_score,
                AVG(s.word_count) as avg_word_count,
                AVG(CAST(strftime('%H', s.submission_date) AS INTEGER)) as avg_submission_hour
            FROM ai_detector_submissions s
            JOIN ai_detector_results r ON s.id = r.submission_id
            WHERE s.student_id = ?
            ''', (student_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if not result or result['submission_count'] == 0:
                return None
            
            return [
                result['submission_count'] or 0,
                result['avg_ai_score'] or 0,
                result['max_ai_score'] or 0,
                result['avg_word_count'] or 0,
                result['avg_submission_hour'] or 12
            ]
            
        except Exception as e:
            logger.error(f"Error extracting student features: {e}")
            return None

class RealTimeProcessor:
    """Processes submissions in real-time"""
    
    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.processing_queue = []
        self.workers = []
        self.is_running = False
    
    def start_real_time_processing(self, num_workers: int = 3):
        """Start real-time processing with worker threads"""
        self.is_running = True
        
        for i in range(num_workers):
            worker = threading.Thread(target=self._worker_process, args=(i,))
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
        
        logger.info(f"Started real-time processing with {num_workers} workers")
    
    def stop_real_time_processing(self):
        """Stop real-time processing"""
        self.is_running = False
        
        # Wait for workers to finish
        for worker in self.workers:
            worker.join(timeout=5)
        
        self.workers = []
        logger.info("Stopped real-time processing")
    
    def queue_submission(self, submission_data: Dict, priority: int = 1) -> str:
        """Queue submission for real-time processing"""
        task_id = str(uuid.uuid4())
        
        task = {
            'id': task_id,
            'data': submission_data,
            'priority': priority,
            'queued_at': datetime.now(),
            'status': 'queued'
        }
        
        # Insert in priority order
        inserted = False
        for i, existing_task in enumerate(self.processing_queue):
            if existing_task['priority'] < priority:
                self.processing_queue.insert(i, task)
                inserted = True
                break
        
        if not inserted:
            self.processing_queue.append(task)
        
        return task_id
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a queued task"""
        for task in self.processing_queue:
            if task['id'] == task_id:
                return {
                    'status': task['status'],
                    'queued_at': task['queued_at'].isoformat(),
                    'position': self.processing_queue.index(task)
                }
        
        return {'status': 'not_found'}
    
    def _worker_process(self, worker_id: int):
        """Worker process for handling queued submissions"""
        logger.info(f"Worker {worker_id} started")
        
        while self.is_running:
            try:
                if self.processing_queue:
                    task = self.processing_queue.pop(0)
                    task['status'] = 'processing'
                    
                    # Process the submission
                    result = self.detector.analyze_text_enhanced(**task['data'])
                    
                    # Store result or send notification
                    self._handle_processing_result(task, result)
                    
                else:
                    time.sleep(0.1)  # Brief sleep when queue is empty
                    
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                time.sleep(1)
        
        logger.info(f"Worker {worker_id} stopped")
    
    def _handle_processing_result(self, task: Dict, result: Dict):
        """Handle the result of processing"""
        # This could send notifications, trigger alerts, etc.
        if result.get('is_ai_generated'):
            logger.warning(f"High-risk submission detected: {task['id']}")
            # Could send alert to instructors here

class InstitutionBenchmarking:
    """Provides benchmarking across institutions"""
    
    def __init__(self, detector_instance):
        self.detector = detector_instance
    
    def generate_benchmark_report(self, institution_id: str, comparison_period: str = '1_month') -> Dict[str, Any]:
        """Generate benchmarking report comparing institution to others"""
        try:
            # Calculate period dates
            if comparison_period == '1_month':
                start_date = datetime.now() - timedelta(days=30)
            elif comparison_period == '3_months':
                start_date = datetime.now() - timedelta(days=90)
            elif comparison_period == '1_year':
                start_date = datetime.now() - timedelta(days=365)
            else:
                start_date = datetime.now() - timedelta(days=30)
            
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()
            
            # Get institution metrics
            cursor.execute('''
            SELECT 
                COUNT(*) as total_submissions,
                AVG(r.ai_score) as avg_ai_score,
                COUNT(CASE WHEN r.ai_score >= 0.7 THEN 1 END) as flagged_submissions,
                COUNT(DISTINCT s.student_id) as unique_students
            FROM ai_detector_submissions s
            JOIN ai_detector_results r ON s.id = r.submission_id
            WHERE s.institution_id = ? AND s.submission_date >= ?
            ''', (institution_id, start_date.isoformat()))
            
            institution_stats = cursor.fetchone()
            
            # Get global benchmarks (anonymized)
            cursor.execute('''
            SELECT 
                AVG(total_submissions) as avg_submissions_per_institution,
                AVG(avg_ai_score) as global_avg_ai_score,
                AVG(flagged_rate) as global_flagged_rate
            FROM (
                SELECT 
                    s.institution_id,
                    COUNT(*) as total_submissions,
                    AVG(r.ai_score) as avg_ai_score,
                    CAST(COUNT(CASE WHEN r.ai_score >= 0.7 THEN 1 END) AS FLOAT) / COUNT(*) as flagged_rate
                FROM ai_detector_submissions s
                JOIN ai_detector_results r ON s.id = r.submission_id
                WHERE s.submission_date >= ?
                GROUP BY s.institution_id
            ) institution_metrics
            ''', (start_date.isoformat(),))
            
            global_stats = cursor.fetchone()
            conn.close()
            
            # Calculate percentiles
            institution_flagged_rate = (institution_stats['flagged_submissions'] / 
                                     max(1, institution_stats['total_submissions']))
            
            report = {
                'institution_id': institution_id,
                'period': comparison_period,
                'institution_metrics': {
                    'total_submissions': institution_stats['total_submissions'],
                    'avg_ai_score': round(institution_stats['avg_ai_score'] or 0, 3),
                    'flagged_rate': round(institution_flagged_rate, 3),
                    'unique_students': institution_stats['unique_students']
                },
                'benchmarks': {
                    'avg_submissions_per_institution': round(global_stats['avg_submissions_per_institution'] or 0, 1),
                    'global_avg_ai_score': round(global_stats['global_avg_ai_score'] or 0, 3),
                    'global_flagged_rate': round(global_stats['global_flagged_rate'] or 0, 3)
                },
                'performance_indicators': {}
            }
            
            # Calculate performance indicators
            if global_stats['global_flagged_rate']:
                flagged_rate_ratio = institution_flagged_rate / global_stats['global_flagged_rate']
                if flagged_rate_ratio > 1.5:
                    report['performance_indicators']['flagged_rate'] = 'above_average'
                elif flagged_rate_ratio < 0.5:
                    report['performance_indicators']['flagged_rate'] = 'below_average'
                else:
                    report['performance_indicators']['flagged_rate'] = 'average'
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating benchmark report: {e}")
            return {'error': str(e)}

class StudentSelfCheckTool:
    """Tool for students to self-assess their work"""
    
    def __init__(self, detector_instance):
        self.detector = detector_instance
    
    def preview_analysis(self, text: str, student_id: str) -> Dict[str, Any]:
        """Provide non-punitive preview of analysis"""
        # Run lightweight analysis
        results = {
            'overall_assessment': 'pending',
            'suggestions': [],
            'risk_indicators': [],
            'confidence': 0
        }
        
        try:
            # Basic pattern detection
            pattern_results = self.detector._detect_ai_patterns(text)
            
            # Calculate preliminary score
            preliminary_score = pattern_results['overall_score']
            
            if preliminary_score > 0.8:
                results['overall_assessment'] = 'high_risk'
                results['suggestions'].extend([
                    "Consider adding more personal examples and experiences",
                    "Review your writing for overly formal or generic language",
                    "Ensure your arguments reflect your own perspective"
                ])
            elif preliminary_score > 0.5:
                results['overall_assessment'] = 'moderate_risk'
                results['suggestions'].extend([
                    "Consider making your writing more personal and specific",
                    "Add more varied sentence structures"
                ])
            else:
                results['overall_assessment'] = 'low_risk'
                results['suggestions'].append("Your writing appears to have good personal voice")
            
            # Educational indicators
            for indicator in pattern_results['indicators']:
                if indicator['score'] > 0.3:
                    results['risk_indicators'].append({
                        'type': indicator['name'],
                        'severity': 'high' if indicator['score'] > 0.7 else 'medium',
                        'suggestion': self._get_improvement_suggestion(indicator['name'])
                    })
            
            results['confidence'] = pattern_results['confidence']
            
            # Record self-check (anonymized)
            self._record_self_check(student_id, preliminary_score)
            
        except Exception as e:
            logger.error(f"Error in self-check analysis: {e}")
            results['error'] = "Analysis temporarily unavailable"
        
        return results
    
    def _get_improvement_suggestion(self, indicator_name: str) -> str:
        """Get educational suggestion for improvement"""
        suggestions = {
            'lack_of_personal_references': "Try including more personal experiences, examples from your own life, or references to 'I think' or 'In my experience'",
            'hedging_language': "Consider being more direct in your statements rather than using phrases like 'it seems' or 'it appears'",
            'perfectly_balanced_arguments': "Real arguments often have stronger evidence on one side. Consider developing your strongest points more fully",
            'formal_language_overuse': "Academic writing can still have personality. Try varying your vocabulary and sentence structures",
            'ai_fingerprints': "Some phrases in your text are commonly associated with AI writing. Try expressing ideas in your own words"
        }
        
        return suggestions.get(indicator_name, "Consider reviewing this aspect of your writing for authenticity")
    
    def _record_self_check(self, student_id: str, score: float):
        """Record self-check usage (anonymized)"""
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()
            
            # Create table if not exists
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS self_check_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_hash TEXT NOT NULL,
                score_range TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            ''')
            
            # Hash student ID for privacy
            student_hash = hashlib.sha256(student_id.encode()).hexdigest()[:16]
            
            # Score range for anonymization
            if score > 0.7:
                score_range = 'high'
            elif score > 0.4:
                score_range = 'medium'
            else:
                score_range = 'low'
            
            cursor.execute('''
            INSERT INTO self_check_usage (student_hash, score_range, timestamp)
            VALUES (?, ?, ?)
            ''', (student_hash, score_range, datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.debug(f"Error recording self-check: {e}")

class AdvancedMLTrainer:
    """Advanced ML training with multiple algorithms and techniques"""
    
    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.models = {}
        self.ensemble_model = None
        self.feature_importance = {}
    
    def train_ensemble_model(self, use_advanced_features: bool = True):
        """Train ensemble model with multiple algorithms"""
        if not ML_AVAILABLE:
            raise AIDetectionError("scikit-learn not available for ML training")
        
        try:
            # Prepare training data
            X, y, feature_names = self._prepare_advanced_training_data(use_advanced_features)
            
            if len(X) < 100:
                raise AIDetectionError("Insufficient training data")
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            # Train multiple models
            models_to_train = {
                'random_forest': RandomForestClassifier(n_estimators=200, random_state=42),
                'isolation_forest': IsolationForest(contamination=0.1, random_state=42),
            }
            
            if TRANSFORMERS_AVAILABLE:
                models_to_train['neural_network'] = self._create_neural_model()
            
            trained_models = {}
            model_scores = {}
            
            for name, model in models_to_train.items():
                if name == 'isolation_forest':
                    # Unsupervised model
                    model.fit(X_train)
                    predictions = model.predict(X_test)
                    # Convert to binary classification
                    predictions = (predictions == -1).astype(int)
                else:
                    # Supervised model
                    model.fit(X_train, y_train)
                    predictions = model.predict(X_test)
                
                accuracy = accuracy_score(y_test, predictions)
                trained_models[name] = model
                model_scores[name] = accuracy
                
                logger.info(f"{name} accuracy: {accuracy:.3f}")
            
            self.models = trained_models
            
            # Create ensemble
            self._create_ensemble_predictor(trained_models, model_scores)
            
            # Calculate feature importance
            if 'random_forest' in trained_models:
                rf_model = trained_models['random_forest']
                self.feature_importance = dict(zip(feature_names, rf_model.feature_importances_))
            
            return {
                'models_trained': list(trained_models.keys()),
                'model_scores': model_scores,
                'feature_importance': self.feature_importance
            }
            
        except Exception as e:
            logger.error(f"Error training ensemble model: {e}")
            raise AIDetectionError(f"Ensemble training failed: {e}")
    
    def _prepare_advanced_training_data(self, use_advanced_features: bool) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Prepare advanced training data with multiple feature types"""
        conn = self.detector._safe_db_connect()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT s.submission_text, r.ai_score, s.word_count, s.character_count,
               r.style_deviation, r.detailed_results
        FROM ai_detector_submissions s
        JOIN ai_detector_results r ON s.id = r.submission_id
        WHERE length(s.submission_text) > 200
        ''')
        
        data = cursor.fetchall()
        conn.close()
        
        if len(data) < 50:
            raise AIDetectionError("Insufficient training data")
        
        features = []
        labels = []
        feature_names = []
        
        for row in data:
            text = row['submission_text']
            label = 1 if row['ai_score'] >= 0.7 else 0
            
            # Basic features
            feature_vector = [
                row['word_count'],
                row['character_count'],
                row['style_deviation'] or 0
            ]
            
            if not feature_names:  # First iteration
                feature_names.extend(['word_count', 'character_count', 'style_deviation'])
            
            if use_advanced_features:
                # Advanced linguistic features
                linguistic_features = self._extract_linguistic_features(text)
                feature_vector.extend(linguistic_features.values())
                
                if not any('linguistic' in name for name in feature_names):
                    feature_names.extend([f'linguistic_{name}' for name in linguistic_features.keys()])
                
                # TF-IDF features (limited set)
                tfidf_features = self._extract_tfidf_features(text)
                feature_vector.extend(tfidf_features)
                
                if not any('tfidf' in name for name in feature_names):
                    feature_names.extend([f'tfidf_{i}' for i in range(len(tfidf_features))])
            
            features.append(feature_vector)
            labels.append(label)
        
        return np.array(features), np.array(labels), feature_names
    
    def _extract_linguistic_features(self, text: str) -> Dict[str, float]:
        """Extract advanced linguistic features"""
        features = {}
        
        # Sentence complexity
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if sentences:
            sentence_lengths = [len(s.split()) for s in sentences]
            features['avg_sentence_length'] = np.mean(sentence_lengths)
            features['sentence_length_std'] = np.std(sentence_lengths)
            features['max_sentence_length'] = np.max(sentence_lengths)
        else:
            features.update({'avg_sentence_length': 0, 'sentence_length_std': 0, 'max_sentence_length': 0})
        
        # Lexical diversity
        words = text.lower().split()
        unique_words = set(words)
        features['lexical_diversity'] = len(unique_words) / max(1, len(words))
        
        # Function word ratio
        function_words = {'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i', 'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at'}
        function_word_count = sum(1 for word in words if word in function_words)
        features['function_word_ratio'] = function_word_count / max(1, len(words))
        
        # Punctuation density
        punctuation_count = len(re.findall(r'[.,;:!?]', text))
        features['punctuation_density'] = punctuation_count / max(1, len(text))
        
        return features
    
    def _extract_tfidf_features(self, text: str, max_features: int = 50) -> List[float]:
        """Extract TF-IDF features"""
        try:
            # Simple TF-IDF on character n-grams
            vectorizer = TfidfVectorizer(
                max_features=max_features,
                ngram_range=(2, 4),
                analyzer='char_wb',
                lowercase=True
            )
            
            # Fit on single text (not ideal, but works for feature extraction)
            tfidf_matrix = vectorizer.fit_transform([text])
            return tfidf_matrix.toarray()[0].tolist()
            
        except Exception:
            return [0.0] * max_features
    
    def _create_neural_model(self):
        """Create neural network model using transformers"""
        # Placeholder for transformer-based model
        # In practice, would use BERT, RoBERTa, or similar
        return None
    
    def _create_ensemble_predictor(self, models: Dict, scores: Dict):
        """Create ensemble predictor from trained models"""
        # Weight models by their performance
        total_score = sum(scores.values())
        weights = {name: score/total_score for name, score in scores.items()}
        
        self.ensemble_model = {
            'models': models,
            'weights': weights
        }
    
    def predict_ensemble(self, text: str) -> Dict[str, Any]:
        """Make prediction using ensemble model"""
        if not self.ensemble_model:
            return None
        
        try:
            # Extract features
            features = self._extract_features_for_prediction(text)
            
            # Get predictions from each model
            predictions = {}
            weighted_sum = 0
            total_weight = 0
            
            for name, model in self.ensemble_model['models'].items():
                weight = self.ensemble_model['weights'][name]
                
                if name == 'isolation_forest':
                    pred = model.predict([features])[0]
                    prob = 1.0 if pred == -1 else 0.0  # Anomaly detection
                else:
                    if hasattr(model, 'predict_proba'):
                        prob = model.predict_proba([features])[0][1]
                    else:
                        prob = float(model.predict([features])[0])
                
                predictions[name] = prob
                weighted_sum += prob * weight
                total_weight += weight
            
            ensemble_score = weighted_sum / total_weight if total_weight > 0 else 0
            
            return {
                'ensemble_score': ensemble_score,
                'individual_predictions': predictions,
                'confidence': self._calculate_ensemble_confidence(predictions)
            }
            
        except Exception as e:
            logger.error(f"Error in ensemble prediction: {e}")
            return None
    
    def _extract_features_for_prediction(self, text: str) -> List[float]:
        """Extract features for prediction"""
        # This should match the feature extraction used in training
        word_count = len(text.split())
        char_count = len(text)
        
        features = [word_count, char_count, 0]  # style_deviation placeholder
        
        # Add linguistic features
        linguistic_features = self._extract_linguistic_features(text)
        features.extend(linguistic_features.values())
        
        # Add TF-IDF features
        tfidf_features = self._extract_tfidf_features(text)
        features.extend(tfidf_features)
        
        return features
    
    def _calculate_ensemble_confidence(self, predictions: Dict[str, float]) -> float:
        """Calculate confidence in ensemble prediction"""
        pred_values = list(predictions.values())
        
        if len(pred_values) < 2:
            return 0.5
        
        # Confidence based on agreement between models
        variance = np.var(pred_values)
        confidence = max(0.1, 1.0 - variance)
        
        return confidence

class VisualAnalyzer:
    """Provides visual analysis and explanations"""
    
    def __init__(self, detector_instance):
        self.detector = detector_instance
    
    def generate_text_heatmap(self, text: str, ai_scores: List[float]) -> Dict[str, Any]:
        """Generate heatmap data for text visualization"""
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(ai_scores) != len(sentences):
            # Adjust scores to match sentences
            if len(ai_scores) > len(sentences):
                ai_scores = ai_scores[:len(sentences)]
            else:
                ai_scores.extend([0] * (len(sentences) - len(ai_scores)))
        
        heatmap_data = []
        
        for i, (sentence, score) in enumerate(zip(sentences, ai_scores)):
            # Determine color intensity based on score
            if score > 0.8:
                color = 'red'
                intensity = 'high'
            elif score > 0.6:
                color = 'orange'
                intensity = 'medium'
            elif score > 0.4:
                color = 'yellow'
                intensity = 'low'
            else:
                color = 'green'
                intensity = 'none'
            
            heatmap_data.append({
                'sentence_index': i,
                'text': sentence,
                'score': score,
                'color': color,
                'intensity': intensity,
                'word_count': len(sentence.split())
            })
        
        return {
            'heatmap_data': heatmap_data,
            'overall_score': sum(ai_scores) / len(ai_scores) if ai_scores else 0,
            'high_risk_sentences': len([s for s in ai_scores if s > 0.7]),
            'total_sentences': len(sentences)
        }
    
    def generate_writing_flow_visualization(self, text: str) -> Dict[str, Any]:
        """Generate writing flow visualization data"""
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        flow_data = []
        
        for i, paragraph in enumerate(paragraphs):
            sentences = re.split(r'[.!?]+', paragraph)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            # Analyze paragraph characteristics
            word_count = len(paragraph.split())
            sentence_count = len(sentences)
            avg_sentence_length = word_count / max(1, sentence_count)
            
            # Detect transitions
            transition_words = ['however', 'furthermore', 'moreover', 'therefore', 'consequently', 'in addition', 'on the other hand']
            has_transition = any(word in paragraph.lower() for word in transition_words)
            
            flow_data.append({
                'paragraph_index': i,
                'word_count': word_count,
                'sentence_count': sentence_count,
                'avg_sentence_length': avg_sentence_length,
                'has_transition': has_transition,
                'complexity_score': self._calculate_paragraph_complexity(paragraph)
            })
        
        return {
            'flow_data': flow_data,
            'total_paragraphs': len(paragraphs),
            'avg_paragraph_length': sum(p['word_count'] for p in flow_data) / len(flow_data) if flow_data else 0,
            'transition_frequency': sum(1 for p in flow_data if p['has_transition']) / len(flow_data) if flow_data else 0
        }
    
    def _calculate_paragraph_complexity(self, paragraph: str) -> float:
        """Calculate complexity score for a paragraph"""
        words = paragraph.split()
        
        # Factors contributing to complexity
        avg_word_length = sum(len(word) for word in words) / len(words) if words else 0
        punctuation_density = len(re.findall(r'[,;:()]', paragraph)) / len(paragraph) if paragraph else 0
        
        # Normalize to 0-1 scale
        complexity = min(1.0, (avg_word_length / 10) + (punctuation_density * 10))
        
        return complexity

class APIGateway:
    """Gateway for external AI detection APIs"""
    
    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.api_configs = {}
        self.rate_limits = {}
        self.circuit_breakers = {}
    
    def register_api(self, name: str, config: Dict[str, Any]):
        """Register an external AI detection API"""
        self.api_configs[name] = {
            'url': config['url'],
            'api_key': config['api_key'],
            'timeout': config.get('timeout', 10),
            'max_requests_per_minute': config.get('max_requests_per_minute', 60),
            'weight': config.get('weight', 1.0)
        }
        
        self.rate_limits[name] = {
            'requests': [],
            'max_per_minute': config.get('max_requests_per_minute', 60)
        }
        
        self.circuit_breakers[name] = {
            'failures': 0,
            'last_failure': None,
            'is_open': False,
            'failure_threshold': 5,
            'recovery_timeout': 300  # 5 minutes
        }
    
    def call_api(self, api_name: str, text: str) -> Optional[Dict[str, Any]]:
        """Call external API with circuit breaker and rate limiting"""
        if not REQUESTS_AVAILABLE:
            return None
        
        if api_name not in self.api_configs:
            logger.error(f"API {api_name} not registered")
            return None
        
        # Check circuit breaker
        if self._is_circuit_open(api_name):
            logger.warning(f"Circuit breaker open for API {api_name}")
            return None
        
        # Check rate limit
        if not self._check_rate_limit(api_name):
            logger.warning(f"Rate limit exceeded for API {api_name}")
            return None
        
        try:
            config = self.api_configs[api_name]
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {config["api_key"]}'
            }
            
            data = {
                'text': text[:5000],  # Limit text length
                'model': 'general'
            }
            
            response = requests.post(
                config['url'],
                headers=headers,
                json=data,
                timeout=config['timeout']
            )
            
            if response.status_code == 200:
                result = response.json()
                self._record_success(api_name)
                return {
                    'api_name': api_name,
                    'score': result.get('score', 0),
                    'confidence': result.get('confidence', 0),
                    'details': result.get('details', {}),
                    'response_time': response.elapsed.total_seconds()
                }
            else:
                self._record_failure(api_name)
                logger.warning(f"API {api_name} returned status {response.status_code}")
                return None
                
        except Exception as e:
            self._record_failure(api_name)
            logger.error(f"Error calling API {api_name}: {e}")
            return None
    
    def _check_rate_limit(self, api_name: str) -> bool:
        """Check if API call is within rate limit"""
        now = datetime.now()
        rate_limit = self.rate_limits[api_name]
        
        # Remove requests older than 1 minute
        rate_limit['requests'] = [
            req_time for req_time in rate_limit['requests']
            if (now - req_time).total_seconds() < 60
        ]
        
        # Check if under limit
        if len(rate_limit['requests']) < rate_limit['max_per_minute']:
            rate_limit['requests'].append(now)
            return True
        
        return False
    
    def _is_circuit_open(self, api_name: str) -> bool:
        """Check if circuit breaker is open"""
        circuit = self.circuit_breakers[api_name]
        
        if not circuit['is_open']:
            return False
        
        # Check if recovery timeout has passed
        if circuit['last_failure']:
            time_since_failure = (datetime.now() - circuit['last_failure']).total_seconds()
            if time_since_failure > circuit['recovery_timeout']:
                circuit['is_open'] = False
                circuit['failures'] = 0
                return False
        
        return True
    
    def _record_success(self, api_name: str):
        """Record successful API call"""
        circuit = self.circuit_breakers[api_name]
        circuit['failures'] = 0
        circuit['is_open'] = False
    
    def _record_failure(self, api_name: str):
        """Record failed API call"""
        circuit = self.circuit_breakers[api_name]
        circuit['failures'] += 1
        circuit['last_failure'] = datetime.now()
        
        if circuit['failures'] >= circuit['failure_threshold']:
            circuit['is_open'] = True
            logger.warning(f"Circuit breaker opened for API {api_name}")

class ComplianceManager:
    """Manages regulatory compliance (GDPR, FERPA, etc.)"""
    
    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.compliance_rules = {}
    
    def initialize_compliance_framework(self, regulations: List[str]):
        """Initialize compliance framework"""
        for regulation in regulations:
            if regulation == 'GDPR':
                self._setup_gdpr_compliance()
            elif regulation == 'FERPA':
                self._setup_ferpa_compliance()
            elif regulation == 'COPPA':
                self._setup_coppa_compliance()
    
    def _setup_gdpr_compliance(self):
        """Setup GDPR compliance rules"""
        self.compliance_rules['GDPR'] = {
            'data_retention_period': 2555,  # 7 years in days
            'requires_consent': True,
            'right_to_deletion': True,
            'data_portability': True,
            'purpose_limitation': True,
            'data_minimization': True
        }
    
    def _setup_ferpa_compliance(self):
        """Setup FERPA compliance rules"""
        self.compliance_rules['FERPA'] = {
            'education_records_protection': True,
            'requires_consent_for_disclosure': True,
            'audit_trail_required': True,
            'data_retention_period': 1825,  # 5 years in days
            'directory_information_rules': True
        }
    
    def check_compliance_before_processing(self, student_id: str, data_type: str) -> Dict[str, Any]:
        """Check compliance requirements before processing data"""
        compliance_status = {
            'can_process': True,
            'requirements': [],
            'warnings': []
        }
        
        for regulation, rules in self.compliance_rules.items():
            # Check consent requirements
            if rules.get('requires_consent'):
                has_consent = self.detector.privacy_manager.check_consent(student_id, data_type)
                if not has_consent:
                    compliance_status['can_process'] = False
                    compliance_status['requirements'].append(f'{regulation}: Consent required for {data_type}')
            
            # Check data retention
            if 'data_retention_period' in rules:
                retention_days = rules['data_retention_period']
                compliance_status['warnings'].append(f'{regulation}: Data must be deleted after {retention_days} days')
        
        return compliance_status
    
    def generate_compliance_report(self) -> Dict[str, Any]:
        """Generate compliance status report"""
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()
            
            # Check data retention compliance
            retention_issues = []
            
            for regulation, rules in self.compliance_rules.items():
                if 'data_retention_period' in rules:
                    retention_days = rules['data_retention_period']
                    cutoff_date = datetime.now() - timedelta(days=retention_days)
                    
                    cursor.execute('''
                    SELECT COUNT(*) as expired_records
                    FROM ai_detector_submissions
                    WHERE submission_date < ?
                    ''', (cutoff_date.isoformat(),))
                    
                    result = cursor.fetchone()
                    if result['expired_records'] > 0:
                        retention_issues.append({
                            'regulation': regulation,
                            'expired_records': result['expired_records'],
                            'cutoff_date': cutoff_date.isoformat()
                        })
            
            # Check consent compliance
            cursor.execute('''
            SELECT COUNT(*) as total_students,
                   COUNT(CASE WHEN pc.granted = 1 THEN 1 END) as consented_students
            FROM (SELECT DISTINCT student_id FROM ai_detector_submissions) s
            LEFT JOIN privacy_consent pc ON s.student_id = pc.student_id
            ''')
            
            consent_stats = cursor.fetchone()
            conn.close()
            
            return {
                'retention_compliance': {
                    'issues': retention_issues,
                    'status': 'compliant' if not retention_issues else 'needs_attention'
                },
                'consent_compliance': {
                    'total_students': consent_stats['total_students'],
                    'consented_students': consent_stats['consented_students'],
                    'consent_rate': (consent_stats['consented_students'] / 
                                   max(1, consent_stats['total_students']))
                },
                'active_regulations': list(self.compliance_rules.keys()),
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating compliance report: {e}")
            return {'error': str(e)}

class AIDetector:
    """Ultimate AI Detector with all advanced features integrated"""
    
    def __init__(self, db_path=str(DEFAULT_DB_PATH), detection_threshold=0.7):
        """Enhanced initialization with proper attribute setup - FIXED VERSION"""
        
        # ⚠️ CRITICAL: Initialize base attributes FIRST - this is the key fix!
        self.db_path = db_path
        self.detection_threshold = detection_threshold  # 🔧 MUST be set early!
        self.current_user = None
        
        # Initialize missing attributes that other methods depend on
        self.detection_methods = {
            'pattern_matching': True,
            'statistical_analysis': True,
            'behavioral_analysis': True,
            'temporal_analysis': True,
            'citation_verification': True
        }
        self.style_profiles = {}
        
        # Initialize all the advanced components (these can come after base attributes)
        try:
            self.temporal_analyzer = TemporalAnalyzer(self)
            self.citation_verifier = CitationVerifier(self)
            self.behavioral_analyzer = BehavioralAnalyzer(self)
            self.multimodal_analyzer = MultiModalAnalyzer(self)
            self.adversarial_detector = AdversarialDetector(self)
            self.federated_learning = FederatedLearning(self)
            self.privacy_manager = PrivacyManager(self)
            self.bias_detector = BiasDetector(self)
            self.blockchain_audit = BlockchainAuditTrail(self)
            self.predictive_analytics = PredictiveAnalytics(self)
            self.realtime_processor = RealTimeProcessor(self)
            self.institution_benchmarking = InstitutionBenchmarking(self)
            self.student_self_check = StudentSelfCheckTool(self)
            self.advanced_ml_trainer = AdvancedMLTrainer(self)
            self.visual_analyzer = VisualAnalyzer(self)
            self.api_gateway = APIGateway(self)
            self.compliance_manager = ComplianceManager(self)
            
            print("✅ All AI detector components initialized successfully")
            
        except Exception as component_error:
            # Don't fail completely if advanced components fail
            print(f"⚠️ Some advanced components failed to initialize: {component_error}")
            # Set minimal fallbacks
            self.temporal_analyzer = None
            self.citation_verifier = None
            # ... etc for other components
        
        # Initialize database and setup
        try:
            self._init_database()
            self._init_advanced_db_tables()
            
            # Initialize privacy and compliance frameworks
            if hasattr(self, 'privacy_manager') and self.privacy_manager:
                self.privacy_manager.initialize_privacy_tables()
            if hasattr(self, 'compliance_manager') and self.compliance_manager:
                self.compliance_manager.initialize_compliance_framework(['GDPR', 'FERPA'])
            
            # Fix database schema issues
            self.fix_database_schema()
            
            print("✅ AI detector database initialization completed")
            
        except Exception as db_error:
            print(f"⚠️ Database initialization had issues: {db_error}")
            # Continue with basic functionality even if advanced features fail
            
    def _init_database(self):
        """Initialize the main database tables"""
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()
            
            # Main submissions table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_detector_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                submission_text TEXT NOT NULL,
                title TEXT,
                course_code TEXT,
                assignment_id TEXT,
                submission_date TEXT NOT NULL,
                word_count INTEGER,
                character_count INTEGER,
                institution_id TEXT
            )
            ''')
            
            # Results table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_detector_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                ai_score REAL NOT NULL,
                confidence REAL NOT NULL,
                detailed_results TEXT,
                created_at TEXT NOT NULL,
                style_deviation REAL,
                FOREIGN KEY (submission_id) REFERENCES ai_detector_submissions (id)
            )
            ''')
            
            # Users table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            ''')
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise DatabaseError(f"Failed to initialize database: {e}")
    
    def _init_advanced_db_tables(self):
        """Initialize additional database tables for new features"""
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()
            
            # Submission metadata table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_detector_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                time_taken INTEGER,
                browser_info TEXT,
                device_fingerprint TEXT,
                ip_address TEXT,
                location_data TEXT,
                keystroke_data TEXT,
                FOREIGN KEY (submission_id) REFERENCES ai_detector_submissions (id)
            )
            ''')
            
            # Institution data
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS institutions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT,
                country TEXT,
                created_at TEXT NOT NULL
            )
            ''')
            
            # Student demographics (for bias analysis)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_demographics (
                student_id TEXT PRIMARY KEY,
                age_group TEXT,
                gender TEXT,
                ethnicity TEXT,
                native_language TEXT,
                academic_level TEXT,
                accommodations TEXT
            )
            ''')

            # Main submissions table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_detector_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                submission_text TEXT NOT NULL,
                title TEXT,
                course_code TEXT,
                assignment_id TEXT,
                submission_date TEXT NOT NULL,
                word_count INTEGER,
                character_count INTEGER,
                institution_id TEXT
            )
            ''')
            
            # Results table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_detector_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                ai_score REAL NOT NULL,
                confidence REAL NOT NULL,
                detailed_results TEXT,
                created_at TEXT NOT NULL,
                style_deviation REAL,
                FOREIGN KEY (submission_id) REFERENCES ai_detector_submissions (id)
            )
            ''')
            
            # Real-time processing queue
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS processing_queue (
                id TEXT PRIMARY KEY,
                submission_data TEXT NOT NULL,
                priority INTEGER DEFAULT 1,
                status TEXT DEFAULT 'queued',
                created_at TEXT NOT NULL,
                processed_at TEXT
            )
            ''')
            
            # Advanced detection results
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS advanced_detection_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                temporal_analysis TEXT,
                citation_analysis TEXT,
                behavioral_analysis TEXT,
                multimodal_analysis TEXT,
                adversarial_analysis TEXT,
                ensemble_prediction TEXT,
                risk_prediction TEXT,
                bias_adjusted_score REAL,
                blockchain_hash TEXT,
                FOREIGN KEY (submission_id) REFERENCES ai_detector_submissions (id)
            )
            ''')
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error initializing advanced database tables: {e}")

    def _safe_db_connect(self):
        """Safely connect to database with proper error handling"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            raise DatabaseError(f"Failed to connect to database: {e}")

    def get_enhanced_statistics(self) -> Dict[str, Any]:
        """
        Enhanced statistics with better error handling and defensive programming
        """
        try:
            # 🔧 DEFENSIVE: Ensure detection_threshold exists with a default value
            detection_threshold = getattr(self, 'detection_threshold', 0.7)
            
            conn = self._safe_db_connect()
            if not conn:
                return self._get_fallback_statistics()
                
            cursor = conn.cursor()
            
            # Get basic counts with error handling
            try:
                cursor.execute('SELECT COUNT(*) as total FROM ai_detector_submissions')
                total_submissions = cursor.fetchone()['total']
            except:
                total_submissions = 0
            
            try:
                cursor.execute('SELECT COUNT(DISTINCT student_id) as total FROM ai_detector_submissions')
                unique_students = cursor.fetchone()['total']
            except:
                unique_students = 0
            
            try:
                cursor.execute('SELECT AVG(ai_score) as avg FROM ai_detector_results WHERE ai_score IS NOT NULL')
                result = cursor.fetchone()
                avg_score = result['avg'] if result and result['avg'] is not None else 0.0
            except:
                avg_score = 0.0
            
            # Get recent activity
            try:
                cursor.execute('''
                SELECT COUNT(*) as recent_count 
                FROM ai_detector_submissions 
                WHERE submission_date >= datetime('now', '-7 days')
                ''')
                recent_submissions = cursor.fetchone()['recent_count']
            except:
                recent_submissions = 0
            
            # Get high-risk submissions
            try:
                cursor.execute('''
                SELECT COUNT(*) as high_risk_count 
                FROM ai_detector_results 
                WHERE ai_score >= ?
                ''', (detection_threshold,))
                high_risk_submissions = cursor.fetchone()['high_risk_count']
            except:
                high_risk_submissions = 0
            
            conn.close()
            
            return {
                'total_submissions': total_submissions,
                'unique_students': unique_students,
                'average_ai_score': round(avg_score, 3),
                'recent_submissions_7_days': recent_submissions,
                'high_risk_submissions': high_risk_submissions,
                'detection_threshold': detection_threshold,
                'active_style_profiles': len(getattr(self, 'style_profiles', {})),
                'active_detection_methods': len(getattr(self, 'detection_methods', {})),
                'database_status': 'connected',
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting enhanced statistics: {e}")
            return self._get_fallback_statistics()

    def _get_fallback_statistics(self) -> Dict[str, Any]:
        """Fallback statistics when database is unavailable"""
        return {
            'total_submissions': 0,
            'unique_students': 0,
            'average_ai_score': 0.0,
            'recent_submissions_7_days': 0,
            'high_risk_submissions': 0,
            'detection_threshold': getattr(self, 'detection_threshold', 0.7),
            'active_style_profiles': 0,
            'active_detection_methods': 0,
            'database_status': 'error',
            'error': 'Database unavailable',
            'generated_at': datetime.now().isoformat()
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Basic statistics method (wrapper for get_enhanced_statistics)
        This fixes the missing get_statistics method error
        """
        try:
            return self.get_enhanced_statistics()
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {
                'total_submissions': 0,
                'unique_students': 0,
                'average_ai_score': 0.0,
                'active_style_profiles': 0,
                'error': str(e)
            }

    def fix_detector_instance(detector):
        """Quick fix for an existing detector instance"""
        if not hasattr(detector, 'detection_threshold'):
            detector.detection_threshold = 0.7
        
        if not hasattr(detector, 'detection_methods'):
            detector.detection_methods = {
                'pattern_matching': True,
                'statistical_analysis': True,
                'behavioral_analysis': True,
                'temporal_analysis': True,
                'citation_verification': True
            }
        
        if not hasattr(detector, 'style_profiles'):
            detector.style_profiles = {}
        
        # Try to fix database schema
        try:
            detector.fix_database_schema()
        except:
            pass
        
        return detector

    def get_statistics_fallback(self) -> Dict[str, Any]:
        """Fallback statistics method that doesn't break"""
        try:
            return {
                'total_submissions': 0,
                'unique_students': 0,
                'average_ai_score': 0.0,
                'active_style_profiles': 0,
                'detection_threshold': getattr(self, 'detection_threshold', 0.7),
                'status': 'basic_mode',
                'message': 'Running in basic mode due to initialization issues'
            }
        except:
            return {
                'error': 'Statistics unavailable',
                'status': 'error'
            }
    
    def get_submission_history(self, student_id: str = None, limit: int = 50) -> Dict[str, Any]:
        """
        Fixed submission history method that handles missing column names
        """
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()
            
            # Build query with proper column handling
            base_query = '''
            SELECT
                s.id,
                s.student_id,
                s.submission_text,
                COALESCE(s.title, 'Untitled') as title,
                s.course_code,
                s.assignment_id,
                s.submission_date,
                s.word_count,
                s.character_count,
                s.institution_id,
                r.ai_score,
                r.confidence,
                r.created_at as analysis_date
            FROM ai_detector_submissions s
            LEFT JOIN ai_detector_results r ON s.id = r.submission_id
            '''
            
            if student_id:
                query = base_query + " WHERE s.student_id = ? ORDER BY s.submission_date DESC LIMIT ?"
                params = (student_id, limit)
            else:
                query = base_query + " ORDER BY s.submission_date DESC LIMIT ?"
                params = (limit,)
            
            cursor.execute(query, params)
            submissions = []
            
            for row in cursor.fetchall():
                try:
                    submission = {
                        'id': row['id'],
                        'student_id': row['student_id'],
                        'title': row['title'] or 'Untitled',
                        'course_code': row['course_code'],
                        'assignment_id': row['assignment_id'],
                        'submission_date': row['submission_date'],
                        'word_count': row['word_count'],
                        'character_count': row['character_count'],
                        'institution_id': row['institution_id'],
                        'ai_score': row['ai_score'],
                        'confidence': row['confidence'],
                        'analysis_date': row['analysis_date'],
                        'is_ai_generated': (row['ai_score'] or 0) >= self.detection_threshold,
                        'text_preview': (row['submission_text'] or '')[:200] + "..." if len(row['submission_text'] or '') > 200 else (row['submission_text'] or '')
                    }
                    submissions.append(submission)
                except Exception as row_error:
                    logger.warning(f"Error processing submission row: {row_error}")
                    continue
            
            conn.close()
            
            return {
                'submissions': submissions,
                'total_count': len(submissions),
                'student_filter': student_id,
                'limit': limit
            }
            
        except Exception as e:
            logger.error(f"Error getting submission history: {e}")
            return {
                'submissions': [],
                'total_count': 0,
                'error': str(e),
                'student_filter': student_id,
                'limit': limit
            }
    
    def fix_database_schema(self):
        """
        Fix database schema issues by adding missing columns
        """
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()
            
            # Check if title column exists, if not add it
            cursor.execute("PRAGMA table_info(ai_detector_submissions)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'title' not in columns and 'submission_title' in columns:
                # Rename submission_title to title
                cursor.execute('''
                ALTER TABLE ai_detector_submissions 
                RENAME COLUMN submission_title TO title
                ''')
                logger.info("Renamed submission_title column to title")
            
            elif 'title' not in columns:
                # Add title column
                cursor.execute('''
                ALTER TABLE ai_detector_submissions 
                ADD COLUMN title TEXT
                ''')
                logger.info("Added missing title column")
            
            # Ensure other common columns exist
            # Define allowed column names and types for validation
            ALLOWED_COLUMN_TYPES = {'TEXT', 'INTEGER', 'REAL', 'BLOB'}
            ALLOWED_COLUMN_NAMES = {'institution_id', 'word_count', 'character_count'}

            missing_columns = {
                'institution_id': 'TEXT',
                'word_count': 'INTEGER',
                'character_count': 'INTEGER'
            }

            for col_name, col_type in missing_columns.items():
                # Validate column name and type to prevent SQL injection
                if col_name not in ALLOWED_COLUMN_NAMES:
                    logger.error(f"Invalid column name: {col_name}")
                    continue
                if col_type not in ALLOWED_COLUMN_TYPES:
                    logger.error(f"Invalid column type: {col_type}")
                    continue

                if col_name not in columns:
                    cursor.execute(f'''
                    ALTER TABLE ai_detector_submissions
                    ADD COLUMN {col_name} {col_type}
                    ''')
                    logger.info(f"Added missing {col_name} column")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error fixing database schema: {e}")
    
    def get_enhanced_statistics(self) -> Dict[str, Any]:
        """
        Enhanced statistics with better error handling
        """
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()
            
            # Get basic counts with error handling
            try:
                cursor.execute('SELECT COUNT(*) as total FROM ai_detector_submissions')
                total_submissions = cursor.fetchone()['total']
            except:
                total_submissions = 0
            
            try:
                cursor.execute('SELECT COUNT(DISTINCT student_id) as total FROM ai_detector_submissions')
                unique_students = cursor.fetchone()['total']
            except:
                unique_students = 0
            
            try:
                cursor.execute('SELECT AVG(ai_score) as avg FROM ai_detector_results WHERE ai_score IS NOT NULL')
                result = cursor.fetchone()
                avg_score = result['avg'] if result and result['avg'] is not None else 0.0
            except:
                avg_score = 0.0
            
            # Get recent activity
            try:
                cursor.execute('''
                SELECT COUNT(*) as recent_count 
                FROM ai_detector_submissions 
                WHERE submission_date >= datetime('now', '-7 days')
                ''')
                recent_submissions = cursor.fetchone()['recent_count']
            except:
                recent_submissions = 0
            
            # Get high-risk submissions
            try:
                cursor.execute('''
                SELECT COUNT(*) as high_risk_count 
                FROM ai_detector_results 
                WHERE ai_score >= ?
                ''', (self.detection_threshold,))
                high_risk_submissions = cursor.fetchone()['high_risk_count']
            except:
                high_risk_submissions = 0
            
            conn.close()
            
            return {
                'total_submissions': total_submissions,
                'unique_students': unique_students,
                'average_ai_score': round(avg_score, 3),
                'recent_submissions_7_days': recent_submissions,
                'high_risk_submissions': high_risk_submissions,
                'detection_threshold': self.detection_threshold,
                'active_style_profiles': len(getattr(self, 'style_profiles', {})),
                'active_detection_methods': len(getattr(self, 'detection_methods', {})),
                'database_status': 'connected',
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting enhanced statistics: {e}")
            return {
                'total_submissions': 0,
                'unique_students': 0,
                'average_ai_score': 0.0,
                'recent_submissions_7_days': 0,
                'high_risk_submissions': 0,
                'detection_threshold': self.detection_threshold,
                'active_style_profiles': 0,
                'active_detection_methods': 0,
                'database_status': 'error',
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }
    
    def list_submissions(self, student_id: str = None, limit: int = 10, 
                        include_text: bool = False) -> Dict[str, Any]:
        """
        Enhanced list_submissions with better error handling
        """
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()
            
            # Build flexible query that handles missing columns
            select_fields = [
                's.id',
                's.student_id', 
                'COALESCE(s.title, "Untitled") as title',
                's.course_code',
                's.assignment_id',
                's.submission_date',
                'COALESCE(s.word_count, 0) as word_count',
                'COALESCE(s.character_count, 0) as character_count',
                'r.ai_score',
                'r.confidence'
            ]
            
            if include_text:
                select_fields.append('s.submission_text')
            
            query = f'''
            SELECT {", ".join(select_fields)}
            FROM ai_detector_submissions s
            LEFT JOIN ai_detector_results r ON s.id = r.submission_id
            '''
            
            params = []
            if student_id:
                query += " WHERE s.student_id = ?"
                params.append(student_id)
            
            query += " ORDER BY s.submission_date DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            submissions = []
            
            for row in cursor.fetchall():
                try:
                    submission = dict(row)
                    # Add computed fields
                    submission['is_ai_generated'] = (submission.get('ai_score') or 0) >= self.detection_threshold
                    submission['risk_level'] = self._calculate_risk_level(submission.get('ai_score', 0))
                    
                    if not include_text and 'submission_text' in submission:
                        # Add preview instead of full text
                        text = submission.pop('submission_text', '')
                        submission['text_preview'] = text[:200] + "..." if len(text) > 200 else text
                    
                    submissions.append(submission)
                except Exception as row_error:
                    logger.warning(f"Error processing submission row: {row_error}")
                    continue
            
            conn.close()
            
            return {
                'submissions': submissions,
                'total': len(submissions),
                'student_filter': student_id,
                'limit': limit,
                'include_text': include_text
            }
            
        except Exception as e:
            logger.error(f"Error listing submissions: {e}")
            return {
                'submissions': [],
                'total': 0,
                'error': str(e),
                'student_filter': student_id,
                'limit': limit
            }
    
    def _calculate_risk_level(self, ai_score: float) -> str:
        """Calculate risk level based on AI score"""
        if ai_score >= 0.9:
            return 'critical'
        elif ai_score >= 0.7:
            return 'high'
        elif ai_score >= 0.5:
            return 'medium'
        else:
            return 'low'
    
    def get_submission_details(self, submission_id: int) -> Dict[str, Any]:
        """Get detailed information about a specific submission"""
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT 
                s.*,
                r.ai_score,
                r.confidence,
                r.detailed_results,
                r.created_at as analysis_date
            FROM ai_detector_submissions s
            LEFT JOIN ai_detector_results r ON s.id = r.submission_id
            WHERE s.id = ?
            ''', (submission_id,))
            
            row = cursor.fetchone()
            if not row:
                return {'error': 'Submission not found'}
            
            submission = dict(row)
            
            # Parse detailed results if available
            if submission.get('detailed_results'):
                try:
                    submission['detailed_results'] = json.loads(submission['detailed_results'])
                except:
                    pass
            
            # Add computed fields
            submission['is_ai_generated'] = (submission.get('ai_score') or 0) >= self.detection_threshold
            submission['risk_level'] = self._calculate_risk_level(submission.get('ai_score', 0))
            submission['word_count'] = submission.get('word_count') or len((submission.get('submission_text') or '').split())
            submission['character_count'] = submission.get('character_count') or len(submission.get('submission_text') or '')
            
            conn.close()
            return submission
            
        except Exception as e:
            logger.error(f"Error getting submission details: {e}")
            return {'error': str(e)}

    def patch_ai_detector_class():
        """
        Quick patch function - add these methods directly to your AIDetector class
        """
        
        # Method 1: Add to __init__
        def add_to_init(self):
            """Add these lines to your __init__ method"""
            # Add missing attributes
            if not hasattr(self, 'detection_methods'):
                self.detection_methods = {
                    'pattern_matching': True,
                    'statistical_analysis': True,
                    'behavioral_analysis': True,
                    'temporal_analysis': True,
                    'citation_verification': True
                }
            
            if not hasattr(self, 'style_profiles'):
                self.style_profiles = {}
            
            # Fix database schema on initialization
            try:
                self.fix_database_schema()
            except:
                pass
        
        # Method 2: Quick fix methods
        def get_statistics(self):
            """Quick fix for missing get_statistics method"""
            return self.get_enhanced_statistics()
        
        def fix_database_schema(self):
            """Quick fix for database schema issues"""
            try:
                conn = self._safe_db_connect()
                cursor = conn.cursor()
                
                # Add title column if missing
                try:
                    cursor.execute('ALTER TABLE ai_detector_submissions ADD COLUMN title TEXT')
                except:
                    pass  # Column might already exist
                    
                conn.close()
            except:
                pass

    def analyze_text(self, text: str, title: str = None, student_id: str = None, 
                    course_code: str = None, assignment_id: str = None) -> Dict[str, Any]:
        """
        Basic text analysis method - wrapper for enhanced analysis
        This method provides backward compatibility and serves as the main entry point
        """
        try:
            # Call the enhanced analysis method
            result = self.analyze_text_enhanced(
                text=text,
                title=title,
                student_id=student_id,
                course_code=course_code,
                assignment_id=assignment_id
            )
            
            logger.info(f"Text analysis completed for {len(text)} characters")
            return result
            
        except Exception as e:
            logger.error(f"Error in text analysis: {e}")
            raise AIDetectionError(f"Analysis failed: {e}")
            
    def analyze_text_ultimate(self, text: str, title: str = None, student_id: str = None, 
                             course_code: str = None, assignment_id: str = None,
                             metadata: SubmissionMetadata = None, images: List[bytes] = None,
                             code_content: str = None, programming_language: str = None) -> Dict[str, Any]:
        """Ultimate text analysis with all advanced features"""
        
        # Check privacy compliance first
        if student_id:
            compliance_check = self.compliance_manager.check_compliance_before_processing(
                student_id, 'ai_detection'
            )
            if not compliance_check['can_process']:
                raise PrivacyError(f"Cannot process due to compliance requirements: {compliance_check['requirements']}")
        
        # Record data access for audit
        self.privacy_manager.record_data_access('analyze_text', student_id, 'submission_text')
        
        # Start with base analysis
        base_results = super().analyze_text_enhanced(text, title, student_id, course_code, assignment_id)
        
        # Initialize ultimate results
        ultimate_results = base_results.copy()
        ultimate_results['advanced_analyses'] = {}
        ultimate_results['risk_factors'] = []
        ultimate_results['recommendations'] = []
        
        # Temporal Analysis
        if metadata and metadata.time_taken:
            temporal_result = self.temporal_analyzer.analyze_writing_speed(text, metadata.time_taken)
            ultimate_results['advanced_analyses']['temporal'] = temporal_result.__dict__
            if temporal_result.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                ultimate_results['risk_factors'].append('unusual_writing_speed')
        
        # Citation Verification
        citation_result = self.citation_verifier.verify_citations(text)
        ultimate_results['advanced_analyses']['citations'] = citation_result.__dict__
        if citation_result.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            ultimate_results['risk_factors'].append('suspicious_citations')
        
        # Behavioral Analysis
        if metadata:
            behavioral_result = self.behavioral_analyzer.analyze_submission_behavior(metadata, text)
            ultimate_results['advanced_analyses']['behavioral'] = behavioral_result.__dict__
            if behavioral_result.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                ultimate_results['risk_factors'].append('suspicious_behavior')
        
        # Multi-Modal Analysis
        if images:
            multimodal_result = self.multimodal_analyzer.analyze_image_text_consistency(text, images)
            ultimate_results['advanced_analyses']['multimodal'] = multimodal_result.__dict__
            if multimodal_result.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                ultimate_results['risk_factors'].append('image_text_inconsistency')
        
        # Code Analysis
        if code_content and programming_language:
            code_result = self.multimodal_analyzer.analyze_code_submission(code_content, programming_language)
            ultimate_results['advanced_analyses']['code'] = code_result.__dict__
            if code_result.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                ultimate_results['risk_factors'].append('ai_generated_code')
        
        # Adversarial Detection
        adversarial_result = self.adversarial_detector.detect_evasion_attempts(text)
        ultimate_results['advanced_analyses']['adversarial'] = adversarial_result.__dict__
        if adversarial_result.risk_level == RiskLevel.CRITICAL:
            ultimate_results['risk_factors'].append('evasion_attempt')
        
        # Advanced ML Prediction
        ensemble_prediction = self.advanced_ml_trainer.predict_ensemble(text)
        if ensemble_prediction:
            ultimate_results['advanced_analyses']['ensemble_ml'] = ensemble_prediction
            # Update overall score with ensemble prediction
            ensemble_weight = 0.3
            ultimate_results['ai_score'] = (
                ultimate_results['ai_score'] * (1 - ensemble_weight) +
                ensemble_prediction['ensemble_score'] * ensemble_weight
            )
        
        # Bias Detection and Correction
        if student_id:
            # Get student demographics for bias analysis
            student_demographics = self._get_student_demographics(student_id)
            if student_demographics:
                bias_adjusted_score = self.bias_detector.apply_bias_correction(
                    ultimate_results['ai_score'], student_demographics
                )
                ultimate_results['bias_adjusted_score'] = bias_adjusted_score
        
        # Predictive Risk Analysis
        if student_id:
            risk_prediction = self.predictive_analytics.predict_student_risk(student_id)
            ultimate_results['advanced_analyses']['risk_prediction'] = risk_prediction
            if risk_prediction['risk_level'] == 'high':
                ultimate_results['risk_factors'].append('high_risk_student_profile')
        
        # Visual Analysis Data
        if ultimate_results.get('sentence_analysis'):
            sentence_scores = [s['ai_score'] for s in ultimate_results['sentence_analysis']['sentences']]
            heatmap_data = self.visual_analyzer.generate_text_heatmap(text, sentence_scores)
            ultimate_results['visual_analysis'] = {
                'heatmap': heatmap_data,
                'writing_flow': self.visual_analyzer.generate_writing_flow_visualization(text)
            }
        
        # Generate comprehensive recommendations
        ultimate_results['recommendations'] = self._generate_ultimate_recommendations(ultimate_results)
        
        # Calculate final risk level
        ultimate_results['final_risk_level'] = self._calculate_final_risk_level(ultimate_results)
        
        # Create blockchain record for audit trail
        blockchain_hash = self.blockchain_audit.create_detection_record(
            ultimate_results['submission_id'], ultimate_results
        )
        ultimate_results['blockchain_hash'] = blockchain_hash
        
        # Store advanced results
        self._store_advanced_results(ultimate_results, metadata)
        
        return ultimate_results
    
    def _get_student_demographics(self, student_id: str) -> Optional[Dict[str, str]]:
        """Get student demographics for bias analysis"""
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM student_demographics WHERE student_id = ?', (student_id,))
            result = cursor.fetchone()
            conn.close()
            
            return dict(result) if result else None
            
        except Exception as e:
            logger.debug(f"Error getting student demographics: {e}")
            return None
    
    def _generate_ultimate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate comprehensive recommendations based on all analyses"""
        recommendations = []
        
        # Risk-based recommendations
        risk_factors = results.get('risk_factors', [])
        
        if 'unusual_writing_speed' in risk_factors:
            recommendations.append("Consider reviewing the submission timeline and interviewing the student about their writing process")
        
        if 'suspicious_citations' in risk_factors:
            recommendations.append("Verify citations manually and discuss proper citation practices with the student")
        
        if 'suspicious_behavior' in risk_factors:
            recommendations.append("Review submission metadata and consider requiring supervised completion of future assignments")
        
        if 'evasion_attempt' in risk_factors:
            recommendations.append("CRITICAL: Evidence of deliberate evasion detected. Immediate review recommended")
        
        if 'ai_generated_code' in risk_factors:
            recommendations.append("Review code for originality and consider requiring explanation of implementation choices")
        
        # Score-based recommendations
        final_score = results.get('ai_score', 0)
        
        if final_score > 0.9:
            recommendations.append("High confidence AI detection. Consider academic integrity proceedings")
        elif final_score > 0.7:
            recommendations.append("Probable AI usage. Follow up with student interview recommended")
        elif final_score > 0.5:
            recommendations.append("Some AI indicators present. Educational intervention may be beneficial")
        
        # Predictive recommendations
        risk_prediction = results.get('advanced_analyses', {}).get('risk_prediction', {})
        if risk_prediction.get('risk_level') == 'high':
            recommendations.append("Student profile indicates elevated risk. Consider additional support and monitoring")
        
        return recommendations
    
    def _calculate_final_risk_level(self, results: Dict[str, Any]) -> str:
        """Calculate final risk level based on all factors"""
        risk_factors = results.get('risk_factors', [])
        ai_score = results.get('ai_score', 0)
        
        # Critical factors
        if 'evasion_attempt' in risk_factors:
            return 'critical'
        
        # High risk factors
        high_risk_count = sum(1 for factor in risk_factors if factor in [
            'suspicious_citations', 'ai_generated_code', 'high_risk_student_profile'
        ])
        
        if ai_score > 0.9 or high_risk_count >= 2:
            return 'high'
        elif ai_score > 0.7 or high_risk_count >= 1:
            return 'medium'
        else:
            return 'low'
    
    def _store_advanced_results(self, results: Dict[str, Any], metadata: SubmissionMetadata):
        """Store advanced analysis results"""
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()
            
            submission_id = results['submission_id']
            
            # Store metadata if provided
            if metadata:
                cursor.execute('''
                INSERT OR REPLACE INTO ai_detector_metadata
                (submission_id, time_taken, browser_info, device_fingerprint, ip_address, location_data)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    submission_id,
                    metadata.time_taken,
                    json.dumps(metadata.browser_info) if metadata.browser_info else None,
                    metadata.device_fingerprint,
                    metadata.ip_address,
                    json.dumps(metadata.location) if metadata.location else None
                ))
            
            # Store advanced results
            advanced_analyses = results.get('advanced_analyses', {})
            
            cursor.execute('''
            INSERT INTO advanced_detection_results
            (submission_id, temporal_analysis, citation_analysis, behavioral_analysis,
             multimodal_analysis, adversarial_analysis, ensemble_prediction, risk_prediction,
             bias_adjusted_score, blockchain_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                submission_id,
                json.dumps(advanced_analyses.get('temporal')),
                json.dumps(advanced_analyses.get('citations')),
                json.dumps(advanced_analyses.get('behavioral')),
                json.dumps(advanced_analyses.get('multimodal')),
                json.dumps(advanced_analyses.get('adversarial')),
                json.dumps(advanced_analyses.get('ensemble_ml')),
                json.dumps(advanced_analyses.get('risk_prediction')),
                results.get('bias_adjusted_score'),
                results.get('blockchain_hash')
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing advanced results: {e}")
    
    def start_real_time_monitoring(self, num_workers: int = 3):
        """Start real-time submission monitoring"""
        self.realtime_processor.start_real_time_processing(num_workers)
        logger.info("Real-time monitoring started")
    
    def stop_real_time_monitoring(self):
        """Stop real-time submission monitoring"""
        self.realtime_processor.stop_real_time_processing()
        logger.info("Real-time monitoring stopped")
    
    def configure_federated_learning(self, institution_id: str, federation_config: Dict):
        """Configure federated learning"""
        self.federated_learning.initialize_federation(institution_id, federation_config)
        logger.info(f"Federated learning configured for institution {institution_id}")
    
    def train_advanced_models(self):
        """Train all advanced ML models"""
        try:
            # Train ensemble model
            ensemble_results = self.advanced_ml_trainer.train_ensemble_model()
            logger.info(f"Ensemble model trained: {ensemble_results}")
            
            # Train risk prediction model
            self.predictive_analytics.train_risk_prediction_model()
            logger.info("Risk prediction model trained")
            
            return {
                'ensemble_training': ensemble_results,
                'risk_model_trained': True
            }
            
        except Exception as e:
            logger.error(f"Error training advanced models: {e}")
            return {'error': str(e)}
    
    def analyze_institutional_bias(self, institution_id: str) -> Dict[str, Any]:
        """Analyze bias in AI detection for an institution"""
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()
            
            # Get demographic data for institution
            cursor.execute('''
            SELECT sd.gender, sd.ethnicity, sd.native_language, sd.academic_level
            FROM student_demographics sd
            JOIN ai_detector_submissions s ON sd.student_id = s.student_id
            WHERE s.institution_id = ?
            ''', (institution_id,))
            
            demographic_data = {}
            for row in cursor.fetchall():
                for field, value in row.items():
                    if value:
                        if field not in demographic_data:
                            demographic_data[field] = []
                        demographic_data[field].append(value)
            
            conn.close()
            
            # Analyze bias across demographic groups
            bias_analysis = self.bias_detector.analyze_detection_bias(demographic_data)
            
            return {
                'institution_id': institution_id,
                'bias_analysis': bias_analysis,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing institutional bias: {e}")
            return {'error': str(e)}
    
    def generate_comprehensive_report(self, report_type: str, **kwargs) -> Dict[str, Any]:
        """Generate comprehensive reports with all new features"""
        if report_type == 'institution_dashboard':
            return self._generate_institution_dashboard(**kwargs)
        elif report_type == 'student_risk_profile':
            return self._generate_student_risk_profile(**kwargs)
        elif report_type == 'compliance_audit':
            return self.compliance_manager.generate_compliance_report()
        elif report_type == 'bias_analysis':
            return self.analyze_institutional_bias(kwargs.get('institution_id'))
        elif report_type == 'benchmark_comparison':
            return self.institution_benchmarking.generate_benchmark_report(**kwargs)
        else:
            return super().generate_report(report_type, **kwargs)
    
    def _generate_institution_dashboard(self, institution_id: str, period: str = '1_month') -> Dict[str, Any]:
        """Generate comprehensive institution dashboard"""
        try:
            # Calculate period
            if period == '1_month':
                start_date = datetime.now() - timedelta(days=30)
            elif period == '3_months':
                start_date = datetime.now() - timedelta(days=90)
            elif period == '1_year':
                start_date = datetime.now() - timedelta(days=365)
            else:
                start_date = datetime.now() - timedelta(days=30)
            
            conn = self._safe_db_connect()
            cursor = conn.cursor()
            
            # Basic metrics
            cursor.execute('''
            SELECT 
                COUNT(*) as total_submissions,
                COUNT(DISTINCT s.student_id) as unique_students,
                COUNT(DISTINCT s.course_code) as courses,
                AVG(r.ai_score) as avg_ai_score,
                COUNT(CASE WHEN r.ai_score >= 0.7 THEN 1 END) as flagged_submissions
            FROM ai_detector_submissions s
            JOIN ai_detector_results r ON s.id = r.submission_id
            WHERE s.institution_id = ? AND s.submission_date >= ?
            ''', (institution_id, start_date.isoformat()))
            
            basic_metrics = cursor.fetchone()
            
            # Trend analysis
            cursor.execute('''
            SELECT 
                DATE(s.submission_date) as date,
                COUNT(*) as daily_submissions,
                AVG(r.ai_score) as daily_avg_score
            FROM ai_detector_submissions s
            JOIN ai_detector_results r ON s.id = r.submission_id
            WHERE s.institution_id = ? AND s.submission_date >= ?
            GROUP BY DATE(s.submission_date)
            ORDER BY date
            ''', (institution_id, start_date.isoformat()))
            
            trend_data = cursor.fetchall()
            
            # Risk distribution
            cursor.execute('''
            SELECT 
                CASE 
                    WHEN r.ai_score >= 0.9 THEN 'critical'
                    WHEN r.ai_score >= 0.7 THEN 'high'
                    WHEN r.ai_score >= 0.5 THEN 'medium'
                    ELSE 'low'
                END as risk_level,
                COUNT(*) as count
            FROM ai_detector_submissions s
            JOIN ai_detector_results r ON s.id = r.submission_id
            WHERE s.institution_id = ? AND s.submission_date >= ?
            GROUP BY risk_level
            ''', (institution_id, start_date.isoformat()))
            
            risk_distribution = {row['risk_level']: row['count'] for row in cursor.fetchall()}
            
            conn.close()
            
            # Get benchmarking data
            benchmark_data = self.institution_benchmarking.generate_benchmark_report(institution_id, period)
            
            # Get compliance status
            compliance_data = self.compliance_manager.generate_compliance_report()
            
            dashboard = {
                'institution_id': institution_id,
                'period': period,
                'basic_metrics': dict(basic_metrics),
                'trend_analysis': [dict(row) for row in trend_data],
                'risk_distribution': risk_distribution,
                'benchmark_comparison': benchmark_data,
                'compliance_status': compliance_data,
                'generated_at': datetime.now().isoformat()
            }
            
            return dashboard
            
        except Exception as e:
            logger.error(f"Error generating institution dashboard: {e}")
            return {'error': str(e)}
    
    def _generate_student_risk_profile(self, student_id: str) -> Dict[str, Any]:
        """Generate comprehensive student risk profile"""
        try:
            # Get submission history
            submissions = self.list_submissions(student_id=student_id, limit=50)
            
            # Get predictive risk analysis
            risk_prediction = self.predictive_analytics.predict_student_risk(student_id)
            
            # Get temporal patterns
            temporal_patterns = self.temporal_analyzer.analyze_submission_patterns(student_id)
            
            # Calculate trend
            submission_scores = [s['ai_score'] for s in submissions['submissions'] if s['ai_score']]
            
            trend = 'stable'
            if len(submission_scores) >= 3:
                recent_avg = sum(submission_scores[:3]) / 3
                older_avg = sum(submission_scores[3:6]) / max(1, len(submission_scores[3:6]))
                
                if recent_avg > older_avg + 0.2:
                    trend = 'increasing_risk'
                elif recent_avg < older_avg - 0.2:
                    trend = 'decreasing_risk'
            
            profile = {
                'student_id': student_id,
                'submission_history': submissions,
                'risk_prediction': risk_prediction,
                'temporal_patterns': temporal_patterns,
                'trend_analysis': {
                    'trend': trend,
                    'recent_submissions': len(submission_scores[:5]),
                    'avg_recent_score': sum(submission_scores[:5]) / len(submission_scores[:5]) if submission_scores else 0
                },
                'recommendations': self._generate_student_recommendations(risk_prediction, temporal_patterns, trend),
                'generated_at': datetime.now().isoformat()
            }
            
            return profile
            
        except Exception as e:
            logger.error(f"Error generating student risk profile: {e}")
            return {'error': str(e)}
    
    def _generate_student_recommendations(self, risk_prediction: Dict, temporal_patterns: Dict, trend: str) -> List[str]:
        """Generate recommendations for student"""
        recommendations = []
        
        if risk_prediction.get('risk_level') == 'high':
            recommendations.append("High-risk profile detected. Consider academic integrity education and increased monitoring")
        
        if temporal_patterns.get('suspicious_hour_ratio', 0) > 0.5:
            recommendations.append("Unusual submission timing patterns. Consider discussing time management and study habits")
        
        if trend == 'increasing_risk':
            recommendations.append("Risk trend increasing. Early intervention recommended")
        elif trend == 'decreasing_risk':
            recommendations.append("Positive trend observed. Continue current support strategies")
        
        return recommendations
    
    def enable_student_self_check(self) -> str:
        """Enable student self-check functionality"""
        # In a real implementation, this would set up web endpoints or API access
        logger.info("Student self-check tool enabled")
        return "Self-check tool available at /student/self-check"
    
    def get_ultimate_statistics(self) -> Dict[str, Any]:
        """Get comprehensive system statistics"""
        try:
            basic_stats = super().get_enhanced_statistics()
            
            # Add advanced statistics
            conn = self._safe_db_connect()
            cursor = conn.cursor()
            
            # Advanced ML statistics
            cursor.execute('''
            SELECT 
                COUNT(CASE WHEN ensemble_prediction IS NOT NULL THEN 1 END) as ensemble_predictions,
                AVG(bias_adjusted_score) as avg_bias_adjusted_score
            FROM advanced_detection_results
            WHERE ensemble_prediction IS NOT NULL
            ''')
            
            advanced_stats = cursor.fetchone()
            
            # Real-time processing stats
            queue_status = {
                'queued_tasks': len(self.realtime_processor.processing_queue),
                'active_workers': len(self.realtime_processor.workers),
                'is_running': self.realtime_processor.is_running
            }
            
            # Compliance stats
            cursor.execute('''
            SELECT 
                COUNT(DISTINCT student_id) as students_with_consent
            FROM privacy_consent
            WHERE granted = 1
            ''')
            
            consent_stats = cursor.fetchone()
            
            conn.close()
            
            ultimate_stats = {
                **basic_stats,
                'advanced_ml': {
                    'ensemble_predictions': advanced_stats['ensemble_predictions'] if advanced_stats else 0,
                    'avg_bias_adjusted_score': advanced_stats['avg_bias_adjusted_score'] if advanced_stats else 0,
                    'models_available': len(self.advanced_ml_trainer.models)
                },
                'real_time_processing': queue_status,
                'privacy_compliance': {
                    'students_with_consent': consent_stats['students_with_consent'] if consent_stats else 0
                },
                'features_active': {
                    'federated_learning': bool(self.federated_learning.institution_id),
                    'blockchain_audit': len(self.blockchain_audit.blockchain) > 0,
                    'bias_detection': True,
                    'predictive_analytics': self.predictive_analytics.risk_model is not None,
                    'adversarial_detection': True,
                    'citation_verification': True,
                    'temporal_analysis': True,
                    'multimodal_analysis': OCR_AVAILABLE,
                    'behavioral_analysis': True
                }
            }
            
            return ultimate_stats
            
        except Exception as e:
            logger.error(f"Error getting ultimate statistics: {e}")
            return {'error': str(e)}

    def analyze_text_enhanced(self, text, title=None, student_id=None, course_code=None, assignment_id=None):
        """Enhanced text analysis (base method)"""
        # Basic AI detection logic
        ai_score = self._calculate_basic_ai_score(text)
        confidence = 0.8  # Default confidence
        
        # Store submission
        submission_id = self._store_submission(text, title, student_id, course_code, assignment_id)
        
        # Store results
        self._store_results(submission_id, ai_score, confidence, {})
        
        return {
            'submission_id': submission_id,
            'ai_score': ai_score,
            'confidence': confidence,
            'is_ai_generated': ai_score >= self.detection_threshold,
            'detailed_results': {}
        }
    
    def _calculate_basic_ai_score(self, text):
        """Calculate basic AI score"""
        # Simple pattern-based scoring
        score = 0.0
        
        # Check for AI patterns
        ai_patterns = [
            r'\bhowever\b.*\bfurthermore\b',
            r'\bon one hand\b.*\bon the other hand\b',
            r'\bit is important to note\b',
            r'\bgenerally speaking\b',
            r'\bit appears that\b'
        ]
        
        for pattern in ai_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                score += 0.2
        
        return min(1.0, score)
    
    def _store_submission(self, text, title, student_id, course_code, assignment_id):
        """Store submission in database"""
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT INTO ai_detector_submissions 
            (student_id, submission_text, title, course_code, assignment_id, 
             submission_date, word_count, character_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                student_id or 'UNKNOWN',
                text,
                title,
                course_code,
                assignment_id,
                datetime.now().isoformat(),
                len(text.split()),
                len(text)
            ))
            
            submission_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return submission_id
            
        except Exception as e:
            logger.error(f"Error storing submission: {e}")
            raise DatabaseError(f"Failed to store submission: {e}")
    
    def _store_results(self, submission_id, ai_score, confidence, detailed_results):
        """Store analysis results"""
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT INTO ai_detector_results 
            (submission_id, ai_score, confidence, detailed_results, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (
                submission_id,
                ai_score,
                confidence,
                json.dumps(detailed_results),
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing results: {e}")
    
    def _detect_ai_patterns(self, text):
        """Detect AI patterns in text"""
        patterns = {
            'hedging': [
                r'\bit seems\b', r'\bit appears\b', r'\bperhaps\b', r'\bmight be\b'
            ],
            'transitions': [
                r'\bhowever\b', r'\bfurthermore\b', r'\bmoreover\b', r'\btherefore\b'
            ],
            'formality': [
                r'\bgenerally speaking\b', r'\bit is important to note\b'
            ]
        }
        
        results = {'indicators': [], 'overall_score': 0, 'confidence': 0.8}
        total_score = 0
        
        for pattern_type, pattern_list in patterns.items():
            matches = 0
            for pattern in pattern_list:
                matches += len(re.findall(pattern, text, re.IGNORECASE))
            
            if matches > 0:
                score = min(1.0, matches / 5)  # Normalize
                total_score += score
                results['indicators'].append({
                    'name': pattern_type,
                    'score': score,
                    'matches': matches
                })
        
        results['overall_score'] = min(1.0, total_score / len(patterns))
        return results

    def list_submissions(self, student_id=None, limit=10):
        """List submissions"""
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()
            
            if student_id:
                cursor.execute('''
                SELECT s.*, r.ai_score, r.confidence
                FROM ai_detector_submissions s
                LEFT JOIN ai_detector_results r ON s.id = r.submission_id
                WHERE s.student_id = ?
                ORDER BY s.submission_date DESC
                LIMIT ?
                ''', (student_id, limit))
            else:
                cursor.execute('''
                SELECT s.*, r.ai_score, r.confidence
                FROM ai_detector_submissions s
                LEFT JOIN ai_detector_results r ON s.id = r.submission_id
                ORDER BY s.submission_date DESC
                LIMIT ?
                ''', (limit,))
            
            submissions = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return {'submissions': submissions, 'total': len(submissions)}
            
        except Exception as e:
            logger.error(f"Error listing submissions: {e}")
            return {'submissions': [], 'total': 0}
    
    def get_enhanced_statistics(self):
        """Get enhanced statistics"""
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) as total FROM ai_detector_submissions')
            total_submissions = cursor.fetchone()['total']
            
            cursor.execute('SELECT COUNT(DISTINCT student_id) as total FROM ai_detector_submissions')
            unique_students = cursor.fetchone()['total']
            
            cursor.execute('SELECT AVG(ai_score) as avg FROM ai_detector_results')
            avg_score = cursor.fetchone()['avg'] or 0
            
            conn.close()
            
            return {
                'total_submissions': total_submissions,
                'unique_students': unique_students,
                'average_ai_score': avg_score,
                'active_style_profiles': 0  # Placeholder
            }
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {
                'total_submissions': 0,
                'unique_students': 0,
                'average_ai_score': 0,
                'active_style_profiles': 0
            }
    
    def set_auth(self, auth):
        """Set authentication handler"""
        self.auth = auth
        self.current_user = getattr(auth, 'current_user', None)

def ultimate_demo():
    """Fixed version of the ultimate demo"""
    print("Ultimate AI Detector Demo (Fixed)")
    print("=================================")

    try:
        # Initialize ultimate detector
        detector = AIDetector()

        # Set up authentication with demo user
        demo_auth = UserAuth()
        demo_auth.current_user = {'id': 1, 'username': 'demo_user', 'role': 'instructor'}
        detector.set_auth(demo_auth)
        
        print("✓ Ultimate AI Detector initialized with all features")
        
        # Test basic analysis first
        test_text = """
        Artificial intelligence has fundamentally transformed numerous aspects of contemporary society. 
        However, it is important to note that these developments present both opportunities and challenges.
        """
        
        print(f"\nAnalyzing text ({len(test_text)} characters)...")
        
        # Run basic analysis first
        result = detector.analyze_text_enhanced(
            text=test_text,
            title="Demo Analysis",
            student_id="DEMO_STUDENT_001",
            course_code="CS499",
            assignment_id="DEMO_PROJECT"
        )
        
        print("\n🎯 ANALYSIS RESULTS")
        print("=" * 30)
        print(f"AI Score: {result['ai_score']:.3f}")
        print(f"Confidence: {result['confidence']:.3f}")
        print(f"AI Generated: {result['is_ai_generated']}")
        
        # Get statistics
        stats = detector.get_enhanced_statistics()
        print(f"\n📈 STATISTICS")
        print(f"Total Submissions: {stats['total_submissions']}")
        print(f"Unique Students: {stats['unique_students']}")
        print(f"Average AI Score: {stats['average_ai_score']:.3f}")
        
        print("\n🎉 Demo completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        print(traceback.format_exc())
        
# Main function
def main():
    """Main function for testing the ultimate detector"""
    print("Ultimate AI Detector - Advanced Testing Mode")
    print("=" * 50)
    
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'ultimate_demo':
        ultimate_demo()
        return
    
    try:
        # Initialize ultimate detector
        detector = AIDetector()
        print("✓ Ultimate AI Detector initialized successfully!")
        
        # Get statistics
        stats = detector.get_ultimate_statistics()
        print(f"✓ System ready with {len(stats['features_active'])} advanced features")
        
        # List active features
        active_features = [name for name, active in stats['features_active'].items() if active]
        print(f"✓ Active features: {', '.join(active_features)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("This is expected if running standalone without proper database setup.")

if __name__ == "__main__":
    main()
