"""School settings in one place.

Kept from the old Settings screen (``interfaces/settings.py``): every
setting is declared once in :data:`REGISTRY` with a type, a default, a
category, a description and limits, and the screens walk the registry
rather than hard-coding fields. The old local keys are all still here
(attendance report window and thresholds, grade alerts, progress period,
fee windows, receipts, UI flags, default year, export folder and format),
with the old actions: show all / by category, view one, edit one, reset
one, reset all, and an effective snapshot (JSON).

New:

* **The school.** Name, URN, local authority number, DfE number (LAESTAB),
  address, phone, e-mail, website, headteacher, logo, the name e-mails are
  sent under and a signature. :func:`get_setting` is how any other module
  reads them (``get_setting("school_name")``); :func:`school_values` gives
  the placeholders e-mail templates use.
* **One table.** New general settings live in ``school_settings`` (key,
  value, type) - the old separate ``settings_kv`` database is gone. Values
  are validated by type and by rule (URN six digits, LAESTAB starting with
  the LA number, UK postcode, e-mail, phone...); a save of several values is
  all or nothing.
* **Who.** Reading for the screens and every change is for
  :data:`access.SETTINGS_EDITORS`; :func:`get_setting` itself is open (it is
  how the school name gets into a letter). Every change is in
  ``settings_audit`` (old and new value) and the activity log (key only).
* **Settings that live elsewhere.** Session times (attendance), library
  loan rules, the cover limit, the homework limit, lessons per week and the
  timetable cycle are shown and changed through their own modules'
  functions (:data:`LINKED`), so their rules and audit still apply. Term
  dates are in Academic Year & Calendar: :func:`term_dates` only reads them.
* **Sign-in policy.** The old "global (auth)" settings are changed here
  again (:func:`set_auth_policy`, :func:`reset_auth_policy`): failed-login
  limit, lockout length, password age and session length are stored in
  auth.db and apply to all seven systems (the platform reads them where
  it signs people in); "force password resets by age" is this school's own
  switch. Defaults shown are the platform's real ones.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from education_system.platform.identity.auth import defaults as _auth_defaults
from education_system.platform.identity.auth import policy as _auth_policy
from education_system.systems.secondary.core.exceptions import errors
from education_system.systems.secondary.core.permissions.access import SETTINGS_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = errors.ValidationError
PermissionDenied = errors.PermissionDenied
NotFound = errors.NotFound

TYPES = ("str", "int", "float", "bool", "choice", "email", "phone", "postcode", "path", "url")


@dataclass(frozen=True)
class SettingSpec:
    key: str
    label: str
    description: str
    type: str
    default: Any
    category: str
    choices: tuple[str, ...] | None = None
    min: float | None = None
    max: float | None = None
    max_len: int = 200
    pattern: str | None = None      # regex the text must match
    pattern_hint: str = ""
    scope: str = "local"            # kept from the old registry ("global" = sign-in policy)


def _s(key, label, description, type_, default, category, **kw) -> SettingSpec:
    return SettingSpec(key, label, description, type_, default, category, **kw)


SCHOOL = "School"
EMAIL = "E-mail"
CONVENTIONS = "Academic year"

REGISTRY: tuple[SettingSpec, ...] = (
    # ── The school (new) ──
    _s("school_name", "School name", "The school's name as it appears on letters, e-mails "
       "and reports.", "str", "Secondary School", SCHOOL, max_len=120),
    _s("urn", "URN", "Unique Reference Number (six digits, from Get Information About "
       "Schools).", "str", "", SCHOOL, pattern=r"^\d{6}$", pattern_hint="six digits"),
    _s("la_number", "LA number", "The local authority's three-digit number.", "str", "",
       SCHOOL, pattern=r"^\d{3}$", pattern_hint="three digits"),
    _s("dfe_number", "DfE number (LAESTAB)", "LA number + four-digit establishment number, "
       "e.g. 123/4567.", "str", "", SCHOOL, pattern=r"^\d{3}/?\d{4}$",
       pattern_hint="LLL/EEEE or LLLEEEE"),
    _s("address_line1", "Address line 1", "", "str", "", SCHOOL, max_len=100),
    _s("address_line2", "Address line 2", "", "str", "", SCHOOL, max_len=100),
    _s("town", "Town", "", "str", "", SCHOOL, max_len=60),
    _s("county", "County", "", "str", "", SCHOOL, max_len=60),
    _s("postcode", "Postcode", "", "postcode", "", SCHOOL, max_len=10),
    _s("phone", "Phone", "The school office number.", "phone", "", SCHOOL, max_len=25),
    _s("email", "E-mail", "The school office e-mail address.", "email", "", SCHOOL,
       max_len=120),
    _s("website", "Website", "", "url", "", SCHOOL, max_len=200),
    _s("headteacher", "Headteacher", "Name used to sign letters, e.g. Mrs J Smith.", "str",
       "", SCHOOL, max_len=100),
    _s("logo_path", "Logo file", "A PNG, GIF or JPEG shown on letters and reports.", "path",
       "", SCHOOL, max_len=500),
    _s("email_sender_name", "E-mail sender name", "The name parents see e-mails from "
       "(blank = the school name).", "str", "", EMAIL, max_len=100),
    _s("email_signature", "E-mail signature", "Added under every e-mail to families "
       "(blank = none).", "str", "", EMAIL, max_len=500),
    _s("email_reply_to", "Reply-to address", "Where families' replies go (blank = the "
       "school e-mail).", "email", "", EMAIL, max_len=120),
    _s("year_start_month", "School year starts in", "The month the school year starts "
       "(term dates themselves are set in Academic Year & Calendar).", "choice",
       "September", CONVENTIONS, choices=("August", "September")),
    _s("year_label_style", "School year written as", "How a school year is written on "
       "screens and reports.", "choice", "2025/26", CONVENTIONS,
       choices=("2025/26", "2025-26", "2025-2026")),
    _s("week_starts_on", "Week starts on", "The first day of the week in calendars and "
       "registers.", "choice", "Monday", CONVENTIONS, choices=("Monday", "Sunday")),
    # ── Kept from the old local settings ──
    _s("attendance.default_window_days", "Default report window (days)", "Default look-back "
       "window for attendance reports when no explicit date range is given.", "int", 28,
       "Attendance", min=1, max=365),
    _s("attendance.threshold_pct", "Attendance threshold (%)", "Below this percentage, "
       "pupils show up on the attendance watchlist.", "float", 90.0, "Attendance",
       min=0, max=100),
    _s("attendance.max_lates", "Max lates per window", "More than this many lates flags "
       "the pupil.", "int", 5, "Attendance", min=0, max=1000),
    _s("attendance.max_absences", "Max absences per window", "More than this many "
       "absences flags the pupil.", "int", 3, "Attendance", min=0, max=1000),
    _s("grades.mock_below_pred_gap", "Mock-below-prediction alert gap", "Grade gap between "
       "predicted and latest mock that triggers a grades alert.", "int", 2, "Grades",
       min=1, max=6),
    _s("grades.min_target_points", "Min target points", "Predicted grade points below this "
       "trigger an alert. Set to 0 to disable.", "int", 0, "Grades", min=0, max=9),
    _s("progress.default_period", "Default progress period", "Selected by default in "
       "new-review dialogs.", "choice", "Mid-Cycle Check", "Progress",
       choices=("Autumn Half-Term 1", "Autumn Half-Term 2", "Spring Half-Term 1",
                "Spring Half-Term 2", "Summer Half-Term 1", "Summer Half-Term 2",
                "End of Year", "Mid-Cycle Check", "Ad Hoc")),
    _s("fees.default_due_days", "Default fee due window (days)", "How many days after the "
       "issue date a new charge becomes due by default.", "int", 30, "Finance",
       min=0, max=365),
    _s("fees.overdue_warning_days", "Overdue warning window (days)", "Charges overdue by "
       "more than this number of days are flagged in the summary.", "int", 0, "Finance",
       min=0, max=365),
    _s("receipts.auto_issue_on_import", "Auto-issue receipts when importing payments",
       "If on, imported payments are stamped Issued immediately rather than Draft.",
       "bool", True, "Finance"),
    _s("ui.confirm_destructive", "Confirm destructive actions", "Ask for confirmation "
       "before delete/void/archive.", "bool", True, "UI"),
    _s("ui.show_advanced", "Show advanced fields", "If off, some less-used form fields are "
       "hidden to keep dialogs compact.", "bool", False, "UI"),
    _s("ui.default_year", "Default academic year", "Pre-filled into 'academic year' fields "
       "(blank = the current school year).", "str", "", "UI",
       pattern=r"^(\d{4}[/-]\d{2})?$", pattern_hint="e.g. 2025/26"),
    _s("reports.export_dir", "Default export directory", "Where exports open their file "
       "picker by default.", "path", "", "Reporting", max_len=500),
    _s("reports.default_format", "Default export format", "Format pre-selected for custom "
       "exports.", "choice", "csv", "Reporting",
       choices=("csv", "tsv", "json", "jsonl", "markdown")),
)

#: The old "global (auth)" settings, now changed here (data in auth.db, so
#: lockout, session and password age apply to all seven systems; the
#: forced-reset switch is this school's own). Defaults are the platform's.
AUTH_POLICY: tuple[SettingSpec, ...] = (
    _s("force_password_reset", "Force password resets by age (this school)", "When on, "
       "anyone in this school whose password is older than the password age must change "
       "it at sign-in. This school's own switch.", "bool", True, "Sign-in policy",
       scope="system"),
    _s("max_login_attempts", "Max failed login attempts", "After this many failed attempts "
       "a user is temporarily locked out. All systems.", "int",
       _auth_defaults.MAX_LOGIN_ATTEMPTS, "Sign-in policy", scope="global",
       min=_auth_policy.POLICY_LIMITS["max_login_attempts"][0],
       max=_auth_policy.POLICY_LIMITS["max_login_attempts"][1]),
    _s("lockout_minutes", "Lockout duration (minutes)", "How long a user is locked out. "
       "All systems.", "int", _auth_defaults.LOCKOUT_DURATION_MINUTES, "Sign-in policy",
       scope="global", min=_auth_policy.POLICY_LIMITS["lockout_minutes"][0],
       max=_auth_policy.POLICY_LIMITS["lockout_minutes"][1]),
    _s("password_max_age_days", "Password max age (days)", "How old a password may get "
       "before a reset is forced - only where forced resets are on. All systems.", "int",
       _auth_policy.DEFAULT_PASSWORD_MAX_AGE_DAYS, "Sign-in policy", scope="global",
       min=_auth_policy.POLICY_LIMITS["password_max_age_days"][0],
       max=_auth_policy.POLICY_LIMITS["password_max_age_days"][1]),
    _s("session_timeout_minutes", "Session timeout (minutes)", "How long a sign-in "
       "session lasts. All systems; applies to new sign-ins.", "int",
       _auth_defaults.SESSION_TIMEOUT_MINUTES, "Sign-in policy", scope="global",
       min=_auth_policy.POLICY_LIMITS["session_timeout_minutes"][0],
       max=_auth_policy.POLICY_LIMITS["session_timeout_minutes"][1]),
)
_AUTH_BY_KEY: dict[str, SettingSpec] = {s.key: s for s in AUTH_POLICY}

_BY_KEY: dict[str, SettingSpec] = {s.key: s for s in REGISTRY}
_POSTCODE_RE = re.compile(r"^[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[0-9 ()-]{7,25}$")
_URL_RE = re.compile(r"^(https?://)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}(/\S*)?$")
_LOGO_EXT = (".png", ".gif", ".jpg", ".jpeg")
_MISSING = object()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS school_settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    value_type  TEXT NOT NULL,
    updated_by  TEXT,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS settings_audit (
    audit_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    key        TEXT,
    action     TEXT NOT NULL,
    old_value  TEXT,
    new_value  TEXT,
    actor      TEXT NOT NULL,
    at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_settings_audit_key ON settings_audit (key, at);
"""
database.register_schema("settings", _SCHEMA)


