"""SAML logins fail closed without signature verification.

When python3-saml was missing — the normal state, since it was not a declared
dependency — the provider parsed the posted XML and trusted whatever NameID
and attributes it found. Anyone who could reach the ACS endpoint could mint an
assertion naming any user.
"""

from __future__ import annotations

import base64

import pytest

from education_system.systems.university.infrastructure.auth.sso_providers import (
    saml_provider,
)

pytestmark = pytest.mark.security


FORGED = base64.b64encode(
    b'<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" '
    b'xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">'
    b"<saml:Assertion><saml:Subject>"
    b"<saml:NameID>admin@university.edu</saml:NameID>"
    b"</saml:Subject><saml:AttributeStatement>"
    b'<saml:Attribute Name="role">'
    b"<saml:AttributeValue>admin</saml:AttributeValue>"
    b"</saml:Attribute></saml:AttributeStatement>"
    b"</saml:Assertion></samlp:Response>"
).decode()


@pytest.fixture
def provider():
    return saml_provider.SAMLProvider({
        "entity_id": "https://idp.example/metadata",
        "sso_url": "https://idp.example/sso",
        "sp_entity_id": "https://sp.example/metadata",
        "sp_acs_url": "https://sp.example/acs",
        "x509_cert": "",
    })


def test_the_unsigned_fallback_path_is_gone():
    assert not hasattr(saml_provider.SAMLProvider, "_process_response_fallback")


def test_a_forged_assertion_is_refused(provider, monkeypatch):
    monkeypatch.setattr(saml_provider, "PYTHON3_SAML_AVAILABLE", False)

    result = provider.process_response(FORGED)

    assert result["success"] is False
    assert result["name_id"] == ""
    assert result["attributes"] == {}


def test_no_certificate_means_no_login(provider, monkeypatch):
    """Even with the library present, there must be something to verify against."""
    monkeypatch.setattr(saml_provider, "PYTHON3_SAML_AVAILABLE", True)

    result = provider.process_response(FORGED)

    assert result["success"] is False
    assert "certificate" in result["error"].lower()


def test_validate_assertion_refuses_without_the_library(monkeypatch):
    import defusedxml.ElementTree as ET

    monkeypatch.setattr(saml_provider, "PYTHON3_SAML_AVAILABLE", False)
    assertion = ET.fromstring(
        '<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"/>'
    )

    assert saml_provider.SAMLProvider.validate_assertion(
        saml_provider.SAMLProvider.__new__(saml_provider.SAMLProvider), assertion
    ) is False


def test_validate_assertion_rejects_an_unsigned_assertion(monkeypatch):
    """With the library present, a assertion carrying no Signature still fails."""
    import defusedxml.ElementTree as ET

    monkeypatch.setattr(saml_provider, "PYTHON3_SAML_AVAILABLE", True)
    provider = saml_provider.SAMLProvider.__new__(saml_provider.SAMLProvider)
    provider.sp_entity_id = "https://sp.example/metadata"
    assertion = ET.fromstring(
        '<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"/>'
    )

    assert provider.validate_assertion(assertion) is False
