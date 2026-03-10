"""CLI interface for attachments management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.attachments.services.attachments_service import AttachmentService
from education_system.college_system.infrastructure.auth.core import UserAuth


def attachments_menu(auth: UserAuth):
    """Attachments management menu."""
    service = AttachmentService(auth._db_path)

    while True:
        print_header("Attachments")
        options = [
            ("1", "List Attachments"),
            ("2", "Add Attachment"),
            ("3", "View Attachment"),
            ("4", "Update Attachment"),
            ("5", "Delete Attachment"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_attachments(service)
        elif choice == "2":
            _add_attachment(service)
        elif choice == "3":
            _view_attachment(service)
        elif choice == "4":
            _update_attachment(service)
        elif choice == "5":
            _delete_attachment(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_attachments(service):
    print_header("List Attachments")
    try:
        items = service.list_attachments()
        if not items:
            print("\n  No attachments found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Uploaded By':<10}" + f"{'Filename':<25}" + f"{'Original':<25}" + f"{'Path':<25}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('uploaded_by', '') or '')[:20].ljust(10) + str(item.get('filename', '') or '')[:20].ljust(25) + str(item.get('original_filename', '') or '')[:20].ljust(25) + str(item.get('file_path', '') or '')[:20].ljust(25))
        print(f"\n  Total: {len(items)} attachments")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_attachment(service):
    print_header("Add Attachment")
    try:
        data = {}
        for field in ['uploaded_by', 'filename', 'original_filename', 'file_path', 'file_type']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_attachment(**data)
        print(f"\n  Attachment created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_attachment(service):
    print_header("View Attachment")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_attachment(pk)
        if not item:
            print("\n  Attachment not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_attachment(service):
    print_header("Update Attachment")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_attachment(pk)
        if not item:
            print("\n  Attachment not found.")
            return
        data = {}
        for field in ['uploaded_by', 'filename', 'original_filename', 'file_path', 'file_type']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_attachment(pk, **data)
            print(f"\n  Attachment updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_attachment(service):
    print_header("Delete Attachment")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete attachment {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_attachment(pk)
            print(f"\n  Attachment deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
