"""Manages regulatory compliance (GDPR, FERPA, etc.)."""

from datetime import datetime, timedelta
from typing import Dict, List, Any

from education_system.systems.university.infrastructure.ai.ai_detector.core.constants import logger


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
