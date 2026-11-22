"""Department budget lines and budget-vs-spend for the Sixth Form System.

:mod:`departments` keeps one budget total per department. This module
adds the detail finance actually manages by:

* ``department_budget_lines`` — budget lines per department per
  academic year (category, description, amount).

and works out spend against them from the records that already hold it
— nothing is keyed in twice:

* **expense claims** (Approved / Paid) whose ``department`` names the
  department (by name or code), dated in the year; each claim line is
  filed under the budget category its expense category maps to;
* **trips** owned by the department (``trips.department_id``, else the
  lead member of staff's department) starting in the year — their
  running cost (``trips.running_cost``) is spend under "Trips & visits";
* **receipts** (Issued) — money taken in that offsets spend: receipt
  lines for the department's trips, and any receipt line attributed to
  the department (``receipt_lines.department_id``).

:func:`budget_report` gives lines vs spend with overspend warnings;
:func:`all_departments` the college-wide picture.
"""

from __future__ import annotations

import datetime as _dt
import logging
from education_system.systems.sixth_form.infrastructure import database as db
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.domains.finance.domain import (
    finance_calendar as fc,
)

logger = logging.getLogger(__name__)

# ``None`` follows the fees module's database (sixthform.db in
# production, like departments / expense claims / trips / receipts), so
# a test that redirects finance redirects budgets too.
DB_PATH: Any = None

CURRENCY_SYMBOL: str = "£"

BUDGET_CATEGORIES: tuple[str, ...] = (
    "Teaching resources", "Books & materials", "Equipment",
    "ICT & software", "Trips & visits", "Staff travel & subsistence",
    "CPD & training", "Exam & entry costs", "Consumables",
    "Hospitality & events", "Other",
)

# Expense-claim category -> budget category.
CLAIM_CATEGORY_MAP: dict[str, str] = {
    "Travel": "Staff travel & subsistence",
    "Mileage": "Staff travel & subsistence",
    "Subsistence": "Staff travel & subsistence",
    "Accommodation": "Staff travel & subsistence",
    "Conference / CPD": "CPD & training",
    "Books / Materials": "Books & materials",
    "Stationery": "Books & materials",
    "Equipment": "Equipment",
    "PPE": "Equipment",
    "Uniform": "Equipment",
    "Software": "ICT & software",
    "Postage": "Consumables",
    "Hospitality": "Hospitality & events",
    "Trip / Visit": "Trips & visits",
    "Other": "Other",
}

#: Utilisation at which a line is flagged as nearly spent.
WARN_AT_PCT: float = 90.0

_SCHEMA = """
CREATE TABLE IF NOT EXISTS department_budget_lines (
    line_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id  INTEGER NOT NULL,
    academic_year  TEXT NOT NULL,
    category       TEXT NOT NULL,
    description    TEXT,
    amount         REAL NOT NULL,
    created_by     TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_dbl_dept_year
    ON department_budget_lines(department_id, academic_year);
"""


class ValidationError(ValueError):
    pass


@dataclass
class BudgetLine:
    line_id: int
    department_id: int
    academic_year: str
    category: str
    description: str | None
    amount: float
    created_by: str | None


@dataclass
class SpendItem:
    source: str          # "Expense claim" / "Trip" / "Receipt"
    ref: str
    date: str | None
    category: str
    description: str
    amount: float        # spend positive; income negative


@dataclass
class CategoryLine:
    category: str
    budget: float
    spend: float
    income: float

    @property
    def net(self) -> float:
        return round(self.spend - self.income, 2)

    @property
    def remaining(self) -> float:
        return round(self.budget - self.net, 2)

    @property
    def utilisation_pct(self) -> float | None:
        return round(100.0 * self.net / self.budget, 1) if self.budget else None

    @property
    def over(self) -> bool:
        return self.net > self.budget + 0.001


