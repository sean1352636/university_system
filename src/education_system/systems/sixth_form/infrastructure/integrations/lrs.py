"""Learning Records Service (LRS) client: find and verify ULNs.

The LRS is a DfE SOAP web service. Using it needs an organisation
account issued by the DfE: the college's UKPRN, an LRS username and
password, and (for the production service) a client certificate. None of
that can be supplied by this code, so the client refuses to run until it
is configured and **never returns made-up responses**.

Configuration (environment first, then the Integrations settings table
for the non-secret values):

==================  =====================================================
LRS_ENDPOINT         Service URL (from the DfE onboarding pack)
LRS_UKPRN            College UKPRN (8 digits)
LRS_USERNAME         LRS organisation user name
LRS_PASSWORD         Password - environment only, never stored in the DB
LRS_VENDOR_ID        Vendor id, if the DfE issued one (optional)
LRS_CERT_FILE        Client certificate (PEM) for mutual TLS (optional)
LRS_KEY_FILE         Its private key (optional; may be inside CERT_FILE)
LRS_SOAP_NAMESPACE   Request namespace, if the WSDL you were issued
                     differs from :data:`DEFAULT_NAMESPACE`
==================  =====================================================

Operations
----------
* :meth:`LRSClient.find_by_demographics` - LearnerByDemographics: family
  name, given name, date of birth, gender, last known postcode -> zero or
  more learners with their ULNs, plus the LRS response code.
* :meth:`LRSClient.verify` - VerifyLearner: is this ULN the learner with
  these details?

Both parse the reply namespace-agnostically: the response code is the
text of the first ``ResponseCode`` element, and every element that has a
``ULN`` child is read as a learner. Check the operation names and
namespace against the WSDL in your LRS onboarding pack.

Offline helpers (no LRS needed): ULN check-digit validation and the
"students missing a ULN" / "ULN fails check digit" lists.
"""

from __future__ import annotations

import logging
import os
import re
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any
from xml.sax.saxutils import escape

from education_system.systems.sixth_form.infrastructure.integrations import (
    store,
)

logger = logging.getLogger(__name__)

DEFAULT_NAMESPACE = "http://api.lrs.qcf.gov.uk/"
SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
TIMEOUT_SECONDS = 30

#: LearnerByDemographics response codes.
FIND_CODES: dict[str, str] = {
    "WSRC0001": "No match",
    "WSRC0002": "Too many matches - add more details (e.g. postcode)",
    "WSRC0003": "Possible matches",
    "WSRC0004": "Exact match",
}
#: VerifyLearner response codes.
VERIFY_CODES: dict[str, str] = {
    "WSVRC001": "Exact match",
    "WSVRC002": "Linked learner found",
    "WSVRC003": "Linked learner match",
    "WSVRC004": "Learner not found / details do not match",
}

#: students.gender -> LRS gender code (0 not known, 1 male, 2 female,
#: 9 not specified).
_GENDER_CODES = {"male": "1", "female": "2"}


class LRSNotConfigured(RuntimeError):
    """Raised when LRS credentials/endpoint are missing."""


class LRSError(RuntimeError):
    """The LRS call failed (network, HTTP, SOAP fault, bad reply)."""


class ValidationError(ValueError):
    pass


# ── ULN check digit (offline) ──────────────────────────────────────

def _identifiers():
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        identifiers,
    )
    return identifiers


def uln_check_digit(first_nine: str) -> int | None:
    """Weights 10..2 over the first nine digits; check = 10 - (sum mod 11).

    None means no valid ULN can start with these nine digits (check 10).
    """
    return _identifiers().uln_check_digit(first_nine)


def is_valid_uln(uln: str | None) -> bool:
    return _identifiers().is_valid_uln((uln or "").replace(" ", ""))


def explain_uln(uln: str | None) -> str:
    """A human sentence on why a ULN is or isn't valid."""
    s = (uln or "").replace(" ", "").strip()
    if not s.isdigit() or len(s) != 10:
        return "A ULN is exactly 10 digits."
    check = uln_check_digit(s[:9])
    if check is None:
        return "Invalid: the first nine digits give a check value of 10, which no ULN can have."
    if check != int(s[9]):
        return f"Invalid: the check digit should be {check}, not {s[9]}."
    return "Valid check digit."


