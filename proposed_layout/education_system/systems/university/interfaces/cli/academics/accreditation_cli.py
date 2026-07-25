"""Accreditation Support CLI menu.

Provides a command-line interface for managing accreditation documents,
scheduling reviews, and maintaining accreditation standards.
"""

import logging
import uuid
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
#  Table initialisation
# ------------------------------------------------------------------ #

def _ensure_tables():
    """Create accreditation tables if they do not already exist."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accreditation_documents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                path TEXT NOT NULL,
                upload_date TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accreditation_reviews (
                id TEXT PRIMARY KEY,
                review_date TEXT NOT NULL,
                review_time TEXT NOT NULL,
                reviewer TEXT NOT NULL,
                created_on TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accreditation_standards (
                id TEXT PRIMARY KEY,
                standard_text TEXT NOT NULL,
                description TEXT,
                last_updated TEXT NOT NULL
            )
        ''')
        conn.commit()
    except Exception as e:
        logger.error("Error creating accreditation tables: %s", e)
        raise
    finally:
        conn.close()


# ------------------------------------------------------------------ #
#  Public entry point
# ------------------------------------------------------------------ #

def display_accreditation_menu(auth=None):
    """Display the accreditation support CLI menu."""
    _ensure_tables()

    while True:
        print("\n" + "=" * 60)
        print("      ACCREDITATION SUPPORT")
        print("=" * 60)

        print("1. Upload Accreditation Document")
        print("2. View Accreditation Documents")
        print("3. Schedule Accreditation Review")
        print("4. View Scheduled Reviews")
        print("5. Manage Accreditation Standards")
        print("6. Return to Main Menu")

        print("=" * 60)
        choice = input("\nEnter your choice: ").strip()

        if choice == "1":
            _upload_document()
        elif choice == "2":
            _view_documents()
        elif choice == "3":
            _schedule_review()
        elif choice == "4":
            _view_reviews()
        elif choice == "5":
            _manage_standards()
        elif choice == "6":
            break
        else:
            print("Invalid choice. Please try again.")


# ------------------------------------------------------------------ #
#  Document operations
# ------------------------------------------------------------------ #

def _upload_document():
    """Upload a new accreditation document record."""
    print("\n--- Upload Accreditation Document ---")

    title = input("Enter document title: ").strip()
    if not title:
        print("Document title is required.")
        input("Press Enter to continue...")
        return

    path = input("Enter document file path: ").strip()
    if not path:
        print("Document file path is required.")
        input("Press Enter to continue...")
        return

    doc_id = str(uuid.uuid4())
    upload_date = datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO accreditation_documents (id, title, path, upload_date) "
            "VALUES (?, ?, ?, ?)",
            (doc_id, title, path, upload_date),
        )
        conn.commit()
        print(f"\nAccreditation document uploaded successfully (ID: {doc_id}).")
    except Exception as e:
        logger.error("Error uploading accreditation document: %s", e)
        print(f"\nError uploading document: {e}")
    finally:
        conn.close()

    input("Press Enter to continue...")


def _view_documents():
    """View all accreditation documents."""
    print("\n--- Accreditation Documents ---")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, title, path, upload_date FROM accreditation_documents "
            "ORDER BY upload_date DESC"
        )
        documents = cursor.fetchall()

        if not documents:
            print("\nNo accreditation documents found.")
            input("Press Enter to continue...")
            return

        print(f"\nTotal documents: {len(documents)}\n")
        print(f"{'ID':<40}{'Title':<30}{'Path':<30}{'Uploaded':<12}")
        print("-" * 112)
        for doc in documents:
            print(f"{doc[0]:<40}{doc[1]:<30}{doc[2]:<30}{doc[3]:<12}")
    except Exception as e:
        logger.error("Error viewing accreditation documents: %s", e)
        print(f"\nError retrieving documents: {e}")
    finally:
        conn.close()

    input("\nPress Enter to continue...")


# ------------------------------------------------------------------ #
#  Review operations
# ------------------------------------------------------------------ #

def _schedule_review():
    """Schedule a new accreditation review."""
    print("\n--- Schedule Accreditation Review ---")

    review_date = input("Enter review date (YYYY-MM-DD): ").strip()
    if not review_date:
        print("Review date is required.")
        input("Press Enter to continue...")
        return

    review_time = input("Enter review time (HH:MM): ").strip()
    if not review_time:
        print("Review time is required.")
        input("Press Enter to continue...")
        return

    reviewer = input("Enter reviewer name: ").strip()
    if not reviewer:
        print("Reviewer name is required.")
        input("Press Enter to continue...")
        return

    review_id = str(uuid.uuid4())
    created_on = datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO accreditation_reviews (id, review_date, review_time, reviewer, created_on) "
            "VALUES (?, ?, ?, ?, ?)",
            (review_id, review_date, review_time, reviewer, created_on),
        )
        conn.commit()
        print(f"\nAccreditation review scheduled successfully (ID: {review_id}).")
    except Exception as e:
        logger.error("Error scheduling accreditation review: %s", e)
        print(f"\nError scheduling review: {e}")
    finally:
        conn.close()

    input("Press Enter to continue...")


def _view_reviews():
    """View all scheduled accreditation reviews."""
    print("\n--- Scheduled Accreditation Reviews ---")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, review_date, review_time, reviewer, created_on "
            "FROM accreditation_reviews ORDER BY review_date ASC"
        )
        reviews = cursor.fetchall()

        if not reviews:
            print("\nNo accreditation reviews scheduled.")
            input("Press Enter to continue...")
            return

        print(f"\nTotal reviews: {len(reviews)}\n")
        print(
            f"{'ID':<40}{'Date':<14}{'Time':<10}"
            f"{'Reviewer':<25}{'Created On':<12}"
        )
        print("-" * 101)
        for r in reviews:
            print(f"{r[0]:<40}{r[1]:<14}{r[2]:<10}{r[3]:<25}{r[4]:<12}")
    except Exception as e:
        logger.error("Error viewing accreditation reviews: %s", e)
        print(f"\nError retrieving reviews: {e}")
    finally:
        conn.close()

    input("\nPress Enter to continue...")


# ------------------------------------------------------------------ #
#  Standards operations
# ------------------------------------------------------------------ #

def _manage_standards():
    """Sub-menu for managing accreditation standards."""
    while True:
        print("\n--- Manage Accreditation Standards ---")
        print("1. Add a New Standard")
        print("2. View All Standards")
        print("3. Update a Standard")
        print("4. Return to Accreditation Menu")

        choice = input("\nEnter your choice: ").strip()

        if choice == "1":
            _add_standard()
        elif choice == "2":
            _view_standards()
        elif choice == "3":
            _update_standard()
        elif choice == "4":
            break
        else:
            print("Invalid choice. Please try again.")


def _add_standard():
    """Add a new accreditation standard."""
    print("\n--- Add Accreditation Standard ---")

    name = input("Enter standard name: ").strip()
    if not name:
        print("Standard name is required.")
        input("Press Enter to continue...")
        return

    description = input("Enter description: ").strip()

    standard_id = str(uuid.uuid4())
    added_on = datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO accreditation_standards (id, standard_text, description, last_updated) "
            "VALUES (?, ?, ?, ?)",
            (standard_id, name, description, added_on),
        )
        conn.commit()
        print(f"\nAccreditation standard added successfully (ID: {standard_id}).")
    except Exception as e:
        logger.error("Error adding accreditation standard: %s", e)
        print(f"\nError adding standard: {e}")
    finally:
        conn.close()

    input("Press Enter to continue...")


def _view_standards():
    """View all accreditation standards."""
    print("\n--- Accreditation Standards ---")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, standard_text, description, last_updated "
            "FROM accreditation_standards ORDER BY last_updated DESC"
        )
        standards = cursor.fetchall()

        if not standards:
            print("\nNo accreditation standards found.")
            input("Press Enter to continue...")
            return

        print(f"\nTotal standards: {len(standards)}\n")
        print(f"{'#':<4}{'ID':<40}{'Name':<30}{'Description':<30}{'Updated':<12}")
        print("-" * 116)
        for idx, s in enumerate(standards, 1):
            desc = (s[2] or "")[:28]
            print(f"{idx:<4}{s[0]:<40}{s[1]:<30}{desc:<30}{s[3]:<12}")
    except Exception as e:
        logger.error("Error viewing accreditation standards: %s", e)
        print(f"\nError retrieving standards: {e}")
    finally:
        conn.close()

    input("\nPress Enter to continue...")


def _update_standard():
    """Update an existing accreditation standard."""
    print("\n--- Update Accreditation Standard ---")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, standard_text, description, last_updated "
            "FROM accreditation_standards ORDER BY last_updated DESC"
        )
        standards = cursor.fetchall()

        if not standards:
            print("\nNo accreditation standards available to update.")
            input("Press Enter to continue...")
            return

        print("\nSelect a standard to update:")
        for idx, s in enumerate(standards, 1):
            print(f"  {idx}. {s[1]}")

        choice_str = input("\nEnter the number of the standard to update (or 0 to cancel): ").strip()
        try:
            choice = int(choice_str)
        except ValueError:
            print("Invalid input. Update cancelled.")
            input("Press Enter to continue...")
            return

        if choice == 0:
            print("Update cancelled.")
            input("Press Enter to continue...")
            return

        if choice < 1 or choice > len(standards):
            print("Invalid selection.")
            input("Press Enter to continue...")
            return

        selected = standards[choice - 1]
        print(f"\nCurrent name: {selected[1]}")
        print(f"Current description: {selected[2] or '(none)'}")
        print("\nLeave fields blank to keep current values.")

        new_name = input("New name: ").strip()
        new_description = input("New description: ").strip()

        if not new_name and not new_description:
            print("No changes made.")
            input("Press Enter to continue...")
            return

        updates = []
        params = []

        if new_name:
            updates.append("standard_text = ?")
            params.append(new_name)
        if new_description:
            updates.append("description = ?")
            params.append(new_description)

        updates.append("last_updated = ?")
        params.append(datetime.now().strftime("%Y-%m-%d"))
        params.append(selected[0])

        query = f"UPDATE accreditation_standards SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, tuple(params))
        conn.commit()
        print("\nAccreditation standard updated successfully.")
    except Exception as e:
        logger.error("Error updating accreditation standard: %s", e)
        print(f"\nError updating standard: {e}")
    finally:
        conn.close()

    input("Press Enter to continue...")
