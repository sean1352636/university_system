"""Settings for the Sixth Form System.

Two scopes:

* **Local** — sixth-form-only preferences stored in our own
  ``settings_kv`` table. Things like default report windows,
  attendance thresholds, UI flags.
* **Global** — auth-wide policy settings (lockout, password
  expiry, force-reset). Read/written via the shared
  ``UserAuth.get_setting`` / ``set_setting`` helpers — admin-only
  in practice. We don't store these locally; we just expose them.

Every setting is declared in ``REGISTRY`` with a type, a default,
a category, a description, and a ``scope`` of ``"local"`` /
``"global"``. The CLI and GUI iterate the registry rather than
hard-coding each field.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.sixthform_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SETTINGS_DB


# ── Types & registry ──────────────────────────────────────────────

class SettingError(ValueError):
    pass


@dataclass
class SettingSpec:
    key: str
    label: str
    description: str
    type: str          # "bool", "int", "float", "str", "choice"
    default: Any
    scope: str         # "local" or "global"
    category: str
    choices: tuple[str, ...] | None = None
    min: float | None = None
    max: float | None = None


REGISTRY: tuple[SettingSpec, ...] = (
    # ── Attendance ──
    SettingSpec(
        key="attendance.default_window_days",
        label="Default report window (days)",
        description="Default look-back window for attendance reports "
                     "when no explicit date range is given.",
        type="int", default=28, scope="local",
        category="Attendance", min=1, max=365),
    SettingSpec(
        key="attendance.threshold_pct",
        label="Attendance threshold (%)",
        description="Below this percentage, students show up on the "
                     "attendance watchlist / cohort below-threshold count.",
        type="float", default=90.0, scope="local",
        category="Attendance", min=0, max=100),
    SettingSpec(
        key="attendance.max_lates",
        label="Max lates per window",
        description="More than this many lates flags the student.",
        type="int", default=5, scope="local",
        category="Attendance", min=0, max=1000),
    SettingSpec(
        key="attendance.max_absences",
        label="Max absences per window",
        description="More than this many absences flags the student.",
        type="int", default=3, scope="local",
        category="Attendance", min=0, max=1000),

    # ── Grades / progress ──
    SettingSpec(
        key="grades.mock_below_pred_gap",
        label="Mock-below-prediction alert gap",
        description="Grade-points gap between predicted and latest "
                     "mock that triggers a grades alert.",
        type="int", default=2, scope="local",
        category="Grades", min=1, max=6),
    SettingSpec(
        key="grades.min_target_points",
        label="Min target points",
        description="Predicted grade points below this trigger an "
                     "alert (A*=6, A=5, B=4, C=3, D=2, E=1). "
                     "Set to 0 to disable.",
        type="int", default=0, scope="local",
        category="Grades", min=0, max=6),
    SettingSpec(
        key="progress.default_period",
        label="Default progress period",
        description="Selected by default in new-review dialogs.",
        type="choice", default="Mid-Cycle Check", scope="local",
        category="Progress",
        choices=("Autumn Half-Term 1", "Autumn Half-Term 2",
                 "Spring Half-Term 1", "Spring Half-Term 2",
                 "Summer Half-Term 1", "Summer Half-Term 2",
                 "End of Year", "Mid-Cycle Check", "Ad Hoc")),

    # ── Fees / finance ──
    SettingSpec(
        key="fees.default_due_days",
        label="Default fee due window (days)",
        description="How many days after the issue date a new fee "
                     "becomes due by default.",
        type="int", default=30, scope="local",
        category="Finance", min=0, max=365),
    SettingSpec(
        key="fees.overdue_warning_days",
        label="Overdue warning window (days)",
        description="Fees overdue by more than this number of days "
                     "are flagged in the summary.",
        type="int", default=0, scope="local",
        category="Finance", min=0, max=365),
    SettingSpec(
        key="receipts.auto_issue_on_import",
        label="Auto-issue receipts when importing payments",
        description="If on, fee/trip payment imports are stamped "
                     "Issued immediately rather than Draft.",
        type="bool", default=True, scope="local",
        category="Finance"),

    # ── UI ──
    SettingSpec(
        key="ui.confirm_destructive",
        label="Confirm destructive actions",
        description="Ask for confirmation before delete/void/archive.",
        type="bool", default=True, scope="local",
        category="UI"),
    SettingSpec(
        key="ui.show_advanced",
        label="Show advanced fields",
        description="If off, some less-used form fields are hidden "
                     "to keep dialogs compact.",
        type="bool", default=False, scope="local",
        category="UI"),
    SettingSpec(
        key="ui.default_year",
        label="Default academic year",
        description="Pre-filled into 'academic year' fields.",
        type="str", default="2025-26", scope="local",
        category="UI"),

    # ── Reporting ──
    SettingSpec(
        key="reports.export_dir",
        label="Default export directory",
        description="Where 'Custom Export' opens its file picker "
                     "by default.",
        type="str", default="", scope="local",
        category="Reporting"),
    SettingSpec(
        key="reports.default_format",
        label="Default export format",
        description="Format pre-selected on the Custom Export tab.",
        type="choice", default="csv", scope="local",
        category="Reporting",
        choices=("csv", "tsv", "json", "jsonl", "markdown")),

    # ── Global (auth) ──
    SettingSpec(
        key="force_password_reset",
        label="Force password reset for legacy users",
        description="When on, users on the legacy password format "
                     "are required to reset on next login.",
        type="bool", default=True, scope="global",
        category="Auth policy"),
    SettingSpec(
        key="max_login_attempts",
        label="Max failed login attempts",
        description="After this many failed attempts a user is "
                     "temporarily locked out.",
        type="int", default=5, scope="global",
        category="Auth policy", min=1, max=100),
    SettingSpec(
        key="lockout_minutes",
        label="Lockout duration (minutes)",
        description="How long a user is locked out after exceeding "
                     "the max login attempts.",
        type="int", default=15, scope="global",
        category="Auth policy", min=1, max=1440),
    SettingSpec(
        key="password_max_age_days",
        label="Password max age (days)",
        description="0 disables age-based expiry.",
        type="int", default=0, scope="global",
        category="Auth policy", min=0, max=3650),
    SettingSpec(
        key="session_timeout_minutes",
        label="Session timeout (minutes)",
        description="Inactive sessions are invalidated after this.",
        type="int", default=120, scope="global",
        category="Auth policy", min=1, max=1440),
)

_BY_KEY: dict[str, SettingSpec] = {s.key: s for s in REGISTRY}


# ── Schema ────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings_kv (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Settings schema ready at %s", DB_PATH)


# ── Coercion / validation ────────────────────────────────────────

def _coerce(spec: SettingSpec, value: Any) -> Any:
    if spec.type == "bool":
        if isinstance(value, bool):
            return value
        s = str(value).strip().lower()
        if s in ("1", "true", "yes", "on", "y"):
            return True
        if s in ("0", "false", "no", "off", "n"):
            return False
        raise SettingError(
            f"{spec.label}: expected true/false")
    if spec.type == "int":
        try:
            v = int(value)
        except (TypeError, ValueError):
            raise SettingError(
                f"{spec.label}: must be a whole number") from None
        if spec.min is not None and v < spec.min:
            raise SettingError(
                f"{spec.label}: must be ≥ {int(spec.min)}")
        if spec.max is not None and v > spec.max:
            raise SettingError(
                f"{spec.label}: must be ≤ {int(spec.max)}")
        return v
    if spec.type == "float":
        try:
            v = float(value)
        except (TypeError, ValueError):
            raise SettingError(
                f"{spec.label}: must be a number") from None
        if spec.min is not None and v < spec.min:
            raise SettingError(
                f"{spec.label}: must be ≥ {spec.min}")
        if spec.max is not None and v > spec.max:
            raise SettingError(
                f"{spec.label}: must be ≤ {spec.max}")
        return round(v, 4)
    if spec.type == "choice":
        s = str(value).strip()
        if spec.choices and s not in spec.choices:
            raise SettingError(
                f"{spec.label}: must be one of "
                f"{', '.join(spec.choices)}")
        return s
    # str
    return str(value)


def _to_storage(spec: SettingSpec, value: Any) -> str:
    return json.dumps(value)


def _from_storage(spec: SettingSpec, raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


# ── Local + global access ────────────────────────────────────────

def list_settings(*, scope: str | None = None,
                     category: str | None = None
                     ) -> list[SettingSpec]:
    rows = list(REGISTRY)
    if scope:
        rows = [r for r in rows if r.scope == scope]
    if category:
        rows = [r for r in rows if r.category == category]
    return rows


def get_spec(key: str) -> SettingSpec:
    s = _BY_KEY.get(key)
    if s is None:
        raise SettingError(f"Unknown setting key: {key}")
    return s


def categories() -> list[str]:
    seen: list[str] = []
    for s in REGISTRY:
        if s.category not in seen:
            seen.append(s.category)
    return seen


def get(key: str, *, auth: Any = None) -> Any:
    """Get a setting's current effective value (or default)."""
    spec = get_spec(key)
    if spec.scope == "local":
        return _get_local(spec)
    if spec.scope == "global":
        if auth is None:
            raise SettingError(
                "Reading a global setting requires an auth session.")
        try:
            v = auth.get_setting(spec.key, spec.default)
        except Exception:
            v = spec.default
        try:
            return _coerce(spec, v)
        except SettingError:
            return spec.default
    raise SettingError(f"Bad scope: {spec.scope}")


