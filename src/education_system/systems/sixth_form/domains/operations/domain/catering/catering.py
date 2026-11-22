"""Catering menus data layer for the Sixth Form System.

Three tables:

* ``catering_items``      — the dishes the kitchen makes: course,
  dietary flags (vegetarian / vegan / halal / gluten-free) and which of
  the 14 UK food-information allergens they contain (FSA list).
* ``catering_menus``      — one menu per date per service (Breakfast /
  Lunch).
* ``catering_menu_items`` — which dishes are on which menu.

No till or spend: this is the menu and allergen record only.

:func:`allergen_check` is the safety net: for a day's menu it reads the
students' recorded allergies (``med_allergies``, owned by the medical
records module — read through its public ``list_allergies``, never
written here) and lists every student whose allergy matches an allergen
in a dish being served, or whose allergen is named in a dish. Allergy
data is medical data, so the check needs the MEDICAL capability and is
written to the sensitive-access log.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from education_system.systems.sixth_form.infrastructure import database as _sql
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_STUDENTS_DB

SERVICES: tuple[str, ...] = ("Breakfast", "Lunch")
DEFAULT_SERVICE = "Lunch"

COURSES: tuple[str, ...] = (
    "Main", "Vegetarian Main", "Side", "Soup", "Salad", "Dessert",
    "Breakfast", "Snack", "Drink")
DEFAULT_COURSE = "Main"

# The 14 allergens UK food businesses must declare (Food Information
# Regulations / FSA guidance), in the FSA's order.
ALLERGENS: tuple[str, ...] = (
    "Celery",
    "Cereals containing gluten",
    "Crustaceans",
    "Eggs",
    "Fish",
    "Lupin",
    "Milk",
    "Molluscs",
    "Mustard",
    "Tree nuts",
    "Peanuts",
    "Sesame",
    "Soya",
    "Sulphur dioxide / sulphites",
)

# Words a recorded allergy might use for each allergen. Matched as word
# prefixes (``\bword``) so "eggs" matches "egg" but "peanut" does not
# match "nut" and "shellfish" does not match "fish".
_ALLERGEN_TERMS: dict[str, tuple[str, ...]] = {
    "Celery": ("celery", "celeriac"),
    "Cereals containing gluten": (
        "gluten", "wheat", "barley", "rye", "oat", "spelt", "kamut",
        "coeliac", "celiac"),
    "Crustaceans": ("crustacean", "shellfish", "prawn", "shrimp", "crab",
                    "lobster", "crayfish", "langoustine"),
    "Eggs": ("egg",),
    "Fish": ("fish", "cod", "salmon", "tuna", "haddock", "anchov"),
    "Lupin": ("lupin", "lupine"),
    "Milk": ("milk", "dairy", "lactose", "casein", "whey", "cheese",
             "butter", "cream", "yoghurt", "yogurt"),
    "Molluscs": ("mollusc", "mollusk", "shellfish", "mussel", "oyster",
                 "squid", "clam", "scallop", "octopus", "snail", "whelk"),
    "Mustard": ("mustard",),
    "Tree nuts": ("tree nut", "nut", "almond", "hazelnut", "walnut",
                  "cashew", "pecan", "pistachio", "brazil", "macadamia"),
    "Peanuts": ("peanut", "groundnut", "monkey nut", "arachis"),
    "Sesame": ("sesame", "tahini"),
    "Soya": ("soy", "soya", "soybean", "tofu", "edamame"),
    "Sulphur dioxide / sulphites": ("sulphite", "sulfite", "sulphur",
                                    "sulfur"),
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS catering_items (
    item_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    description  TEXT,
    course       TEXT NOT NULL DEFAULT 'Main',
    vegetarian   INTEGER NOT NULL DEFAULT 0,
    vegan        INTEGER NOT NULL DEFAULT 0,
    halal        INTEGER NOT NULL DEFAULT 0,
    gluten_free  INTEGER NOT NULL DEFAULT 0,
    allergens    TEXT,
    may_contain  TEXT,
    active       INTEGER NOT NULL DEFAULT 1,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS catering_menus (
    menu_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    menu_date    TEXT NOT NULL,
    service      TEXT NOT NULL DEFAULT 'Lunch',
    published    INTEGER NOT NULL DEFAULT 0,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(menu_date, service)
);

CREATE TABLE IF NOT EXISTS catering_menu_items (
    menu_id      INTEGER NOT NULL,
    item_id      INTEGER NOT NULL,
    sort_order   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (menu_id, item_id),
    FOREIGN KEY (menu_id) REFERENCES catering_menus(menu_id)
        ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES catering_items(item_id)
);

CREATE INDEX IF NOT EXISTS idx_cat_menu_date ON catering_menus(menu_date);
CREATE INDEX IF NOT EXISTS idx_cat_mi_item   ON catering_menu_items(item_id);
"""