@dataclass(frozen=True)
class Setting:
    spec: SettingSpec
    value: Any
    is_default: bool
    updated_by: str | None = None
    updated_at: str | None = None

    @property
    def shown(self) -> str:
        return format_value(self.spec, self.value)


# ── Who may do what ──────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in SETTINGS_EDITORS


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        activity_log.record(f"settings.{action}", target=target, outcome="denied",
                            principal=actor)
        raise PermissionDenied("Only a system administrator can see or change the school "
                               "settings.")


def _audit(conn, action: str, actor: Principal, key: str | None = None,
           old: Any = None, new: Any = None) -> None:
    conn.execute("INSERT INTO settings_audit (key, action, old_value, new_value, actor) "
                 "VALUES (?, ?, ?, ?, ?)",
                 (key, action, None if old is None else json.dumps(old, default=str),
                  None if new is None else json.dumps(new, default=str),
                  actor.username or "unknown"))


def history(key: str | None = None, *, limit: int = 300) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM settings_audit", []
    if key:
        sql += " WHERE key = ?"
        params.append(key)
    with database.connect() as conn:
        rows = conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                            (*params, int(limit))).fetchall()
    return [{"at": r["at"], "key": r["key"], "action": r["action"], "actor": r["actor"],
             "old": json.loads(r["old_value"]) if r["old_value"] else None,
             "new": json.loads(r["new_value"]) if r["new_value"] else None} for r in rows]


