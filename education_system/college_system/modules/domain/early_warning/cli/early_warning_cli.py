"""Early Warning System CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.early_warning.services.early_warning_service import EarlyWarningService
from education_system.college_system.infrastructure.auth.core import UserAuth


def early_warning_menu(auth: UserAuth):
    """Early Warning System management menu."""
    svc = EarlyWarningService(auth._db_path)

    while True:
        print_header("Early Warning System")
        options = [
            ("1", "List Alerts"),
            ("2", "View Alert"),
            ("3", "New Alert"),
            ("4", "Update Alert"),
            ("5", "Resolve Alert"),
            ("6", "Delete Alert"),
            ("7", "List Rules"),
            ("8", "New Rule"),
            ("9", "Update Rule"),
            ("10", "Delete Rule"),
            ("11", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break

        elif choice == "1":
            show_resolved = input("  Include resolved? (y/n) [n]: ").strip().lower() == "y"
            severity = input("  Severity filter (low/medium/high/critical or Enter): ").strip() or None
            alerts = svc.list_alerts(
                resolved=None if show_resolved else 0,
                severity=severity)
            for a in alerts:
                name = f"{a.get('first_name', '')} {a.get('last_name', '')}".strip() or f"#{a.get('student_id', '')}"
                att = f" Att:{a['attendance_pct']:.0f}%" if a.get("attendance_pct") is not None else ""
                res = " [RESOLVED]" if a.get("resolved") else ""
                print(f"  [{a['id']}] {name} | {a.get('alert_type', '')} | "
                      f"{a.get('severity', '')}{att}{res}")
            if not alerts:
                print("  No alerts found.")

        elif choice == "2":
            try:
                aid = int(input("  Alert ID: ").strip())
                rec = svc.get_alert(aid)
                if not rec:
                    print("  Alert not found.")
                    continue
                name = f"{rec.get('first_name', '')} {rec.get('last_name', '')}".strip()
                print(f"\n  Student:          {name or '#' + str(rec.get('student_id', ''))}")
                print(f"  Alert Type:       {rec.get('alert_type', '')}")
                print(f"  Severity:         {rec.get('severity', '')}")
                print(f"  Trigger Source:   {rec.get('trigger_source', '')}")
                print(f"  Trigger Detail:   {rec.get('trigger_detail', '')}")
                att = f"{rec['attendance_pct']:.1f}%" if rec.get("attendance_pct") is not None else "N/A"
                print(f"  Attendance %:     {att}")
                print(f"  Grade Trend:      {rec.get('grade_trend', '')}")
                print(f"  Behaviour Count:  {rec.get('behaviour_count', '')}")
                print(f"  Recommended:      {rec.get('recommended_action', '')}")
                print(f"  Action Taken:     {rec.get('action_taken', '')}")
                print(f"  Resolved:         {'Yes' if rec.get('resolved') else 'No'}")
                print(f"  Created:          {rec.get('created_at', '')}")
            except ValueError:
                print("  Invalid ID.")

        elif choice == "3":
            try:
                sid = int(input("  Student ID: ").strip())
                atype = input("  Alert type (attendance/grades/behaviour/engagement/welfare): ").strip() or "attendance"
                severity = input("  Severity (low/medium/high/critical) [medium]: ").strip() or "medium"
                source = input("  Trigger source: ").strip() or None
                detail = input("  Trigger detail: ").strip() or None
                att = input("  Attendance %: ").strip()
                action = input("  Recommended action: ").strip() or None
                rec = svc.create_alert(
                    sid, atype, severity=severity,
                    trigger_source=source, trigger_detail=detail,
                    attendance_pct=float(att) if att else None,
                    recommended_action=action)
                print(f"\n  Alert #{rec['id']} created.")
            except ValueError:
                print("  Invalid input.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "4":
            try:
                aid = int(input("  Alert ID to update: ").strip())
                rec = svc.get_alert(aid)
                if not rec:
                    print("  Alert not found.")
                    continue
                print("  (Press Enter to keep current value)")
                kwargs = {}
                sev = input(f"  Severity [{rec.get('severity', '')}]: ").strip()
                if sev:
                    kwargs["severity"] = sev
                action = input(f"  Recommended Action: ").strip()
                if action:
                    kwargs["recommended_action"] = action
                taken = input(f"  Action Taken: ").strip()
                if taken:
                    kwargs["action_taken"] = taken
                if kwargs:
                    svc.update_alert(aid, **kwargs)
                    print("  Alert updated.")
                else:
                    print("  Nothing to update.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "5":
            try:
                aid = int(input("  Alert ID to resolve: ").strip())
                action = input("  Action taken: ").strip()
                if not action:
                    print("  Action taken is required.")
                    continue
                svc.resolve_alert(aid, action)
                print("  Alert resolved.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "6":
            try:
                aid = int(input("  Alert ID to delete: ").strip())
                confirm = input(f"  Delete alert #{aid}? (y/n): ").strip().lower()
                if confirm == "y":
                    svc.delete_alert(aid)
                    print("  Alert deleted.")
                else:
                    print("  Cancelled.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "7":
            rules = svc.list_rules()
            for r in rules:
                active = "Active" if r.get("is_active") else "Inactive"
                print(f"  [{r['id']}] {r.get('rule_name', '')} | "
                      f"{r.get('rule_type', '')} {r.get('comparison', '')} "
                      f"{r.get('threshold', '')} | {r.get('severity', '')} | {active}")
            if not rules:
                print("  No rules defined.")

        elif choice == "8":
            try:
                name = input("  Rule Name: ").strip()
                rtype = input("  Rule type (attendance_pct/grade_avg/behaviour_incidents): ").strip()
                thresh = float(input("  Threshold: ").strip())
                comp = input("  Comparison (less_than/greater_than/equals) [less_than]: ").strip() or "less_than"
                severity = input("  Severity (low/medium/high/critical) [medium]: ").strip() or "medium"
                role = input("  Auto-assign role: ").strip() or None
                rec = svc.create_rule(name, rtype, thresh,
                                       comparison=comp, severity=severity,
                                       auto_assign_role=role)
                print(f"\n  Rule #{rec['id']} created.")
            except ValueError:
                print("  Invalid input.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "9":
            try:
                rid = int(input("  Rule ID to update: ").strip())
                rec = svc.get_rule(rid)
                if not rec:
                    print("  Rule not found.")
                    continue
                kwargs = {}
                thresh = input(f"  Threshold [{rec.get('threshold', '')}]: ").strip()
                if thresh:
                    kwargs["threshold"] = float(thresh)
                sev = input(f"  Severity [{rec.get('severity', '')}]: ").strip()
                if sev:
                    kwargs["severity"] = sev
                active = input(f"  Active [{rec.get('is_active', '')}] (y/n): ").strip().lower()
                if active in ("y", "n"):
                    kwargs["is_active"] = 1 if active == "y" else 0
                if kwargs:
                    svc.update_rule(rid, **kwargs)
                    print("  Rule updated.")
                else:
                    print("  Nothing to update.")
            except ValueError:
                print("  Invalid input.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "10":
            try:
                rid = int(input("  Rule ID to delete: ").strip())
                confirm = input(f"  Delete rule #{rid}? (y/n): ").strip().lower()
                if confirm == "y":
                    svc.delete_rule(rid)
                    print("  Rule deleted.")
                else:
                    print("  Cancelled.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "11":
            try:
                stats = svc.get_stats()
                print(f"\n  Total Alerts:      {stats['total_alerts']}")
                print(f"  Active:            {stats['active_alerts']}")
                print(f"  Resolved:          {stats['resolved_alerts']}")
                print(f"  Active Rules:      {stats['active_rules']}")
                by_sev = stats.get("active_by_severity", {})
                if by_sev:
                    print("\n  Active by Severity:")
                    for k, v in by_sev.items():
                        print(f"    {k}: {v}")
                by_type = stats.get("active_by_type", {})
                if by_type:
                    print("\n  Active by Type:")
                    for k, v in by_type.items():
                        print(f"    {k}: {v}")
            except Exception as e:
                print(f"\n  Error: {e}")

        else:
            print("\n  Invalid option.")
