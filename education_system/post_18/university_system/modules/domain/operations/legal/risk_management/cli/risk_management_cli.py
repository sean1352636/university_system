"""
University Risk Management — interactive CLI.

Wired to :class:`RiskDB` in
``risk_management.risk_service``, which reads/writes the central
``student_records.db`` ``risks`` table — the same database and table the
Risk Management GUI (``university_risk_management.py``) uses. Anything
created here is visible in the GUI and vice-versa.

Covers the areas the GUI exposes and that actually persist: the Risk
Register (list/view/create/edit/delete), the 5x5 Risk Matrix
(likelihood x impact heat-map), and a dashboard-style summary by rating /
status / category. Mitigation plans and status/outcome are tracked as
fields on each risk (edited in place), mirroring the GUI.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from education_system.post_18.university_system.modules.domain.operations.legal.risk_management.risk_service import (
    CATEGORIES,
    DEPARTMENTS,
    STATUSES,
    LIKELIHOOD_LEVELS,
    IMPACT_LEVELS,
    Risk,
    RiskDB,
)


# --------------------------------------------------------------------------- #
# Small input helpers
# --------------------------------------------------------------------------- #
def _prompt(text: str, default: str = "") -> str:
    """Prompt for a string. Returns the trimmed input (or *default* if blank)."""
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or default


def _prompt_int(text: str, *, allow_blank: bool = True) -> Optional[int]:
    """Prompt for an integer. Blank returns None when *allow_blank*."""
    while True:
        raw = input(f"{text}: ").strip()
        if not raw:
            if allow_blank:
                return None
            print("A value is required.")
            continue
        try:
            return int(raw)
        except ValueError:
            print("Please enter a whole number.")


def _prompt_choice(text: str, options: list, default: str = "") -> str:
    """Prompt for one of *options*, shown as a numbered list. Blank keeps default."""
    print(f"\n{text}:")
    for idx, opt in enumerate(options, start=1):
        print(f"  [{idx}] {opt}")
    while True:
        suffix = f" [{default}]" if default else ""
        raw = input(f"Select 1-{len(options)}{suffix}: ").strip()
        if not raw:
            return default
        try:
            n = int(raw)
            if 1 <= n <= len(options):
                return options[n - 1]
        except ValueError:
            # Allow typing the value verbatim too.
            if raw in options:
                return raw
        print("Invalid selection.")


def _prompt_scale(text: str, mapping: dict, default: int = 3) -> int:
    """Prompt for a 1-5 scale value described by *mapping*. Blank keeps default."""
    print(f"\n{text}:")
    for k in sorted(mapping):
        print(f"  [{k}] {mapping[k]}")
    while True:
        raw = input(f"Select 1-5 [{default}]: ").strip()
        if not raw:
            return default
        try:
            n = int(raw)
            if n in mapping:
                return n
        except ValueError:
            pass
        print("Please enter a value 1-5.")


def _pause() -> None:
    input("\nPress Enter to continue...")


def _current_username(auth) -> str:
    """Best-effort current username for the risk 'owner' field."""
    try:
        user = getattr(auth, "current_user", None)
        if isinstance(user, dict):
            return user.get("username") or user.get("name") or "cli-user"
    except Exception:
        pass
    return "cli-user"


def _header(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


# --------------------------------------------------------------------------- #
# 1. Risk Register
# --------------------------------------------------------------------------- #
def _print_risk_table(risks: list) -> None:
    print(f"\n{'ID':<5}{'Title':<30}{'Category':<20}{'L':<3}{'I':<3}"
          f"{'Score':<7}{'Rating':<10}{'Status':<13}Owner")
    print("-" * 105)
    for r in risks:
        print(f"{r.id:<5}{(r.title or '')[:29]:<30}"
              f"{(r.category or '')[:19]:<20}"
              f"{r.likelihood:<3}{r.impact:<3}{r.score:<7}"
              f"{r.rating:<10}{(r.status or '')[:12]:<13}"
              f"{(r.owner or '')[:20]}")


def _list_risks(db: RiskDB) -> None:
    status = _prompt("Status filter (Open/In Progress/Mitigated/... blank = All)") or "All"
    category = _prompt("Category filter (blank = All)") or "All"
    search = _prompt("Search title/description/owner (optional)")
    risks = db.fetch_all(search=search, category=category, status=status)
    if not risks:
        print("\nNo risks found.")
        return
    _print_risk_table(risks)
    print(f"\n{len(risks)} risk(s).")


def _view_risk(db: RiskDB) -> None:
    rid = _prompt_int("Risk id", allow_blank=False)
    r = db.fetch(rid)
    if not r:
        print(f"\nNo risk with id {rid}.")
        return
    print(f"\n--- Risk {r.id} ---")
    print(f"  Title       : {r.title}")
    print(f"  Category    : {r.category}")
    print(f"  Department  : {r.department}")
    print(f"  Owner       : {r.owner or '-'}")
    print(f"  Likelihood  : {r.likelihood} ({LIKELIHOOD_LEVELS.get(r.likelihood, '?')})")
    print(f"  Impact      : {r.impact} ({IMPACT_LEVELS.get(r.impact, '?')})")
    print(f"  Score/Rating: {r.score}  ({r.rating})")
    print(f"  Status      : {r.status}")
    print(f"  Description : {r.description or '-'}")
    print(f"  Mitigation  : {r.mitigation or '-'}")
    print(f"  Created     : {r.created or '-'}")
    print(f"  Updated     : {r.updated or '-'}")


def _create_risk(db: RiskDB, auth) -> None:
    title = _prompt("Title")
    if not title:
        print("Title is required.")
        return
    category = _prompt_choice("Category", CATEGORIES, default=CATEGORIES[0])
    department = _prompt_choice("Department", DEPARTMENTS, default=DEPARTMENTS[0])
    owner = _prompt("Owner", default=_current_username(auth))
    description = _prompt("Description (optional)")
    likelihood = _prompt_scale("Likelihood", LIKELIHOOD_LEVELS, default=3)
    impact = _prompt_scale("Impact", IMPACT_LEVELS, default=3)
    status = _prompt_choice("Status", STATUSES, default=STATUSES[0])
    mitigation = _prompt("Mitigation plan (optional)")
    try:
        r = Risk(
            id=None, title=title, category=category, department=department,
            description=description, likelihood=likelihood, impact=impact,
            status=status, owner=owner, mitigation=mitigation,
            created="", updated="",
        )
        new_id = db.add(r)
        print(f"\n✓ Created risk '{title}' (id={new_id}, score={r.score}, {r.rating}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _edit_risk(db: RiskDB, auth) -> None:
    rid = _prompt_int("Risk id to edit", allow_blank=False)
    r = db.fetch(rid)
    if not r:
        print(f"\nNo risk with id {rid}.")
        return
    print("\nLeave a field blank to keep its current value.")
    title = _prompt("Title", default=r.title)
    category = _prompt_choice("Category", CATEGORIES, default=r.category)
    department = _prompt_choice("Department", DEPARTMENTS, default=r.department)
    owner = _prompt("Owner", default=r.owner)
    description = _prompt("Description", default=r.description)
    likelihood = _prompt_scale("Likelihood", LIKELIHOOD_LEVELS, default=r.likelihood)
    impact = _prompt_scale("Impact", IMPACT_LEVELS, default=r.impact)
    status = _prompt_choice("Status", STATUSES, default=r.status)
    mitigation = _prompt("Mitigation plan", default=r.mitigation)
    try:
        updated = Risk(
            id=r.id, title=title, category=category, department=department,
            description=description, likelihood=likelihood, impact=impact,
            status=status, owner=owner, mitigation=mitigation,
            created=r.created, updated="",
        )
        db.update(updated)
        print(f"\n✓ Updated risk {r.id} (score={updated.score}, {updated.rating}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _delete_risk(db: RiskDB) -> None:
    rid = _prompt_int("Risk id to delete", allow_blank=False)
    r = db.fetch(rid)
    if not r:
        print(f"\nNo risk with id {rid}.")
        return
    confirm = _prompt(f"Delete risk #{rid} '{r.title}'? Type 'yes' to confirm")
    if confirm.lower() != "yes":
        print("Cancelled.")
        return
    try:
        db.delete(rid)
        print(f"\n✓ Deleted risk {rid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _register_menu(db: RiskDB, auth) -> None:
    while True:
        _header("Risk Register")
        print("[1] List risks")
        print("[2] View a risk")
        print("[3] Create risk")
        print("[4] Edit risk")
        print("[5] Delete risk")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_risks(db)
        elif choice == "2":
            _view_risk(db)
        elif choice == "3":
            _create_risk(db, auth)
        elif choice == "4":
            _edit_risk(db, auth)
        elif choice == "5":
            _delete_risk(db)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 2. Risk Matrix (5x5 likelihood x impact heat-map)
# --------------------------------------------------------------------------- #
def _rating_for_score(score: int) -> str:
    if score >= 20:
        return "Critical"
    if score >= 12:
        return "High"
    if score >= 6:
        return "Medium"
    return "Low"


def _show_matrix(db: RiskDB) -> None:
    counts = {(lk, im): 0 for lk in range(1, 6) for im in range(1, 6)}
    for r in db.fetch_all():
        counts[(r.likelihood, r.impact)] = counts.get((r.likelihood, r.impact), 0) + 1

    _header("Risk Matrix — Likelihood (rows) x Impact (columns)")
    print("Cells show: <count of risks> / score\n")
    header = "L\\I  " + "".join(f"{im:>10}" for im in range(1, 6))
    print(header)
    print("     " + "".join(f"{IMPACT_LEVELS[im][:9]:>10}" for im in range(1, 6)))
    print("-" * len(header))
    # Likelihood 5 at top, 1 at bottom (standard risk-matrix orientation).
    for lk in range(5, 0, -1):
        cells = []
        for im in range(1, 6):
            score = lk * im
            cells.append(f"{counts[(lk, im)]}/{score:<2}")
        row = f"{lk} {LIKELIHOOD_LEVELS[lk][:3]:<3}" + "".join(f"{c:>10}" for c in cells)
        print(row)
    print("\nRating bands: Low 1-5 | Medium 6-11 | High 12-19 | Critical 20-25")


def _matrix_summary(db: RiskDB) -> None:
    stats = db.stats()
    _header("Risk Summary")
    print(f"Total risks: {stats['total']}\n")
    print("By rating:")
    for rating in ("Critical", "High", "Medium", "Low"):
        print(f"  {rating:<10}: {stats['by_rating'].get(rating, 0)}")
    print("\nBy status:")
    for st in STATUSES:
        print(f"  {st:<13}: {stats['by_status'].get(st, 0)}")
    print("\nBy category:")
    for cat in CATEGORIES:
        cnt = stats['by_category'].get(cat, 0)
        if cnt:
            print(f"  {cat:<22}: {cnt}")


def _matrix_menu(db: RiskDB, auth) -> None:
    while True:
        _header("Risk Matrix & Analytics")
        print("[1] View 5x5 risk matrix")
        print("[2] Summary (by rating / status / category)")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _show_matrix(db)
        elif choice == "2":
            _matrix_summary(db)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 3. Mitigation Tracking
# --------------------------------------------------------------------------- #
def _list_by_status(db: RiskDB) -> None:
    status = _prompt_choice("Status to review", STATUSES, default="Open")
    risks = db.fetch_all(status=status)
    if not risks:
        print(f"\nNo risks with status '{status}'.")
        return
    _print_risk_table(risks)


def _update_mitigation(db: RiskDB) -> None:
    rid = _prompt_int("Risk id", allow_blank=False)
    r = db.fetch(rid)
    if not r:
        print(f"\nNo risk with id {rid}.")
        return
    print(f"\nCurrent status    : {r.status}")
    print(f"Current mitigation: {r.mitigation or '-'}")
    status = _prompt_choice("New status", STATUSES, default=r.status)
    mitigation = _prompt("Mitigation plan / outcome", default=r.mitigation)
    try:
        updated = Risk(
            id=r.id, title=r.title, category=r.category, department=r.department,
            description=r.description, likelihood=r.likelihood, impact=r.impact,
            status=status, owner=r.owner, mitigation=mitigation,
            created=r.created, updated="",
        )
        db.update(updated)
        print(f"\n✓ Updated risk {r.id} → status '{status}'.")
    except Exception as e:
        print(f"\n✗ {e}")


def _mitigation_menu(db: RiskDB, auth) -> None:
    while True:
        _header("Mitigation & Outcome Tracking")
        print("[1] List risks by status")
        print("[2] Update status / mitigation for a risk")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_by_status(db)
        elif choice == "2":
            _update_mitigation(db)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_risk_management_menu(auth) -> None:
    """Run the University Risk Management CLI loop."""
    try:
        db = RiskDB()
    except Exception as e:
        print(f"❌ Could not open the risk register: {e}")
        return

    while True:
        print("\n" + "=" * 50)
        print("    UNIVERSITY RISK MANAGEMENT")
        print(f"    (as of {datetime.now().strftime('%Y-%m-%d')})")
        print("=" * 50)
        print("1. Risk Register (list / view / create / edit / delete)")
        print("2. Risk Matrix & Analytics")
        print("3. Mitigation & Outcome Tracking")
        print("4. Return to Main Menu")
        print("=" * 50)

        try:
            choice = input("\nEnter your choice (1-4): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return

        try:
            if choice == "1":
                _register_menu(db, auth)
            elif choice == "2":
                _matrix_menu(db, auth)
            elif choice == "3":
                _mitigation_menu(db, auth)
            elif choice == "4":
                print("Returning to main menu...")
                return
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            print("\nCancelled.")
        except Exception as e:  # keep the menu resilient
            print(f"❌ Error: {e}")