# ── The registry ─────────────────────────────────────────────────────

def get_spec(key: str) -> SettingSpec:
    s = _BY_KEY.get(key)
    if s is None:
        raise NotFound(f"Unknown setting: {key}")
    return s


def categories() -> list[str]:
    out: list[str] = []
    for s in REGISTRY:
        if s.category not in out:
            out.append(s.category)
    return out


def list_specs(*, category: str | None = None) -> list[SettingSpec]:
    return [s for s in REGISTRY if category in (None, "", s.category)]


def format_value(spec: SettingSpec, v: Any) -> str:
    if spec.type == "bool":
        return "Yes" if v else "No"
    if v in ("", None):
        return "(unset)"
    return str(v)


# ── Checking a value ─────────────────────────────────────────────────

def coerce(spec: SettingSpec, value: Any) -> Any:
    """The clean value for *spec*, or raise ValidationError."""
    label = spec.label
    if spec.type == "bool":
        if isinstance(value, bool):
            return value
        s = str(value if value is not None else "").strip().lower()
        if s in ("1", "true", "yes", "on", "y"):
            return True
        if s in ("0", "false", "no", "off", "n", ""):
            return False
        raise ValidationError([f"{label}: answer yes or no"])
    if spec.type in ("int", "float"):
        try:
            v: Any = int(str(value).strip()) if spec.type == "int" else \
                round(float(str(value).strip()), 4)
        except (TypeError, ValueError):
            raise ValidationError([f"{label}: must be a "
                                   + ("whole number" if spec.type == "int" else "number")]
                                  ) from None
        if spec.min is not None and v < spec.min or spec.max is not None and v > spec.max:
            lo = int(spec.min) if spec.type == "int" else spec.min
            hi = int(spec.max) if spec.type == "int" else spec.max
            raise ValidationError([f"{label}: must be from {lo} to {hi}"])
        return v
    text = " ".join(str(value if value is not None else "").split()) \
        if spec.key != "email_signature" else str(value or "").strip()
    if len(text) > spec.max_len:
        raise ValidationError([f"{label}: at most {spec.max_len} characters"])
    if spec.type == "choice":
        hit = next((c for c in spec.choices or () if c.lower() == text.lower()), None)
        if hit is None:
            raise ValidationError([f"{label}: must be one of {', '.join(spec.choices or ())}"])
        return hit
    if not text:
        return ""
    if spec.pattern and not re.match(spec.pattern, text):
        raise ValidationError([f"{label}: should be {spec.pattern_hint or 'a valid value'}"])
    if spec.type == "email" and not _EMAIL_RE.match(text):
        raise ValidationError([f"{label}: doesn't look like an e-mail address"])
    if spec.type == "phone" and (not _PHONE_RE.match(text)
                                 or sum(c.isdigit() for c in text) < 7):
        raise ValidationError([f"{label}: doesn't look like a phone number"])
    if spec.type == "url" and not _URL_RE.match(text):
        raise ValidationError([f"{label}: doesn't look like a web address"])
    if spec.type == "postcode":
        text = text.upper()
        if not _POSTCODE_RE.match(text):
            raise ValidationError([f"{label}: doesn't look like a UK postcode"])
        if " " not in text:
            text = f"{text[:-3]} {text[-3:]}"
    if spec.key == "logo_path" and not text.lower().endswith(_LOGO_EXT):
        raise ValidationError([f"{label}: must be a PNG, GIF or JPEG file"])
    if spec.key == "dfe_number" and "/" not in text:
        text = f"{text[:3]}/{text[3:]}"
    return text


