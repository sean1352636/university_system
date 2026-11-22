"""Manages regulatory compliance (UK GDPR, FERPA, etc.).

Academic integrity checks rest on the university's public task, not on
consent: a student cannot opt out of having work checked. What the law
requires is that they are told — the academic integrity notice, which they
acknowledge in the University app — and that data is kept no longer than
needed: the integrity retention period (``retention_years``), after which
the text of readings is removed by the daily integrity jobs.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any

from education_system.systems.university.shared.ai.ai_detector.core.constants import logger


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
            'data_retention_period': None,   # the integrity setting retention_years
            'requires_consent': False,       # public task; the student is told (notice)
            'requires_notice': True,
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
            'data_retention_period': None,   # the integrity setting retention_years
            'directory_information_rules': True
        }

    def _setup_coppa_compliance(self):
        """Setup COPPA compliance rules (children under 13)"""
        self.compliance_rules['COPPA'] = {
            'minimum_age_without_consent': 13,
            'requires_parental_consent': True,
            'parental_access_and_deletion': True,
            'data_minimization': True,
            'data_retention_period': None,   # the integrity setting retention_years
        }

    def _retention_days(self, conn) -> int:
        from education_system.systems.university.application.integrity import (
            access as integrity_access,
        )
        return int(integrity_access.number(conn, "retention_years") * 365)

    def check_compliance_before_processing(self, student_id: str, data_type: str) -> Dict[str, Any]:
        """Processing may go ahead (public task). A warning is given when the
        student has not acknowledged the current integrity notice."""
        from education_system.systems.university.application.integrity import (
            access as integrity_access,
        )
        status = {'can_process': True, 'requirements': [], 'warnings': []}
        conn = self.detector._safe_db_connect()
        try:
            row = conn.execute("SELECT username FROM users WHERE student_id = ? LIMIT 1",
                               (str(student_id),)).fetchone()
            if row is None or not integrity_access.has_acknowledged(
                    conn, integrity_access.person(conn, row[0])):
                status['warnings'].append('The student has not acknowledged the current '
                                          'academic integrity notice')
            status['warnings'].append(f'Text is removed after {self._retention_days(conn)} days '
                                      '(integrity retention period)')
        finally:
            conn.close()
        return status

    def generate_compliance_report(self) -> Dict[str, Any]:
        """Generate compliance status report"""
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()

            # Check data retention compliance
            retention_issues = []

            retention_days = self._retention_days(conn)
            for regulation in self.compliance_rules:
                if True:
                    cutoff_date = datetime.now() - timedelta(days=retention_days)

                    cursor.execute('''
                    SELECT COUNT(*) as expired_records
                    FROM ai_detector_submissions
                    WHERE submission_date < ? AND COALESCE(purged, 0) = 0
                    ''', (cutoff_date.isoformat(),))

                    result = cursor.fetchone()
                    if result['expired_records'] > 0:
                        retention_issues.append({
                            'regulation': regulation,
                            'expired_records': result['expired_records'],
                            'cutoff_date': cutoff_date.isoformat()
                        })

            # Students told: acknowledged the current integrity notice
            from education_system.systems.university.application.integrity import (
                access as integrity_access,
            )
            version = integrity_access.setting(conn, "notice_version")
            cursor.execute('''
            SELECT COUNT(DISTINCT s.student_id) as total_students,
                   COUNT(DISTINCT CASE WHEN a.username IS NOT NULL THEN s.student_id END)
                       as consented_students
            FROM ai_detector_submissions s
            LEFT JOIN users u ON u.student_id = s.student_id
            LEFT JOIN integrity_acknowledgements a ON a.username = u.username
                 AND a.notice_version = ?
            ''', (version,))

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
