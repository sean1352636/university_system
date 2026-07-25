"""
SSO Providers Package

Contains provider implementations for different SSO protocols:
- SAML 2.0 (saml_provider.py)
- OpenID Connect / OAuth 2.0 (oidc_provider.py)
"""

try:
    from education_system.systems.university.infrastructure.auth.sso_providers.saml_provider import SAMLProvider
except ImportError:
    SAMLProvider = None

try:
    from education_system.systems.university.infrastructure.auth.sso_providers.oidc_provider import OIDCProvider
except ImportError:
    OIDCProvider = None

__all__ = ['SAMLProvider', 'OIDCProvider']