def _cross_check(values: dict[str, Any]) -> list[str]:
    """Rules across settings (checked on the values as they will be)."""
    problems = []
    la, dfe = values.get("la_number") or "", values.get("dfe_number") or ""
    if la and dfe and not dfe.startswith(la):
        problems.append(f"DfE number (LAESTAB): should start with the LA number {la}")
    return problems


def warnings(values: dict[str, Any] | None = None) -> list[str]:
    """Worth a look but not wrong: a logo file that isn't there."""
    vals = values or effective()
    out = []
    logo = vals.get("logo_path")
    if logo and not Path(str(logo)).expanduser().is_file():
        out.append(f"The logo file {logo} can't be found on this computer.")
    if not vals.get("school_name") or vals.get("school_name") == _BY_KEY["school_name"].default:
        out.append("The school name is still the default - set it so letters and e-mails "
                   "carry the right name.")
    return out


# ── Reading ──────────────────────────────────────────────────────────

def _stored() -> dict[str, Any]:
    with database.connect() as conn:
        return {r["key"]: r for r in conn.execute("SELECT * FROM school_settings")}


def _decode(spec: SettingSpec, raw: str) -> Any:
    try:
        return coerce(spec, json.loads(raw))
    except (ValueError, ValidationError):
        return spec.default


