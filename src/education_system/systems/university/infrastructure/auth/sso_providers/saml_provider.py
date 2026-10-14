"""
SAML 2.0 Single Sign-On Provider

Provides SAML 2.0 authentication support for the University Management System.
Handles AuthnRequest creation, Response processing, assertion validation,
attribute extraction, and logout request generation.

Uses python3-saml as the primary library with a basic XML fallback
when the dependency is not installed.

Usage:
    from education_system.systems.university.infrastructure.auth.sso_providers.saml_provider import SAMLProvider

    config = {
        'entity_id': 'https://idp.university.edu',
        'sso_url': 'https://idp.university.edu/sso/saml',
        'slo_url': 'https://idp.university.edu/slo/saml',
        'x509_cert': '-----BEGIN CERTIFICATE-----...',
        'sp_entity_id': 'https://app.university.edu',
        'sp_acs_url': 'https://app.university.edu/saml/acs',
    }
    provider = SAMLProvider(config)
    result = provider.create_authn_request(relay_state='/dashboard')
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import uuid
import defusedxml.ElementTree as ET
import zlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlencode

logger = logging.getLogger(__name__)

# Attempt to import python3-saml for full SAML support
try:
    from onelogin.saml2.auth import OneLogin_Saml2_Auth
    from onelogin.saml2.utils import OneLogin_Saml2_Utils
    from onelogin.saml2.response import OneLogin_Saml2_Response
    from onelogin.saml2.settings import OneLogin_Saml2_Settings

    PYTHON3_SAML_AVAILABLE = True
except ImportError:
    PYTHON3_SAML_AVAILABLE = False
    logger.warning(
        "python3-saml is not installed, so SAML assertion signatures cannot be "
        "verified and SAML logins will be refused. Install the extra to enable "
        "SAML: pip install 'education-system[sso]'"
    )

# SAML 2.0 XML namespaces
SAML_NAMESPACES = {
    "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
    "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
    "ds": "http://www.w3.org/2000/09/xmldsig#",
    "xenc": "http://www.w3.org/2001/04/xmlenc#",
}

# Common SAML attribute name URIs
SAML_ATTRIBUTE_MAP = {
    "urn:oid:0.9.2342.19200300.100.1.3": "email",
    "urn:oid:2.5.4.42": "first_name",
    "urn:oid:2.5.4.4": "last_name",
    "urn:oid:2.5.4.3": "common_name",
    "urn:oid:0.9.2342.19200300.100.1.1": "uid",
    "urn:oid:1.3.6.1.4.1.5923.1.1.1.1": "edu_person_affiliation",
    "urn:oid:1.3.6.1.4.1.5923.1.1.1.6": "edu_person_principal_name",
    "urn:oid:1.3.6.1.4.1.5923.1.1.1.9": "edu_person_scoped_affiliation",
    "urn:oid:2.16.840.1.113730.3.1.241": "display_name",
}


class SAMLProvider:
    """SAML 2.0 Single Sign-On Provider.

    Implements SAML 2.0 Service Provider (SP) functionality for integrating
    with Identity Providers (IdP) such as Shibboleth, ADFS, or Okta.

    Attributes:
        entity_id: The IdP entity ID.
        sso_url: The IdP Single Sign-On URL.
        slo_url: The IdP Single Logout URL.
        x509_cert: The IdP X.509 certificate for signature validation.
        sp_entity_id: The SP entity ID.
        sp_acs_url: The SP Assertion Consumer Service URL.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize the SAML provider with configuration.

        Args:
            config: Dictionary containing SAML configuration keys:
                - entity_id: IdP entity identifier
                - sso_url: IdP SSO endpoint URL
                - slo_url: IdP SLO endpoint URL
                - x509_cert: IdP X.509 certificate (PEM format)
                - sp_entity_id: SP entity identifier
                - sp_acs_url: SP Assertion Consumer Service URL
        """
        self.entity_id = config.get("entity_id", "")
        self.sso_url = config.get("sso_url", "")
        self.slo_url = config.get("slo_url", "")
        self.x509_cert = config.get("x509_cert", "")
        self.sp_entity_id = config.get("sp_entity_id", "")
        self.sp_acs_url = config.get("sp_acs_url", "")
        self._config = config

        # Validate required configuration
        missing = []
        for key in ("entity_id", "sso_url", "sp_entity_id", "sp_acs_url"):
            if not config.get(key):
                missing.append(key)
        if missing:
            logger.warning(
                "SAML provider initialized with missing config keys: %s",
                ", ".join(missing),
            )

        # Track pending request IDs for replay protection
        self._pending_requests: Dict[str, datetime] = {}

        logger.info(
            "SAML provider initialized for SP '%s' with IdP '%s'",
            self.sp_entity_id,
            self.entity_id,
        )

    def create_authn_request(
        self, relay_state: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a SAML AuthnRequest for initiating SSO.

        Generates a SAML 2.0 AuthnRequest XML document, encodes it, and
        constructs the redirect URL to the Identity Provider.

        Args:
            relay_state: Optional URL to redirect the user to after SSO
                completes. Typically the page the user originally requested.

        Returns:
            Dict with keys:
                - success (bool): Whether request creation succeeded.
                - request_url (str): The full URL to redirect the user to.
                - request_id (str): Unique ID for this request (for validation).
                - error (str): Error message if success is False.
        """
        try:
            request_id = f"_id-{uuid.uuid4().hex}"
            issue_instant = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

            if PYTHON3_SAML_AVAILABLE:
                return self._create_authn_request_onelogin(
                    request_id, issue_instant, relay_state
                )

            return self._create_authn_request_fallback(
                request_id, issue_instant, relay_state
            )

        except Exception as e:
            logger.error("Failed to create SAML AuthnRequest")
            return {
                "success": False,
                "error": f"Failed to create AuthnRequest: {e}",
                "request_url": "",
                "request_id": "",
            }

    def _create_authn_request_onelogin(
        self,
        request_id: str,
        issue_instant: str,
        relay_state: Optional[str],
    ) -> Dict[str, Any]:
        """Create AuthnRequest using python3-saml library.

        Args:
            request_id: Unique identifier for this request.
            issue_instant: ISO timestamp of request creation.
            relay_state: Optional relay state URL.

        Returns:
            Dict with request_url, request_id, and success status.
        """
        settings_data = {
            "strict": True,
            "sp": {
                "entityId": self.sp_entity_id,
                "assertionConsumerService": {
                    "url": self.sp_acs_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
                },
            },
            "idp": {
                "entityId": self.entity_id,
                "singleSignOnService": {
                    "url": self.sso_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
                },
                "singleLogoutService": {
                    "url": self.slo_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
                },
                "x509cert": self._clean_certificate(self.x509_cert),
            },
        }

        settings = OneLogin_Saml2_Settings(settings_data, custom_base_path=None)
        authn_request = OneLogin_Saml2_Utils.generate_unique_id()

        # Build the redirect URL using the library
        request_url = self.sso_url
        saml_request = OneLogin_Saml2_Utils.deflate_and_base64_encode(
            self._build_authn_request_xml(request_id, issue_instant)
        )

        params = {"SAMLRequest": saml_request}
        if relay_state:
            params["RelayState"] = relay_state

        separator = "&" if "?" in request_url else "?"
        request_url = request_url + separator + urlencode(params)

        # Store the request ID for response validation
        self._pending_requests[request_id] = datetime.utcnow()
        self._cleanup_expired_requests()

        logger.info(
            "SAML AuthnRequest created (python3-saml) with ID: %s", request_id
        )
        return {
            "success": True,
            "request_url": request_url,
            "request_id": request_id,
        }

    def _create_authn_request_fallback(
        self,
        request_id: str,
        issue_instant: str,
        relay_state: Optional[str],
    ) -> Dict[str, Any]:
        """Create AuthnRequest using basic XML handling (fallback).

        Args:
            request_id: Unique identifier for this request.
            issue_instant: ISO timestamp of request creation.
            relay_state: Optional relay state URL.

        Returns:
            Dict with request_url, request_id, and success status.
        """
        authn_xml = self._build_authn_request_xml(request_id, issue_instant)

        # Deflate and base64-encode the request
        compressed = zlib.compress(authn_xml.encode("utf-8"))[2:-4]
        encoded = base64.b64encode(compressed).decode("utf-8")
        saml_request = quote(encoded)

        params = {"SAMLRequest": encoded}
        if relay_state:
            params["RelayState"] = relay_state

        separator = "&" if "?" in self.sso_url else "?"
        request_url = self.sso_url + separator + urlencode(params)

        # Store the request ID for response validation
        self._pending_requests[request_id] = datetime.utcnow()
        self._cleanup_expired_requests()

        logger.info(
            "SAML AuthnRequest created (XML fallback) with ID: %s", request_id
        )
        return {
            "success": True,
            "request_url": request_url,
            "request_id": request_id,
        }

    def _build_authn_request_xml(
        self, request_id: str, issue_instant: str
    ) -> str:
        """Build the AuthnRequest XML document.

        Args:
            request_id: Unique request identifier.
            issue_instant: ISO-formatted timestamp.

        Returns:
            The AuthnRequest XML string.
        """
        xml = (
            f'<samlp:AuthnRequest xmlns:samlp="{SAML_NAMESPACES["samlp"]}" '
            f'xmlns:saml="{SAML_NAMESPACES["saml"]}" '
            f'ID="{request_id}" '
            f'Version="2.0" '
            f'IssueInstant="{issue_instant}" '
            f'Destination="{self.sso_url}" '
            f'AssertionConsumerServiceURL="{self.sp_acs_url}" '
            f'ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">'
            f"<saml:Issuer>{self.sp_entity_id}</saml:Issuer>"
            f"<samlp:NameIDPolicy "
            f'Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress" '
            f'AllowCreate="true"/>'
            f"</samlp:AuthnRequest>"
        )
        return xml

    def process_response(
        self, saml_response: str, request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a SAML Response from the Identity Provider.

        Decodes the base64-encoded SAML Response, validates the signature
        and assertions, and extracts user attributes.

        Args:
            saml_response: Base64-encoded SAML Response string.
            request_id: Optional request ID to match against InResponseTo
                for replay protection.

        Returns:
            Dict with keys:
                - success (bool): Whether processing succeeded.
                - attributes (dict): Extracted user attributes.
                - name_id (str): The NameID from the assertion.
                - session_index (str): The session index for logout.
                - error (str): Error message if success is False.
        """
        # Fail closed. There used to be an XML-parsing fallback here for when
        # python3-saml was missing — which is the *normal* state, since it is
        # not a declared dependency. That path read the NameID and attributes
        # straight out of the posted XML without verifying any signature, so
        # anyone who could reach the ACS endpoint could mint an assertion
        # naming any user and be logged in as them. An unverifiable assertion
        # is not a weaker credential; it is no credential at all.
        if not PYTHON3_SAML_AVAILABLE:
            logger.error(
                "Refusing SAML login: python3-saml is not installed, so the "
                "assertion signature cannot be verified."
            )
            return {
                "success": False,
                "error": (
                    "SAML is not available: the signature verification library "
                    "is not installed."
                ),
                "attributes": {},
                "name_id": "",
                "session_index": "",
            }

        if not self._clean_certificate(self.x509_cert):
            logger.error(
                "Refusing SAML login: no IdP certificate is configured, so "
                "there is nothing to verify the assertion against."
            )
            return {
                "success": False,
                "error": "SAML is not configured: no trusted IdP certificate.",
                "attributes": {},
                "name_id": "",
                "session_index": "",
            }

        try:
            return self._process_response_onelogin(saml_response, request_id)
        except Exception as e:
            logger.error("Failed to process SAML response")
            return {
                "success": False,
                "error": f"Failed to process SAML response: {e}",
                "attributes": {},
                "name_id": "",
                "session_index": "",
            }

    def _process_response_onelogin(
        self, saml_response: str, request_id: Optional[str]
    ) -> Dict[str, Any]:
        """Process SAML Response using python3-saml library.

        Args:
            saml_response: Base64-encoded SAML Response.
            request_id: Optional request ID for InResponseTo validation.

        Returns:
            Dict with attributes, name_id, session_index, and success status.
        """
        settings_data = {
            "strict": True,
            "sp": {
                "entityId": self.sp_entity_id,
                "assertionConsumerService": {
                    "url": self.sp_acs_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
                },
            },
            "idp": {
                "entityId": self.entity_id,
                "singleSignOnService": {
                    "url": self.sso_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
                },
                "x509cert": self._clean_certificate(self.x509_cert),
            },
        }

        settings = OneLogin_Saml2_Settings(settings_data)
        response = OneLogin_Saml2_Response(settings, saml_response)
        response.is_valid(raise_exceptions=True)

        attributes = {}
        raw_attrs = response.get_attributes()
        for attr_name, attr_values in raw_attrs.items():
            friendly_name = SAML_ATTRIBUTE_MAP.get(attr_name, attr_name)
            attributes[friendly_name] = (
                attr_values[0] if len(attr_values) == 1 else attr_values
            )

        name_id = response.get_nameid() or ""
        session_index = response.get_session_index() or ""

        # Remove used request ID
        if request_id and request_id in self._pending_requests:
            del self._pending_requests[request_id]

        logger.info(
            "SAML response processed successfully for NameID: %s", name_id
        )
        return {
            "success": True,
            "attributes": attributes,
            "name_id": name_id,
            "session_index": session_index,
        }

    def validate_assertion(self, assertion: Any) -> bool:
        """Validate a SAML assertion.

        Checks the audience restriction, timestamp conditions (NotBefore,
        NotOnOrAfter) and the presence of a signature.

        This is a **supporting** check, not a substitute for signature
        verification: the cryptographic check is done by python3-saml in
        :meth:`_process_response_onelogin`. Because a caller could mistake a
        True here for "this assertion is trustworthy", it refuses outright
        when the verification library is missing.

        Args:
            assertion: An XML Element representing the SAML Assertion.
                Can be an ElementTree Element or a python3-saml object.

        Returns:
            True if the assertion passes validation, False otherwise.
        """
        try:
            if not PYTHON3_SAML_AVAILABLE:
                logger.error(
                    "Refusing to validate a SAML assertion: python3-saml is "
                    "not installed, so its signature cannot be checked."
                )
                return False

            if not isinstance(assertion, ET.Element):
                logger.warning(
                    "validate_assertion received unexpected type: %s",
                    type(assertion).__name__,
                )
                return False

            now = datetime.utcnow()

            # Validate conditions (NotBefore, NotOnOrAfter)
            conditions = assertion.find(
                f".//{{{SAML_NAMESPACES['saml']}}}Conditions"
            )
            if conditions is not None:
                not_before = conditions.get("NotBefore")
                not_on_or_after = conditions.get("NotOnOrAfter")

                if not_before:
                    nb_time = datetime.strptime(not_before, "%Y-%m-%dT%H:%M:%SZ")
                    # Allow 5 minutes of clock skew
                    if now < nb_time - timedelta(minutes=5):
                        logger.warning(
                            "Assertion not yet valid: NotBefore=%s, now=%s",
                            not_before,
                            now.isoformat(),
                        )
                        return False

                if not_on_or_after:
                    noa_time = datetime.strptime(
                        not_on_or_after, "%Y-%m-%dT%H:%M:%SZ"
                    )
                    # Allow 5 minutes of clock skew
                    if now > noa_time + timedelta(minutes=5):
                        logger.warning(
                            "Assertion has expired: NotOnOrAfter=%s, now=%s",
                            not_on_or_after,
                            now.isoformat(),
                        )
                        return False

            # Validate audience restriction
            audience_elem = assertion.find(
                f".//{{{SAML_NAMESPACES['saml']}}}AudienceRestriction"
                f"/{{{SAML_NAMESPACES['saml']}}}Audience"
            )
            if audience_elem is not None:
                audience = audience_elem.text or ""
                if audience and audience != self.sp_entity_id:
                    logger.warning(
                        "Audience mismatch: expected '%s', got '%s'",
                        self.sp_entity_id,
                        audience,
                    )
                    return False

            # An unsigned assertion is rejected here rather than noted. The
            # enclosing Response may legitimately carry the signature instead,
            # which is why the authoritative check lives in python3-saml —
            # but this method must never report success for an assertion with
            # no signature anywhere in it.
            signature = assertion.find(
                f".//{{{SAML_NAMESPACES['ds']}}}Signature"
            )
            if signature is None:
                logger.warning(
                    "Rejecting SAML assertion: no Signature element present."
                )
                return False

            logger.debug("SAML assertion passed the supporting checks")
            return True

        except Exception:
            logger.error("Error validating SAML assertion")
            return False

    def extract_attributes(self, assertion: Any) -> Dict[str, Any]:
        """Extract user attributes from a SAML assertion.

        Parses the AttributeStatement within the assertion and maps
        known SAML attribute OIDs to friendly names.

        Args:
            assertion: An XML Element representing the SAML Assertion.

        Returns:
            Dict mapping attribute names to their values. Known OIDs are
            translated to friendly names (e.g., 'email', 'first_name').
        """
        attributes: Dict[str, Any] = {}

        try:
            if not isinstance(assertion, ET.Element):
                logger.warning(
                    "extract_attributes received unexpected type: %s",
                    type(assertion).__name__,
                )
                return attributes

            saml_ns = SAML_NAMESPACES["saml"]

            # Find all Attribute elements within AttributeStatement
            attr_statement = assertion.find(
                f".//{{{saml_ns}}}AttributeStatement"
            )
            if attr_statement is None:
                logger.debug("No AttributeStatement found in assertion")
                return attributes

            for attr_elem in attr_statement.findall(f"{{{saml_ns}}}Attribute"):
                attr_name = attr_elem.get("Name", "")
                friendly_name = attr_elem.get("FriendlyName", "")

                # Get all attribute values
                values: List[str] = []
                for value_elem in attr_elem.findall(
                    f"{{{saml_ns}}}AttributeValue"
                ):
                    if value_elem.text:
                        values.append(value_elem.text)

                # Determine the key: prefer mapped name, then FriendlyName,
                # then the raw Name
                key = SAML_ATTRIBUTE_MAP.get(
                    attr_name, friendly_name or attr_name
                )

                # Store single values as strings, multiple as lists
                if len(values) == 1:
                    attributes[key] = values[0]
                elif values:
                    attributes[key] = values

            logger.debug(
                "Extracted %d attributes from SAML assertion",
                len(attributes),
            )

        except Exception:
            logger.error("Error extracting SAML attributes")

        return attributes

    def create_logout_request(
        self, name_id: str, session_index: str
    ) -> Dict[str, Any]:
        """Create a SAML LogoutRequest.

        Generates a SAML 2.0 LogoutRequest for Single Logout (SLO) and
        constructs the redirect URL to the Identity Provider's SLO endpoint.

        Args:
            name_id: The NameID of the user to log out.
            session_index: The session index from the original authentication.

        Returns:
            Dict with keys:
                - success (bool): Whether request creation succeeded.
                - logout_url (str): The full URL to redirect the user to.
                - request_id (str): Unique ID for this logout request.
                - error (str): Error message if success is False.
        """
        try:
            if not self.slo_url:
                return {
                    "success": False,
                    "error": "Single Logout URL (slo_url) is not configured",
                    "logout_url": "",
                    "request_id": "",
                }

            request_id = f"_logout-{uuid.uuid4().hex}"
            issue_instant = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

            logout_xml = (
                f'<samlp:LogoutRequest '
                f'xmlns:samlp="{SAML_NAMESPACES["samlp"]}" '
                f'xmlns:saml="{SAML_NAMESPACES["saml"]}" '
                f'ID="{request_id}" '
                f'Version="2.0" '
                f'IssueInstant="{issue_instant}" '
                f'Destination="{self.slo_url}">'
                f"<saml:Issuer>{self.sp_entity_id}</saml:Issuer>"
                f"<saml:NameID "
                f'Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">'
                f"{name_id}</saml:NameID>"
                f"<samlp:SessionIndex>{session_index}</samlp:SessionIndex>"
                f"</samlp:LogoutRequest>"
            )

            # Deflate and base64-encode
            compressed = zlib.compress(logout_xml.encode("utf-8"))[2:-4]
            encoded = base64.b64encode(compressed).decode("utf-8")

            params = {"SAMLRequest": encoded}
            separator = "&" if "?" in self.slo_url else "?"
            logout_url = self.slo_url + separator + urlencode(params)

            logger.info("SAML LogoutRequest created with ID: %s", request_id)
            return {
                "success": True,
                "logout_url": logout_url,
                "request_id": request_id,
            }

        except Exception as e:
            logger.error("Failed to create SAML LogoutRequest")
            return {
                "success": False,
                "error": f"Failed to create LogoutRequest: {e}",
                "logout_url": "",
                "request_id": "",
            }

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    def _clean_certificate(self, cert: str) -> str:
        """Strip PEM headers and whitespace from an X.509 certificate.

        Args:
            cert: The certificate string, possibly with PEM headers.

        Returns:
            The raw base64 certificate content without headers.
        """
        return (
            cert.replace("-----BEGIN CERTIFICATE-----", "")
            .replace("-----END CERTIFICATE-----", "")
            .replace("\n", "")
            .replace("\r", "")
            .strip()
        )

    def _cleanup_expired_requests(self) -> None:
        """Remove pending request IDs older than 10 minutes.

        This prevents unbounded memory growth from accumulated request IDs
        that were never matched with a response.
        """
        cutoff = datetime.utcnow() - timedelta(minutes=10)
        expired = [
            rid
            for rid, timestamp in self._pending_requests.items()
            if timestamp < cutoff
        ]
        for rid in expired:
            del self._pending_requests[rid]
        if expired:
            logger.debug(
                "Cleaned up %d expired SAML request IDs", len(expired)
            )
