"""The student record's profile fields: census ethnicity, home address and
postcode, preferred name, previous school, start/leave dates, and the DfE
UPN check. Pure validation with no database access; ``students`` stores
what these return. Kept apart so the record module stays under the size
limit.
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Any


class ValidationError(ValueError):
    """Raised for any invalid student-form input."""


#: ILR / census ethnicity codes and their labels. The census return
#: exports the code (99 when nothing is held).
ETHNICITIES: tuple[tuple[str, str], ...] = (
    ("31", "White - English, Welsh, Scottish, Northern Irish or British"),
    ("32", "White - Irish"),
    ("33", "White - Gypsy or Irish Traveller"),
    ("34", "White - any other White background"),
    ("35", "Mixed - White and Black Caribbean"),
    ("36", "Mixed - White and Black African"),
    ("37", "Mixed - White and Asian"),
    ("38", "Mixed - any other Mixed or multiple ethnic background"),
    ("39", "Asian or Asian British - Indian"),
    ("40", "Asian or Asian British - Pakistani"),
    ("41", "Asian or Asian British - Bangladeshi"),
    ("42", "Asian or Asian British - Chinese"),
    ("43", "Asian or Asian British - any other Asian background"),
    ("44", "Black or Black British - African"),
    ("45", "Black or Black British - Caribbean"),
    ("46", "Black or Black British - any other Black background"),
    ("47", "Arab"),
    ("98", "Any other ethnic group"),
    ("99", "Not provided"),
)
ETHNICITY_LABELS: dict[str, str] = dict(ETHNICITIES)

#: Longest staff note, medical note or SEND description the add form takes.
NOTES_MAX_LENGTH = 2000

#: Who the emergency contact is to the learner. The same pick list the FE
#: College and Apprenticeships add forms offer.
EMERGENCY_RELATIONSHIPS: tuple[str, ...] = (
    "Parent", "Carer", "Guardian", "Partner", "Spouse", "Sibling",
    "Grandparent", "Other relative", "Friend", "Other",
)
_RELATION_ALIASES: dict[str, str] = {
    **dict.fromkeys(("mother", "father", "mum", "mom", "dad", "stepmother",
                     "stepfather", "step-mother", "step-father", "parent/carer",
                     "parent / carer", "parents"), "Parent"),
    **dict.fromkeys(("foster carer", "carer/guardian"), "Carer"),
    **dict.fromkeys(("brother", "sister", "stepbrother", "stepsister"), "Sibling"),
    **dict.fromkeys(("grandmother", "grandfather", "grandma", "grandad",
                     "grandpa", "nan", "nana", "gran"), "Grandparent"),
    **dict.fromkeys(("husband", "wife", "civil partner"), "Spouse"),
    **dict.fromkeys(("boyfriend", "girlfriend"), "Partner"),
    **dict.fromkeys(("aunt", "auntie", "uncle", "cousin", "relative"),
                    "Other relative"),
}


def normalise_relationship(value: str | None) -> str | None:
    """The pick-list name for a relationship (``"father"`` -> ``"Parent"``).

    Admissions, CTF and bulk imports hand over free text, so a value that
    is not on the list is kept as written rather than refusing the record.
    """
    text = " ".join(str(value or "").split())
    if not text:
        return None
    key = text.lower()
    for choice in EMERGENCY_RELATIONSHIPS:
        if choice.lower() == key:
            return choice
    if key in _RELATION_ALIASES:
        return _RELATION_ALIASES[key]
    if len(text) > 40:
        raise ValidationError("Emergency contact relationship is too long (at most 40 characters)")
    return text


def check_emergency_contact(data: dict[str, Any]) -> None:
    """The add/edit form's rule, as on the other systems' forms: a contact
    needs both a name and a phone number. Not applied to automated intake,
    which takes whatever the application held."""
    name = str(data.get("emergency_contact_name") or "").strip()
    phone = str(data.get("emergency_contact_phone") or "").strip()
    relation = str(data.get("emergency_contact_relation") or "").strip()
    if (name or phone or relation) and not (name and phone):
        raise ValidationError("An emergency contact needs both a name and a phone number")

#: The gender options every system's add form offers, in this order. The
#: sixth form stores the lower-case form (``"non-binary"``), as it always has
#: for male/female/other, so the census, CTF and LRS mappings keep working.
GENDER_OPTIONS: tuple[str, ...] = ("Female", "Male", "Non-binary", "Other", "Prefer not to say")
GENDER_CODES: tuple[str, ...] = tuple(o.lower() for o in GENDER_OPTIONS)
_GENDER_ALIASES = {"f": "female", "m": "male", "nonbinary": "non-binary",
                   "non binary": "non-binary", "unspecified": "prefer not to say",
                   "not stated": "prefer not to say", "prefer not to say": "prefer not to say"}


def gender_code(value: Any) -> str | None:
    """The stored value for a gender typed or picked anywhere (label, code
    or common shorthand); None when blank. Raises on anything else."""
    text = " ".join(str(value or "").split()).lower()
    if not text:
        return None
    code = text if text in GENDER_CODES else _GENDER_ALIASES.get(text)
    if code is None:
        raise ValidationError(f"Gender must be one of: {', '.join(GENDER_OPTIONS)}")
    return code


def gender_label(code: str | None) -> str:
    """``"non-binary"`` -> ``"Non-binary"``; blank or unknown as held."""
    return dict(zip(GENDER_CODES, GENDER_OPTIONS)).get((code or "").lower(), code or "")


#: The home address as every other system asks for it. ``address`` is kept
#: as these joined one per line, because the census, CTF and the handover
#: read it.
ADDRESS_LINE_FIELDS: tuple[str, ...] = ("address_line1", "address_line2", "town")


def split_address(lines: list[str]) -> tuple[str | None, str | None, str | None]:
    """Line 1, line 2 and town from free address lines (postcode removed):
    one line is line 1; two are line 1 and town; more put the middle ones
    in line 2."""
    if not lines:
        return None, None, None
    if len(lines) == 1:
        return lines[0], None, None
    if len(lines) == 2:
        return lines[0], None, lines[1]
    return lines[0], ", ".join(lines[1:-1]), lines[-1]


def address_parts(record: Any) -> tuple[str, str, str]:
    """A record's line 1 / line 2 / town for a form, split from ``address``
    when it predates the separate fields."""
    parts = tuple(getattr(record, k, None) for k in ADDRESS_LINE_FIELDS)
    if not any(parts) and getattr(record, "address", None):
        parts = split_address([ln for ln in record.address.splitlines() if ln.strip()])
    return tuple(p or "" for p in parts)  # type: ignore[return-value]


_POSTCODE_RE = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?) ?(\d[A-Z]{2})\b")


def normalise_postcode(value: str | None) -> str | None:
    """``"sw1a1aa"`` -> ``"SW1A 1AA"``; None when it is not a UK postcode."""
    text = re.sub(r"\s+", "", (value or "").upper())
    m = re.fullmatch(r"([A-Z]{1,2}\d[A-Z\d]?)(\d[A-Z]{2})", text)
    return f"{m.group(1)} {m.group(2)}" if m else None


def postcode_in(address: str | None) -> str | None:
    """The last UK postcode written anywhere in *address*, if any."""
    found = _POSTCODE_RE.findall((address or "").upper())
    return f"{found[-1][0]} {found[-1][1]}" if found else None


def _short(data: dict[str, Any], key: str, label: str,
           limit: int = 80) -> str | None:
    value = " ".join(str(data.get(key) or "").split()) or None
    if value and len(value) > limit:
        raise ValidationError(f"{label} is too long (at most {limit} characters)")
    return value


def _validate_profile(data: dict[str, Any]) -> dict[str, Any]:
    """The preferred name, address, census and start/leave fields."""
    out: dict[str, Any] = {
        "preferred_name": _short(data, "preferred_name", "Preferred name", 40),
        "pronouns": _short(data, "pronouns", "Pronouns", 30),
        "previous_school": _short(data, "previous_school", "Previous school", 120),
        "nationality": _short(data, "nationality", "Nationality", 60),
        "first_language": _short(data, "first_language", "First language", 60),
        "leaving_reason": _short(data, "leaving_reason", "Leaving reason", 200),
    }
    # The form sends line 1 / line 2 / town; admissions, CTF and bulk edits
    # send one ``address`` string, which is split the same way.
    parts = [" ".join(str(data.get(k) or "").split()) or None for k in ADDRESS_LINE_FIELDS]
    from_lines = any(parts) or not str(data.get("address") or "").strip()
    for value, label in zip(parts, ("Address line 1", "Address line 2", "Town")):
        if value and len(value) > 100:
            raise ValidationError(f"{label} is too long (at most 100 characters)")
    if from_lines:
        lines = [p for p in parts if p]
    else:
        lines = [" ".join(ln.split()) for ln in str(data.get("address") or "")
                 .replace(",", "\n").splitlines()]
        lines = [ln for ln in lines if ln]
    address = "\n".join(lines) or None
    if address and len(address) > 300:
        raise ValidationError("Home address is too long (at most 300 characters)")
    raw_pc = (data.get("postcode") or "").strip()
    if raw_pc:
        postcode = normalise_postcode(raw_pc)
        if postcode is None:
            raise ValidationError(f"{raw_pc!r} is not a UK postcode")
    else:
        # Admissions and CTF hand over one address string with the
        # postcode in it; keep the postcode where the census can find it.
        postcode = postcode_in(address)
    if postcode:
        # The postcode has its own field, so drop a copy typed into a line.
        parts = [None if p and normalise_postcode(p) == postcode else p for p in parts]
        lines = [ln for ln in lines if normalise_postcode(ln) != postcode]
    line1, line2, town = parts if from_lines else split_address(lines)
    out.update(address_line1=line1, address_line2=line2, town=town, postcode=postcode,
               address="\n".join(p for p in (line1, line2, town) if p) or None)

    notes = str(data.get("notes") or "").strip() or None
    if notes and len(notes) > NOTES_MAX_LENGTH:
        raise ValidationError(f"Notes must be {NOTES_MAX_LENGTH} characters or fewer")
    out["notes"] = notes

    ethnicity = (data.get("ethnicity") or "").strip() or None
    if ethnicity and ethnicity not in ETHNICITY_LABELS:
        by_label = {v.lower(): k for k, v in ETHNICITIES}
        ethnicity = by_label.get(ethnicity.lower())
        if ethnicity is None:
            raise ValidationError("Ethnicity must be one of the census codes")
    out["ethnicity"] = ethnicity

    for key, label in (("start_date", "Start date"),
                       ("leaving_date", "Leaving date")):
        value = (data.get(key) or "").strip() or None
        if value:
            try:
                _dt.date.fromisoformat(value)
            except ValueError:
                raise ValidationError(f"{label} must be YYYY-MM-DD") from None
        out[key] = value
    if out["start_date"] and out["leaving_date"] \
            and out["leaving_date"] < out["start_date"]:
        raise ValidationError("Leaving date is before the start date")
    return out


# ── UPN ─────────────────────────────────────────────────────────────

_UPN_LETTERS = "ABCDEFGHJKLMNPQRTUVWXYZ"


def validate_upn(value: str | None) -> str | None:
    """A DfE Unique Pupil Number, upper-cased, or None if blank.

    Thirteen characters: a check letter then twelve digits; a temporary
    UPN ends in a letter instead of the last digit. The check letter is
    the weighted sum of characters 2-13 (weights 2-13) mod 23.
    """
    upn = re.sub(r"[^0-9A-Za-z]", "", value or "").upper()
    if not upn:
        return None
    if not re.fullmatch(r"[A-Z]\d{11}[0-9A-Z]", upn):
        raise ValidationError(
            "UPN must be 13 characters: a letter, then 11 digits, then a "
            "digit (or a letter for a temporary UPN)")
    total = 0
    for pos, ch in enumerate(upn[1:], start=2):
        if ch.isdigit():
            n = int(ch)
        elif ch in _UPN_LETTERS:
            n = _UPN_LETTERS.index(ch)
        else:
            raise ValidationError(f"UPN cannot end in {ch!r}")
        total += n * pos
    if _UPN_LETTERS[total % 23] != upn[0]:
        raise ValidationError(f"UPN {upn} fails its check letter")
    return upn
