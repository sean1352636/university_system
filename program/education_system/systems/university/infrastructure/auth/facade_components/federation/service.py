"""Extracted backwards-compatible UserAuth methods."""
from ...facade_support import *

class AuthFederationServiceMixin:
    def configure_sso_provider(self, provider_id, provider_type, display_name, config, **kwargs):
        """Configure an SSO provider"""
        return self.sso_manager.configure_provider(provider_id, provider_type, display_name, config, **kwargs)

    def list_sso_providers(self, enabled_only=True):
        """List configured SSO providers"""
        return self.sso_manager.list_providers(enabled_only)

    def get_sso_provider_config(self, provider_id):
        """Get SSO provider configuration"""
        return self.sso_manager.get_provider_config(provider_id)

    def delete_sso_provider(self, provider_id):
        """Delete an SSO provider"""
        return self.sso_manager.delete_provider(provider_id)

    def enable_sso_provider(self, provider_id):
        """Enable an SSO provider"""
        return self.sso_manager.enable_provider(provider_id)

    def disable_sso_provider(self, provider_id):
        """Disable an SSO provider"""
        return self.sso_manager.disable_provider(provider_id)
