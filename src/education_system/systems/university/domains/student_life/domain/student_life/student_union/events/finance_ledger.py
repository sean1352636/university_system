"""One reading of a Student Union event's money.

Event money has been written three ways over the years, all of which
are still live:

* ``event_finances`` with ``expense_type`` (amount stored negative) or
  ``revenue_type`` (positive) — the CLI tracker and ticket sales
  (``interfaces/cli/student_union_events/finances.py``, ``ticketing.py``)
  and ``reporting/financial_report.py`` read it that way;
* ``event_finances`` with ``entry_type``/``transaction_type`` of
  ``'income'``/``'expense'`` and a positive amount — the quick CLI
  tracker and the older GUI dialog;
* ``event_income`` / ``event_expenses`` keyed by event *name* — the
  "Add Income"/"Add Expense" dialogs before this module existed.

:func:`entries` reads all three and normalises them (direction, positive
amount, category, date). New rows go through :func:`add_entry`, which
writes ``event_finances`` in a shape every existing reader understands
(sign *and* type columns set). Budgets live in ``su_event_budgets``.

Ticket income posted to Finance (``services/payments.py``) is the GL
record of the same cash; the event P&L here is the ``event_finances``
row the ticketing flow writes alongside it, so nothing is counted twice.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Optional

INCOME, EXPENSE = "income", "expense"

INCOME_CATEGORIES = ("Ticket Sales", "Sponsorships", "Merchandise", "Donations",
                     "Entry Fees", "Food Sales", "Grants", "Other")
EXPENSE_CATEGORIES = ("Venue", "Catering", "Equipment", "Marketing", "Entertainment",
                      "Decorations", "Staffing", "Transportation", "Supplies", "Other")

_UNION_EVENTS_SQL = """
    SELECT event_id, title,
           COALESCE(event_date, substr(start_datetime, 1, 10)) AS event_date,
           status, max_capacity
    FROM unified_events
    WHERE source_type = 'union'
"""


def ensure_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS su_event_budgets (
            budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            direction TEXT NOT NULL CHECK (direction IN ('income', 'expense')),
            category TEXT NOT NULL,
            amount REAL NOT NULL CHECK (amount >= 0),
            updated_by TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE (event_id, direction, category),
            FOREIGN KEY (event_id) REFERENCES unified_events (event_id)
        )
        """
    )


def union_events(conn, *, since_days: Optional[int] = None) -> list[dict]:
    """Student Union events, newest first."""
    sql = _UNION_EVENTS_SQL
    params: list = []
    if since_days is not None:
        sql += " AND COALESCE(event_date, substr(start_datetime, 1, 10)) >= date('now', ?)"
        params.append(f"-{int(since_days)} days")
    sql += " ORDER BY COALESCE(event_date, start_datetime) DESC, event_id DESC"
    rows = conn.execute(sql, params).fetchall()
    return [dict(zip(("event_id", "title", "event_date", "status", "max_capacity"),
                     tuple(r))) for r in rows]


def event_label(event: dict) -> str:
    return f"{event['event_id']}: {event['title']} ({event['event_date'] or 'no date'})"


def _event_title(conn, event_id: int) -> Optional[str]:
    row = conn.execute("SELECT title FROM unified_events WHERE event_id = ?",
                       (event_id,)).fetchone()
    return row[0] if row else None


