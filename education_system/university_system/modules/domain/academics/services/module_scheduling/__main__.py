# Entry point
if __name__ == "__main__":
    from .core import ModuleScheduler
    from .menus import display_enhanced_scheduling_menu, display_main_menu_info, handle_graceful_exit

    try:
        # Display welcome information
        display_main_menu_info()

        # Initialize system
        print("\n🚀 Initializing system...")
        scheduler = ModuleScheduler()

        # Create automatic backup on startup if enabled
        auto_backup = scheduler.get_system_setting('auto_backup', 'True')
        if auto_backup == 'True':
            print("💾 Creating startup backup...")
            scheduler.create_backup(description="Automatic startup backup")

        # Quick system health check
        print("🔍 Performing system health check...")
        issues = scheduler.validate_data_consistency()
        if issues:
            print(f"⚠️  Found {len(issues)} data issues. Consider running data validation.")
        else:
            print("✅ System health check passed.")

        print("🎯 System ready!")

        # Run the enhanced menu system
        display_enhanced_scheduling_menu()

    except KeyboardInterrupt:
        print("\n\n⏹️  System interrupted by user.")
    except Exception as e:
        print(f"\n❌ Critical error: {e}")
        print("Please check your database file and try again.")
    finally:
        # Always perform graceful exit
        handle_graceful_exit()
