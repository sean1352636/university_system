"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def handle_graceful_exit():
    """Handle graceful system exit with cleanup"""
    print("\n" + "="*60)
    print("🔄 Performing final system checks...")

    try:
        scheduler = ModuleScheduler()

        # Create exit backup if auto-backup is enabled
        auto_backup = scheduler.get_system_setting('auto_backup', 'True')
        if auto_backup == 'True':
            print("💾 Creating exit backup...")
            scheduler.create_backup(description="Automatic exit backup")

        # Quick data validation
        print("🔍 Running quick data validation...")
        issues = scheduler.validate_data_consistency()
        if issues:
            print(f"⚠️  Warning: {len(issues)} data consistency issues detected.")
            print("   Run data validation from the main menu for details.")
        else:
            print("✅ Data validation passed.")

        # Check for unresolved conflicts
        conflicts = scheduler._get_all_conflicts()
        active_conflicts = [c for c in conflicts if not c['resolved']]
        if active_conflicts:
            print(f"⚠️  Warning: {len(active_conflicts)} unresolved scheduling conflicts.")
        else:
            print("✅ No scheduling conflicts detected.")

        print("✅ System shutdown complete.")

    except Exception as e:
        print(f"❌ Error during shutdown: {e}")

    print("=" * 60)
    print("Thank you for using the Enhanced Module Scheduling System!")
    print("Have a great day! 🌟")
    print("=" * 60)
