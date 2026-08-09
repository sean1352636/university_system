"""Component extracted from the legacy menu router."""
from __future__ import annotations
from ..bootstrap.integrations import ValidationError

def display_accessibility_tools_menu(auth):
    """Display the Accessibility & Accommodation Tools CLI menu"""
    print("\n" + "="*50)
    print("  ACCESSIBILITY & ACCOMMODATION TOOLS")
    print("="*50)
    print("1. Manage Accommodation Requests")
    print("2. Accessibility Profiles")
    print("3. Assistive Technology Settings")
    print("4. Document Formats & Conversions")
    print("5. Captioning & Transcripts")
    print("6. Testing Accommodations")
    print("7. Compliance Audits")
    print("8. Return to Main Menu")
    print("="*50)

    while True:
        try:
            choice = input("\nEnter your choice (1-8): ").strip()
            if choice in ['1', '2', '3', '4', '5', '6', '7']:
                print("\n♿ Accessibility feature - Database tables available")
                print("Database tables: accommodation_requests, accommodation_approvals,")
                print("accessibility_profiles, assistive_technology, document_formats,")
                print("captioning_requests, testing_accommodations, accessibility_audits,")
                print("accommodation_documentation")
                print("\nAccess via SQL or create manager following existing patterns.")
            elif choice == '8':
                break
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            break
        except (ValueError, TypeError, ValidationError) as e:
            print(f"❌ Error: {e}")
