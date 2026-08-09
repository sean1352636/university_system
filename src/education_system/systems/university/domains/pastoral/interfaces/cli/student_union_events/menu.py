"""Workflow extracted from the legacy event-management module."""
from __future__ import annotations
from education_system.systems.university.domains.pastoral.domain.student_life.student_union.events.application.ports import (
    AcademicCalendarManager, DatabaseManager, HAS_AUTH, UserAuth, datetime,
    get_connection, get_events_support_phone, os, random,
    send_confirmation_email, set_auth_instance, sqlite3, string,
)
from education_system.systems.university.domains.pastoral.interfaces.cli.student_union_events.context import auth
from education_system.systems.university.domains.pastoral.interfaces.cli.student_union_events.catalogue import view_events
from education_system.systems.university.domains.pastoral.interfaces.cli.student_union_events.context import auth
from education_system.systems.university.domains.pastoral.interfaces.cli.student_union_events.registrations import register_for_event, view_my_events

def display_event_menu():
    """Display the event management menu"""
    global auth

    while True:
        print("\nEvents")
        print("======")

        # Options
        print("1. View Upcoming Events")
        print("2. View My Registered Events")

        if auth.check_permission('register_for_events'):
            print("3. Register for an Event")
            print("4. Return to Student Union Menu")
            max_option = 4
        else:
            print("3. Return to Student Union Menu")
            max_option = 3

        choice = input("\nEnter your choice: ")

        if choice == '1':
            # View Events
            view_events()
        elif choice == '2':
            # View My Events
            view_my_events()
        elif choice == '3' and auth.check_permission('register_for_events'):
            # Register for Event
            register_for_event()
        elif choice == str(max_option):
            # Return to Student Union Menu
            return
        else:
            print("Invalid choice. Please try again.")
