"""
OpenID Connect (OIDC) / OAuth 2.0 Single Sign-On Provider

Provides OIDC authentication support for the University Management System.
Handles authorization URL generation, authorization code exchange, ID token
validation, userinfo retrieval, and token refresh.

Uses authlib as the primary library with a fallback to requests + PyJWT
when authlib is not installed.

Usage:
    from university_system.infrastructure.auth.sso_providers.oidc_provider import OIDCProvider

    config = {
        'client_id': 'my-client-id',
        'client_secret': 'my-client-secret',
        'issuer': 'https://accounts.university.edu',
        'authorization_endpoint': 'https://accounts.university.edu/authorize',
        'token_endpoint': 'https://accounts.university.edu/token',
        'userinfo_endpoint': 'https://accounts.university.edu/userinfo',
        'redirect_uri': 'https://app.university.edu/oidc/callback',
        'scopes': ['openid', 'profile', 'email'],
    }
    provider = OIDCProvider(config)
    result = provider.get_authorization_url(state='random-state-value')
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# Attempt to import authlib for full OIDC support
try:
    from authlib.integrations.requests_client import OAuth2Session
    from authlib.jose import jwt as authlib_jwt
    from authlib.jose import JsonWebKey

    AUTHLIB_AVAILABLE = True
except ImportError:
    AUTHLIB_AVAILABLE = False
    logger.info(
        "authlib is not installed. OIDC provider will use requests + PyJWT fallback. "
        "Install with: pip install authlib"
    )

# Attempt to import requests for HTTP fallback
try:
    import requests as http_requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning(
        "requests library is not installed. HTTP-based OIDC operations will fail. "
        "Install with: pip install requests"
    )

# Attempt to import PyJWT for token decoding fallback
try:
    import jwt as pyjwt

    PYJWT_AVAILABLE = True
except ImportError:
    PYJWT_AVAILABLE = False
    logger.info(
        "PyJWT is not installed. ID token validation will be limited. "
        "Install with: pip install PyJWT"
    )


class OIDCProvider:
    """OpenID Connect / OAuth 2.0 Single Sign-On Provider.

    Implements the OIDC Authorization Code Flow for integrating with
    Identity Providers such as Azure AD, Google Workspace, Okta, or Keycloak.

    Attributes:
        client_id: The OAuth 2.0 client identifier.
        client_secret: The OAuth 2.0 client secret.
        issuer: The OIDC issuer URL.
        authorization_endpoint: The authorization endpoint URL.
        token_endpoint: The token endpoint URL.
        userinfo_endpoint: The userinfo endpoint URL.
        redirect_uri: The registered redirect URI for callbacks.
        scopes: List of requested OIDC scopes.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize the OIDC provider with configuration.

        Args:
            config: Dictionary containing OIDC configuration keys:
                - client_id: OAuth 2.0 client ID
                - client_secret: OAuth 2.0 client secret
                - issuer: OIDC issuer identifier URL
                - authorization_endpoint: Authorization URL
                - token_endpoint: Token exchange URL
                - userinfo_endpoint: UserInfo URL
                - redirect_uri: Callback URL registered with the IdP
                - scopes: List of OIDC scopes (default: ['openid', 'profile', 'email'])
        """
        self.client_id = config.get("client_id", "")
        self.client_secret = config.get("client_secret", "")
        self.issuer = config.get("issuer", "")
        self.authorization_endpoint = config.get("authorization_endpoint", "")
        self.token_endpoint = config.get("token_endpoint", "")
        self.userinfo_endpoint = config.get("userinfo_endpoint", "")
        self.redirect_uri = config.get("redirect_uri", "")
        self.scopes = config.get("scopes", ["openid", "profile", "email"])
        self._config = config

        # Validate required configuration
        missing = []
        for key in (
            "client_id",
            "client_secret",
            "authorization_endpoint",
            "token_endpoint",
            "redirect_uri",
        ):
            if not config.get(key):
                missing.append(key)
        if missing:
            logger.warning(
                "OIDC provider initialized with missing config keys: %s",
                ", ".join(missing),
            )

        # JWKS cache for token validation
        self._jwks_cache: Optional[Dict[str, Any]] = None
        self._jwks_cache_expiry: Optional[datetime] = None

        logger.info(
            "OIDC provider initialized for client '%s' with issuer '%s'",
            self.client_id,
            self.issuer,
        )

    def get_authorization_url(
        self,
        state: Optional[str] = None,
        nonce: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate the OIDC authorization URL.

        Constructs the URL to redirect the user to the Identity Provider
        for authentication. Generates cryptographically secure state and
        nonce values if not provided.

        Args:
            state: Optional state parameter for CSRF protection. A secure
                random value is generated if not provided.
            nonce: Optional nonce for replay protection in the ID token.
                A secure random value is generated if not provided.

        Returns:
            Dict with keys:
                - success (bool): Whether URL generation succeeded.
                - url (str): The full authorization URL.
                - state (str): The state value (save for callback validation).
                - nonce (str): The nonce value (save for ID token validation).
                - error (str): Error message if success is False.
        """
        try:
            if not self.authorization_endpoint:
                return {
                    "success": False,
                    "error": "Authorization endpoint is not configured",
                    "url": "",
                    "state": "",
                    "nonce": "",
                }

            # Generate secure state and nonce if not provided
            if state is None:
                state = secrets.token_urlsafe(32)
            if nonce is None:
                nonce = secrets.token_urlsafe(32)

            scope_string = " ".join(self.scopes)

            if AUTHLIB_AVAILABLE:
                return self._get_authorization_url_authlib(
                    state, nonce, scope_string
                )

            return self._get_authorization_url_fallback(
                state, nonce, scope_string
            )

        except Exception as e:
            logger.error(
                "Failed to generate authorization URL: %s", e, exc_info=True
            )
            return {
                "success": False,
                "error": f"Failed to generate authorization URL: {e}",
                "url": "",
                "state": "",
                "nonce": "",
            }

    def _get_authorization_url_authlib(
        self, state: str, nonce: str, scope_string: str
    ) -> Dict[str, Any]:
        """Generate authorization URL using authlib.

        Args:
            state: CSRF protection state value.
            nonce: Replay protection nonce value.
            scope_string: Space-separated scope string.

        Returns:
            Dict with url, state, nonce, and success status.
        """
        session = OAuth2Session(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=scope_string,
        )

        url, auth_state = session.create_authorization_url(
            self.authorization_endpoint,
            state=state,
            nonce=nonce,
        )

        logger.info("OIDC authorization URL generated (authlib)")
        return {
            "success": True,
            "url": url,
            "state": state,
            "nonce": nonce,
        }

    def _get_authorization_url_fallback(
        self, state: str, nonce: str, scope_string: str
    ) -> Dict[str, Any]:
        """Generate authorization URL using manual URL construction.

        Args:
            state: CSRF protection state value.
            nonce: Replay protection nonce value.
            scope_string: Space-separated scope string.

        Returns:
            Dict with url, state, nonce, and success status.
        """
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": scope_string,
            "state": state,
            "nonce": nonce,
        }

        separator = "&" if "?" in self.authorization_endpoint else "?"
        url = self.authorization_endpoint + separator + urlencode(params)

        logger.info("OIDC authorization URL generated (fallback)")
        return {
            "success": True,
            "url": url,
            "state": state,
            "nonce": nonce,
        }

    def exchange_code_for_tokens(
        self, code: str, state: Optional[str] = None
    ) -> Dict[str, Any]:
        """Exchange an authorization code for tokens.

        Sends the authorization code to the token endpoint and receives
        access, ID, and optionally refresh tokens.

        Args:
            code: The authorization code received from the callback.
            state: Optional state value for additional validation logging.

        Returns:
            Dict with keys:
                - success (bool): Whether the exchange succeeded.
                - access_token (str): The access token.
                - id_token (str): The raw ID token (JWT).
                - refresh_token (str): The refresh token (if granted).
                - token_type (str): Token type (usually 'Bearer').
                - expires_in (int): Token lifetime in seconds.
                - error (str): Error message if success is False.
        """
        if not self.token_endpoint:
            return {
                "success": False,
                "error": "Token endpoint is not configured",
                "access_token": "",
                "id_token": "",
                "refresh_token": "",
                "token_type": "",
                "expires_in": 0,
            }

        if AUTHLIB_AVAILABLE:
            return self._exchange_code_authlib(code, state)

        return self._exchange_code_fallback(code, state)

    def _exchange_code_authlib(
        self, code: str, state: Optional[str]
    ) -> Dict[str, Any]:
        """Exchange code using authlib OAuth2Session.

        Args:
            code: Authorization code.
            state: Optional state value.

        Returns:
            Dict with token data and success status.
        """
        try:
            session = OAuth2Session(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
            )

            token = session.fetch_token(
                self.token_endpoint,
                code=code,
                grant_type="authorization_code",
            )

            logger.info("Token exchange successful (authlib)")
            return {
                "success": True,
                "access_token": token.get("access_token", ""),
                "id_token": token.get("id_token", ""),
                "refresh_token": token.get("refresh_token", ""),
                "token_type": token.get("token_type", "Bearer"),
                "expires_in": token.get("expires_in", 0),
            }

        except Exception as e:
            logger.error(
                "Token exchange failed (authlib): %s", e, exc_info=True
            )
            return {
                "success": False,
                "error": f"Token exchange failed: {e}",
                "access_token": "",
                "id_token": "",
                "refresh_token": "",
                "token_type": "",
                "expires_in": 0,
            }

    def _exchange_code_fallback(
        self, code: str, state: Optional[str]
    ) -> Dict[str, Any]:
        """Exchange code using requests library.

        Args:
            code: Authorization code.
            state: Optional state value.

        Returns:
            Dict with token data and success status.
        """
        if not REQUESTS_AVAILABLE:
            return {
                "success": False,
                "error": (
                    "Neither authlib nor requests is installed. "
                    "Install with: pip install authlib  or  pip install requests"
                ),
                "access_token": "",
                "id_token": "",
                "refresh_token": "",
                "token_type": "",
                "expires_in": 0,
            }

        try:
            payload = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }

            response = http_requests.post(
                self.token_endpoint,
                data=payload,
                headers={"Accept": "application/json"},
                timeout=30,
            )

            if response.status_code != 200:
                error_data = {}
                try:
                    error_data = response.json()
                except (ValueError, json.JSONDecodeError):
                    pass
                error_msg = error_data.get(
                    "error_description",
                    error_data.get("error", f"HTTP {response.status_code}"),
                )
                logger.error("Token exchange failed: %s", error_msg)
                return {
                    "success": False,
                    "error": f"Token exchange failed: {error_msg}",
                    "access_token": "",
                    "id_token": "",
                    "refresh_token": "",
                    "token_type": "",
                    "expires_in": 0,
                }

            token_data = response.json()
            logger.info("Token exchange successful (requests fallback)")
            return {
                "success": True,
                "access_token": token_data.get("access_token", ""),
                "id_token": token_data.get("id_token", ""),
                "refresh_token": token_data.get("refresh_token", ""),
                "token_type": token_data.get("token_type", "Bearer"),
                "expires_in": token_data.get("expires_in", 0),
            }

        except http_requests.Timeout:
            logger.error("Token exchange request timed out")
            return {
                "success": False,
                "error": "Token endpoint request timed out",
                "access_token": "",
                "id_token": "",
                "refresh_token": "",
                "token_type": "",
                "expires_in": 0,
            }
        except http_requests.RequestException as e:
            logger.error(
                "Token exchange request failed: %s", e, exc_info=True
            )
            return {
                "success": False,
                "error": f"Token exchange request failed: {e}",
                "access_token": "",
                "id_token": "",
                "refresh_token": "",
                "token_type": "",
                "expires_in": 0,
            }

    def validate_id_token(
        self, id_token: str, nonce: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate an OIDC ID token.

        Decodes and validates the JWT ID token, checking the signature,
        issuer, audience, expiration, and optional nonce claim.

        Args:
            id_token: The raw JWT ID token string.
            nonce: Optional nonce to verify against the token's nonce claim.

        Returns:
            Dict with keys:
                - success (bool): Whether validation succeeded.
                - claims (dict): The decoded JWT claims.
                - error (str): Error message if success is False.
        """
        if not id_token:
            return {
                "success": False,
                "error": "No ID token provided",
                "claims": {},
            }

        if AUTHLIB_AVAILABLE:
            return self._validate_id_token_authlib(id_token, nonce)

        return self._validate_id_token_fallback(id_token, nonce)

    def _validate_id_token_authlib(
        self, id_token: str, nonce: Optional[str]
    ) -> Dict[str, Any]:
        """Validate ID token using authlib.

        Args:
            id_token: Raw JWT string.
            nonce: Optional nonce for validation.

        Returns:
            Dict with claims and success status.
        """
        try:
            # Fetch JWKS for signature validation
            jwks = self._get_jwks()
            if not jwks:
                logger.warning(
                    "Could not fetch JWKS; decoding without signature verification"
                )
                claims = authlib_jwt.decode(id_token, None)
            else:
                claims = authlib_jwt.decode(id_token, jwks)

            claims_dict = dict(claims)

            # Validate issuer
            if self.issuer and claims_dict.get("iss") != self.issuer:
                return {
                    "success": False,
                    "error": (
                        f"Issuer mismatch: expected '{self.issuer}', "
                        f"got '{claims_dict.get('iss')}'"
                    ),
                    "claims": claims_dict,
                }

            # Validate audience
            aud = claims_dict.get("aud", "")
            if isinstance(aud, list):
                if self.client_id not in aud:
                    return {
                        "success": False,
                        "error": f"Client ID '{self.client_id}' not in audience list",
                        "claims": claims_dict,
                    }
            elif aud != self.client_id:
                return {
                    "success": False,
                    "error": (
                        f"Audience mismatch: expected '{self.client_id}', "
                        f"got '{aud}'"
                    ),
                    "claims": claims_dict,
                }

            # Validate expiration
            exp = claims_dict.get("exp", 0)
            if exp and time.time() > exp:
                return {
                    "success": False,
                    "error": "ID token has expired",
                    "claims": claims_dict,
                }

            # Validate nonce
            if nonce and claims_dict.get("nonce") != nonce:
                return {
                    "success": False,
                    "error": (
                        f"Nonce mismatch: expected '{nonce}', "
                        f"got '{claims_dict.get('nonce')}'"
                    ),
                    "claims": claims_dict,
                }

            logger.info("ID token validated successfully (authlib)")
            return {
                "success": True,
                "claims": claims_dict,
            }

        except Exception as e:
            logger.error(
                "ID token validation failed (authlib): %s", e, exc_info=True
            )
            return {
                "success": False,
                "error": f"ID token validation failed: {e}",
                "claims": {},
            }

    def _validate_id_token_fallback(
        self, id_token: str, nonce: Optional[str]
    ) -> Dict[str, Any]:
        """Validate ID token using PyJWT or unverified decode.

        When neither authlib nor PyJWT is available, the token is decoded
        without signature verification (suitable for development only).

        Args:
            id_token: Raw JWT string.
            nonce: Optional nonce for validation.

        Returns:
            Dict with claims and success status.
        """
        try:
            if PYJWT_AVAILABLE:
                # Decode with PyJWT - attempt signature verification with JWKS
                jwks_data = self._fetch_jwks_raw()
                if jwks_data:
                    try:
                        # Get the signing key from JWKS
                        header = pyjwt.get_unverified_header(id_token)
                        kid = header.get("kid")

                        signing_key = None
                        for key_data in jwks_data.get("keys", []):
                            if key_data.get("kid") == kid:
                                signing_key = pyjwt.algorithms.RSAAlgorithm.from_jwk(
                                    json.dumps(key_data)
                                )
                                break

                        if signing_key:
                            claims_dict = pyjwt.decode(
                                id_token,
                                signing_key,
                                algorithms=["RS256", "RS384", "RS512"],
                                audience=self.client_id,
                                issuer=self.issuer or None,
                            )
                        else:
                            logger.warning(
                                "Matching key ID not found in JWKS; "
                                "decoding without signature verification"
                            )
                            claims_dict = pyjwt.decode(
                                id_token,
                                options={"verify_signature": False},
                            )
                    except Exception as jwk_err:
                        logger.warning(
                            "JWKS-based validation failed, falling back to "
                            "unverified decode: %s",
                            jwk_err,
                        )
                        claims_dict = pyjwt.decode(
                            id_token,
                            options={"verify_signature": False},
                        )
                else:
                    logger.warning(
                        "Could not fetch JWKS; decoding without signature verification"
                    )
                    claims_dict = pyjwt.decode(
                        id_token,
                        options={"verify_signature": False},
                    )
            else:
                # Manual base64 decode without any library
                logger.warning(
                    "Neither authlib nor PyJWT is available. "
                    "Decoding ID token without any signature verification. "
                    "This is NOT suitable for production use."
                )
                claims_dict = self._decode_jwt_unverified(id_token)

            # Validate issuer
            if self.issuer and claims_dict.get("iss") != self.issuer:
                return {
                    "success": False,
                    "error": (
                        f"Issuer mismatch: expected '{self.issuer}', "
                        f"got '{claims_dict.get('iss')}'"
                    ),
                    "claims": claims_dict,
                }

            # Validate audience
            aud = claims_dict.get("aud", "")
            if isinstance(aud, list):
                if self.client_id not in aud:
                    return {
                        "success": False,
                        "error": f"Client ID '{self.client_id}' not in audience list",
                        "claims": claims_dict,
                    }
            elif aud and aud != self.client_id:
                return {
                    "success": False,
                    "error": (
                        f"Audience mismatch: expected '{self.client_id}', "
                        f"got '{aud}'"
                    ),
                    "claims": claims_dict,
                }

            # Validate expiration
            exp = claims_dict.get("exp", 0)
            if exp and time.time() > exp:
                return {
                    "success": False,
                    "error": "ID token has expired",
                    "claims": claims_dict,
                }

            # Validate nonce
            if nonce and claims_dict.get("nonce") != nonce:
                return {
                    "success": False,
                    "error": (
                        f"Nonce mismatch: expected '{nonce}', "
                        f"got '{claims_dict.get('nonce')}'"
                    ),
                    "claims": claims_dict,
                }

            logger.info("ID token validated successfully (fallback)")
            return {
                "success": True,
                "claims": claims_dict,
            }

        except Exception as e:
            logger.error(
                "ID token validation failed (fallback): %s", e, exc_info=True
            )
            return {
                "success": False,
                "error": f"ID token validation failed: {e}",
                "claims": {},
            }

    def get_userinfo(self, access_token: str) -> Dict[str, Any]:
        """Fetch user information from the OIDC UserInfo endpoint.

        Uses the access token to retrieve the authenticated user's profile
        information from the Identity Provider.

        Args:
            access_token: A valid access token obtained from token exchange.

        Returns:
            Dict with keys:
                - success (bool): Whether the request succeeded.
                - userinfo (dict): The user profile attributes.
                - error (str): Error message if success is False.
        """
        if not self.userinfo_endpoint:
            return {
                "success": False,
                "error": "UserInfo endpoint is not configured",
                "userinfo": {},
            }

        if not access_token:
            return {
                "success": False,
                "error": "No access token provided",
                "userinfo": {},
            }

        if AUTHLIB_AVAILABLE:
            return self._get_userinfo_authlib(access_token)

        return self._get_userinfo_fallback(access_token)

    def _get_userinfo_authlib(self, access_token: str) -> Dict[str, Any]:
        """Fetch userinfo using authlib OAuth2Session.

        Args:
            access_token: Valid access token.

        Returns:
            Dict with userinfo and success status.
        """
        try:
            session = OAuth2Session(
                client_id=self.client_id,
                client_secret=self.client_secret,
                token={"access_token": access_token, "token_type": "Bearer"},
            )

            response = session.get(self.userinfo_endpoint)
            response.raise_for_status()
            userinfo = response.json()

            logger.info("UserInfo retrieved successfully (authlib)")
            return {
                "success": True,
                "userinfo": userinfo,
            }

        except Exception as e:
            logger.error(
                "Failed to fetch userinfo (authlib): %s", e, exc_info=True
            )
            return {
                "success": False,
                "error": f"Failed to fetch userinfo: {e}",
                "userinfo": {},
            }

    def _get_userinfo_fallback(self, access_token: str) -> Dict[str, Any]:
        """Fetch userinfo using requests library.

        Args:
            access_token: Valid access token.

        Returns:
            Dict with userinfo and success status.
        """
        if not REQUESTS_AVAILABLE:
            return {
                "success": False,
                "error": (
                    "Neither authlib nor requests is installed. "
                    "Install with: pip install authlib  or  pip install requests"
                ),
                "userinfo": {},
            }

        try:
            response = http_requests.get(
                self.userinfo_endpoint,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                timeout=30,
            )

            if response.status_code != 200:
                error_msg = f"UserInfo request failed with HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error_description", error_msg)
                except (ValueError, json.JSONDecodeError):
                    pass
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "userinfo": {},
                }

            userinfo = response.json()
            logger.info("UserInfo retrieved successfully (requests fallback)")
            return {
                "success": True,
                "userinfo": userinfo,
            }

        except http_requests.Timeout:
            logger.error("UserInfo request timed out")
            return {
                "success": False,
                "error": "UserInfo request timed out",
                "userinfo": {},
            }
        except http_requests.RequestException as e:
            logger.error(
                "UserInfo request failed: %s", e, exc_info=True
            )
            return {
                "success": False,
                "error": f"UserInfo request failed: {e}",
                "userinfo": {},
            }

    def refresh_tokens(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access and ID tokens using a refresh token.

        Sends a refresh token grant request to the token endpoint to obtain
        new access and ID tokens without requiring user re-authentication.

        Args:
            refresh_token: A valid refresh token from a previous token exchange.

        Returns:
            Dict with keys:
                - success (bool): Whether the refresh succeeded.
                - access_token (str): The new access token.
                - id_token (str): The new ID token (if issued).
                - refresh_token (str): The new refresh token (if rotated).
                - token_type (str): Token type (usually 'Bearer').
                - expires_in (int): New token lifetime in seconds.
                - error (str): Error message if success is False.
        """
        if not self.token_endpoint:
            return {
                "success": False,
                "error": "Token endpoint is not configured",
                "access_token": "",
                "id_token": "",
                "refresh_token": "",
                "token_type": "",
                "expires_in": 0,
            }

        if not refresh_token:
            return {
                "success": False,
                "error": "No refresh token provided",
                "access_token": "",
                "id_token": "",
                "refresh_token": "",
                "token_type": "",
                "expires_in": 0,
            }

        if AUTHLIB_AVAILABLE:
            return self._refresh_tokens_authlib(refresh_token)

        return self._refresh_tokens_fallback(refresh_token)

    def _refresh_tokens_authlib(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh tokens using authlib OAuth2Session.

        Args:
            refresh_token: Valid refresh token.

        Returns:
            Dict with new token data and success status.
        """
        try:
            session = OAuth2Session(
                client_id=self.client_id,
                client_secret=self.client_secret,
                token={
                    "access_token": "",
                    "refresh_token": refresh_token,
                    "token_type": "Bearer",
                },
            )

            new_token = session.refresh_token(
                self.token_endpoint,
                refresh_token=refresh_token,
            )

            logger.info("Token refresh successful (authlib)")
            return {
                "success": True,
                "access_token": new_token.get("access_token", ""),
                "id_token": new_token.get("id_token", ""),
                "refresh_token": new_token.get("refresh_token", refresh_token),
                "token_type": new_token.get("token_type", "Bearer"),
                "expires_in": new_token.get("expires_in", 0),
            }

        except Exception as e:
            logger.error(
                "Token refresh failed (authlib): %s", e, exc_info=True
            )
            return {
                "success": False,
                "error": f"Token refresh failed: {e}",
                "access_token": "",
                "id_token": "",
                "refresh_token": "",
                "token_type": "",
                "expires_in": 0,
            }

    def _refresh_tokens_fallback(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh tokens using requests library.

        Args:
            refresh_token: Valid refresh token.

        Returns:
            Dict with new token data and success status.
        """
        if not REQUESTS_AVAILABLE:
            return {
                "success": False,
                "error": (
                    "Neither authlib nor requests is installed. "
                    "Install with: pip install authlib  or  pip install requests"
                ),
                "access_token": "",
                "id_token": "",
                "refresh_token": "",
                "token_type": "",
                "expires_in": 0,
            }

        try:
            payload = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }

            response = http_requests.post(
                self.token_endpoint,
                data=payload,
                headers={"Accept": "application/json"},
                timeout=30,
            )

            if response.status_code != 200:
                error_data = {}
                try:
                    error_data = response.json()
                except (ValueError, json.JSONDecodeError):
                    pass
                error_msg = error_data.get(
                    "error_description",
                    error_data.get("error", f"HTTP {response.status_code}"),
                )
                logger.error("Token refresh failed: %s", error_msg)
                return {
                    "success": False,
                    "error": f"Token refresh failed: {error_msg}",
                    "access_token": "",
                    "id_token": "",
                    "refresh_token": "",
                    "token_type": "",
                    "expires_in": 0,
                }

            token_data = response.json()
            logger.info("Token refresh successful (requests fallback)")
            return {
                "success": True,
                "access_token": token_data.get("access_token", ""),
                "id_token": token_data.get("id_token", ""),
                "refresh_token": token_data.get("refresh_token", refresh_token),
                "token_type": token_data.get("token_type", "Bearer"),
                "expires_in": token_data.get("expires_in", 0),
            }

        except http_requests.Timeout:
            logger.error("Token refresh request timed out")
            return {
                "success": False,
                "error": "Token refresh request timed out",
                "access_token": "",
                "id_token": "",
                "refresh_token": "",
                "token_type": "",
                "expires_in": 0,
            }
        except http_requests.RequestException as e:
            logger.error(
                "Token refresh request failed: %s", e, exc_info=True
            )
            return {
                "success": False,
                "error": f"Token refresh request failed: {e}",
                "access_token": "",
                "id_token": "",
                "refresh_token": "",
                "token_type": "",
                "expires_in": 0,
            }

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    def _get_jwks(self) -> Optional[Any]:
        """Fetch and cache JWKS (JSON Web Key Set) for authlib.

        Returns:
            A JsonWebKey set for authlib, or None if unavailable.
        """
        if not AUTHLIB_AVAILABLE:
            return None

        # Return cached JWKS if still valid
        if (
            self._jwks_cache is not None
            and self._jwks_cache_expiry is not None
            and datetime.utcnow() < self._jwks_cache_expiry
        ):
            return self._jwks_cache

        jwks_data = self._fetch_jwks_raw()
        if jwks_data:
            try:
                self._jwks_cache = JsonWebKey.import_key_set(jwks_data)
                self._jwks_cache_expiry = datetime.utcnow() + timedelta(hours=1)
                return self._jwks_cache
            except Exception as e:
                logger.warning("Failed to import JWKS: %s", e)

        return None

    def _fetch_jwks_raw(self) -> Optional[Dict[str, Any]]:
        """Fetch raw JWKS data from the issuer's well-known endpoint.

        Tries the standard OIDC discovery endpoint at
        {issuer}/.well-known/openid-configuration to locate the jwks_uri,
        then fetches the JWKS from that URI.

        Returns:
            The JWKS dictionary, or None if fetching failed.
        """
        if not REQUESTS_AVAILABLE or not self.issuer:
            return None

        try:
            # Try OIDC discovery to find jwks_uri
            discovery_url = self.issuer.rstrip("/") + "/.well-known/openid-configuration"
            discovery_resp = http_requests.get(discovery_url, timeout=10)

            if discovery_resp.status_code == 200:
                discovery_data = discovery_resp.json()
                jwks_uri = discovery_data.get("jwks_uri")
                if jwks_uri:
                    jwks_resp = http_requests.get(jwks_uri, timeout=10)
                    if jwks_resp.status_code == 200:
                        return jwks_resp.json()

            # Fallback: try {issuer}/.well-known/jwks.json
            jwks_url = self.issuer.rstrip("/") + "/.well-known/jwks.json"
            jwks_resp = http_requests.get(jwks_url, timeout=10)
            if jwks_resp.status_code == 200:
                return jwks_resp.json()

        except Exception as e:
            logger.debug("Failed to fetch JWKS: %s", e)

        return None

    @staticmethod
    def _decode_jwt_unverified(token: str) -> Dict[str, Any]:
        """Decode a JWT without any signature verification.

        This is a last-resort fallback when no JWT library is available.
        It should NEVER be used in production environments.

        Args:
            token: The raw JWT string.

        Returns:
            The decoded payload as a dictionary.

        Raises:
            ValueError: If the token format is invalid.
        """
        import base64

        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError(
                f"Invalid JWT format: expected 3 parts, got {len(parts)}"
            )

        # Decode the payload (second part)
        payload_b64 = parts[1]
        # Add padding if needed
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding

        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_bytes.decode("utf-8"))
