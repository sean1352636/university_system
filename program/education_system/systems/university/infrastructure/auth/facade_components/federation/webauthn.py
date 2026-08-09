"""Extracted backwards-compatible UserAuth methods."""
from ...facade_support import *

class AuthFederationWebauthnMixin:
    def register_webauthn_key(self, credential_name=None):
        """Begin WebAuthn key registration"""
        return self.webauthn_manager.register_key(credential_name)

    def complete_webauthn_registration(self, session_id, attestation_response):
        """Complete WebAuthn key registration"""
        return self.webauthn_manager.complete_registration(session_id, attestation_response)

    def begin_webauthn_authentication(self, username=None):
        """Begin WebAuthn authentication"""
        return self.webauthn_manager.begin_authentication(username)

    def complete_webauthn_authentication(self, session_id, assertion_response):
        """Complete WebAuthn authentication"""
        return self.webauthn_manager.complete_authentication(session_id, assertion_response)

    def list_webauthn_keys(self, user_id=None):
        """List registered WebAuthn keys"""
        return self.webauthn_manager.list_user_keys(user_id)

    def remove_webauthn_key(self, credential_id):
        """Remove a WebAuthn key"""
        return self.webauthn_manager.remove_key(credential_id)

    def rename_webauthn_key(self, credential_id, new_name):
        """Rename a WebAuthn key"""
        return self.webauthn_manager.rename_key(credential_id, new_name)
