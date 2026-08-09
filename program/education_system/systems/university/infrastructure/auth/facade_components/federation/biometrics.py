"""Extracted backwards-compatible UserAuth methods."""
from ...facade_support import *

class AuthFederationBiometricsMixin:
    def enroll_biometric(self, biometric_type, data, quality_score=None):
        """Enroll a biometric template"""
        return self.biometric_manager.enroll_biometric(biometric_type, data, quality_score)

    def authenticate_biometric(self, biometric_type, data):
        """Authenticate using biometric data"""
        return self.biometric_manager.authenticate_biometric(biometric_type, data)

    def list_biometric_enrollments(self, user_id=None):
        """List biometric enrollments"""
        return self.biometric_manager.list_enrollments(user_id)

    def revoke_biometric_enrollment(self, enrollment_id):
        """Revoke a biometric enrollment"""
        return self.biometric_manager.revoke_enrollment(enrollment_id)
