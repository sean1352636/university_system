import re
from datetime import datetime
from typing import Dict, List, Any

from education_system.systems.university.shared.ai.ai_detector.core.constants import logger, REQUESTS_AVAILABLE
from education_system.systems.university.shared.ai.ai_detector.core.enums import DetectionMethod, RiskLevel
from education_system.systems.university.shared.ai.ai_detector.core.dataclasses import DetectionResult

try:
    import requests
except ImportError:
    pass


class CitationVerifier:
    """Checks citations that can be checked.

    A DOI is looked up at doi.org: found, not found (a 404 — worth asking
    about), or *unverified* when the lookup could not be made (no network,
    ``requests`` missing, a timeout). A citation dated in the future is
    flagged. Everything else is unverified: there is no source to check it
    against, so it is neither trusted nor suspected. Informational: never
    part of a reading's strength."""

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
                confidence=0,
                evidence={'reason': 'No citations found'},
                risk_level=RiskLevel.LOW,
                informational=True,
            )

        verification_results = [self._verify_single_citation(c) for c in citations]
        suspicious_count = sum(1 for r in verification_results if r['status'] in
                               ('not_found', 'future_date'))
        checked = sum(1 for r in verification_results if r['status'] != 'unverified')
        suspicious_ratio = suspicious_count / len(citations)

        risk_level = (RiskLevel.HIGH if suspicious_count >= 3 else
                      RiskLevel.MEDIUM if suspicious_count else RiskLevel.LOW)

        return DetectionResult(
            method=DetectionMethod.CITATION_VERIFICATION,
            score=round(suspicious_ratio, 3),
            confidence=round(checked / len(citations), 3),  # share actually checked
            evidence={
                'total_citations': len(citations),
                'checked': checked,
                'unverified': len(citations) - checked,
                'suspicious_citations': suspicious_count,
                'suspicious_ratio': suspicious_ratio,
                'citation_details': verification_results
            },
            risk_level=risk_level,
            informational=True,
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
            'status': 'unverified',     # verified | not_found | future_date | unverified
            'exists': None,
            'suspicious': False,
            'details': {}
        }

        year_match = re.search(r'\b(19|20)\d{2}\b', citation)
        if year_match and int(year_match.group()) > datetime.now().year:
            result.update(status='future_date', suspicious=True)
            result['details']['reason'] = 'Publication date in the future'
            return result

        doi_match = re.search(r'10\.\d+/[^\s)\]]+', citation)
        if not doi_match:
            result['details']['reason'] = 'No DOI to look up'
            return result
        if not REQUESTS_AVAILABLE:
            result['details']['reason'] = 'Lookup not possible here (requests not installed)'
            return result
        found = self._verify_doi(doi_match.group())
        if found is None:
            result['details']['reason'] = 'doi.org could not be reached'
        elif found:
            result.update(status='verified', exists=True)
        else:
            result.update(status='not_found', exists=False, suspicious=True)
            result['details']['reason'] = 'doi.org does not know this DOI'
        return result

    def _verify_doi(self, doi: str):
        """``True`` found, ``False`` not found (404), ``None`` when the lookup
        could not be made."""
        try:
            response = requests.get(f"https://doi.org/{doi}", timeout=10, allow_redirects=False)
        except requests.RequestException as exc:
            logger.debug("DOI lookup failed for %s: %s", doi, exc)
            return None
        if response.status_code in (200, 301, 302, 303):
            return True
        if response.status_code == 404:
            return False
        return None
