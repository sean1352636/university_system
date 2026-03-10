import re
from datetime import datetime
from typing import Dict, List, Any

from education_system.university_system.utils.ai.ai_detector.core.constants import logger, REQUESTS_AVAILABLE
from education_system.university_system.utils.ai.ai_detector.core.enums import DetectionMethod, RiskLevel
from education_system.university_system.utils.ai.ai_detector.core.dataclasses import DetectionResult

try:
    import requests
except ImportError:
    pass


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
        except Exception:
            return False
