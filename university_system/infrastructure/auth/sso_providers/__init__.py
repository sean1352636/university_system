"""
SSO Providers Package

Contains provider implementations for different SSO protocols:
- SAML 2.0 (saml_provider.py)
- OpenID Connect / OAuth 2.0 (oidc_provider.py)
"""

try:
    from .saml_provider import SAMLProvider
except ImportError:
    SAMLProvider = None

try:
    from .oidc_provider import OIDCProvider
except ImportError:
    OIDCProvider = None

__all__ = ['SAMLProvider', 'OIDCProvider']