def _students():
    from education_system.systems.sixth_form.domain.learners.students import (
        students,
    )
    return students


def students_missing_uln(*, include_left: bool = False) -> list:
    """Students with no ULN recorded (Active/Inactive/Suspended by default)."""
    return [s for s in _students().list_students()
            if not s.uln and (include_left or s.status != "Left")]


def students_with_invalid_uln() -> list:
    return [s for s in _students().list_students()
            if s.uln and not is_valid_uln(s.uln)]


# ── Configuration ──────────────────────────────────────────────────

@dataclass
class LRSConfig:
    endpoint: str
    ukprn: str
    username: str
    password: str
    vendor_id: str = ""
    cert_file: str = ""
    key_file: str = ""
    namespace: str = DEFAULT_NAMESPACE

    def missing(self) -> list[str]:
        out = []
        for name, value in (("LRS_ENDPOINT", self.endpoint),
                            ("LRS_UKPRN", self.ukprn),
                            ("LRS_USERNAME", self.username),
                            ("LRS_PASSWORD", self.password)):
            if not value:
                out.append(name)
        return out


def _setting(env_name: str, setting_key: str | None) -> str:
    v = (os.environ.get(env_name) or "").strip()
    if v or setting_key is None:
        return v
    try:
        return store.get_setting(setting_key)
    except Exception:
        logger.debug("Could not read setting %s", setting_key, exc_info=True)
        return ""


def load_config() -> LRSConfig:
    return LRSConfig(
        endpoint=_setting("LRS_ENDPOINT", "lrs_endpoint"),
        ukprn=_setting("LRS_UKPRN", "lrs_ukprn"),
        username=_setting("LRS_USERNAME", "lrs_username"),
        password=_setting("LRS_PASSWORD", None),
        vendor_id=_setting("LRS_VENDOR_ID", "lrs_vendor_id"),
        cert_file=_setting("LRS_CERT_FILE", None),
        key_file=_setting("LRS_KEY_FILE", None),
        namespace=_setting("LRS_SOAP_NAMESPACE", None) or DEFAULT_NAMESPACE,
    )


def config_status() -> tuple[bool, str]:
    """(configured?, human description) - safe to show in the UI."""
    cfg = load_config()
    missing = cfg.missing()
    if missing:
        return False, ("LRS not configured. Missing: " + ", ".join(missing)
                       + ". The LRS needs DfE-issued organisation credentials "
                         "(UKPRN, username, password and usually a client "
                         "certificate).")
    return True, (f"LRS configured: {cfg.endpoint} (UKPRN {cfg.ukprn}, user "
                  f"{cfg.username}"
                  + (", client certificate set" if cfg.cert_file else "") + ")")


# ── Results ────────────────────────────────────────────────────────

@dataclass
class LRSLearner:
    uln: str
    given_name: str | None
    family_name: str | None
    date_of_birth: str | None
    gender: str | None
    postcode: str | None
    status: str | None
    extra: dict[str, str] = field(default_factory=dict)


@dataclass
class LRSResponse:
    operation: str
    code: str | None
    description: str
    learners: list[LRSLearner]


def _local(tag: Any) -> str:
    return tag.split("}", 1)[1] if isinstance(tag, str) and "}" in tag else str(tag)


def parse_response(raw: bytes, operation: str) -> LRSResponse:
    """Parse a SOAP reply from the LRS (namespace-agnostic)."""
    from defusedxml import ElementTree as SafeET
    try:
        root = SafeET.fromstring(raw)
    except Exception as e:
        raise LRSError(f"LRS reply is not valid XML: {e}") from None
    for el in root.iter():
        if _local(el.tag) == "Fault":
            msg = next((c.text for c in el.iter()
                        if _local(c.tag) in ("faultstring", "Text") and c.text),
                       "SOAP fault")
            raise LRSError(f"LRS returned a fault: {msg.strip()}")
    code = next((el.text.strip() for el in root.iter()
                 if _local(el.tag) == "ResponseCode" and el.text), None)
    learners: list[LRSLearner] = []
    for el in root.iter():
        kids = {_local(c.tag): (c.text or "").strip() for c in list(el)}
        if kids.get("ULN") and _local(el.tag) not in ("Envelope", "Body"):
            learners.append(LRSLearner(
                uln=kids["ULN"],
                given_name=kids.get("GivenName") or None,
                family_name=kids.get("FamilyName") or None,
                date_of_birth=(kids.get("DateOfBirth") or "")[:10] or None,
                gender=kids.get("Gender") or None,
                postcode=kids.get("LastKnownPostCode") or None,
                status=kids.get("LearnerStatus") or None,
                extra={k: v for k, v in kids.items() if v and k not in (
                    "ULN", "GivenName", "FamilyName", "DateOfBirth", "Gender",
                    "LastKnownPostCode", "LearnerStatus")},
            ))
    table = FIND_CODES if operation == "LearnerByDemographics" else VERIFY_CODES
    desc = table.get(code or "", f"LRS response code {code}" if code
                     else "No response code in reply")
    return LRSResponse(operation=operation, code=code, description=desc,
                       learners=learners)


