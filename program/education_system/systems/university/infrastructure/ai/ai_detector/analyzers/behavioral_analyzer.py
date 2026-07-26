from datetime import datetime
from typing import Dict, Any

from education_system.systems.university.infrastructure.ai.ai_detector.core.constants import logger
from education_system.systems.university.infrastructure.ai.ai_detector.core.enums import DetectionMethod, RiskLevel
from education_system.systems.university.infrastructure.ai.ai_detector.core.dataclasses import DetectionResult, SubmissionMetadata


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