def get_setting(key: str, default: Any = _MISSING) -> Any:
    """A setting's value, for any module (no permission check: it is how the
    school name reaches a letter). A key not set gives *default* when one is
    passed, else the registry default; an unknown key gives *default* (None)."""
    spec = _BY_KEY.get(key)
    if spec is None:
        return None if default is _MISSING else default
    with database.connect() as conn:
        r = conn.execute("SELECT value FROM school_settings WHERE key = ?", (key,)).fetchone()
    if r is None:
        return spec.default if default is _MISSING else default
    return _decode(spec, r["value"])


def effective() -> dict[str, Any]:
    """Every setting's current value, by key (no permission check)."""
    stored = _stored()
    return {s.key: _decode(s, stored[s.key]["value"]) if s.key in stored else s.default
            for s in REGISTRY}


def school_values() -> dict[str, str]:
    """The placeholders e-mail templates and letters use."""
    v = effective()
    address = ", ".join(x for x in (v["address_line1"], v["address_line2"], v["town"],
                                    v["county"], v["postcode"]) if x)
    return {"school_name": v["school_name"] or _BY_KEY["school_name"].default,
            "school_address": address, "school_phone": v["phone"],
            "school_email": v["email"], "school_website": v["website"],
            "headteacher": v["headteacher"], "urn": v["urn"],
            "email_sender_name": v["email_sender_name"] or v["school_name"],
            "email_signature": v["email_signature"]}


def list_settings(*, actor: Principal, category: str | None = None) -> list[Setting]:
    _require_editor(actor, "view")
    stored = _stored()
    out = []
    for s in list_specs(category=category):
        r = stored.get(s.key)
        out.append(Setting(s, _decode(s, r["value"]) if r else s.default, r is None,
                           r["updated_by"] if r else None, r["updated_at"] if r else None))
    return out


def get(key: str, *, actor: Principal) -> Setting:
    _require_editor(actor, "view", key)
    spec = get_spec(key)
    r = _stored().get(key)
    return Setting(spec, _decode(spec, r["value"]) if r else spec.default, r is None,
                   r["updated_by"] if r else None, r["updated_at"] if r else None)


# ── Changing ─────────────────────────────────────────────────────────

