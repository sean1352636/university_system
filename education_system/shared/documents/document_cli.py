"""Shared Document Storage CLI.

Text-based menu interface for managing cross-system documents:
searching, listing, uploading, viewing, and deleting documents.
"""

import os
from pathlib import Path

from education_system.shared.documents.document_service import (
    DocumentService, DOCUMENT_TYPES,
)

SYSTEM_KEYS = ["primary", "secondary", "college", "university"]
SYSTEM_LABELS = {
    "primary": "Primary School",
    "secondary": "Secondary School",
    "college": "Sixth Form College",
    "university": "University",
}


def _print_header(title):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def _print_doc(doc):
    """Print a single document's details."""
    print(f"    ID:          {doc['id']}")
    print(f"    Title:       {doc['title']}")
    print(f"    Student:     {doc['student_name']}")
    print(f"    Student ID:  {doc.get('student_id', 'N/A')}")
    print(f"    System:      {SYSTEM_LABELS.get(doc['system'], doc['system'])}")
    print(f"    Type:        {doc['doc_type']}")
    print(f"    Description: {doc.get('description', '') or 'N/A'}")
    print(f"    Uploaded by: {doc.get('uploaded_by', 'N/A')}")
    print(f"    Date:        {doc.get('created_at', 'N/A')}")
    print(f"    File:        {doc.get('file_path', 'N/A')}")
    file_path = doc.get("file_path", "")
    exists = Path(file_path).exists() if file_path else False
    print(f"    File exists: {'Yes' if exists else 'No'}")


def _search_documents(svc):
    _print_header("Search Documents")
    query = input("  Search query (title, student, or tags): ").strip()
    if not query:
        print("\n  Query is required.")
        return

    docs = svc.search_documents(query)
    if not docs:
        print("\n  No documents found.")
    else:
        print(f"\n  Found {len(docs)} document(s):\n")
        print(f"  {'ID':5s} {'Title':30s} {'Student':20s} {'Type':14s} {'System':20s} {'Date':16s}")
        print("  " + "-" * 105)
        for d in docs:
            sys_label = SYSTEM_LABELS.get(d["system"], d["system"])
            print(f"  {str(d['id']):5s} {d['title'][:30]:30s} "
                  f"{d['student_name'][:20]:20s} {d['doc_type']:14s} "
                  f"{sys_label:20s} {(d.get('created_at') or '')[:16]:16s}")
    print()


def _list_by_student(svc):
    _print_header("List Documents by Student")
    name = input("  Student name: ").strip()
    if not name:
        print("\n  Name is required.")
        return

    docs = svc.get_documents(student_name=name)
    if not docs:
        print(f"\n  No documents found for '{name}'.")
    else:
        print(f"\n  {len(docs)} document(s) for '{name}':\n")
        for d in docs:
            print(f"\n  --- Document #{d['id']} ---")
            _print_doc(d)
    print()


def _upload_document(svc):
    _print_header("Upload Document")

    student_name = input("  Student name: ").strip()
    if not student_name:
        print("\n  Student name is required.")
        return

    student_id = input("  Student ID (optional): ").strip()

    print("\n  Select system:")
    for i, key in enumerate(SYSTEM_KEYS, 1):
        print(f"    {i}) {SYSTEM_LABELS[key]}")
    sys_choice = input("  System: ").strip()
    if not sys_choice.isdigit() or not (1 <= int(sys_choice) <= len(SYSTEM_KEYS)):
        print("\n  Invalid choice.")
        return
    system = SYSTEM_KEYS[int(sys_choice) - 1]

    print("\n  Document types:")
    for i, dt in enumerate(DOCUMENT_TYPES, 1):
        print(f"    {i}) {dt}")
    type_choice = input("  Type: ").strip()
    if not type_choice.isdigit() or not (1 <= int(type_choice) <= len(DOCUMENT_TYPES)):
        print("\n  Invalid choice.")
        return
    doc_type = DOCUMENT_TYPES[int(type_choice) - 1]

    title = input("  Title: ").strip()
    if not title:
        print("\n  Title is required.")
        return

    description = input("  Description (optional): ").strip()

    file_path = input("  File path: ").strip()
    if not file_path or not Path(file_path).exists():
        print("\n  File not found.")
        return

    uploaded_by = input("  Your username: ").strip() or "cli_user"

    try:
        filename = Path(file_path).name
        doc_id = svc.upload_document(
            student_name=student_name,
            student_id=student_id,
            system=system,
            doc_type=doc_type,
            title=title,
            description=description,
            file_data=file_path,
            filename=filename,
            uploaded_by=uploaded_by,
            uploaded_system="cli",
        )
        print(f"\n  Document uploaded successfully (ID: {doc_id}).")
    except Exception as e:
        print(f"\n  Error: {e}")
    print()


def _view_document(svc):
    _print_header("View Document Info")
    doc_id_str = input("  Document ID: ").strip()
    if not doc_id_str.isdigit():
        print("\n  Invalid ID.")
        return

    doc = svc.get_document(int(doc_id_str))
    if not doc:
        print("\n  Document not found.")
    else:
        print()
        _print_doc(doc)
    print()


def _delete_document(svc):
    _print_header("Delete Document")
    doc_id_str = input("  Document ID: ").strip()
    if not doc_id_str.isdigit():
        print("\n  Invalid ID.")
        return

    doc_id = int(doc_id_str)
    doc = svc.get_document(doc_id)
    if not doc:
        print("\n  Document not found.")
        return

    print(f"\n  Document: '{doc['title']}' for {doc['student_name']}")
    confirm = input("  Are you sure you want to delete? (yes/no): ").strip().lower()
    if confirm == "yes":
        if svc.delete_document(doc_id):
            print("\n  Document deleted.")
        else:
            print("\n  Failed to delete document.")
    else:
        print("\n  Deletion cancelled.")
    print()


def run(db_path=None, auth=None):
    """Run the Shared Documents CLI menu loop."""
    svc = DocumentService()
    _print_header("Shared Documents")

    while True:
        print("\n  1) Search documents")
        print("  2) List by student")
        print("  3) Upload document")
        print("  4) View document info")
        print("  5) Delete document")
        print("  0) Back")

        choice = input("\n  Select option: ").strip()

        if choice == "1":
            _search_documents(svc)
        elif choice == "2":
            _list_by_student(svc)
        elif choice == "3":
            _upload_document(svc)
        elif choice == "4":
            _view_document(svc)
        elif choice == "5":
            _delete_document(svc)
        elif choice == "0":
            print("\n  Returning...\n")
            break
        else:
            print("\n  Invalid option. Please try again.")
