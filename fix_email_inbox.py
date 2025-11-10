#!/usr/bin/env python3
"""Fix missing inbox messages from stored emails"""

import sys
import os

# Add project root to path
sys.path.insert(0, '/home/seancatchpole989')

from university_system.infrastructure.email.email_service import fix_inbox_display_issue

if __name__ == "__main__":
    print("=" * 60)
    print("FIXING MISSING INBOX MESSAGES")
    print("=" * 60)
    print("\nThis script will sync emails from 'stored_emails' table")
    print("to the 'messages' (inbox) table for recipients.\n")

    try:
        fixed_count = fix_inbox_display_issue()
        print(f"\n✅ SUCCESS: Fixed {fixed_count} missing inbox messages!")
        print("\nUsers should now be able to see all their emails in their inbox.")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