def _get_local(spec: SettingSpec) -> Any:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT value FROM settings_kv WHERE key = ?",
            (spec.key,)).fetchone()
    if r is None:
        return spec.default
    try:
        return _coerce(spec, _from_storage(spec, r["value"]))
    except SettingError:
        return spec.default


def set(key: str, value: Any, *, auth: Any = None) -> Any:
    """Set a setting and return the coerced stored value."""
    spec = get_spec(key)
    coerced = _coerce(spec, value)
    if spec.scope == "local":
        return _set_local(spec, coerced)
    if spec.scope == "global":
        if auth is None:
            raise SettingError(
                "Changing a global setting requires an auth "
                "session — sign in as an admin user.")
        try:
            auth.set_setting(spec.key, coerced)
        except Exception as e:
            raise SettingError(str(e)) from e
        logger.info("Set global setting %s = %r", spec.key, coerced)
        return coerced
    raise SettingError(f"Bad scope: {spec.scope}")


def _set_local(spec: SettingSpec, coerced: Any) -> Any:
    init_db()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO settings_kv (key, value, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET
                   value=excluded.value,
                   updated_at=datetime('now')""",
            (spec.key, _to_storage(spec, coerced)))
        conn.commit()
    logger.info("Set local setting %s = %r", spec.key, coerced)
    return coerced


def reset_to_default(key: str, *, auth: Any = None) -> Any:
    spec = get_spec(key)
    if spec.scope == "local":
        init_db()
        with _connect() as conn:
            conn.execute(
                "DELETE FROM settings_kv WHERE key = ?", (spec.key,))
            conn.commit()
        logger.info("Reset local setting %s to default %r",
                    spec.key, spec.default)
        return spec.default
    return set(key, spec.default, auth=auth)


def export_all(*, auth: Any = None) -> dict[str, Any]:
    """Return a snapshot of every setting's current value (locals
    always, globals only if ``auth`` is provided)."""
    out: dict[str, Any] = {}
    for s in REGISTRY:
        if s.scope == "global" and auth is None:
            continue
        try:
            out[s.key] = get(s.key, auth=auth)
        except SettingError:
            out[s.key] = s.default
    return out


def reset_all_local() -> int:
    """Wipe the local settings table. Returns rows deleted."""
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM settings_kv")
        conn.commit()
    logger.info("Reset all local settings (%d row(s))", cur.rowcount)
    return cur.rowcount