@dataclass
class BudgetReport:
    department_id: int
    department_name: str
    academic_year: str
    lines: list[CategoryLine] = field(default_factory=list)
    items: list[SpendItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    uncosted_trips: list[str] = field(default_factory=list)

    @property
    def total_budget(self) -> float:
        return round(sum(l.budget for l in self.lines), 2)

    @property
    def total_spend(self) -> float:
        return round(sum(l.spend for l in self.lines), 2)

    @property
    def total_income(self) -> float:
        return round(sum(l.income for l in self.lines), 2)

    @property
    def net_spend(self) -> float:
        return round(self.total_spend - self.total_income, 2)

    @property
    def remaining(self) -> float:
        return round(self.total_budget - self.net_spend, 2)

    @property
    def utilisation_pct(self) -> float | None:
        return (round(100.0 * self.net_spend / self.total_budget, 1)
                if self.total_budget else None)

    @property
    def overspent(self) -> bool:
        return self.net_spend > self.total_budget + 0.001


# ── DB plumbing ────────────────────────────────────────────────────

def _path() -> str:
    if DB_PATH:
        return str(DB_PATH)
    from education_system.systems.sixth_form.domains.finance.domain.fees import fees
    return str(fees.DB_PATH)


def _connect() -> db.Connection:
    paths.ensure_sixth_form_directories()
    conn = db.connect(_path())
    conn.row_factory = db.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _has_table(conn: db.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                        "AND name=?", (name,)).fetchone() is not None


def _columns(conn: db.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


_READY: set[str] = set()


def init_db() -> None:
    """Create the budget-line table (and the departments table it hangs
    off, when this is the live departments database)."""
    key = _path()
    if key in _READY:
        return
    if key == str(paths.SIXTH_FORM_DEPARTMENTS_DB):
        from education_system.systems.sixth_form.domain.staff.departments import (
            departments,
        )
        departments.init_db()
    with _connect() as conn:
        if not _has_table(conn, "departments"):
            raise ValidationError(
                "No departments table in this database — create a "
                "department first")
        conn.executescript(_SCHEMA)
        # Receipt lines can be attributed to a department (income that
        # offsets its spend). Added here because budgets are its reader.
        if _has_table(conn, "receipt_lines") and \
                "department_id" not in _columns(conn, "receipt_lines"):
            conn.execute(
                "ALTER TABLE receipt_lines ADD COLUMN department_id INTEGER")
        conn.commit()
    _READY.add(key)


def _row_line(r: db.Row) -> BudgetLine:
    return BudgetLine(line_id=r["line_id"], department_id=r["department_id"],
                      academic_year=r["academic_year"],
                      category=r["category"], description=r["description"],
                      amount=r["amount"], created_by=r["created_by"])


def _year(v: Any) -> str:
    try:
        return fc.normalise_year(v)
    except ValueError as exc:
        raise ValidationError(str(exc)) from None


def _department(conn: db.Connection, department_id: int) -> db.Row:
    r = conn.execute("SELECT * FROM departments WHERE department_id = ?",
                     (department_id,)).fetchone()
    if r is None:
        raise ValidationError(f"No department with id {department_id}")
    return r


# ── Budget lines ──────────────────────────────────────────────────

def add_line(department_id: int, *, academic_year: str | None,
             category: str, amount: float, description: str | None = None,
             created_by: str | None = None) -> BudgetLine:
    init_db()
    year = _year(academic_year)
    if category not in BUDGET_CATEGORIES:
        raise ValidationError(
            f"Category must be one of: {', '.join(BUDGET_CATEGORIES)}")
    try:
        d = Decimal(str(amount))
    except (InvalidOperation, TypeError):
        raise ValidationError("Amount must be a number") from None
    if d < 0:
        raise ValidationError("Amount cannot be negative")
    with _connect() as conn:
        _department(conn, int(department_id))
        cur = conn.execute(
            """INSERT INTO department_budget_lines
                   (department_id, academic_year, category, description,
                    amount, created_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (int(department_id), year, category,
             (description or "").strip() or None,
             float(d.quantize(Decimal("0.01"))),
             (created_by or "").strip() or None))
        conn.commit()
        r = conn.execute("SELECT * FROM department_budget_lines "
                         "WHERE line_id = ?", (cur.lastrowid,)).fetchone()
    return _row_line(r)


def update_line(line_id: int, *, amount: float | None = None,
                category: str | None = None,
                description: str | None = None) -> BudgetLine:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM department_budget_lines "
                         "WHERE line_id = ?", (line_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No budget line #{line_id}")
        cat = category or r["category"]
        if cat not in BUDGET_CATEGORIES:
            raise ValidationError("Unknown budget category")
        amt = r["amount"] if amount in (None, "") else float(amount)
        if amt < 0:
            raise ValidationError("Amount cannot be negative")
        conn.execute(
            """UPDATE department_budget_lines SET category=?, amount=?,
                   description=?, updated_at=datetime('now')
               WHERE line_id=?""",
            (cat, round(amt, 2),
             r["description"] if description is None
             else (description.strip() or None), line_id))
        conn.commit()
        r = conn.execute("SELECT * FROM department_budget_lines "
                         "WHERE line_id = ?", (line_id,)).fetchone()
    return _row_line(r)


def delete_line(line_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM department_budget_lines "
                           "WHERE line_id = ?", (line_id,))
        conn.commit()
    return bool(cur.rowcount)


def list_lines(*, department_id: int | None = None,
               academic_year: str | None = None) -> list[BudgetLine]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if department_id is not None:
        clauses.append("department_id = ?")
        args.append(int(department_id))
    if academic_year:
        clauses.append("academic_year = ?")
        args.append(_year(academic_year))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM department_budget_lines {where} "
            "ORDER BY academic_year DESC, department_id, category, line_id",
            args).fetchall()
    return [_row_line(r) for r in rows]


def copy_year(department_id: int, *, from_year: str, to_year: str,
              uplift_pct: float = 0.0, created_by: str | None = None
              ) -> list[BudgetLine]:
    """Roll a department's lines into the next year (optional uplift)."""
    src = list_lines(department_id=department_id, academic_year=from_year)
    if not src:
        raise ValidationError(f"No budget lines in {_year(from_year)}")
    if list_lines(department_id=department_id, academic_year=to_year):
        raise ValidationError(f"{_year(to_year)} already has budget lines")
    factor = 1.0 + float(uplift_pct) / 100.0
    return [add_line(department_id, academic_year=to_year,
                     category=l.category, description=l.description,
                     amount=round(l.amount * factor, 2),
                     created_by=created_by) for l in src]


# ── Spend ─────────────────────────────────────────────────────────

def _spend_items(conn: db.Connection, dept: db.Row,
                 year: str) -> tuple[list[SpendItem], list[str]]:
    y_from, y_to = fc.year_bounds(year)
    names = {str(dept["name"]).strip().lower()}
    if dept["code"]:
        names.add(str(dept["code"]).strip().lower())
    items: list[SpendItem] = []
    uncosted: list[str] = []

    if _has_table(conn, "expense_claims"):
        has_lines = _has_table(conn, "expense_claim_lines")
        for c in conn.execute(
                "SELECT * FROM expense_claims WHERE status IN "
                "('Approved', 'Paid')").fetchall():
            if (c["department"] or "").strip().lower() not in names:
                continue
            when = (c["incurred_to"] or c["incurred_from"]
                    or c["submitted_on"] or c["created_on"] or "")[:10]
            if not (y_from <= when <= y_to):
                continue
            lines = conn.execute(
                "SELECT * FROM expense_claim_lines WHERE claim_id = ?",
                (c["claim_id"],)).fetchall() if has_lines else []
            if lines:
                for ln in lines:
                    items.append(SpendItem(
                        "Expense claim", c["claim_ref"], ln["incurred_on"],
                        CLAIM_CATEGORY_MAP.get(ln["category"], "Other"),
                        f"{c['title']}: {ln['description'] or ln['category']}",
                        round(float(ln["gross_amount"] or 0.0), 2)))
            else:
                items.append(SpendItem(
                    "Expense claim", c["claim_ref"], when,
                    CLAIM_CATEGORY_MAP.get(c["category"], "Other"),
                    c["title"], round(float(c["total_amount"] or 0.0), 2)))

    trip_ids: list[int] = []
    if _has_table(conn, "trips"):
        cols = _columns(conn, "trips")
        staff_dept: dict[str, str] = {}
        if _has_table(conn, "staff"):
            staff_dept = {r["staff_id"]: (r["department"] or "").strip().lower()
                          for r in conn.execute(
                              "SELECT staff_id, department FROM staff")}
        for t in conn.execute(
                "SELECT * FROM trips WHERE status <> 'Cancelled' "
                "AND start_date BETWEEN ? AND ?", (y_from, y_to)).fetchall():
            owner = t["department_id"] if "department_id" in cols else None
            mine = (owner == dept["department_id"]) if owner is not None \
                else staff_dept.get(t["lead_staff_id"] or "") in names
            if not mine:
                continue
            trip_ids.append(int(t["trip_id"]))
            cost = t["running_cost"] if "running_cost" in cols else None
            if cost is None:
                uncosted.append(f"#{t['trip_id']} {t['name']}")
                continue
            items.append(SpendItem("Trip", f"Trip #{t['trip_id']}",
                                   t["start_date"], "Trips & visits",
                                   t["name"], round(float(cost), 2)))

    if _has_table(conn, "receipts") and _has_table(conn, "receipt_lines"):
        has_dept = "department_id" in _columns(conn, "receipt_lines")
        sql = ("SELECT rl.*, r.receipt_number, r.issued_date FROM "
               "receipt_lines rl JOIN receipts r ON r.receipt_id = "
               "rl.receipt_id WHERE r.status = 'Issued' "
               "AND r.issued_date BETWEEN ? AND ?")
        for ln in conn.execute(sql, (y_from, y_to)).fetchall():
            is_trip = ln["kind"] == "trip" and ln["source_id"] in trip_ids
            is_dept = has_dept and ln["department_id"] == dept["department_id"]
            if not (is_trip or is_dept):
                continue
            items.append(SpendItem(
                "Receipt", ln["receipt_number"], ln["issued_date"],
                "Trips & visits" if is_trip else "Other",
                ln["description"], -round(float(ln["amount"] or 0.0), 2)))
    return items, uncosted


def budget_report(department_id: int,
                  academic_year: str | None = None) -> BudgetReport:
    """Budget lines vs spend for one department and year, with warnings."""
    init_db()
    year = _year(academic_year)
    with _connect() as conn:
        dept = _department(conn, int(department_id))
        items, uncosted = _spend_items(conn, dept, year)
    report = BudgetReport(department_id=int(department_id),
                          department_name=dept["name"], academic_year=year,
                          items=items, uncosted_trips=uncosted)
    by_cat: dict[str, CategoryLine] = {}
    for l in list_lines(department_id=department_id, academic_year=year):
        cl = by_cat.setdefault(l.category, CategoryLine(l.category, 0, 0, 0))
        cl.budget = round(cl.budget + l.amount, 2)
    for it in items:
        cl = by_cat.setdefault(it.category, CategoryLine(it.category, 0, 0, 0))
        if it.amount >= 0:
            cl.spend = round(cl.spend + it.amount, 2)
        else:
            cl.income = round(cl.income - it.amount, 2)
    report.lines = sorted(by_cat.values(),
                          key=lambda c: BUDGET_CATEGORIES.index(c.category)
                          if c.category in BUDGET_CATEGORIES else 99)
    for cl in report.lines:
        if cl.budget == 0 and cl.net > 0:
            report.warnings.append(
                f"{cl.category}: {CURRENCY_SYMBOL}{cl.net:,.2f} spent with "
                "no budget line")
        elif cl.over:
            report.warnings.append(
                f"OVERSPENT {cl.category}: {CURRENCY_SYMBOL}{cl.net:,.2f} "
                f"against {CURRENCY_SYMBOL}{cl.budget:,.2f} "
                f"({CURRENCY_SYMBOL}{-cl.remaining:,.2f} over)")
        elif cl.utilisation_pct is not None and \
                cl.utilisation_pct >= WARN_AT_PCT:
            report.warnings.append(
                f"{cl.category} is {cl.utilisation_pct:.0f}% spent")
    if report.overspent:
        report.warnings.insert(0, (
            f"DEPARTMENT OVERSPENT: net {CURRENCY_SYMBOL}"
            f"{report.net_spend:,.2f} against a {CURRENCY_SYMBOL}"
            f"{report.total_budget:,.2f} budget"))
    if uncosted:
        report.warnings.append(
            f"{len(uncosted)} trip(s) have no running cost recorded")
    return report


@dataclass
class DepartmentRow:
    department_id: int
    name: str
    budget: float
    net_spend: float
    remaining: float
    utilisation_pct: float | None
    overspent: bool
    warnings: int


def all_departments(academic_year: str | None = None) -> list[DepartmentRow]:
    """Budget-vs-spend for every department, worst first."""
    init_db()
    with _connect() as conn:
        ids = [r["department_id"] for r in conn.execute(
            "SELECT department_id FROM departments ORDER BY name")]
    rows: list[DepartmentRow] = []
    for did in ids:
        rep = budget_report(did, academic_year)
        if not rep.lines and not rep.items:
            continue
        rows.append(DepartmentRow(
            department_id=did, name=rep.department_name,
            budget=rep.total_budget, net_spend=rep.net_spend,
            remaining=rep.remaining, utilisation_pct=rep.utilisation_pct,
            overspent=rep.overspent, warnings=len(rep.warnings)))
    rows.sort(key=lambda r: (not r.overspent, -(r.utilisation_pct or 0)))
    return rows


def overspend_warnings(academic_year: str | None = None) -> list[str]:
    """Every department warning for the year, prefixed with its name."""
    init_db()
    with _connect() as conn:
        ids = [r["department_id"] for r in conn.execute(
            "SELECT department_id FROM departments ORDER BY name")]
    out: list[str] = []
    for did in ids:
        rep = budget_report(did, academic_year)
        out.extend(f"{rep.department_name}: {w}" for w in rep.warnings)
    return out


def sync_department_totals(academic_year: str | None = None) -> int:
    """Copy each department's line total and net spend for the year
    into ``departments.budget_total`` / ``budget_spent`` /
    ``budget_year``, so the Departments screens show the same figures."""
    year = _year(academic_year)
    n = 0
    from education_system.systems.sixth_form.domain.staff.departments import (
        departments,
    )
    for row in all_departments(year):
        dept = departments.get_department(row.department_id)
        if dept is None:
            continue
        data = departments._to_department_dict(dept)
        data.update(budget_year=year, budget_total=row.budget,
                    budget_spent=row.net_spend)
        departments.update_department(row.department_id, data)
        n += 1
    return n


def attribute_receipt_line(line_id: int, department_id: int | None) -> None:
    """File a receipt line's income against a department (or clear it)."""
    init_db()
    with _connect() as conn:
        if department_id is not None:
            _department(conn, int(department_id))
        cur = conn.execute(
            "UPDATE receipt_lines SET department_id = ? WHERE line_id = ?",
            (department_id, line_id))
        conn.commit()
    if not cur.rowcount:
        raise ValidationError(f"No receipt line #{line_id}")


def list_departments() -> list[tuple[int, str]]:
    """(id, name) of every department, for pickers."""
    init_db()
    with _connect() as conn:
        return [(r["department_id"], r["name"]) for r in conn.execute(
            "SELECT department_id, name FROM departments ORDER BY name")]
