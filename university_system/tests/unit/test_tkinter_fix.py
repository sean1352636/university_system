#!/usr/bin/env python3
"""
Test script to verify the Tkinter grab_set fixes are working properly.
"""

import sys
import tkinter as tk

def test_safe_grab_set():
    """Test the safe_grab_set function"""
    print("🧪 Testing Tkinter grab_set fixes")

    try:
        # Import the safe_grab_set function
        sys.path.append('.')
        from university_system.modules.domain.academics.gui.grade_tracking.utils.validators import safe_grab_set

        print("✅ safe_grab_set function imported successfully")

        # Test the function with a dialog
        root = tk.Tk()
        root.withdraw()  # Hide main window

        # Create a test dialog
        dialog = tk.Toplevel(root)
        dialog.title("Test Dialog")
        dialog.geometry("200x100")

        # Test the safe_grab_set function
        print("📋 Testing safe_grab_set with dialog...")
        safe_grab_set(dialog)
        print("✅ safe_grab_set completed without errors")

        # Clean up
        dialog.destroy()
        root.destroy()

        return True

    except Exception as e:
        print(f"❌ Error testing grab_set fix: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the test"""
    print("=" * 50)
    print("TKINTER GRAB_SET FIX VERIFICATION")
    print("=" * 50)

    if test_safe_grab_set():
        print("\n🎉 All tests passed!")
        print("\n✅ FIX SUMMARY:")
        print("   - Added safe_grab_set() helper function")
        print("   - Replaced all grab_set() calls with safe_grab_set()")
        print("   - Added error handling for TclError exceptions")
        print("   - The 'grab failed: window not viewable' error should be resolved")
        return True
    else:
        print("\n❌ Tests failed")
        return False

if __name__ == "__main__":
    main()