class ValidationError(ValueError):
    pass


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class MenuItem:
    item_id: int
    name: str
    description: str | None
    course: str
    vegetarian: bool
    vegan: bool
    halal: bool
    gluten_free: bool
    allergens: list[str]
    may_contain: list[str]
    active: bool
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def dietary_label(self) -> str:
        flags = [lbl for on, lbl in ((self.vegan, "VG"),
                                     (self.vegetarian and not self.vegan,
                                      "V"),
                                     (self.halal, "H"),
                                     (self.gluten_free, "GF")) if on]
        return " ".join(flags)


@dataclass
class Menu:
    menu_id: int
    menu_date: str
    service: str
    published: bool
    notes: str | None
    created_at: str
    updated_at: str
    items: list[MenuItem] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.menu_date} {self.service}"

    @property
    def allergens(self) -> list[str]:
        found = {a for i in self.items for a in i.allergens + i.may_contain}
        return [a for a in ALLERGENS if a in found]


@dataclass
class AllergenMatch:
    """One student whose recorded allergy meets something on a menu."""
    student_id: str
    student_name: str
    allergy: str
    severity: str
    has_epipen: bool
    menu_label: str
    matched_allergens: list[str]
    items: list[str]
    may_contain_only: bool = False


@dataclass
class CateringSummary:
    items: int = 0
    active_items: int = 0
    by_course: dict[str, int] = field(default_factory=dict)
    vegetarian: int = 0
    vegan: int = 0
    halal: int = 0
    gluten_free: int = 0
    by_allergen: dict[str, int] = field(default_factory=dict)
    menus: int = 0
    menus_next_7_days: int = 0
    unpublished_upcoming: int = 0


# ── DB plumbing ─────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[_sql.Connection]:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Catering schema ready at %s", DB_PATH)
    _DB_READY = True


def _split(v: str | None) -> list[str]:
    found = {s.strip() for s in (v or "").split("|") if s.strip()}
    return [a for a in ALLERGENS if a in found]