def set_many(changes: dict[str, Any], *, actor: Principal) -> dict[str, Any]:
    """Save several settings at once: all or nothing. Returns what changed
    (key -> new value)."""
    _require_editor(actor, "update")
    problems: list[str] = []
    clean: dict[str, Any] = {}
    for key, value in changes.items():
        spec = _BY_KEY.get(key)
        if spec is None:
            problems.append(f"Unknown setting: {key}")
            continue
        try:
            clean[key] = coerce(spec, value)
        except ValidationError as e:
            problems += e.problems
    current = effective()
    problems += _cross_check({**current, **clean})
    if problems:
        activity_log.record("settings.update", outcome="invalid", principal=actor,
                            problems=len(problems))
        raise ValidationError(problems)
    changed = {k: v for k, v in clean.items() if v != current[k]}
    if not changed:
        return {}
    with database.connect() as conn:
        for k, v in changed.items():
            conn.execute(
                "INSERT INTO school_settings (key, value, value_type, updated_by) "
                "VALUES (?, ?, ?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value, "
                "value_type = excluded.value_type, updated_by = excluded.updated_by, "
                "updated_at = datetime('now')",
                (k, json.dumps(v), _BY_KEY[k].type, actor.username))
            _audit(conn, "set", actor, k, current[k], v)
    activity_log.record("settings.update", principal=actor, keys=sorted(changed))
    return changed


def set_setting(key: str, value: Any, *, actor: Principal) -> Any:
    """The old Edit one: save and return the clean value."""
    get_spec(key)
    set_many({key: value}, actor=actor)
    return get_setting(key)


def reset(key: str, *, actor: Principal) -> Any:
    """The old Reset one to default."""
    _require_editor(actor, "reset", key)
    spec = get_spec(key)
    old = get_setting(key)
    with database.connect() as conn:
        n = conn.execute("DELETE FROM school_settings WHERE key = ?", (key,)).rowcount
        if n:
            _audit(conn, "reset", actor, key, old, spec.default)
    activity_log.record("settings.reset", target=key, principal=actor)
    return spec.default


def reset_all(*, actor: Principal, category: str | None = None) -> int:
    """The old Reset all local (optionally one category). Returns how many
    saved values were removed."""
    _require_editor(actor, "reset_all", category)
    keys = [s.key for s in list_specs(category=category)]
    current = effective()
    with database.connect() as conn:
        stored = [r["key"] for r in conn.execute(
            f"SELECT key FROM school_settings WHERE key IN ({','.join('?' * len(keys))})",
            keys)]
        for k in stored:
            conn.execute("DELETE FROM school_settings WHERE key = ?", (k,))
            _audit(conn, "reset", actor, k, current[k], _BY_KEY[k].default)
    activity_log.record("settings.reset_all", target=category, principal=actor,
                        count=len(stored))
    return len(stored)


# ── Snapshot (the old Effective snapshot / Export…) ─────────────────

def snapshot(*, actor: Principal) -> dict[str, Any]:
    _require_editor(actor, "snapshot")
    out: dict[str, Any] = dict(effective())
    out.update({f"linked.{k}": v for k, v in linked_values().items()})
    out.update({f"auth.{k}": v for k, v in auth_policy().items()})
    return out


def export_json(path: str | Path, *, actor: Principal) -> int:
    snap = snapshot(actor=actor)
    Path(path).write_text(json.dumps(snap, indent=2, default=str) + "\n", encoding="utf-8")
    activity_log.record("settings.export", principal=actor, count=len(snap))
    return len(snap)


def import_json(path: str | Path, *, actor: Principal) -> dict[str, Any]:
    """Load a snapshot written by :func:`export_json` (school settings only;
    linked and sign-in keys are skipped). All or nothing."""
    _require_editor(actor, "import")
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValidationError([f"Can't read {path}: {e}"]) from None
    if not isinstance(data, dict):
        raise ValidationError(["The file must hold a JSON object of settings"])
    return set_many({k: v for k, v in data.items() if k in _BY_KEY}, actor=actor)


# ── Settings that live in other modules ──────────────────────────────

@dataclass(frozen=True)
class Linked:
    key: str
    label: str
    area: str
    hint: str
    read: Callable[[], Any]
    write: Callable[[Any, Principal], Any]


