"""Prevent Duty CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.prevent_duty.services.prevent_duty_service import PreventDutyService
from education_system.college_system.infrastructure.auth.core import UserAuth


def prevent_duty_menu(auth: UserAuth):
    """Prevent Duty management menu."""
    svc = PreventDutyService(auth._db_path)

    while True:
        print_header("Prevent Duty")
        options = [
            ("1", "List Referrals"),
            ("2", "Create Referral"),
            ("3", "View Referral"),
            ("4", "Update Referral"),
            ("5", "Escalate to Channel"),
            ("6", "Delete Referral"),
            ("7", "List Training Records"),
            ("8", "Add Training Record"),
            ("9", "Update Training Record"),
            ("10", "Delete Training Record"),
            ("11", "Expiring Training"),
            ("12", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break

        elif choice == "1":
            _list_referrals(svc)

        elif choice == "2":
            _create_referral(svc, auth)

        elif choice == "3":
            _view_referral(svc)

        elif choice == "4":
            _update_referral(svc)

        elif choice == "5":
            _escalate_referral(svc)

        elif choice == "6":
            _delete_referral(svc)

        elif choice == "7":
            _list_training(svc)

        elif choice == "8":
            _create_training(svc)

        elif choice == "9":
            _update_training(svc)

        elif choice == "10":
            _delete_training(svc)

        elif choice == "11":
            _expiring_training(svc)

        elif choice == "12":
            _show_stats(svc)

        else:
            print("\n  Invalid option.")


# ── Referral helpers ──────────────────────────────────────────────


def _list_referrals(svc: PreventDutyService):
    status = input("  Filter by status (open/under_review/escalated/closed or Enter for all): ").strip() or None
    risk = input("  Filter by risk level (low/medium/high/critical or Enter for all): ").strip() or None
    search = input("  Search by name (or Enter to skip): ").strip() or None
    try:
        items = svc.list_referrals(status=status, risk_level=risk, search=search)
        if not items:
            print("  No referrals found.")
            return
        for r in items:
            ch = " [CHANNEL]" if r.get("channel_referral") else ""
            print(f"  [{r['id']}] {r.get('subject_name', '')} - "
                  f"{r.get('concern_type', 'N/A')} | Risk: {r.get('risk_level', '')} | "
                  f"Status: {r.get('status', '')}{ch}")
        print(f"\n  {len(items)} referral(s) found.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _create_referral(svc: PreventDutyService, auth: UserAuth):
    try:
        name = input("  Subject Name: ").strip()
        if not name:
            print("  Subject name is required.")
            return
        subject_type = input("  Subject Type (student/staff/visitor/other) [student]: ").strip() or "student"
        sid = input("  Subject ID (or Enter to skip): ").strip()
        subject_id = int(sid) if sid else None
        concern_type = input("  Concern Type: ").strip() or None
        details = input("  Concern Details: ").strip()
        if not details:
            print("  Concern details are required.")
            return
        risk = input("  Risk Level (low/medium/high/critical) [low]: ").strip() or "low"
        actions = input("  Actions Taken (or Enter to skip): ").strip() or None
        reported_by = None
        if hasattr(auth, "current_user") and auth.current_user:
            reported_by = auth.current_user.get("user_id")
        r = svc.create_referral(
            subject_name=name, concern_details=details,
            reported_by=reported_by, subject_type=subject_type,
            subject_id=subject_id, concern_type=concern_type,
            risk_level=risk, actions_taken=actions,
        )
        print(f"\n  Referral #{r['id']} created.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_referral(svc: PreventDutyService):
    try:
        rid = int(input("  Referral ID: ").strip())
        r = svc.get_referral(rid)
        if not r:
            print("  Referral not found.")
            return
        for k, v in r.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_referral(svc: PreventDutyService):
    try:
        rid = int(input("  Referral ID: ").strip())
        r = svc.get_referral(rid)
        if not r:
            print("  Referral not found.")
            return
        print("  Leave blank to keep current value.")
        updates: dict = {}
        val = input(f"  Status [{r.get('status', '')}]: ").strip()
        if val:
            updates["status"] = val
        val = input(f"  Risk Level [{r.get('risk_level', '')}]: ").strip()
        if val:
            updates["risk_level"] = val
        val = input(f"  Concern Type [{r.get('concern_type', '')}]: ").strip()
        if val:
            updates["concern_type"] = val
        val = input(f"  Actions Taken [{r.get('actions_taken', '')}]: ").strip()
        if val:
            updates["actions_taken"] = val
        val = input(f"  Outcome [{r.get('outcome', '')}]: ").strip()
        if val:
            updates["outcome"] = val
        if not updates:
            print("  No changes made.")
            return
        svc.update_referral(rid, **updates)
        print("  Referral updated.")
    except ValueError:
        print("  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _escalate_referral(svc: PreventDutyService):
    try:
        rid = int(input("  Referral ID: ").strip())
        r = svc.get_referral(rid)
        if not r:
            print("  Referral not found.")
            return
        if r.get("channel_referral"):
            print("  Already escalated to Channel.")
            return
        ref = input("  Channel Reference (or Enter to skip): ").strip() or None
        svc.escalate_to_channel(rid, channel_reference=ref)
        print(f"  Referral #{rid} escalated to Channel.")
    except ValueError:
        print("  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_referral(svc: PreventDutyService):
    try:
        rid = int(input("  Referral ID: ").strip())
        confirm = input("  Confirm delete? (y/n): ").strip().lower()
        if confirm != "y":
            print("  Cancelled.")
            return
        svc.delete_referral(rid)
        print("  Referral deleted.")
    except ValueError:
        print("  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Training helpers ──────────────────────────────────────────────


def _list_training(svc: PreventDutyService):
    status = input("  Filter by status (completed/pending/expired or Enter for all): ").strip() or None
    try:
        items = svc.list_training(status=status)
        if not items:
            print("  No training records found.")
            return
        for t in items:
            print(f"  [{t['id']}] Staff {t.get('staff_id', '')} - "
                  f"{t.get('training_type', '')} | {t.get('status', '')} | "
                  f"Expires: {t.get('expiry_date', 'N/A')}")
        print(f"\n  {len(items)} record(s) found.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _create_training(svc: PreventDutyService):
    try:
        staff_id = int(input("  Staff ID: ").strip())
        training_type = input("  Training Type (basic/advanced/refresher/wrap) [basic]: ").strip() or "basic"
        completed = input("  Completed Date (YYYY-MM-DD or Enter): ").strip() or None
        expiry = input("  Expiry Date (YYYY-MM-DD or Enter): ").strip() or None
        cert = input("  Certificate Ref (or Enter): ").strip() or None
        status = input("  Status (completed/pending/expired) [completed]: ").strip() or "completed"
        t = svc.create_training(
            staff_id=staff_id, training_type=training_type,
            completed_date=completed, expiry_date=expiry,
            certificate_ref=cert, status=status,
        )
        print(f"\n  Training record #{t['id']} created.")
    except ValueError:
        print("  Invalid Staff ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_training(svc: PreventDutyService):
    try:
        tid = int(input("  Training Record ID: ").strip())
        t = svc.get_training(tid)
        if not t:
            print("  Training record not found.")
            return
        print("  Leave blank to keep current value.")
        updates: dict = {}
        val = input(f"  Training Type [{t.get('training_type', '')}]: ").strip()
        if val:
            updates["training_type"] = val
        val = input(f"  Completed Date [{t.get('completed_date', '')}]: ").strip()
        if val:
            updates["completed_date"] = val
        val = input(f"  Expiry Date [{t.get('expiry_date', '')}]: ").strip()
        if val:
            updates["expiry_date"] = val
        val = input(f"  Certificate Ref [{t.get('certificate_ref', '')}]: ").strip()
        if val:
            updates["certificate_ref"] = val
        val = input(f"  Status [{t.get('status', '')}]: ").strip()
        if val:
            updates["status"] = val
        if not updates:
            print("  No changes made.")
            return
        svc.update_training(tid, **updates)
        print("  Training record updated.")
    except ValueError:
        print("  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_training(svc: PreventDutyService):
    try:
        tid = int(input("  Training Record ID: ").strip())
        confirm = input("  Confirm delete? (y/n): ").strip().lower()
        if confirm != "y":
            print("  Cancelled.")
            return
        svc.delete_training(tid)
        print("  Training record deleted.")
    except ValueError:
        print("  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _expiring_training(svc: PreventDutyService):
    days = input("  Within how many days? [30]: ").strip()
    within = int(days) if days else 30
    try:
        items = svc.get_expiring_training(within_days=within)
        if not items:
            print(f"  No training records expiring within {within} days.")
            return
        for t in items:
            print(f"  [{t['id']}] Staff {t.get('staff_id', '')} - "
                  f"{t.get('training_type', '')} | Expires: {t.get('expiry_date', '')}")
        print(f"\n  {len(items)} record(s) expiring within {within} days.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _show_stats(svc: PreventDutyService):
    try:
        stats = svc.get_stats()
        print("\n  === Prevent Duty Statistics ===")
        print(f"\n  REFERRALS")
        print(f"    Total:              {stats.get('total_referrals', 0)}")
        print(f"    Open:               {stats.get('open_referrals', 0)}")
        print(f"    Closed:             {stats.get('closed_referrals', 0)}")
        print(f"    Channel referrals:  {stats.get('channel_referrals', 0)}")
        print(f"\n    By Risk Level:")
        for level, count in stats.get("by_risk_level", {}).items():
            print(f"      {level:<12} {count}")
        print(f"\n  TRAINING")
        print(f"    Total records:      {stats.get('total_training', 0)}")
        print(f"    Completed:          {stats.get('completed_training', 0)}")
        print(f"    Expiring (30 days): {stats.get('expiring_soon', 0)}")
    except Exception as e:
        print(f"\n  Error: {e}")
