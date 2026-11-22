"""Learner identifiers the funding and exam returns need.

* **ULN** — Unique Learner Number, issued by the Learning Records
  Service. Ten digits; the tenth is a check digit. The LRS check: weight
  the first nine digits 10, 9, ... 2, sum, take the remainder mod 11 and
  subtract it from 10. A result of 10 cannot be a single digit, so no
  valid ULN produces it.
* **UCI** — Unique Candidate Identifier (JCQ), the 13-character id that
  follows a candidate between exam series: 5-digit centre number, 1-digit
  year, 4-digit candidate number, then three further characters
  (reserved positions and a check character). **Only the format is
  validated here** — the JCQ check-character algorithm is not
  implemented, so a UCI with a mistyped check character will be accepted.
  Confirm UCIs against the awarding bodies' records.
* **Candidate number** — the 4-digit centre candidate number used on
  entries and seating plans.
"""

from __future__ import annotations

import re

ULN_RE = re.compile(r"^\d{10}$")
UCI_RE = re.compile(r"^\d{5}\d\d{4}[0-9A-Z]{3}$")
CANDIDATE_NO_RE = re.compile(r"^\d{4}$")


def uln_check_digit(first_nine: str) -> int | None:
    """The LRS check digit for nine digits, or None if no digit is valid."""
    if not re.fullmatch(r"\d{9}", first_nine or ""):
        raise ValueError("Need exactly nine digits")
    total = sum(int(d) * w for d, w in zip(first_nine, range(10, 1, -1)))
    check = 10 - (total % 11)
    return None if check == 10 else check


def is_valid_uln(uln: str | None) -> bool:
    s = (uln or "").strip()
    if not ULN_RE.match(s):
        return False
    check = uln_check_digit(s[:9])
    return check is not None and check == int(s[9])


def validate_uln(uln: str | None) -> str | None:
    """Return the ULN normalised (or None if blank); raise ValueError if bad."""
    s = (uln or "").replace(" ", "").strip()
    if not s:
        return None
    if not ULN_RE.match(s):
        raise ValueError("ULN must be exactly 10 digits")
    if not is_valid_uln(s):
        raise ValueError("ULN check digit is wrong — re-check the number with the LRS")
    return s


def validate_uci(uci: str | None) -> str | None:
    """Format-only UCI check (see module docstring)."""
    s = (uci or "").replace(" ", "").strip().upper()
    if not s:
        return None
    if not UCI_RE.match(s):
        raise ValueError(
            "UCI must be 13 characters: 5-digit centre number, year digit, "
            "4-digit candidate number, then 3 letters/digits")
    return s


def validate_candidate_number(value: str | int | None) -> str | None:
    s = str(value).strip() if value not in (None, "") else ""
    if not s:
        return None
    if s.isdigit() and len(s) < 4:
        s = s.zfill(4)
    if not CANDIDATE_NO_RE.match(s):
        raise ValueError("Candidate number must be 4 digits")
    return s


def uci_centre(uci: str) -> str:
    return uci[:5]


def uci_candidate_number(uci: str) -> str:
    return uci[6:10]
