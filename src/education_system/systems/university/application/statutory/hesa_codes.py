"""HESA coding frames as lookup tables (``hesa_coding_frames``) and the
mapping of our own values onto them.

The seed holds only real HESA / ISO code values for the fields this
system can source: SEXID, NATION (ISO 3166-1 alpha-2, the frame HESA uses
for nationality), MODE, FUNDCOMP, RSNENGEND, CLASS and MODOUT. MODE,
RSNENGEND, CLASS and MODOUT carry the long-standing Student-record codes;
the Data Futures coding manual for the reporting year is the authority, so
every code is editable here and a code can be retired (``active = 0``)
rather than deleted. Nothing is ever guessed: a value with no code is left
out of the return and reported by validation.

Our value → code overrides use the existing ``hesa_field_mappings`` table
(``return_type='Student'``, ``hesa_field``, ``local_field`` = our value,
``transform_rule`` = the code), the same convention as the staff return.
"""

from __future__ import annotations

from education_system.systems.university.application.statutory import access as sa

RETURN_TYPE = "Student"

SEED: dict[str, tuple[tuple[str, str], ...]] = {
    "SEXID": (("10", "Female"), ("11", "Male"), ("12", "Other")),
    "NATION": (
        ("GB", "United Kingdom"), ("IE", "Ireland"), ("FR", "France"), ("DE", "Germany"),
        ("ES", "Spain"), ("IT", "Italy"), ("PT", "Portugal"), ("PL", "Poland"),
        ("RO", "Romania"), ("NL", "Netherlands"), ("BE", "Belgium"), ("GR", "Greece"),
        ("SE", "Sweden"), ("CY", "Cyprus"), ("BG", "Bulgaria"), ("LT", "Lithuania"),
        ("CN", "China"), ("HK", "Hong Kong"), ("IN", "India"), ("PK", "Pakistan"),
        ("BD", "Bangladesh"), ("LK", "Sri Lanka"), ("NP", "Nepal"), ("MY", "Malaysia"),
        ("SG", "Singapore"), ("VN", "Viet Nam"), ("TH", "Thailand"), ("JP", "Japan"),
        ("KR", "Korea, Republic of"), ("SA", "Saudi Arabia"), ("AE", "United Arab Emirates"),
        ("TR", "Turkey"), ("NG", "Nigeria"), ("GH", "Ghana"), ("KE", "Kenya"),
        ("ZA", "South Africa"), ("ZW", "Zimbabwe"), ("EG", "Egypt"), ("US", "United States"),
        ("CA", "Canada"), ("BR", "Brazil"), ("AU", "Australia"), ("NZ", "New Zealand"),
    ),
    "MODE": (
        ("01", "Full-time"), ("31", "Part-time"),
        ("63", "Dormant - previously full-time"), ("64", "Dormant - previously part-time"),
    ),
    "FUNDCOMP": (
        ("1", "Completed current year of programme of study"),
        ("2", "Not yet completed current year of programme of study"),
        ("3", "Not completed current year of programme of study"),
    ),
    "RSNENGEND": (
        ("01", "Successful completion of course"),
        ("02", "Academic failure/left in bad standing/not permitted to progress"),
        ("03", "Transferred to another provider"), ("04", "Health reasons"), ("05", "Death"),
        ("06", "Financial reasons"), ("07", "Other personal reasons & dropped out"),
        ("08", "Written off after lapse of time"), ("09", "Exclusion"),
        ("10", "Gone into employment"), ("11", "Other"),
        ("12", "Completion of course - result unknown"), ("98", "Unknown"),
    ),
    "CLASS": (
        ("01", "First class honours"), ("02", "Upper second class honours"),
        ("03", "Lower second class honours"), ("05", "Third class honours/Fourth class"),
        ("07", "Unclassified honours"),
    ),
    "MODOUT": (
        ("1", "Successfully completed the module"), ("2", "Did not complete the module"),
        ("3", "Completed the module but failed"),
    ),
}

