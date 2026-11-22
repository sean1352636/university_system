"""Split from cli_menus.py — assembled in package __init__.py."""
from __future__ import annotations

import sys
import json
import logging
import random
import secrets
import string
from pathlib import Path
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    DatabaseError,
)
from ._shared import is_chatbot_available

logger = logging.getLogger("education_system.systems.university.shell.cli.auth.cli_menus")

def display_chatbot_integration_menu(auth):
    """Display chatbot integration menu"""
    from education_system.systems.university.infrastructure.auth.integrations.chatbot_integration import (
        launch_chatbot_interface as _launch_chatbot,
        get_chatbot_conversation_history as _get_chatbot_history,
        generate_chatbot_analytics as _gen_chatbot_analytics,
        initialize_chatbot_integration as _init_chatbot,
    )
    while True:
        if not auth.check_session():
            return

        user = auth.current_user

        # Check if user has chatbot access
        user_perms = user.get('permissions', [])
        if 'access_chatbot' not in user_perms:
            print("You don't have permission to access the chatbot.")
            return

        print("\nUniversity Chatbot Integration:")
        print("===============================")
        print(f"Logged in as: {user['username']} ({user['role']})")

        if is_chatbot_available():
            print("Status: ✅ Available")
        else:
            print("Status: ⚠️ Limited functionality")

        # Build menu based on permissions
        menu_options = []
        menu_options.append("1. Start Chatbot Session")
        menu_options.append("2. View My Conversation History")

        option_num = 3
        if 'chatbot_admin' in user_perms:
            menu_options.append(f"{option_num}. View Chatbot Analytics")
            analytics_option = option_num
            option_num += 1
        else:
            analytics_option = None

        if 'view_all_conversations' in user_perms:
            menu_options.append(f"{option_num}. View All User Conversations")
            all_conversations_option = option_num
            option_num += 1
        else:
            all_conversations_option = None

        from education_system.systems.university.shell.cli.ai import chatbot_care_menu as care_menu
        menu_options.append(f"{option_num}. Support & privacy (speak to a person, my questions, "
                            "download / delete my conversations)")
        support_option = option_num
        option_num += 1
        staff_option = None
        if care_menu.has_staff_role(auth):
            menu_options.append(f"{option_num}. Chatbot staff tools")
            staff_option = option_num
            option_num += 1

        menu_options.append(f"{option_num}. Test Chatbot Integration")
        test_option = option_num
        option_num += 1

        menu_options.append(f"{option_num}. Back")
        back_option = option_num

        # Display menu
        for option in menu_options:
            print(option)

        choice = input(f"\nEnter your choice (1-{back_option}): ")

        try:
            choice_num = int(choice)
        except ValueError:
            print("Invalid choice. Please enter a number.")
            continue

        if choice == '1':
            # Start chatbot session
            _launch_chatbot(auth)

        elif choice_num == 2:
            # View conversation history - FIXED VERSION
            try:
                history = _get_chatbot_history(auth, user['username'])
                if history:
                    print(f"\nYour Chatbot Conversation History ({len(history)} interactions):")
                    print("=" * 60)
                    for i, conv in enumerate(history[:10], 1):
                        # Handle different conversation history formats
                        timestamp = conv.get('timestamp', 'Unknown time')

                        # Try to extract message text from different possible structures
                        message_text = None
                        if 'message' in conv:
                            message_text = conv['message']
                        elif 'details' in conv:
                            # Extract from details field (activity log format)
                            details = conv['details']
                            if details and 'Q:' in details:
                                # Extract question from "Q: ... A: ..." format
                                try:
                                    message_text = details.split('Q:')[1].split('A:')[0].strip()
                                except (IndexError, AttributeError) as e:
                                    logger.debug(f"Failed to parse Q/A format: {e}")
                                    message_text = details[:40] if details else "Chat interaction"
                            else:
                                message_text = details[:40] if details else "Chat interaction"
                        else:
                            message_text = "Chat interaction"

                        # Truncate message if too long
                        if message_text and len(message_text) > 40:
                            display_text = message_text[:40] + "..."
                        else:
                            display_text = message_text or "Chat interaction"

                        print(f"{i}. {timestamp} - {display_text}")

                    if len(history) > 10:
                        print(f"... and {len(history) - 10} more interactions")
                else:
                    print("No conversation history found. Start a chatbot session to begin!")

            except Exception as e:
                print(f"Error retrieving conversation history: {e}")
                print("No conversation history available at this time.")

        elif choice_num == analytics_option and analytics_option:
            # View analytics
            try:
                analytics = _gen_chatbot_analytics(auth)
                if analytics and 'error' not in analytics:
                    print("\nChatbot Analytics:")
                    print("=" * 40)
                    print(f"Total Interactions: {analytics.get('total_interactions', 0)}")
                    if 'unique_users' in analytics:
                        print(f"Unique Users: {analytics.get('unique_users', 0)}")
                    if 'interactions_by_role' in analytics:
                        print(f"Interactions by Role: {analytics.get('interactions_by_role', {})}")
                    print(f"Status: {analytics.get('status', 'Active')}")
                    print(f"Generated: {analytics.get('generated_at', 'unknown')}")

                    if analytics.get('daily_interactions'):
                        print("\nDaily Activity:")
                        for date, count in analytics['daily_interactions'].items():
                            print(f"  {date}: {count}")
                else:
                    print("No analytics data available or error occurred.")
            except Exception as e:
                print(f"Error generating analytics: {e}")

        elif choice_num == all_conversations_option and all_conversations_option:
            # Counts per person only; nobody reads another person's messages here.
            print("\nChatbot use by person:")
            print("=" * 50)
            try:
                from education_system.systems.university.infrastructure.database.db import (
                    get_connection,
                )
                conn = get_connection(row_factory=False)
                try:
                    rows = conn.execute(
                        "SELECT username, COUNT(*), MAX(timestamp) FROM chatbot_conversations "
                        "GROUP BY username ORDER BY MAX(timestamp) DESC LIMIT 20").fetchall()
                finally:
                    conn.close()
                if rows:
                    print(f"{'Username':<15} {'Turns':<12} {'Last Activity':<20}")
                    print("-" * 50)
                    for username, count, last_chat in rows:
                        print(f"{username or 'anonymous':<15} {count:<12} {last_chat or '':<20}")
                else:
                    print("No conversations found.")
            except sqlite3.Error as e:
                print(f"Error retrieving conversations: {e}")

        elif choice_num == support_option:
            from education_system.systems.university.shell.cli.ai.chatbot_integration import (
                get_chatbot_instance,
            )
            care_menu.self_service_menu(get_chatbot_instance(), auth)

        elif staff_option and choice_num == staff_option:
            care_menu.staff_menu(auth)

        elif choice_num == test_option:
            # Test integration
            print("\nTesting Chatbot Integration:")
            print("=" * 35)

            if is_chatbot_available():
                print("✅ Chatbot module available")

                if hasattr(auth, 'chatbot') and auth.chatbot:
                    print("✅ Chatbot instance created")

                    try:
                        test_response = auth.chatbot.process_message("Hello", user['username'])
                        print("✅ Message processing works")
                        print(f"  Test response: {test_response[:80]}...")
                    except Exception as e:
                        print(f"❌ Message processing failed: {e}")

                    print("✅ Integration test completed")
                else:
                    print("❌ Chatbot instance not found")
                    if _init_chatbot(auth):
                        print("✅ Chatbot initialized successfully")
                    else:
                        print("❌ Failed to initialize chatbot")
            else:
                print("⚠️ Chatbot in limited mode")

        elif choice_num == back_option:
            return

        else:
            print("Invalid choice. Please try again.")
