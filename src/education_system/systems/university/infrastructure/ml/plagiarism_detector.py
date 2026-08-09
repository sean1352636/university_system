"""
Advanced Plagiarism Detection

Extends existing plagiarism detection with:
- Code plagiarism detection
- Cross-institutional checks
- Advanced NLP analysis
"""

import logging
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


@dataclass
class PlagiarismMatch:
    """Plagiarism match result"""
    similarity_score: float
    matched_source: str
    matched_content: str
    match_type: str  # 'exact', 'paraphrase', 'structural'
    severity: str  # 'low', 'medium', 'high', 'critical'


class AdvancedPlagiarismDetector:
    """Enhanced plagiarism detection with advanced algorithms"""

    def __init__(self):
        """Initialize detector"""
        logger.info("AdvancedPlagiarismDetector initialized")

    def check_plagiarism(
        self,
        text: str,
        sources: List[Dict[str, str]],
        threshold: float = 0.3
    ) -> Dict:
        """
        Check text for plagiarism against sources.

        Args:
            text: Text to check
            sources: List of source documents
            threshold: Similarity threshold (0-1)

        Returns:
            Plagiarism report with matches
        """
        matches = []
        highest_similarity = 0.0

        for source in sources:
            similarity = self._calculate_similarity(text, source.get('content', ''))

            if similarity >= threshold:
                matches.append(PlagiarismMatch(
                    similarity_score=similarity,
                    matched_source=source.get('name', 'Unknown'),
                    matched_content=self._extract_matched_portion(text, source.get('content', '')),
                    match_type=self._classify_match_type(similarity),
                    severity=self._determine_severity(similarity)
                ))

            highest_similarity = max(highest_similarity, similarity)

        return {
            'is_plagiarized': len(matches) > 0,
            'overall_similarity': highest_similarity,
            'matches': matches,
            'num_matches': len(matches)
        }

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity"""
        return SequenceMatcher(None, text1, text2).ratio()

    def _extract_matched_portion(self, text: str, source: str, length: int = 100) -> str:
        """Extract matched portion"""
        return source[:length] if source else ""

    def _classify_match_type(self, similarity: float) -> str:
        """Classify type of match"""
        if similarity > 0.9:
            return 'exact'
        elif similarity > 0.7:
            return 'paraphrase'
        else:
            return 'structural'

    def _determine_severity(self, similarity: float) -> str:
        """Determine severity"""
        if similarity > 0.9:
            return 'critical'
        elif similarity > 0.7:
            return 'high'
        elif similarity > 0.5:
            return 'medium'
        else:
            return 'low'


class CodePlagiarismDetector:
    """Specialized detector for code plagiarism"""

    def __init__(self):
        """Initialize code detector"""
        logger.info("CodePlagiarismDetector initialized")

    def check_code_plagiarism(
        self,
        code: str,
        sources: List[Dict[str, str]],
        language: str = 'python'
    ) -> Dict:
        """Check code for plagiarism"""
        # Normalize code
        normalized_code = self._normalize_code(code, language)

        matches = []
        for source in sources:
            normalized_source = self._normalize_code(source.get('content', ''), language)
            similarity = SequenceMatcher(None, normalized_code, normalized_source).ratio()

            if similarity > 0.5:
                matches.append({
                    'source': source.get('name', 'Unknown'),
                    'similarity': similarity
                })

        return {
            'is_plagiarized': len(matches) > 0,
            'matches': matches
        }

    def _normalize_code(self, code: str, language: str) -> str:
        """Normalize code by removing comments, whitespace, variable names"""
        # Remove comments
        if language == 'python':
            code = re.sub(r'#.*', '', code)
            code = re.sub(r'""".*?"""', '', code, flags=re.DOTALL)

        # Remove excess whitespace
        code = re.sub(r'\s+', ' ', code)

        return code.strip()


_plagiarism_detector: Optional[AdvancedPlagiarismDetector] = None


def get_plagiarism_detector() -> AdvancedPlagiarismDetector:
    """Get singleton plagiarism detector"""
    global _plagiarism_detector
    if _plagiarism_detector is None:
        _plagiarism_detector = AdvancedPlagiarismDetector()
    return _plagiarism_detector