def _item(r: _sql.Row) -> MenuItem:
    return MenuItem(
        item_id=r["item_id"], name=r["name"],
        description=r["description"], course=r["course"],
        vegetarian=bool(r["vegetarian"]), vegan=bool(r["vegan"]),
        halal=bool(r["halal"]), gluten_free=bool(r["gluten_free"]),
        allergens=_split(r["allergens"]),
        may_contain=_split(r["may_contain"]),
        active=bool(r["active"]), notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"])


def _menu(r: _sql.Row) -> Menu:
    return Menu(
        menu_id=r["menu_id"], menu_date=r["menu_date"],
        service=r["service"], published=bool(r["published"]),
        notes=r["notes"], created_at=r["created_at"],
        updated_at=r["updated_at"])


# ── Validation helpers ──────────────────────────────────────────────

def _text(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _date(v: Any, label: str, *, required: bool = False) -> str | None:
    s = _text(v)
    if not s:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _choice(v: Any, options: tuple[str, ...], label: str,
            default: str | None = None) -> str:
    s = _text(v) or default
    for o in options:
        if s and s.lower() == o.lower():
            return o
    raise ValidationError(f"{label} must be one of: {', '.join(options)}")


def validate_allergens(values: Any) -> list[str]:
    """Accept a list or a comma/pipe-separated string; match each entry
    to the FSA list case-insensitively (a unique prefix is enough, so
    "sulph" or "tree" work)."""
    if values in (None, ""):
        return []
    if isinstance(values, str):
        raw = [v for v in re.split(r"[|,;]", values)]
    else:
        raw = list(values)
    out: set[str] = set()
    for v in raw:
        s = str(v).strip().lower()
        if not s:
            continue
        exact = [a for a in ALLERGENS if a.lower() == s]
        hits = exact or [a for a in ALLERGENS if a.lower().startswith(s)]
        if len(hits) != 1:
            raise ValidationError(
                f"'{v}' is not one of the 14 allergens: "
                f"{', '.join(ALLERGENS)}")
        out.add(hits[0])
    return [a for a in ALLERGENS if a in out]


def _validate_item(p: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    name = _text(p.get("name"))
    if not name:
        raise ValidationError("Dish name is required")
    out["name"] = name
    out["description"] = _text(p.get("description"))
    out["course"] = _choice(p.get("course"), COURSES, "Course",
                            DEFAULT_COURSE)
    for k in ("vegetarian", "vegan", "halal", "gluten_free"):
        out[k] = 1 if p.get(k) else 0
    out["allergens"] = validate_allergens(p.get("allergens"))
    out["may_contain"] = [a for a in validate_allergens(
        p.get("may_contain")) if a not in out["allergens"]]
    # A vegan dish is vegetarian, and cannot contain milk/eggs/fish etc.
    if out["vegan"]:
        out["vegetarian"] = 1
        animal = {"Milk", "Eggs", "Fish", "Crustaceans", "Molluscs"} & \
            set(out["allergens"])
        if animal:
            raise ValidationError(
                f"A vegan dish cannot contain {', '.join(sorted(animal))}")
    if out["vegetarian"]:
        meat = {"Fish", "Crustaceans", "Molluscs"} & set(out["allergens"])
        if meat:
            raise ValidationError(
                f"A vegetarian dish cannot contain "
                f"{', '.join(sorted(meat))}")
    if out["gluten_free"] and "Cereals containing gluten" in \
            out["allergens"]:
        raise ValidationError(
            "A gluten-free dish cannot list cereals containing gluten")
    out["active"] = 0 if p.get("active") is False else 1
    out["notes"] = _text(p.get("notes"))
    return out


# ── Dishes ──────────────────────────────────────────────────────────

def create_item(payload: dict[str, Any]) -> MenuItem:
    init_db()
    p = _validate_item(payload)
    with _connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO catering_items (name, description, course, "
                "vegetarian, vegan, halal, gluten_free, allergens, "
                "may_contain, active, notes) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (p["name"], p["description"], p["course"], p["vegetarian"],
                 p["vegan"], p["halal"], p["gluten_free"],
                 "|".join(p["allergens"]), "|".join(p["may_contain"]),
                 p["active"], p["notes"]))
        except _sql.IntegrityError:
            raise ValidationError(
                f"A dish called '{p['name']}' already exists") from None
        new_id = cur.lastrowid
    out = get_item(new_id)
    assert out is not None
    return out


def update_item(item_id: int, payload: dict[str, Any]) -> MenuItem:
    existing = get_item(item_id)
    if existing is None:
        raise ValidationError(f"No dish #{item_id}")
    merged = {
        "name": existing.name, "description": existing.description,
        "course": existing.course, "vegetarian": existing.vegetarian,
        "vegan": existing.vegan, "halal": existing.halal,
        "gluten_free": existing.gluten_free,
        "allergens": existing.allergens,
        "may_contain": existing.may_contain,
        "active": existing.active, "notes": existing.notes,
    }
    merged.update(payload)
    p = _validate_item(merged)
    with _connect() as conn:
        try:
            conn.execute(
                "UPDATE catering_items SET name=?, description=?, course=?, "
                "vegetarian=?, vegan=?, halal=?, gluten_free=?, "
                "allergens=?, may_contain=?, active=?, notes=?, "
                "updated_at=datetime('now') WHERE item_id=?",
                (p["name"], p["description"], p["course"], p["vegetarian"],
                 p["vegan"], p["halal"], p["gluten_free"],
                 "|".join(p["allergens"]), "|".join(p["may_contain"]),
                 p["active"], p["notes"], item_id))
        except _sql.IntegrityError:
            raise ValidationError(
                f"A dish called '{p['name']}' already exists") from None
    out = get_item(item_id)
    assert out is not None
    return out


def get_item(item_id: int) -> MenuItem | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM catering_items WHERE item_id=?",
                         (item_id,)).fetchone()
    return _item(r) if r else None


def list_items(*, course: str | None = None, active_only: bool = False,
               name_like: str | None = None,
               free_from: list[str] | None = None,
               vegetarian: bool = False, vegan: bool = False,
               halal: bool = False, gluten_free: bool = False
               ) -> list[MenuItem]:
    """Dishes, optionally only those free from the given allergens
    (neither contains nor may contain)."""
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if course:
        clauses.append("course = ?")
        args.append(_choice(course, COURSES, "Course"))
    if active_only:
        clauses.append("active = 1")
    if name_like:
        clauses.append("name LIKE ?")
        args.append(f"%{name_like.strip()}%")
    for flag, col in ((vegetarian, "vegetarian"), (vegan, "vegan"),
                      (halal, "halal"), (gluten_free, "gluten_free")):
        if flag:
            clauses.append(f"{col} = 1")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = [_item(r) for r in conn.execute(
            f"SELECT * FROM catering_items{where} "
            "ORDER BY course, name COLLATE NOCASE", args).fetchall()]
    avoid = set(validate_allergens(free_from)) if free_from else set()
    if avoid:
        rows = [i for i in rows
                if not avoid & set(i.allergens + i.may_contain)]
    return rows


def delete_item(item_id: int) -> bool:
    """Remove a dish never put on a menu; otherwise mark it inactive."""
    init_db()
    with _connect() as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM catering_menu_items WHERE item_id=?",
            (item_id,)).fetchone()[0]
        if n:
            raise ValidationError(
                f"This dish is on {n} menu(s) — mark it inactive instead")
        cur = conn.execute("DELETE FROM catering_items WHERE item_id=?",
                           (item_id,))
    return bool(cur.rowcount)


