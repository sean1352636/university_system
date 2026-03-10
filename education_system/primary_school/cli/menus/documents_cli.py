"""Documents CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def documents_menu(auth):
    """Documents management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.admin.documents.services.document_service import DocumentService

    svc = DocumentService(get_db_path())

    while True:
        print_header("Documents")
        print_menu([
            ("1", "List documents"),
            ("2", "View details"),
            ("3", "Add Document"),
            ("4", "Update Document"),
            ("5", "Delete Document"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_documents()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_document(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            title = input("  Title: ").strip()
            document_type = input("  Document Type: ").strip()
            try:
                svc.create_document(title=title, document_type=document_type)
                print("\n  Document created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            title = input("  Title: ").strip()
            document_type = input("  Document Type: ").strip()
            try:
                svc.update_document(int(pk), title=title, document_type=document_type)
                print("\n  Document updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_document(int(pk))
                print("\n  Document deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
