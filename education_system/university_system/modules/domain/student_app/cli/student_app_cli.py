"""Student App CLI."""


def display_student_app_menu(auth):
    from education_system.university_system.modules.domain.student_app.services.student_app_service import StudentAppService
    service = StudentAppService()
    student_id = auth.current_user.get('username', 'unknown') if auth and auth.current_user else 'unknown'

    while True:
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 70)
        print("STUDENT APP".center(70))
        print("=" * 70)
        unread = service.get_unread_count(student_id)
        print(f"\n  Notifications: {unread} unread")
        print("\n  1. My Dashboard")
        print("  2. View Notifications")
        print("  3. Mark All Read")
        print("  4. Preferences")
        print("  5. Quick Links")
        print("\n  0. Back")
        print("=" * 70)

        choice = input("\nSelect: ").strip()
        if choice == '0':
            break
        elif choice == '1':
            dash = service.get_student_dashboard(student_id)
            print(f"\n  Unread notifications: {dash.get('unread_notifications', 0)}")
            if dash.get('timetable'):
                print("\n  Today's Timetable:")
                for t in dash['timetable'][:5]:
                    print(f"    {t}")
            if dash.get('grades'):
                print("\n  Recent Grades:")
                for g in dash['grades'][:5]:
                    print(f"    {g}")
            if dash.get('notifications'):
                print("\n  Recent Notifications:")
                for n in dash['notifications'][:3]:
                    print(f"    [{n.get('notification_type', '')}] {n['title']}")
        elif choice == '2':
            notifs = service.get_notifications(student_id)
            for n in notifs:
                read = "R" if n['is_read'] else "U"
                print(f"  [{read}] {n['id']}: [{n.get('notification_type', '')}] {n['title']} - {n.get('message', '')}")
            mid = input("\nMark notification ID as read (or Enter to skip): ").strip()
            if mid:
                service.mark_notification_read(int(mid))
                print("Marked as read.")
        elif choice == '3':
            count = service.mark_all_notifications_read(student_id)
            print(f"\n{count} notifications marked as read.")
        elif choice == '4':
            prefs = service.get_preferences(student_id)
            if prefs:
                print(f"\n  Theme: {prefs.get('theme', 'light')}")
                print(f"  Notifications: {'On' if prefs.get('notifications_enabled', 1) else 'Off'}")
                print(f"  Language: {prefs.get('language', 'en')}")
            if input("\nUpdate preferences? (y/n): ").strip().lower() == 'y':
                theme = input("Theme (light/dark): ").strip() or None
                lang = input("Language (en/cy/fr): ").strip() or None
                service.update_preferences(student_id, theme=theme, language=lang)
                print("Preferences updated.")
        elif choice == '5':
            links = service.get_quick_links(student_id)
            for l in links:
                print(f"  {l['id']}: {l['link_title']} -> {l['link_url']}")
            sub = input("\n(a)dd link, (r)emove link, or Enter: ").strip().lower()
            if sub == 'a':
                title = input("Title: ").strip()
                url = input("URL: ").strip()
                service.add_quick_link(student_id, title, url)
                print("Link added.")
            elif sub == 'r':
                lid = int(input("Link ID to remove: ").strip())
                service.remove_quick_link(lid)
                print("Link removed.")
        input("\nPress Enter to continue...")
