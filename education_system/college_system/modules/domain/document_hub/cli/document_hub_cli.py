"""CLI interface for document hub management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.document_hub.services.document_hub_service import DocumentHubService
from education_system.college_system.infrastructure.auth.core import UserAuth


def document_hub_menu(auth: UserAuth):
    """Document Hub management menu."""
    service = DocumentHubService(auth._db_path)

    while True:
        print_header("Document Hub")
        options = [
            ("1", "List Documents"),
            ("2", "Add Document"),
            ("3", "View Document"),
            ("4", "Update Document"),
            ("5", "Delete Document"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_documents(service)
        elif choice == "2":
            _add_document(service)
        elif choice == "3":
            _view_document(service)
        elif choice == "4":
            _update_document(service)
        elif choice == "5":
            _delete_document(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_documents(service):
    print_header("List Documents")
    try:
        items = service.list_documents()
        if not items:
            print("\n  No documents found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Title':<25}" + f"{'Category':<15}" + f"{'File':<25}" + f"{'Type':<10}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('title', '') or '')[:20].ljust(25) + str(item.get('category', '') or '')[:20].ljust(15) + str(item.get('file_path', '') or '')[:20].ljust(25) + str(item.get('file_type', '') or '')[:20].ljust(10))
        print(f"\n  Total: {len(items)} documents")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_document(service):
    print_header("Add Document")
    try:
        data = {}
        for field in ['title', 'category', 'file_path', 'file_type', 'file_size']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_document(**data)
        print(f"\n  Document created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_document(service):
    print_header("View Document")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_document(pk)
        if not item:
            print("\n  Document not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_document(service):
    print_header("Update Document")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_document(pk)
        if not item:
            print("\n  Document not found.")
            return
        data = {}
        for field in ['title', 'category', 'file_path', 'file_type', 'file_size']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_document(pk, **data)
            print(f"\n  Document updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_document(service):
    print_header("Delete Document")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete document {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_document(pk)
            print(f"\n  Document deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