# ── Menus ───────────────────────────────────────────────────────────

def create_menu(menu_date: str, service: str = DEFAULT_SERVICE, *,
                item_ids: list[int] | None = None,
                notes: str | None = None) -> Menu:
    init_db()
    d = _date(menu_date, "Menu date", required=True)
    svc = _choice(service, SERVICES, "Service", DEFAULT_SERVICE)
    with _connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO catering_menus (menu_date, service, notes) "
                "VALUES (?, ?, ?)", (d, svc, _text(notes)))
        except _sql.IntegrityError:
            raise ValidationError(
                f"There is already a {svc} menu for {d}") from None
        menu_id = cur.lastrowid
    for iid in item_ids or []:
        add_item_to_menu(menu_id, iid)
    out = get_menu(menu_id)
    assert out is not None
    logger.info("Created %s menu for %s", svc, d)
    return out


def update_menu(menu_id: int, *, notes: str | None = None,
                published: bool | None = None) -> Menu:
    m = _require_menu(menu_id)
    with _connect() as conn:
        conn.execute(
            "UPDATE catering_menus SET notes=?, published=?, "
            "updated_at=datetime('now') WHERE menu_id=?",
            (_text(notes) if notes is not None else m.notes,
             (1 if published else 0) if published is not None
             else int(m.published), menu_id))
    return _require_menu(menu_id)


