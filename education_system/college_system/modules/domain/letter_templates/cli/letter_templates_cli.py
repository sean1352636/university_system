"""Letter Templates CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.letter_templates.services.letter_templates_service import LetterTemplateService
from education_system.college_system.infrastructure.auth.core import UserAuth


def letter_templates_menu(auth: UserAuth):
    """Letter Templates management menu."""
    svc = LetterTemplateService(auth._db_path)

    while True:
        print_header("Letter Templates")
        options = [
            ("1", "List Templates"),
            ("2", "View Template"),
            ("3", "New Template"),
            ("4", "Update Template"),
            ("5", "Toggle Active"),
            ("6", "Delete Template"),
            ("7", "List Letters"),
            ("8", "Generate Letter"),
            ("9", "View Letter"),
            ("10", "Mark Sent"),
            ("11", "Delete Letter"),
            ("12", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break

        elif choice == "1":
            cat = input("  Category (or Enter for all): ").strip() or None
            search = input("  Search (or Enter to skip): ").strip() or None
            templates = svc.list_templates(category=cat, search=search)
            for t in templates:
                active = "active" if t.get("is_active") else "inactive"
                print(f"  [{t['id']}] {t['template_name']} "
                      f"({t.get('category', '')}) [{active}]")
            if not templates:
                print("  No templates found.")

        elif choice == "2":
            try:
                tid = int(input("  Template ID: ").strip())
                t = svc.get_template(tid)
                if t:
                    active = "Yes" if t.get("is_active") else "No"
                    print(f"\n  ID:           {t['id']}")
                    print(f"  Name:         {t['template_name']}")
                    print(f"  Category:     {t.get('category', '')}")
                    print(f"  Subject:      {t.get('subject_line', '')}")
                    print(f"  Active:       {active}")
                    print(f"  Merge Fields: {t.get('merge_fields', '')}")
                    print(f"  Created:      {t.get('created_at', '')}")
                    print(f"  Updated:      {t.get('updated_at', '')}")
                    print(f"  Body:\n{t.get('body_template', '')}")
                else:
                    print("  Template not found.")
            except ValueError:
                print("\n  Invalid ID.")

        elif choice == "3":
            try:
                name = input("  Template Name: ").strip()
                category = input("  Category [general]: ").strip() or "general"
                subject = input("  Subject Line: ").strip()
                merge = input("  Merge Fields (comma-separated): ").strip()
                print("  Body (enter blank line to finish):")
                body_lines = []
                while True:
                    line = input()
                    if line == "":
                        break
                    body_lines.append(line)
                body = "\n".join(body_lines)
                t = svc.create_template(
                    template_name=name,
                    body_template=body,
                    category=category,
                    subject_line=subject,
                    merge_fields=merge,
                )
                print(f"\n  Template #{t['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "4":
            try:
                tid = int(input("  Template ID: ").strip())
                name = input("  New Name (Enter to skip): ").strip() or None
                category = input("  New Category (Enter to skip): ").strip() or None
                subject = input("  New Subject (Enter to skip): ").strip() or None
                merge = input("  New Merge Fields (Enter to skip): ").strip() or None
                print("  New Body (Enter blank line to skip/finish):")
                body_lines = []
                while True:
                    line = input()
                    if line == "":
                        break
                    body_lines.append(line)
                body = "\n".join(body_lines) if body_lines else None
                kwargs = {}
                if name:
                    kwargs["template_name"] = name
                if category:
                    kwargs["category"] = category
                if subject:
                    kwargs["subject_line"] = subject
                if merge:
                    kwargs["merge_fields"] = merge
                if body:
                    kwargs["body_template"] = body
                if kwargs:
                    svc.update_template(tid, **kwargs)
                    print("  Template updated.")
                else:
                    print("  Nothing to update.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "5":
            try:
                tid = int(input("  Template ID: ").strip())
                t = svc.toggle_active(tid)
                status = "active" if t.get("is_active") else "inactive"
                print(f"  Template #{tid} is now {status}.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "6":
            try:
                tid = int(input("  Template ID: ").strip())
                confirm = input("  Delete template and all its letters? (y/n): ").strip().lower()
                if confirm == "y":
                    svc.delete_template(tid)
                    print("  Template deleted.")
                else:
                    print("  Cancelled.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "7":
            status = input("  Status filter (or Enter for all): ").strip() or None
            tid = input("  Template ID filter (or Enter for all): ").strip()
            tid = int(tid) if tid else None
            letters = svc.list_letters(template_id=tid, status=status)
            for lt in letters:
                print(f"  [{lt['id']}] {lt.get('template_name', '')} -> "
                      f"{lt.get('recipient_name', '')} "
                      f"({lt.get('status', '')}) via {lt.get('sent_via', '')}")
            if not letters:
                print("  No letters found.")

        elif choice == "8":
            try:
                tid = int(input("  Template ID: ").strip())
                rname = input("  Recipient Name: ").strip()
                rtype = input("  Recipient Type [student]: ").strip() or "student"
                subject = input("  Subject: ").strip()
                via = input("  Sent Via [email]: ").strip() or "email"
                print("  Body (enter blank line to finish):")
                body_lines = []
                while True:
                    line = input()
                    if line == "":
                        break
                    body_lines.append(line)
                body = "\n".join(body_lines)
                lt = svc.generate_letter(
                    template_id=tid,
                    recipient_name=rname,
                    body=body,
                    recipient_type=rtype,
                    subject=subject,
                    sent_via=via,
                )
                print(f"\n  Letter #{lt['id']} generated.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "9":
            try:
                lid = int(input("  Letter ID: ").strip())
                lt = svc.get_letter(lid)
                if lt:
                    print(f"\n  ID:           {lt['id']}")
                    print(f"  Template:     {lt.get('template_name', '')}")
                    print(f"  Recipient:    {lt.get('recipient_name', '')}")
                    print(f"  Type:         {lt.get('recipient_type', '')}")
                    print(f"  Subject:      {lt.get('subject', '')}")
                    print(f"  Sent Via:     {lt.get('sent_via', '')}")
                    print(f"  Status:       {lt.get('status', '')}")
                    print(f"  Sent At:      {lt.get('sent_at', 'N/A')}")
                    print(f"  Created:      {lt.get('created_at', '')}")
                    print(f"  Body:\n{lt.get('body', '')}")
                else:
                    print("  Letter not found.")
            except ValueError:
                print("\n  Invalid ID.")

        elif choice == "10":
            try:
                lid = int(input("  Letter ID: ").strip())
                via = input("  Sent Via [email]: ").strip() or "email"
                lt = svc.mark_sent(lid, sent_via=via)
                print(f"  Letter #{lid} marked as sent via {via}.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "11":
            try:
                lid = int(input("  Letter ID: ").strip())
                confirm = input("  Delete this letter? (y/n): ").strip().lower()
                if confirm == "y":
                    svc.delete_letter(lid)
                    print("  Letter deleted.")
                else:
                    print("  Cancelled.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "12":
            try:
                stats = svc.get_stats()
                print(f"\n  Total Templates:  {stats['total_templates']}")
                print(f"    Active:         {stats['active_templates']}")
                print(f"    Inactive:       {stats['inactive_templates']}")
                print(f"  Total Letters:    {stats['total_letters']}")
                print("  Letters by Status:")
                for s, c in stats.get("by_status", {}).items():
                    print(f"    {s:<16} {c}")
                print("  Templates by Category:")
                for cat, c in stats.get("by_category", {}).items():
                    print(f"    {cat:<16} {c}")
            except Exception as e:
                print(f"\n  Error: {e}")

        else:
            print("\n  Invalid option.")