def _AT():
    from education_system.systems.secondary.modules.attendance.domain import attendance
    return attendance


def _LB():
    from education_system.systems.secondary.modules.library.domain import library
    return library


def _CV():
    from education_system.systems.secondary.modules.curriculum.domain import cover
    return cover


def _HW():
    from education_system.systems.secondary.modules.curriculum.domain import homework
    return homework


def _SJ():
    from education_system.systems.secondary.modules.curriculum.domain import subjects
    return subjects


def _TT():
    from education_system.systems.secondary.modules.curriculum.domain import timetable
    return timetable


def _times(key: str) -> Linked:
    return Linked(f"attendance.{key}", {"am_start": "Morning session starts",
                                        "am_close": "Morning register closes",
                                        "pm_start": "Afternoon session starts",
                                        "pm_close": "Afternoon register closes"}[key],
                  "Attendance", "HH:MM", lambda: _AT().session_times()[key],
                  lambda v, a: _AT().set_session_times({key: v}, actor=a)[key])


def _library(key: str, label: str, hint: str) -> Linked:
    return Linked(f"library.{key}", label, "Library", hint, lambda: _LB().settings()[key],
                  lambda v, a: _LB().set_settings({key: v}, actor=a)[key])


LINKED: tuple[Linked, ...] = (
    _times("am_start"), _times("am_close"), _times("pm_start"), _times("pm_close"),
    _library("loan_days", "Loan length (days)", "1-120"),
    _library("max_loans", "Books per pupil", "1-20"),
    _library("max_renewals", "Renewals", "0-10"),
    _library("hold_days", "Days a reservation is kept", "1-30"),
    _library("block_overdue", "Block borrowing when overdue", "1 = yes, 0 = no"),
    Linked("cover.weekly_limit", "Covers per member of staff a week", "Cover", "0-30",
           lambda: _CV().weekly_limit(), lambda v, a: _CV().set_weekly_limit(v, actor=a)),
    Linked("homework.daily_limit", "Homework pieces a day (limit)", "Homework", "1-10",
           lambda: _HW().daily_limit(), lambda v, a: _HW().set_daily_limit(v, actor=a)),
    Linked("subjects.periods_per_week", "Lessons in the timetable week", "Subjects", "10-60",
           lambda: _SJ().periods_per_week(),
           lambda v, a: _SJ().set_periods_per_week(v, actor=a)),
    Linked("timetable.cycle_weeks", "Timetable cycle (weeks)", "Timetable", "1 or 2",
           lambda: _TT().cycle_weeks(),
           lambda v, a: (_TT().set_cycle(v, _TT().cycle_restart(), actor=a),
                         _TT().cycle_weeks())[1]),
    Linked("timetable.cycle_restart", "Week A restarts each", "Timetable", "year or term",
           lambda: _TT().cycle_restart(),
           lambda v, a: (_TT().set_cycle(_TT().cycle_weeks(), str(v).strip().lower(),
                                         actor=a), _TT().cycle_restart())[1]),
)
_LINKED_BY_KEY = {x.key: x for x in LINKED}


def linked_values() -> dict[str, Any]:
    out = {}
    for x in LINKED:
        try:
            out[x.key] = x.read()
        except Exception:  # noqa: BLE001 - one module's fault doesn't hide the rest
            out[x.key] = None
    return out


def set_linked(key: str, value: Any, *, actor: Principal) -> Any:
    """Change a setting through its own module (its rules and audit apply)."""
    _require_editor(actor, "linked", key)
    x = _LINKED_BY_KEY.get(key)
    if x is None:
        raise NotFound(f"Unknown setting: {key}")
    old = x.read()
    new = x.write(value, actor)
    if str(new) != str(old):
        with database.connect() as conn:
            _audit(conn, "linked", actor, key, old, new)
    return new


# ── Sign-in policy and read-only views ───────────────────────────────

def auth_policy() -> dict[str, Any]:
    """The sign-in policy as it applies now (stored values, else the
    platform defaults)."""
    out = {s.key: s.default for s in AUTH_POLICY}
    try:
        from education_system.systems.secondary.infrastructure.authentication import accounts
        for s in AUTH_POLICY:
            try:
                raw = accounts.password_reset_policy() if s.key == "force_password_reset" \
                    else accounts.auth_setting(s.key, s.default)
                out[s.key] = coerce(s, raw)
            except ValidationError:
                pass
    except Exception:  # noqa: BLE001 - shown as the defaults when auth.db can't be read
        pass
    return out