# ── Client ─────────────────────────────────────────────────────────

def _el(tag: str, value: Any) -> str:
    return f"<{tag}>{escape('' if value is None else str(value))}</{tag}>"


class LRSClient:
    def __init__(self, config: LRSConfig | None = None) -> None:
        self.config = config or load_config()
        missing = self.config.missing()
        if missing:
            raise LRSNotConfigured(
                "LRS not configured (missing " + ", ".join(missing) + "). "
                "Set them in the environment; the LRS needs DfE-issued "
                "organisation credentials.")

    # -- request building -------------------------------------------------

    def _org(self) -> str:
        c = self.config
        return ("<invokingOrganisation>" + _el("Password", c.password)
                + _el("Ukprn", c.ukprn) + _el("Username", c.username)
                + "</invokingOrganisation>" + _el("userType", "LEA")
                + _el("vendorId", c.vendor_id) + _el("language", "ENG"))

    def _envelope(self, operation: str, inner: str) -> bytes:
        ns = self.config.namespace
        return (
            '<?xml version="1.0" encoding="utf-8"?>'
            f'<soap:Envelope xmlns:soap="{SOAP_ENV}">'
            f'<soap:Body><{operation} xmlns="{escape(ns)}">'
            f"{self._org()}{inner}</{operation}></soap:Body></soap:Envelope>"
        ).encode("utf-8")

    def build_find_request(self, *, family_name: str, given_name: str,
                           date_of_birth: str, gender: str | None = None,
                           postcode: str | None = None) -> bytes:
        if not family_name or not given_name or not date_of_birth:
            raise ValidationError(
                "Family name, given name and date of birth are required for "
                "an LRS search")
        inner = (_el("findType", "FUL") + _el("familyName", family_name)
                 + _el("givenName", given_name)
                 + _el("dateOfBirth", date_of_birth)
                 + _el("gender", _GENDER_CODES.get((gender or "").lower(), "0"))
                 + _el("lastKnownPostCode", (postcode or "").upper()))
        return self._envelope("LearnerByDemographics", inner)

    def build_verify_request(self, *, uln: str, family_name: str,
                             given_name: str, date_of_birth: str | None = None,
                             gender: str | None = None) -> bytes:
        if not is_valid_uln(uln):
            raise ValidationError(f"{uln} is not a valid ULN ({explain_uln(uln)})")
        inner = ("<LearnerToVerify>" + _el("ULN", uln)
                 + _el("FamilyName", family_name) + _el("GivenName", given_name)
                 + (_el("DateOfBirth", date_of_birth) if date_of_birth else "")
                 + _el("Gender", _GENDER_CODES.get((gender or "").lower(), "0"))
                 + "</LearnerToVerify>")
        return self._envelope("VerifyLearner", inner)

    # -- transport --------------------------------------------------------

    def _post(self, operation: str, body: bytes) -> bytes:
        c = self.config
        ctx = ssl.create_default_context()
        if c.cert_file:
            ctx.load_cert_chain(c.cert_file, c.key_file or None)
        action = f"{c.namespace.rstrip('/')}/{operation}"
        req = urllib.request.Request(
            c.endpoint, data=body, method="POST",
            headers={"Content-Type": "text/xml; charset=utf-8",
                     "SOAPAction": f'"{action}"'})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS,  # noqa: S310
                                        context=ctx) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            payload = e.read() if hasattr(e, "read") else b""
            if payload:
                # A SOAP fault arrives as HTTP 500 with a body worth reading.
                parse_response(payload, operation)
            raise LRSError(f"LRS HTTP error {e.code}: {e.reason}") from None
        except urllib.error.URLError as e:
            raise LRSError(f"Could not reach the LRS: {e.reason}") from None

    def call(self, operation: str, body: bytes) -> LRSResponse:
        return parse_response(self._post(operation, body), operation)

    # -- operations -------------------------------------------------------

    def find_by_demographics(self, **kw: Any) -> LRSResponse:
        return self.call("LearnerByDemographics", self.build_find_request(**kw))

    def verify(self, **kw: Any) -> LRSResponse:
        return self.call("VerifyLearner", self.build_verify_request(**kw))