def publish_menu(menu_id: int, published: bool = True) -> Menu:
    m = _require_menu(menu_id)
    if published and not m.items:
        raise ValidationError("Add at least one dish before publishing")
    return update_menu(menu_id, published=published)


def add_item_to_menu(menu_id: int, item_id: int) -> Menu:
    _require_menu(menu_id)
    item = get_item(int(item_id))
    if item is None:
        raise ValidationError(f"No dish #{item_id}")
    if not item.active:
        raise ValidationError(f"'{item.name}' is inactive")
    with _connect() as conn:
        nxt = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM "
            "catering_menu_items WHERE menu_id=?", (menu_id,)).fetchone()[0]
        try:
            conn.execute(
                "INSERT INTO catering_menu_items (menu_id, item_id, "
                "sort_order) VALUES (?, ?, ?)", (menu_id, item.item_id, nxt))
        except _sql.IntegrityError:
            raise ValidationError(
                f"'{item.name}' is already on this menu") from None
    return _require_menu(menu_id)


def remove_item_from_menu(menu_id: int, item_id: int) -> Menu:
    _require_menu(menu_id)
    with _connect() as conn:
        conn.execute("DELETE FROM catering_menu_items WHERE menu_id=? "
                     "AND item_id=?", (menu_id, int(item_id)))
    return _require_menu(menu_id)


def copy_menu(menu_id: int, to_date: str,
              service: str | None = None) -> Menu:
    """Repeat a menu on another day (menus run on a cycle)."""
    src = _require_menu(menu_id)
    return create_menu(to_date, service or src.service,
                       item_ids=[i.item_id for i in src.items
                                 if i.active],
                       notes=src.notes)


def _require_menu(menu_id: int) -> Menu:
    m = get_menu(menu_id)
    if m is None:
        raise ValidationError(f"No menu #{menu_id}")
    return m


def _load_items(conn: _sql.Connection, menu: Menu) -> Menu:
    menu.items = [_item(r) for r in conn.execute(
        "SELECT i.* FROM catering_menu_items mi "
        "JOIN catering_items i ON i.item_id = mi.item_id "
        "WHERE mi.menu_id = ? ORDER BY mi.sort_order, i.name",
        (menu.menu_id,)).fetchall()]
    return menu


def get_menu(menu_id: int) -> Menu | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM catering_menus WHERE menu_id=?",
                         (menu_id,)).fetchone()
        return _load_items(conn, _menu(r)) if r else None


def list_menus(*, date_from: str | None = None, date_to: str | None = None,
               service: str | None = None,
               published_only: bool = False) -> list[Menu]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if date_from:
        clauses.append("menu_date >= ?")
        args.append(_date(date_from, "From"))
    if date_to:
        clauses.append("menu_date <= ?")
        args.append(_date(date_to, "To"))
    if service:
        clauses.append("service = ?")
        args.append(_choice(service, SERVICES, "Service"))
    if published_only:
        clauses.append("published = 1")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        menus = [_menu(r) for r in conn.execute(
            f"SELECT * FROM catering_menus{where} "
            "ORDER BY menu_date, CASE service WHEN 'Breakfast' THEN 0 "
            "ELSE 1 END", args).fetchall()]
        return [_load_items(conn, m) for m in menus]


def menus_for_date(menu_date: str) -> list[Menu]:
    d = _date(menu_date, "Date", required=True)
    return list_menus(date_from=d, date_to=d)


def delete_menu(menu_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM catering_menus WHERE menu_id=?",
                           (menu_id,))
    return bool(cur.rowcount)


# ── Allergen check ──────────────────────────────────────────────────