def set_auth_policy(key: str, value: Any, *, actor: Principal) -> Any:
    """Change one sign-in setting (settings editors). Lockout, session and
    password age apply to every system; the forced-reset switch to this
    school. Recorded in the settings history as ``auth.<key>``."""
    _require_editor(actor, "auth_set", key)
    spec = _AUTH_BY_KEY.get(key)
    if spec is None:
        raise NotFound(f"Unknown sign-in setting: {key}")
    new = coerce(spec, value)
    old = auth_policy()[key]
    from education_system.systems.secondary.infrastructure.authentication import accounts
    if key == "force_password_reset":
        accounts.set_password_reset_policy(bool(new))
    else:
        accounts.set_auth_setting(key, new)
    if str(new) != str(old):
        with database.connect() as conn:
            _audit(conn, "auth", actor, f"auth.{key}", old, new)
    activity_log.record("settings.auth_set", target=key, principal=actor)
    return new


def reset_auth_policy(key: str, *, actor: Principal) -> Any:
    """Back to the platform default (the stored value is removed; for the
    forced-reset switch, this school's own switch is removed so the
    platform-wide one applies)."""
    _require_editor(actor, "auth_reset", key)
    spec = _AUTH_BY_KEY.get(key)
    if spec is None:
        raise NotFound(f"Unknown sign-in setting: {key}")
    old = auth_policy()[key]
    from education_system.systems.secondary import SYSTEM_KEY
    from education_system.systems.secondary.infrastructure.authentication import accounts
    accounts.clear_auth_setting(f"force_password_reset:{SYSTEM_KEY}"
                                if key == "force_password_reset" else key)
    new = auth_policy()[key]
    with database.connect() as conn:
        _audit(conn, "auth_reset", actor, f"auth.{key}", old, new)
    activity_log.record("settings.auth_reset", target=key, principal=actor)
    return new


def term_dates() -> dict[str, Any]:
    """The current school year and its terms, from Academic Year & Calendar."""
    try:
        from education_system.systems.secondary.modules.curriculum.domain import academic_year as AY
        y = AY.current_year()
        if y is None:
            return {"year": None, "terms": []}
        return {"year": {"name": y.name, "start": y.start_date, "end": y.end_date,
                         "status": y.status},
                "terms": [{"name": t.name, "start": t.start_date, "end": t.end_date}
                          for t in AY.list_terms(y.year_id)]}
    except Exception:  # noqa: BLE001
        return {"year": None, "terms": []}


def default_year() -> str:
    """The default academic year for forms: the setting, else this year."""
    from education_system.systems.secondary.core.academic_calendar.school_year import current_year
    return get_setting("ui.default_year") or current_year()


def summary_text(*, actor: Principal) -> str:
    """Everything as text (the old Show all, by category)."""
    rows = list_settings(actor=actor)
    lines = []
    for cat in categories():
        lines.append(f"── {cat} ──")
        for s in (r for r in rows if r.spec.category == cat):
            lines.append(f"  {s.spec.label:<44} {s.shown}"
                         + ("" if s.is_default else "   (changed)"))
    lines.append("── Other areas ──")
    linked = linked_values()
    for x in LINKED:
        lines.append(f"  {x.area + ': ' + x.label:<44} {linked.get(x.key)}")
    lines.append("── Sign-in policy ──")
    pol = auth_policy()
    for s in AUTH_POLICY:
        lines.append(f"  {s.label:<44} {format_value(s, pol[s.key])}")
    td = term_dates()
    lines.append("── Term dates (Academic Year & Calendar) ──")
    if td["year"]:
        lines.append(f"  {td['year']['name']}: {td['year']['start']} to {td['year']['end']}")
        lines += [f"    {t['name']}: {t['start']} to {t['end']}" for t in td["terms"]]
    else:
        lines.append("  No current school year set up.")
    return "\n".join(lines)