# ── Student-level helpers (log every call) ─────────────────────────

def _log(operation: str, student_id: str | None, resp: LRSResponse | None,
         error: str | None, who: str | None) -> None:
    try:
        with store.connect() as conn:
            conn.execute(
                "INSERT INTO lrs_requests (operation, student_id, response_code, "
                "response_text, ulns_returned, error, requested_by) "
                "VALUES (?,?,?,?,?,?,?)",
                (operation, student_id, resp.code if resp else None,
                 resp.description if resp else None,
                 ",".join(l.uln for l in resp.learners) if resp else None,
                 error, who))
            conn.commit()
    except Exception:
        logger.exception("Could not log LRS request")


def last_known_postcode(student_id: str) -> str | None:
    """Postcode from the pupil address on the student's latest CTF import."""
    store.init_db()
    with store.connect() as conn:
        r = conn.execute(
            "SELECT address FROM ctf_import_pupils WHERE student_id = ? "
            "AND address IS NOT NULL ORDER BY row_id DESC LIMIT 1",
            (student_id,)).fetchone()
    if not r:
        return None
    last = r["address"].strip().splitlines()[-1].strip()
    return last if re.match(r"^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$", last.upper()) else None


def find_uln_for_student(student_id: str, *, postcode: str | None = None,
                         client: LRSClient | None = None) -> LRSResponse:
    who = store.require("STUDENTS_MANAGE", "LRS lookup")
    store.init_db()
    s = _students().get_student(student_id)
    if s is None:
        raise ValidationError(f"No student with id {student_id}")
    if not s.date_of_birth:
        raise ValidationError(f"{student_id} has no date of birth; the LRS needs one")
    try:
        client = client or LRSClient()
        resp = client.find_by_demographics(
            family_name=s.last_name, given_name=s.first_name,
            date_of_birth=s.date_of_birth, gender=s.gender,
            postcode=postcode or last_known_postcode(student_id))
    except LRSNotConfigured:
        raise
    except Exception as e:
        _log("LearnerByDemographics", student_id, None, str(e), who)
        raise
    _log("LearnerByDemographics", student_id, resp, None, who)
    return resp


def verify_student_uln(student_id: str, *, client: LRSClient | None = None
                       ) -> LRSResponse:
    who = store.require("STUDENTS_MANAGE", "LRS verify")
    store.init_db()
    s = _students().get_student(student_id)
    if s is None:
        raise ValidationError(f"No student with id {student_id}")
    if not s.uln:
        raise ValidationError(f"{student_id} has no ULN to verify")
    try:
        client = client or LRSClient()
        resp = client.verify(uln=s.uln, family_name=s.last_name,
                             given_name=s.first_name,
                             date_of_birth=s.date_of_birth, gender=s.gender)
    except LRSNotConfigured:
        raise
    except Exception as e:
        _log("VerifyLearner", student_id, None, str(e), who)
        raise
    _log("VerifyLearner", student_id, resp, None, who)
    return resp


def apply_uln(student_id: str, uln: str):
    """Record a ULN (e.g. one the LRS returned) on the student."""
    who = store.require("STUDENTS_MANAGE", "set ULN")
    if not is_valid_uln(uln):
        raise ValidationError(explain_uln(uln))
    s = _students().set_identifiers(student_id, uln=uln)
    logger.info("ULN set for %s by %s", student_id, who)
    return s


def list_requests(limit: int = 200) -> list[dict[str, Any]]:
    store.init_db()
    with store.connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM lrs_requests ORDER BY request_id DESC LIMIT ?",
            (limit,)).fetchall()]
