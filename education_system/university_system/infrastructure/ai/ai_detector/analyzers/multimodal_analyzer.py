import re
from typing import Dict, List, Any

from education_system.university_system.infrastructure.ai.ai_detector.core.constants import (
    logger, OCR_AVAILABLE, OPENCV_AVAILABLE, ML_AVAILABLE,
)
from education_system.university_system.infrastructure.ai.ai_detector.core.enums import DetectionMethod, RiskLevel
from education_system.university_system.infrastructure.ai.ai_detector.core.dataclasses import DetectionResult

try:
    from PIL import Image
    import pytesseract
except ImportError:
    pass

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
except ImportError:
    pass


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
