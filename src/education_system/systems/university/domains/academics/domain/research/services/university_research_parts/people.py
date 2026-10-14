"""People, read from the university's existing registers.

The portal used to own a ``research_people`` table and seed it with demo
names. Everyone it needs already exists somewhere canonical:

* university staff        -> ``staff`` (+ ``staff_profiles`` for department)
* research-degree students -> ``students``
* external examiners      -> ``external_examiners``

Those three have independent primary keys, so a person is addressed by a
composite key: ``"staff:12"``, ``"student:S12345"``, ``"external:3"``. The
portal's person-reference columns are TEXT for exactly this reason.

Nothing here writes. Creating a member of staff means creating a login, and
that belongs to Staff HR, not to a research portal.
"""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


SOURCES = ("staff", "student", "external")

#: Person key -> human label, cached per Database instance for the life of
#: a dialog. The registers are small and change rarely.
_CACHE_ATTR = "_people_cache"


def person_key(source, raw_id):
    return f"{source}:{raw_id}"


def split_key(key):
    """``"staff:12"`` -> ``("staff", "12")``; ``("", key)`` if unprefixed."""
    text = "" if key is None else str(key)
    source, sep, raw = text.partition(":")
    if sep and source in SOURCES:
        return source, raw
    return "", text


def fetch_people(db, role=None):
    """Return ``[(key, name, role, department, email)]`` across all registers.

    ``role`` filters to one of :data:`SOURCES`.
    """
    out = []

    if role in (None, "staff"):
        # staff_profiles keys on username, not on staff.id.
        for r in db.query(
            "SELECT s.id, s.name, s.email, "
            "       COALESCE(p.department, '') AS department "
            "  FROM staff s "
            "  LEFT JOIN staff_profiles p ON p.user_id = s.username "
            " WHERE COALESCE(s.status,'active') != 'inactive' "
            " ORDER BY s.name"
        ):
            out.append((person_key("staff", r["id"]), r["name"], "staff",
                        r["department"], r["email"] or ""))

    if role in (None, "student"):
        for r in db.query(
            "SELECT student_id, "
            "       TRIM(COALESCE(first_name,'') || ' ' || COALESCE(last_name,'')) AS name, "
            "       COALESCE(department, course, '') AS department, "
            "       COALESCE(email_address,'') AS email "
            "  FROM students WHERE COALESCE(is_active,1)=1 "
            " ORDER BY last_name, first_name"
        ):
            out.append((person_key("student", r["student_id"]),
                        r["name"] or "(unnamed)", "student",
                        r["department"], r["email"]))

    if role in (None, "external"):
        for r in db.query(
            "SELECT examiner_id, name, COALESCE(institution,'') AS institution, "
            "       COALESCE(email,'') AS email FROM external_examiners "
            " ORDER BY name"
        ):
            out.append((person_key("external", r["examiner_id"]), r["name"],
                        "external", r["institution"], r["email"]))

    return out


def people_index(db, refresh=False):
    """``{key: (name, role, department, email)}``, cached on the connection."""
    cached = getattr(db, _CACHE_ATTR, None)
    if cached is None or refresh:
        cached = {k: (n, r, d, e) for k, n, r, d, e in fetch_people(db)}
        setattr(db, _CACHE_ATTR, cached)
    return cached


def person_name(db, key, default="—"):
    """Resolve a person key to a display name without a per-row query."""
    if not key:
        return default
    entry = people_index(db).get(str(key))
    if entry:
        return entry[0]
    # Unknown key — show it rather than silently blanking, so a dangling
    # reference is visible instead of looking like "no lead author".
    source, raw = split_key(key)
    return f"({source or 'unknown'} {raw})" if raw else default


def person_choices(db, role=None):
    """``[(key, "Name (Department)")]`` for a combo box."""
    return [
        (key, f"{name} ({dept or '—'})")
        for key, name, _role, dept, _email in fetch_people(db, role)
    ]


__all__ = ["SOURCES", "person_key", "split_key", "fetch_people",
           "people_index", "person_name", "person_choices"]