#: Our stored values -> code, before any institution override.
BUILT_IN: dict[str, dict[str, str]] = {
    "SEXID": {"female": "10", "f": "10", "male": "11", "m": "11", "other": "12"},
    "MODE": {"full-time": "01", "full time": "01", "fulltime": "01", "ft": "01",
             "part-time": "31", "part time": "31", "parttime": "31", "pt": "31"},
    "CLASS": {"first": "01", "1st": "01", "upper second": "02", "2:1": "02", "2.1": "02",
              "lower second": "03", "2:2": "03", "2.2": "03", "third": "05",
              "unclassified": "07"},
    "RSNENGEND": {"complete": "01", "completed": "01"},
}

FIELDS = tuple(SEED)


def seed(conn) -> int:
    """Insert the real seed codes that are missing (never overwrites edits)."""
    sa.ensure(conn)
    added = 0
    for field, codes in SEED.items():
        for code, label in codes:
            added += conn.execute(
                "INSERT OR IGNORE INTO hesa_coding_frames (field, code, label, notes) "
                "VALUES (?, ?, ?, 'seeded')", (field, code, label)).rowcount
    return added


def frame(conn, field) -> list[dict]:
    seed(conn)
    return sa.dicts(conn.execute("SELECT * FROM hesa_coding_frames WHERE field = ? "
                                 "ORDER BY code", (field,)))


def save_code(current, field, code, label, active=True) -> None:
    who = sa.officer(current)
    field = str(field or "").strip().upper()
    code = str(code or "").strip()
    label = str(label or "").strip()
    if not field or not code or not label:
        raise ValueError("Field, code and label are all required")
    with sa.session() as conn:
        seed(conn)
        conn.execute(
            "INSERT INTO hesa_coding_frames (field, code, label, notes, active) "
            "VALUES (?, ?, ?, 'edited', ?) ON CONFLICT(field, code) DO UPDATE SET "
            "label = excluded.label, active = excluded.active, notes = 'edited'",
            (field, code, label, int(bool(active))))
        sa.audit(conn, who, "hesa", "coding_frame", f"{field}:{code}", "saved",
                 {"label": label, "active": bool(active)})


def _overrides(conn) -> dict:
    out: dict[str, dict[str, str]] = {}
    if not sa.has_table(conn, "hesa_field_mappings"):
        return out
    for field, local, code in conn.execute(
            "SELECT hesa_field, local_field, transform_rule FROM hesa_field_mappings "
            "WHERE return_type = ? AND COALESCE(is_active, 1) = 1 AND transform_rule IS NOT NULL",
            (RETURN_TYPE,)):
        out.setdefault(str(field).upper(), {})[str(local).strip().lower()] = str(code).strip()
    return out


class Coder:
    """Maps our values to active codes for one build (reads the tables once)."""

    def __init__(self, conn):
        seed(conn)
        self.valid: dict[str, dict[str, str]] = {}
        for field, code, label in conn.execute(
                "SELECT field, code, label FROM hesa_coding_frames WHERE active = 1"):
            self.valid.setdefault(field, {})[code] = label
        self.overrides = _overrides(conn)

    def code(self, field, value) -> str | None:
        if value in (None, ""):
            return None
        key = str(value).strip().lower()
        valid = self.valid.get(field, {})
        for table in (self.overrides.get(field, {}), BUILT_IN.get(field, {})):
            if key in table and table[key] in valid:
                return table[key]
        raw = str(value).strip()
        if raw in valid or raw.upper() in valid:
            return raw if raw in valid else raw.upper()
        for code, label in valid.items():
            if label.lower() == key:
                return code
        return None

    def label(self, field, code) -> str:
        return self.valid.get(field, {}).get(code, "")


__all__ = ["BUILT_IN", "Coder", "FIELDS", "RETURN_TYPE", "SEED", "frame", "save_code", "seed"]
