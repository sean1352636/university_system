import re
from typing import Dict, List, Any

from education_system.systems.university.shared.ai.ai_detector.core.constants import (
    logger, OCR_AVAILABLE, OPENCV_AVAILABLE, ML_AVAILABLE,
)
from education_system.systems.university.shared.ai.ai_detector.core.enums import DetectionMethod, RiskLevel
from education_system.systems.university.shared.ai.ai_detector.core.dataclasses import DetectionResult


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
                evidence={'reason': 'No images given' if images is not None and OCR_AVAILABLE
                          else 'Not assessed: text recognition (Pillow + pytesseract) is not '
                               'installed here'},
                risk_level=RiskLevel.LOW,
                informational=True,
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
                    risk_level=RiskLevel.LOW,
                    informational=True,
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
                risk_level=risk_level,
                informational=True,
            )

        except Exception as e:
            logger.error(f"Error in multi-modal analysis: {e}")
            return DetectionResult(
                method=DetectionMethod.MULTI_MODAL,
                score=0,
                confidence=0,
                evidence={'error': str(e), 'assessed': False},
                risk_level=RiskLevel.LOW,
                informational=True,
            )

    def analyze_code_submission(self, code: str, language: str) -> DetectionResult:
        """Leftover chat text in code comments and strings ("Here's the
        updated function", "As an AI language model", "[Insert …]") —
        informational. Ordinary code conventions (``if __name__ ==
        "__main__":``, ``def main()``, ``public static void main``, a variable
        called ``result``, blank lines) are what people write too and are not
        counted."""
        from education_system.systems.university.application.integrity import ai_indicators

        code = str(code or "")
        found = [m.group(0) for m in ai_indicators._ARTEFACT_RX.finditer(code)]
        lines = code.split('\n')
        return DetectionResult(
            method=DetectionMethod.MULTI_MODAL,
            score=1.0 if found else 0.0,
            confidence=1.0 if found else 0.0,
            evidence={
                'language': language,
                'patterns_found': found[:20],
                'line_count': len(lines),
                'note': 'Only leftover chat text is looked for; coding conventions are not.'
            },
            risk_level=RiskLevel.MEDIUM if found else RiskLevel.LOW,
            informational=True,
        )

    def _extract_text_from_image(self, img_data: bytes) -> str:
        """Extract text from image using OCR"""
        try:
            # Convert bytes to PIL Image
            from io import BytesIO
            from PIL import Image
            import pytesseract
            img = Image.open(BytesIO(img_data))

            # Extract text using pytesseract
            text = pytesseract.image_to_string(img)
            return text.strip()

        except Exception as e:
            logger.debug(f"OCR extraction error: {e}")
            return ""

    @staticmethod
    def _word_overlap(text1: str, text2: str) -> float:
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        return len(words1 & words2) / len(words1 | words2)

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Similarity of two texts: TF-IDF cosine with scikit-learn, word
        overlap without it (or when the texts have no usable words)."""
        if not ML_AVAILABLE:
            return self._word_overlap(text1, text2)
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        try:
            matrix = TfidfVectorizer().fit_transform([text1, text2])
        except ValueError:            # empty vocabulary
            return self._word_overlap(text1, text2)
        return float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])
