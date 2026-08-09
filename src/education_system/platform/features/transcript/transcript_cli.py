"""Digital Transcript — CLI module.

Text-based menu:
  1) Search student
  2) Generate full transcript
  3) Generate summary
  4) Save to file
  0) Back
"""

from education_system.platform.features.transcript.transcript_service import (
    TranscriptService,
    SYSTEM_LABELS,
)


def run(db_path=None, auth=None):
    """Entry point for the CLI transcript menu."""
    service = TranscriptService()
    last_transcript_text = None
    last_student_name = None

    while True:
        print("\n===== Digital Transcript =====")
        print("1) Search student")
        print("2) Generate full transcript")
        print("3) Generate summary")
        print("4) Save to file")
        print("0) Back")

        choice = input("\nChoice: ").strip()

        if choice == "1":
            last_student_name = _search(service)
        elif choice == "2":
            last_transcript_text, last_student_name = _generate(service, last_student_name)
        elif choice == "3":
            _summary(service, last_student_name)
        elif choice == "4":
            _save(service, last_transcript_text)
        elif choice == "0":
            break
        else:
            print("Invalid choice.")


def _search(service):
    """Search for students across systems. Returns selected name or None."""
    query = input("Student name: ").strip()
    if not query:
        print("No name entered.")
        return None

    try:
        results = service.search_students(query)
    except Exception as exc:
        print(f"Error: {exc}")
        return None

    if not results:
        print("No students found.")
        return None

    print(f"\n{'#':<4} {'System':<20} {'ID':<12} {'Name':<25} {'Year':<10} {'Status'}")
    print("-" * 85)
    for i, r in enumerate(results, 1):
        sys_label = SYSTEM_LABELS.get(r["system"], r["system"])
        print(
            f"{i:<4} {sys_label:<20} {r.get('student_id',''):<12} "
            f"{r.get('name',''):<25} {r.get('year_group',''):<10} "
            f"{r.get('status','')}"
        )

    sel = input("\nSelect # (or Enter to skip): ").strip()
    if sel.isdigit() and 1 <= int(sel) <= len(results):
        name = results[int(sel) - 1].get("name", "")
        print(f"Selected: {name}")
        return name

    return None


def _generate(service, student_name=None):
    """Generate and display a full transcript. Returns (text, name)."""
    if not student_name:
        student_name = input("Student name: ").strip()
    if not student_name:
        print("No student name provided.")
        return None, None

    print(f"\nGenerating transcript for: {student_name} ...")
    try:
        transcript = service.generate_transcript(student_name)
        text = service.format_transcript(transcript)
        print()
        print(text)
        return text, student_name
    except Exception as exc:
        print(f"Error: {exc}")
        return None, student_name


def _summary(service, student_name=None):
    """Generate and display a summary."""
    if not student_name:
        student_name = input("Student name: ").strip()
    if not student_name:
        print("No student name provided.")
        return

    try:
        summary = service.get_transcript_summary(student_name)
        print(f"\nSummary:\n{summary}")
    except Exception as exc:
        print(f"Error: {exc}")


def _save(service, text):
    """Save the last generated transcript to a file."""
    if not text:
        print("No transcript generated yet. Generate one first (option 2).")
        return

    path = input("Output file path: ").strip()
    if not path:
        print("No path provided.")
        return

    try:
        service.save_transcript(text, path)
        print(f"Transcript saved to: {path}")
    except Exception as exc:
        print(f"Error: {exc}")