def _table_exists(conn, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone() is not None


def _columns(conn, table: str) -> set[str]:
    # db-audit: ignore[DBW001] - table is one of three literals above
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _direction(row: dict) -> str:
    for key in ("transaction_type", "entry_type"):
        val = (row.get(key) or "").strip().lower()
        if val in ("income", "revenue"):
            return INCOME
        if val == "expense":
            return EXPENSE
    if (row.get("expense_type") or "").strip():
        return EXPENSE
    if (row.get("revenue_type") or "").strip():
        return INCOME
    return EXPENSE if (row.get("amount") or 0) < 0 else INCOME


def entries(conn, event_id: int) -> list[dict]:
    """Every money line for an event, normalised, newest first.

    Each dict: ``direction`` ('income'/'expense'), ``category``,
    ``amount`` (always positive), ``date``, ``counterparty`` (vendor for
    expenses, payment method for income), ``description``, ``source``.
    """
    out: list[dict] = []
    if _table_exists(conn, "event_finances"):
        cols = _columns(conn, "event_finances")
        wanted = [c for c in ("finance_id", "transaction_id", "expense_type", "revenue_type",
                              "category", "amount", "description", "vendor",
                              "transaction_type", "entry_type", "transaction_date",
                              "entry_date", "date_recorded", "created_at", "receipt_path")
                  if c in cols]
        # db-audit: ignore[DBW001] - column names come from PRAGMA table_info
        rows = conn.execute(
            f"SELECT {', '.join(wanted)} FROM event_finances WHERE event_id = ?",
            (event_id,),
        ).fetchall()
        for r in rows:
            row = dict(zip(wanted, tuple(r)))
            direction = _direction(row)
            category = (row.get("category") or
                        (row.get("expense_type") if direction == EXPENSE else row.get("revenue_type"))
                        or row.get("expense_type") or row.get("revenue_type") or "Uncategorised")
            when = (row.get("transaction_date") or row.get("entry_date")
                    or row.get("date_recorded") or row.get("created_at") or "")
            out.append({
                "id": row.get("finance_id") or row.get("transaction_id"),
                "direction": direction,
                "category": category,
                "amount": abs(float(row.get("amount") or 0)),
                "date": str(when)[:10],
                "counterparty": row.get("vendor") or "",
                "description": row.get("description") or "",
                "source": "event_finances",
            })

    title = _event_title(conn, event_id)
    if title:
        if _table_exists(conn, "event_income"):
            for r in conn.execute(
                "SELECT income_id, source, amount, date, payment_method, notes "
                "FROM event_income WHERE event_name = ?", (title,)
            ).fetchall():
                out.append({"id": r[0], "direction": INCOME, "category": r[1] or "Other",
                            "amount": abs(float(r[2] or 0)), "date": str(r[3] or "")[:10],
                            "counterparty": r[4] or "", "description": r[5] or "",
                            "source": "event_income"})
        if _table_exists(conn, "event_expenses"):
            for r in conn.execute(
                "SELECT expense_id, category, amount, date, vendor, notes, receipt_number "
                "FROM event_expenses WHERE event_name = ?", (title,)
            ).fetchall():
                desc = r[5] or ""
                if r[6]:
                    desc = f"{desc} (receipt {r[6]})".strip()
                out.append({"id": r[0], "direction": EXPENSE, "category": r[1] or "Other",
                            "amount": abs(float(r[2] or 0)), "date": str(r[3] or "")[:10],
                            "counterparty": r[4] or "", "description": desc,
                            "source": "event_expenses"})
    out.sort(key=lambda e: e["date"] or "", reverse=True)
    return out


def add_entry(conn, *, event_id: int, direction: str, category: str, amount: float,
              entry_date: Optional[str] = None, counterparty: str = "",
              description: str = "", receipt: str = "", recorded_by: Optional[str] = None) -> int:
    """Record one income or expense line for an event and commit it.

    Writes the sign convention (expenses negative, with ``expense_type``)
    *and* the type columns, so the CLI report, the CLI tracker and this
    module all read the row the same way. ``counterparty`` is the vendor
    for an expense and the payment method for income.
    """
    direction = (direction or "").lower()
    if direction not in (INCOME, EXPENSE):
        raise ValueError("Direction must be income or expense.")
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise ValueError("Please enter a valid amount.")
    if amount <= 0:
        raise ValueError("Amount must be positive.")
    category = (category or "").strip()
    if not category:
        raise ValueError("Please choose a category.")
    entry_date = (entry_date or datetime.now().strftime("%Y-%m-%d")).strip()
    try:
        datetime.strptime(entry_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Date must be in YYYY-MM-DD format.")
    if _event_title(conn, event_id) is None:
        raise ValueError("That event no longer exists.")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    signed = -amount if direction == EXPENSE else amount
    cols = _columns(conn, "event_finances")
    values = {
        "event_id": event_id,
        "amount": signed,
        "description": (description or "").strip() or None,
        "date_recorded": f"{entry_date} {now[11:]}",
        "expense_type": category if direction == EXPENSE else None,
        "revenue_type": category if direction == INCOME else None,
        "category": category,
        "transaction_type": direction,
        "entry_type": direction,
        "transaction_date": entry_date,
        "entry_date": entry_date,
        "vendor": (counterparty or "").strip() or None,
        "receipt_path": (receipt or "").strip() or None,
        "created_at": now,
        "created_by": recorded_by,
    }
    values = {k: v for k, v in values.items() if k in cols}
    names = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    # db-audit: ignore[DBW001] - column names filtered against PRAGMA table_info
    cur = conn.execute(f"INSERT INTO event_finances ({names}) VALUES ({marks})",
                       tuple(values.values()))
    conn.commit()
    return cur.lastrowid


def budgets(conn, event_id: int) -> list[dict]:
    ensure_schema(conn)
    rows = conn.execute(
        "SELECT direction, category, amount, updated_by, updated_at FROM su_event_budgets "
        "WHERE event_id = ? ORDER BY direction, category",
        (event_id,),
    ).fetchall()
    return [dict(zip(("direction", "category", "amount", "updated_by", "updated_at"),
                     tuple(r))) for r in rows]


def set_budget(conn, *, event_id: int, direction: str, category: str, amount: float,
               updated_by: Optional[str] = None) -> None:
    """Set (or clear, with amount 0) one budget line and commit."""
    ensure_schema(conn)
    direction = (direction or "").lower()
    if direction not in (INCOME, EXPENSE):
        raise ValueError("Direction must be income or expense.")
    category = (category or "").strip()
    if not category:
        raise ValueError("Please choose a category.")
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise ValueError("Please enter a valid amount.")
    if amount < 0:
        raise ValueError("A budget cannot be negative.")
    if _event_title(conn, event_id) is None:
        raise ValueError("That event no longer exists.")
    if amount == 0:
        conn.execute("DELETE FROM su_event_budgets WHERE event_id = ? AND direction = ? "
                     "AND category = ?", (event_id, direction, category))
    else:
        conn.execute(
            """
            INSERT INTO su_event_budgets (event_id, direction, category, amount,
                                          updated_by, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (event_id, direction, category)
            DO UPDATE SET amount = excluded.amount, updated_by = excluded.updated_by,
                          updated_at = excluded.updated_at
            """,
            (event_id, direction, category, amount, updated_by,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
    conn.commit()


def attendance(conn, event_id: int) -> dict:
    """Registered and attended counts from unified_event_registrations."""
    if not _table_exists(conn, "unified_event_registrations"):
        return {"registered": 0, "attended": 0}
    row = conn.execute(
        """
        SELECT COUNT(*),
               SUM(CASE WHEN LOWER(COALESCE(attendance_status, '')) IN ('attended', 'checked_in', 'present')
                         OR checked_in_at IS NOT NULL THEN 1 ELSE 0 END)
        FROM unified_event_registrations
        WHERE event_id = ? AND COALESCE(is_waitlisted, 0) = 0
          AND LOWER(COALESCE(attendance_status, '')) NOT IN ('cancelled', 'canceled')
        """,
        (event_id,),
    ).fetchone()
    return {"registered": int(row[0] or 0), "attended": int(row[1] or 0)}


def summary(conn, event_id: int) -> dict:
    """Totals, per-category breakdown, budget variance and per-head figures."""
    lines = entries(conn, event_id)
    by_cat: dict[str, dict[str, float]] = {INCOME: defaultdict(float), EXPENSE: defaultdict(float)}
    for e in lines:
        by_cat[e["direction"]][e["category"]] += e["amount"]
    total_income = sum(by_cat[INCOME].values())
    total_expense = sum(by_cat[EXPENSE].values())
    budget_rows = budgets(conn, event_id)
    budgeted = {INCOME: 0.0, EXPENSE: 0.0}
    for b in budget_rows:
        budgeted[b["direction"]] += float(b["amount"] or 0)
    people = attendance(conn, event_id)
    heads = people["attended"] or people["registered"]
    return {
        "event_id": event_id,
        "title": _event_title(conn, event_id),
        "entries": lines,
        "income_by_category": dict(by_cat[INCOME]),
        "expense_by_category": dict(by_cat[EXPENSE]),
        "total_income": total_income,
        "total_expense": total_expense,
        "net": total_income - total_expense,
        "budgets": budget_rows,
        "budgeted_income": budgeted[INCOME] if budget_rows else None,
        "budgeted_expense": budgeted[EXPENSE] if budget_rows else None,
        "attendance": people,
        "headcount": heads,
        "headcount_basis": "attended" if people["attended"] else "registered",
    }


def _money(v: float) -> str:
    return f"£{v:,.2f}" if v >= 0 else f"-£{abs(v):,.2f}"


def _variance(actual: float, budget: Optional[float]) -> str:
    if not budget:
        return "no budget set"
    diff = actual - budget
    sign = "+" if diff >= 0 else "-"
    return f"{sign}£{abs(diff):,.2f} ({sign}{abs(diff) / budget * 100:.1f}%)"


def summary_text(s: dict) -> str:
    """Plain-text statement for the summary tab and report export."""
    if not s["entries"] and not s["budgets"]:
        return (f"FINANCIAL SUMMARY - {s['title']}\n{'=' * 60}\n\n"
                "No income, expenses or budget have been recorded for this event yet.\n")
    lines = [f"FINANCIAL SUMMARY - {s['title']}", "=" * 60, "", "INCOME:"]
    if s["income_by_category"]:
        for cat, amt in sorted(s["income_by_category"].items(), key=lambda kv: -kv[1]):
            lines.append(f"  {cat + ':':<22}{_money(amt):>14}")
    else:
        lines.append("  None recorded")
    lines += ["  " + "-" * 34, f"  {'Total Income:':<22}{_money(s['total_income']):>14}", "", "EXPENSES:"]
    if s["expense_by_category"]:
        for cat, amt in sorted(s["expense_by_category"].items(), key=lambda kv: -kv[1]):
            lines.append(f"  {cat + ':':<22}{_money(amt):>14}")
    else:
        lines.append("  None recorded")
    net = s["net"]
    lines += ["  " + "-" * 34, f"  {'Total Expenses:':<22}{_money(s['total_expense']):>14}", "",
              "NET PROFIT/LOSS:", f"  {'Net Profit' if net >= 0 else 'Net Loss'}:"
              f"{'':<11}{_money(net):>14}", "", "BUDGET ANALYSIS:"]
    if s["budgets"]:
        lines += [
            f"  {'Budgeted Income:':<22}{_money(s['budgeted_income']):>14}",
            f"  {'Actual Income:':<22}{_money(s['total_income']):>14}",
            f"  Variance: {_variance(s['total_income'], s['budgeted_income'])}",
            "",
            f"  {'Budgeted Expenses:':<22}{_money(s['budgeted_expense']):>14}",
            f"  {'Actual Expenses:':<22}{_money(s['total_expense']):>14}",
            f"  Variance: {_variance(s['total_expense'], s['budgeted_expense'])}",
        ]
    else:
        lines.append("  No budget has been set for this event.")
    lines += ["", "COST PER ATTENDEE:"]
    heads = s["headcount"]
    if heads:
        lines += [
            f"  Attendees ({s['headcount_basis']}): {heads}",
            f"  Cost per Attendee: {_money(s['total_expense'] / heads)}",
            f"  Revenue per Attendee: {_money(s['total_income'] / heads)}",
            f"  Profit per Attendee: {_money(net / heads)}",
        ]
    else:
        lines.append("  No registrations recorded, so per-attendee figures are not available.")
    status = "profitable" if net > 0 else ("broke even" if net == 0 else "ran at a loss")
    if s["budgets"] and s["budgeted_expense"]:
        status += (" and under budget" if s["total_expense"] <= s["budgeted_expense"]
                   else " and over budget")
    lines += ["", f"STATUS: Event {status}"]
    return "\n".join(lines) + "\n"


__all__ = [
    "INCOME", "EXPENSE", "INCOME_CATEGORIES", "EXPENSE_CATEGORIES", "ensure_schema",
    "union_events", "event_label", "entries", "add_entry", "budgets", "set_budget",
    "attendance", "summary", "summary_text",
]
