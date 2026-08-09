"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_main_menu_info():
    """Display welcome information and system status"""
    print("\n🎓 Enhanced Module Scheduling System")
    print("=" * 50)
    print("📋 Features Available:")
    print("  • Smart scheduling with conflict detection")
    print("  • Advanced analytics and reporting")
    print("  • Multiple export formats (PDF, CSV, Excel, iCal)")
    print("  • Room and instructor management")
    print("  • Visual timetables and charts")
    print("  • Backup and data validation")
    print("  • Holiday management")
    print("  • Notification system")
    print("=" * 50)
