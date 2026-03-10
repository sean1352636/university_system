"""Risk Management CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.risk_management.services.risk_management_service import (
    RiskManagementService, RISK_CATEGORIES, RISK_STATUSES,
)
from education_system.college_system.infrastructure.auth.core import UserAuth


def risk_management_menu(auth: UserAuth):
    """Risk Management menu."""
    svc = RiskManagementService(auth._db_path)

    while True:
        print_header("Risk Management")
        options = [
            ("1", "List Risks"),
            ("2", "Create Risk"),
            ("3", "View Risk"),
            ("4", "Update Risk"),
            ("5", "Delete Risk"),
            ("6", "List Reviews"),
            ("7", "Create Review"),
            ("8", "Delete Review"),
            ("9", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            _list_risks(svc)
        elif choice == "2":
            _create_risk(svc)
        elif choice == "3":
            _view_risk(svc)
        elif choice == "4":
            _update_risk(svc)
        elif choice == "5":
            _delete_risk(svc)
        elif choice == "6":
            _list_reviews(svc)
        elif choice == "7":
            _create_review(svc)
        elif choice == "8":
            _delete_review(svc)
        elif choice == "9":
            _show_stats(svc)
        else:
            print("\n  Invalid option.")


# ── Risk CRUD ────────────────────────────────────────────────────────────


def _list_risks(svc):
    print_header("Risk Register")
    try:
        status_f = input("  Filter by status (leave blank for all): ").strip() or None
        cat_f = input("  Filter by category (leave blank for all): ").strip() or None
        search = input("  Search term (leave blank to skip): ").strip() or None

        risks = svc.list_risks(status=status_f, category=cat_f, search=search)
        if not risks:
            print("\n  No risks found.")
            return

        print(f"\n  {'ID':<5} {'Score':<6} {'Status':<12} {'Category':<18} {'Title'}")
        print(f"  {'-'*70}")
        for r in risks:
            score = r.get("risk_score") or 0
            marker = " **" if score >= 15 else ""
            print(f"  {r['id']:<5} {score:<6} {r['status']:<12} "
                  f"{r['category']:<18} {r['risk_title']}{marker}")
        print(f"\n  Total: {len(risks)} risk(s)")
    except Exception as e:
        print(f"\n  Error: {e}")


def _create_risk(svc):
    print_header("Create Risk")
    try:
        title = input("  Title: ").strip()
        if not title:
            print("\n  Title is required.")
            return

        print(f"  Categories: {', '.join(RISK_CATEGORIES)}")
        category = input("  Category [operational]: ").strip() or "operational"

        description = input("  Description (optional): ").strip() or None

        likelihood = _get_int("  Likelihood (1-5) [3]: ", default=3, lo=1, hi=5)
        impact = _get_int("  Impact (1-5) [3]: ", default=3, lo=1, hi=5)
        print(f"  >> Risk Score: {likelihood * impact}")

        current_controls = input("  Current Controls (optional): ").strip() or None
        mitigation_strategy = input("  Mitigation Strategy (optional): ").strip() or None
        risk_owner = input("  Risk Owner (optional): ").strip() or None
        review_date = input("  Review Date YYYY-MM-DD (optional): ").strip() or None

        print(f"  Statuses: {', '.join(RISK_STATUSES)}")
        status = input("  Status [open]: ").strip() or "open"
        notes = input("  Notes (optional): ").strip() or None

        risk = svc.create_risk(
            risk_title=title, category=category, description=description,
            likelihood=likelihood, impact=impact,
            current_controls=current_controls,
            mitigation_strategy=mitigation_strategy,
            risk_owner=risk_owner, review_date=review_date,
            status=status, notes=notes,
        )
        print(f"\n  Risk created — ID: {risk['id']}, Score: {risk['risk_score']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_risk(svc):
    print_header("View Risk")
    try:
        rid = _get_int("  Risk ID: ")
        r = svc.get_risk(rid)
        if not r:
            print("\n  Risk not found.")
            return

        score = r.get("risk_score") or 0
        level = "HIGH" if score >= 15 else ("MEDIUM" if score >= 8 else "LOW")

        print(f"\n  ID:            {r['id']}")
        print(f"  Title:         {r['risk_title']}")
        print(f"  Category:      {r['category']}")
        print(f"  Status:        {r['status']}")
        print(f"  Likelihood:    {r['likelihood']}")
        print(f"  Impact:        {r['impact']}")
        print(f"  Risk Score:    {score}  [{level}]")
        if r.get("residual_likelihood") and r.get("residual_impact"):
            res = r["residual_likelihood"] * r["residual_impact"]
            print(f"  Residual:      {r['residual_likelihood']} x {r['residual_impact']} = {res}")
        print(f"  Owner:         {r.get('risk_owner', '')}")
        print(f"  Review Date:   {r.get('review_date', '')}")
        print(f"  Controls:      {r.get('current_controls', '')}")
        print(f"  Mitigation:    {r.get('mitigation_strategy', '')}")
        print(f"  Notes:         {r.get('notes', '')}")
        print(f"  Description:   {r.get('description', '')}")
        print(f"  Created:       {r.get('created_at', '')}")
        print(f"  Updated:       {r.get('updated_at', '')}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_risk(svc):
    print_header("Update Risk")
    try:
        rid = _get_int("  Risk ID: ")
        r = svc.get_risk(rid)
        if not r:
            print("\n  Risk not found.")
            return

        print(f"  Current: {r['risk_title']} | {r['category']} | "
              f"L={r['likelihood']} I={r['impact']} Score={r.get('risk_score', '')}")
        print("  (Press Enter to keep current value)\n")

        title = input(f"  Title [{r['risk_title']}]: ").strip() or None
        category = input(f"  Category [{r['category']}]: ").strip() or None
        description = input(f"  Description [{r.get('description', '')}]: ").strip() or None

        lk_s = input(f"  Likelihood [{r['likelihood']}]: ").strip()
        likelihood = int(lk_s) if lk_s else None
        imp_s = input(f"  Impact [{r['impact']}]: ").strip()
        impact = int(imp_s) if imp_s else None

        if likelihood or impact:
            new_l = likelihood if likelihood else r["likelihood"]
            new_i = impact if impact else r["impact"]
            print(f"  >> New Risk Score: {new_l * new_i}")

        current_controls = input(f"  Controls [{r.get('current_controls', '')}]: ").strip() or None
        mitigation_strategy = input(f"  Mitigation [{r.get('mitigation_strategy', '')}]: ").strip() or None
        risk_owner = input(f"  Owner [{r.get('risk_owner', '')}]: ").strip() or None
        review_date = input(f"  Review Date [{r.get('review_date', '')}]: ").strip() or None
        status = input(f"  Status [{r['status']}]: ").strip() or None
        notes = input(f"  Notes [{r.get('notes', '')}]: ").strip() or None

        updated = svc.update_risk(
            rid, risk_title=title, category=category, description=description,
            likelihood=likelihood, impact=impact,
            current_controls=current_controls,
            mitigation_strategy=mitigation_strategy,
            risk_owner=risk_owner, review_date=review_date,
            status=status, notes=notes,
        )
        print(f"\n  Risk updated — Score: {updated['risk_score']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_risk(svc):
    print_header("Delete Risk")
    try:
        rid = _get_int("  Risk ID: ")
        r = svc.get_risk(rid)
        if not r:
            print("\n  Risk not found.")
            return
        print(f"  Risk: {r['risk_title']} (Score: {r.get('risk_score', '')})")
        confirm = input("  This will also delete all reviews. Confirm? (y/n): ").strip().lower()
        if confirm != "y":
            print("  Cancelled.")
            return
        svc.delete_risk(rid)
        print("\n  Risk and associated reviews deleted.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Reviews ──────────────────────────────────────────────────────────────


def _list_reviews(svc):
    print_header("Risk Reviews")
    try:
        rid = _get_int("  Risk ID: ")
        reviews = svc.list_reviews(rid)
        if not reviews:
            print("\n  No reviews found for this risk.")
            return
        print(f"\n  {'ID':<5} {'Date':<12} {'Reviewer':<15} {'Prev':<6} {'New':<6} {'Commentary'}")
        print(f"  {'-'*65}")
        for rv in reviews:
            print(f"  {rv['id']:<5} {rv['review_date']:<12} "
                  f"{(rv.get('reviewer') or ''):<15} "
                  f"{(rv.get('previous_score') or '')!s:<6} "
                  f"{(rv.get('new_score') or '')!s:<6} "
                  f"{rv.get('commentary', '')}")
        print(f"\n  Total: {len(reviews)} review(s)")
    except Exception as e:
        print(f"\n  Error: {e}")


def _create_review(svc):
    print_header("Create Review")
    try:
        rid = _get_int("  Risk ID: ")
        r = svc.get_risk(rid)
        if not r:
            print("\n  Risk not found.")
            return
        print(f"  Risk: {r['risk_title']} (Current Score: {r.get('risk_score', '')})")

        review_date = input("  Review Date (YYYY-MM-DD): ").strip()
        if not review_date:
            print("\n  Review date is required.")
            return
        reviewer = input("  Reviewer (optional): ").strip() or None
        prev_s = input("  Previous Score (optional): ").strip()
        new_s = input("  New Score (optional): ").strip()
        commentary = input("  Commentary (optional): ").strip() or None
        actions_taken = input("  Actions Taken (optional): ").strip() or None

        rv = svc.create_review(
            risk_id=rid, review_date=review_date, reviewer=reviewer,
            previous_score=int(prev_s) if prev_s else None,
            new_score=int(new_s) if new_s else None,
            commentary=commentary, actions_taken=actions_taken,
        )
        print(f"\n  Review created — ID: {rv['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_review(svc):
    print_header("Delete Review")
    try:
        rev_id = _get_int("  Review ID: ")
        confirm = input("  Confirm delete? (y/n): ").strip().lower()
        if confirm != "y":
            print("  Cancelled.")
            return
        svc.delete_review(rev_id)
        print("\n  Review deleted.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Statistics ───────────────────────────────────────────────────────────


def _show_stats(svc):
    print_header("Risk Statistics")
    try:
        stats = svc.get_stats()
        print(f"\n  Total Risks:        {stats['total_risks']}")
        print(f"  High Risks (>=15):  {stats['high_risks']}")
        print(f"  Average Score:      {stats['avg_risk_score']}")
        print(f"  Total Reviews:      {stats['reviews_count']}")

        print("\n  By Status:")
        for s, c in stats["by_status"].items():
            print(f"    {s:<14} {c}")

        print("\n  By Category:")
        for cat, c in stats["by_category"].items():
            print(f"    {cat:<18} {c}")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Helpers ──────────────────────────────────────────────────────────────


def _get_int(prompt: str, default: int | None = None,
             lo: int | None = None, hi: int | None = None) -> int:
    """Prompt for an integer with optional default and range."""
    raw = input(prompt).strip()
    if not raw and default is not None:
        return default
    val = int(raw)
    if lo is not None and val < lo:
        val = lo
    if hi is not None and val > hi:
        val = hi
    return val