def allergens_for_text(text: str) -> list[str]:
    """Which of the 14 allergens a free-text allergy names."""
    s = (text or "").lower()
    hits = [a for a, terms in _ALLERGEN_TERMS.items()
            if any(re.search(rf"\b{re.escape(t)}", s) for t in terms)]
    return [a for a in ALLERGENS if a in hits]


def _named_in(allergy: str, item: MenuItem) -> bool:
    """The allergy's own word appears in the dish name/description —
    catches allergens outside the 14 (kiwi, strawberry, ...)."""
    word = (allergy or "").strip().lower()
    if len(word) < 3:
        return False
    hay = f"{item.name} {item.description or ''}".lower()
    return re.search(rf"\b{re.escape(word)}", hay) is not None


def allergen_check(menu_date: str, service: str | None = None
                   ) -> list[AllergenMatch]:
    """Students whose recorded allergies meet the day's menu(s).

    Needs the MEDICAL capability. Every student listed is written to the
    sensitive-access log against this check; a refused attempt is logged
    too.
    """
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    p = access.current()
    d = _date(menu_date, "Date", required=True)
    ref = f"catering:{d}:{service or 'all'}"
    if not p.can(access.MEDICAL):
        access.log_sensitive_access(p, "medical", "catering allergen check",
                                    record_ref=ref, allowed=False)
        p.require(access.MEDICAL, "student allergy information")

    menus = [m for m in menus_for_date(d)
             if service is None or m.service == service]
    if not menus:
        return []

    from education_system.systems.sixth_form.domain.pastoral.health.medical_records import (
        medical_records as _med,
    )
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    allergies = _med.list_allergies()
    names: dict[str, str] = {}
    out: list[AllergenMatch] = []
    for alg in allergies:
        wanted = set(allergens_for_text(alg.allergen))
        for menu in menus:
            matched: set[str] = set()
            items: list[str] = []
            only_may = True
            for item in menu.items:
                contains = wanted & set(item.allergens)
                may = wanted & set(item.may_contain)
                named = _named_in(alg.allergen, item)
                if contains or may or named:
                    matched |= contains | may
                    items.append(item.name)
                    if contains or named:
                        only_may = False
            if not items:
                continue
            if alg.student_id not in names:
                s = _students.get_student(alg.student_id)
                names[alg.student_id] = s.full_name if s else alg.student_id
            out.append(AllergenMatch(
                student_id=alg.student_id,
                student_name=names[alg.student_id],
                allergy=alg.allergen, severity=alg.severity,
                has_epipen=bool(alg.has_epipen),
                menu_label=menu.label,
                matched_allergens=[a for a in ALLERGENS if a in matched]
                or [alg.allergen],
                items=items, may_contain_only=only_may))
    for sid in sorted({m.student_id for m in out}):
        access.log_sensitive_access(p, "medical", "catering allergen check",
                                    student_id=sid, record_ref=ref)
    if not out:
        access.log_sensitive_access(p, "medical", "catering allergen check",
                                    record_ref=ref)
    logger.info("Allergen check %s: %d match(es)", ref, len(out))
    return out


# ── Summary ─────────────────────────────────────────────────────────

def summary() -> CateringSummary:
    init_db()
    out = CateringSummary(by_course={c: 0 for c in COURSES},
                          by_allergen={a: 0 for a in ALLERGENS})
    for i in list_items():
        out.items += 1
        if not i.active:
            continue
        out.active_items += 1
        out.by_course[i.course] = out.by_course.get(i.course, 0) + 1
        out.vegetarian += int(i.vegetarian)
        out.vegan += int(i.vegan)
        out.halal += int(i.halal)
        out.gluten_free += int(i.gluten_free)
        for a in i.allergens:
            out.by_allergen[a] += 1
    today = _dt.date.today()
    horizon = (today + _dt.timedelta(days=7)).isoformat()
    for m in list_menus():
        out.menus += 1
        if today.isoformat() <= m.menu_date <= horizon:
            out.menus_next_7_days += 1
            if not m.published:
                out.unpublished_upcoming += 1
    return out
