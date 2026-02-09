"""
Event Discovery Engine CLI Interface

Provides command-line interface for event discovery, RSVP management,
attendance tracking, and personalized recommendations.
"""

import sys
from datetime import datetime, timedelta
from typing import Optional

from university_system.modules.domain.events.services.events_service import get_events_service
from university_system.infrastructure.shared_context import get_auth


class EventsCLI:
    """CLI interface for Event Discovery Engine"""

    def __init__(self):
        """Initialize the events CLI"""
        self.service = get_events_service()
        self.auth = get_auth()

    def run(self):
        """Main CLI loop"""
        if not self.auth.is_logged_in():
            print("\nYou must be logged in to access Event Discovery Engine.")
            return

        while True:
            self.show_main_menu()
            choice = input("\nEnter your choice: ").strip()

            if choice == '1':
                self.browse_upcoming_events()
            elif choice == '2':
                self.search_events()
            elif choice == '3':
                self.view_recommendations()
            elif choice == '4':
                self.view_my_rsvps()
            elif choice == '5':
                self.rsvp_to_event()
            elif choice == '6':
                self.check_in_to_event()
            elif choice == '7':
                self.view_past_events()
            elif choice == '8':
                self.rate_event()
            elif choice == '9':
                self.manage_interests()
            elif choice == '10':
                self.view_event_details()
            elif choice == '11':
                self.create_event()
            elif choice == '12':
                self.view_my_statistics()
            elif choice == '0':
                print("\nReturning to main menu...")
                break
            else:
                print("\nInvalid choice. Please try again.")

    def show_main_menu(self):
        """Display the main menu"""
        print("\n" + "="*60)
        print("EVENT DISCOVERY ENGINE")
        print("="*60)
        print("\n1.  Browse Upcoming Events")
        print("2.  Search Events")
        print("3.  View Personalized Recommendations")
        print("4.  My RSVPs")
        print("5.  RSVP to Event")
        print("6.  Check In to Event")
        print("7.  View Past Events & Attendance")
        print("8.  Rate/Review Event")
        print("9.  Manage Interest Preferences")
        print("10. View Event Details")
        print("11. Create New Event")
        print("12. My Event Statistics")
        print("0.  Return to Main Menu")
        print("="*60)

    def browse_upcoming_events(self):
        """Browse upcoming events"""
        print("\n" + "="*60)
        print("UPCOMING EVENTS")
        print("="*60)

        try:
            events = self.service.get_upcoming_events(limit=50)

            if not events:
                print("\nNo upcoming events found.")
                return

            # Group by date
            events_by_date = {}
            for event in events:
                date = event['start_datetime'][:10]
                if date not in events_by_date:
                    events_by_date[date] = []
                events_by_date[date].append(event)

            for date in sorted(events_by_date.keys()):
                print(f"\n{self._format_date(date)}")
                print("-" * 60)

                for event in events_by_date[date]:
                    self._print_event_summary(event)

        except Exception as e:
            print(f"\nError browsing events: {e}")

    def search_events(self):
        """Search for events with filters"""
        print("\n" + "="*60)
        print("SEARCH EVENTS")
        print("="*60)

        print("\nCategories:")
        for i, category in enumerate(self.service.CATEGORIES, 1):
            print(f"{i}. {category}")

        category_choice = input("\nSelect category (0 for all): ").strip()
        category = None
        if category_choice != '0' and category_choice.isdigit():
            idx = int(category_choice) - 1
            if 0 <= idx < len(self.service.CATEGORIES):
                category = self.service.CATEGORIES[idx]

        keyword = input("Enter keyword (or press Enter to skip): ").strip()
        keyword = keyword if keyword else None

        start_date = input("Start date (YYYY-MM-DD, or press Enter for today): ").strip()
        start_date = start_date if start_date else datetime.now().isoformat()

        try:
            events = self.service.search_events(
                category=category,
                keyword=keyword,
                start_date=start_date,
                upcoming_only=True
            )

            if not events:
                print("\nNo events found matching your criteria.")
                return

            print(f"\n\nFound {len(events)} event(s):")
            print("="*60)

            for event in events:
                self._print_event_summary(event)
                print()

        except Exception as e:
            print(f"\nError searching events: {e}")

    def view_recommendations(self):
        """View personalized event recommendations"""
        print("\n" + "="*60)
        print("PERSONALIZED RECOMMENDATIONS - FOR YOU")
        print("="*60)

        user_id = self.auth.get_current_user_id()

        try:
            recommendations = self.service.get_personalized_recommendations(
                user_id=user_id,
                limit=15
            )

            if not recommendations:
                print("\nNo recommendations available.")
                print("Tip: Set your interest preferences to get better recommendations!")
                return

            print(f"\nBased on your interests and activity, we recommend these events:\n")

            for i, event in enumerate(recommendations, 1):
                print(f"\n{i}. {event['title']}")
                print(f"   Category: {event['category']}")
                print(f"   When: {self._format_datetime(event['start_datetime'])}")
                print(f"   Where: {event['location']}")
                print(f"   RSVPs: {event['rsvp_count']} going")
                print(f"   Match Score: {event['recommendation_score']}/100")

                if event.get('description'):
                    desc = event['description'][:100]
                    print(f"   {desc}{'...' if len(event['description']) > 100 else ''}")

        except Exception as e:
            print(f"\nError getting recommendations: {e}")

    def view_my_rsvps(self):
        """View user's RSVPs"""
        print("\n" + "="*60)
        print("MY RSVPS")
        print("="*60)

        user_id = self.auth.get_current_user_id()

        try:
            rsvps = self.service.get_user_rsvps(user_id=user_id, upcoming_only=True)

            if not rsvps:
                print("\nYou haven't RSVP'd to any upcoming events.")
                return

            # Group by status
            going = [e for e in rsvps if e['rsvp_status'] == 'Going']
            interested = [e for e in rsvps if e['rsvp_status'] == 'Interested']

            if going:
                print(f"\nGoing ({len(going)}):")
                print("-" * 60)
                for event in going:
                    self._print_event_summary(event)
                    if event['added_to_calendar']:
                        print("   [Added to Calendar]")
                    print()

            if interested:
                print(f"\nInterested ({len(interested)}):")
                print("-" * 60)
                for event in interested:
                    self._print_event_summary(event)
                    print()

        except Exception as e:
            print(f"\nError getting RSVPs: {e}")

    def rsvp_to_event(self):
        """RSVP to an event"""
        print("\n" + "="*60)
        print("RSVP TO EVENT")
        print("="*60)

        event_id = input("\nEnter Event ID: ").strip()
        if not event_id.isdigit():
            print("Invalid Event ID.")
            return

        event_id = int(event_id)

        # Show event details
        try:
            event = self.service.get_event(event_id)
            if not event:
                print(f"Event {event_id} not found.")
                return

            print("\nEvent Details:")
            self._print_event_details(event)

            print("\nRSVP Options:")
            print("1. Going")
            print("2. Interested")
            print("3. Not Going")
            print("0. Cancel")

            choice = input("\nYour response: ").strip()

            status_map = {
                '1': 'Going',
                '2': 'Interested',
                '3': 'Not Going'
            }

            if choice not in status_map:
                print("Cancelled.")
                return

            status = status_map[choice]

            add_to_calendar = False
            if status == 'Going':
                cal_choice = input("Add to calendar? (y/n): ").strip().lower()
                add_to_calendar = cal_choice == 'y'

            user_id = self.auth.get_current_user_id()
            self.service.rsvp_to_event(
                event_id=event_id,
                user_id=user_id,
                status=status,
                add_to_calendar=add_to_calendar
            )

            print(f"\nSuccessfully RSVP'd as '{status}'!")
            if add_to_calendar:
                print("Event added to your calendar.")

        except ValueError as e:
            print(f"\nError: {e}")
        except Exception as e:
            print(f"\nError RSVPing to event: {e}")

    def check_in_to_event(self):
        """Check in to an event"""
        print("\n" + "="*60)
        print("CHECK IN TO EVENT")
        print("="*60)

        event_id = input("\nEnter Event ID: ").strip()
        if not event_id.isdigit():
            print("Invalid Event ID.")
            return

        event_id = int(event_id)

        try:
            user_id = self.auth.get_current_user_id()
            self.service.check_in_to_event(event_id=event_id, user_id=user_id)

            print("\nSuccessfully checked in to the event!")
            print("Enjoy the event!")

        except ValueError as e:
            print(f"\nError: {e}")
        except Exception as e:
            print(f"\nError checking in: {e}")

    def view_past_events(self):
        """View past events and attendance history"""
        print("\n" + "="*60)
        print("MY PAST EVENTS & ATTENDANCE")
        print("="*60)

        user_id = self.auth.get_current_user_id()

        try:
            attendance = self.service.get_user_attendance_history(user_id=user_id)

            if not attendance:
                print("\nYou haven't attended any events yet.")
                return

            print(f"\nYou've attended {len(attendance)} event(s):\n")

            for event in attendance[:20]:  # Show last 20
                print(f"\nEvent ID: {event['event_id']}")
                print(f"Title: {event['title']}")
                print(f"Category: {event['category']}")
                print(f"Date: {self._format_datetime(event['start_datetime'])}")
                print(f"Check-in: {self._format_datetime(event['check_in_time'])}")

                if event['check_out_time']:
                    print(f"Check-out: {self._format_datetime(event['check_out_time'])}")

                print("-" * 60)

        except Exception as e:
            print(f"\nError getting attendance history: {e}")

    def rate_event(self):
        """Rate and review an event"""
        print("\n" + "="*60)
        print("RATE & REVIEW EVENT")
        print("="*60)

        print("\nNote: You can only rate events you've attended.\n")

        event_id = input("Enter Event ID: ").strip()
        if not event_id.isdigit():
            print("Invalid Event ID.")
            return

        event_id = int(event_id)

        # Show event details
        try:
            event = self.service.get_event(event_id)
            if not event:
                print(f"Event {event_id} not found.")
                return

            print(f"\nEvent: {event['title']}")
            print(f"Date: {self._format_datetime(event['start_datetime'])}")

            rating = input("\nRating (1-5 stars): ").strip()
            if not rating.isdigit() or not 1 <= int(rating) <= 5:
                print("Invalid rating. Must be 1-5.")
                return

            rating = int(rating)

            review = input("Write a review (optional, press Enter to skip): ").strip()
            review = review if review else None

            user_id = self.auth.get_current_user_id()
            self.service.rate_event(
                event_id=event_id,
                user_id=user_id,
                rating=rating,
                review=review
            )

            print(f"\nThank you for rating this event!")
            print(f"Your rating: {'★' * rating}{'☆' * (5 - rating)}")

        except ValueError as e:
            print(f"\nError: {e}")
        except Exception as e:
            print(f"\nError rating event: {e}")

    def manage_interests(self):
        """Manage interest preferences"""
        print("\n" + "="*60)
        print("MANAGE INTEREST PREFERENCES")
        print("="*60)

        user_id = self.auth.get_current_user_id()

        try:
            current_interests = self.service.get_user_interests(user_id)

            print("\nSet your interest level for each category (1-10, 10 = most interested):")
            print("Press Enter to skip a category.\n")

            for category in self.service.CATEGORIES:
                current = current_interests.get(category, 5)
                print(f"\n{category} (current: {current})")
                level = input("Interest level (1-10): ").strip()

                if level:
                    if not level.isdigit() or not 1 <= int(level) <= 10:
                        print("Invalid level. Skipping.")
                        continue

                    self.service.set_interest_preference(
                        user_id=user_id,
                        category=category,
                        interest_level=int(level)
                    )
                    print(f"Set {category} interest to {level}")

            print("\nInterest preferences updated!")
            print("Your recommendations will be personalized based on these preferences.")

        except Exception as e:
            print(f"\nError managing interests: {e}")

    def view_event_details(self):
        """View detailed information about an event"""
        print("\n" + "="*60)
        print("EVENT DETAILS")
        print("="*60)

        event_id = input("\nEnter Event ID: ").strip()
        if not event_id.isdigit():
            print("Invalid Event ID.")
            return

        event_id = int(event_id)

        try:
            event = self.service.get_event(event_id)
            if not event:
                print(f"Event {event_id} not found.")
                return

            self._print_event_details(event)

            # Show reviews
            reviews = self.service.get_event_reviews(event_id)
            if reviews:
                print("\nReviews:")
                print("-" * 60)
                for review in reviews[:5]:  # Show top 5
                    stars = '★' * review['rating'] + '☆' * (5 - review['rating'])
                    print(f"\n{stars}")
                    if review['review']:
                        print(f"{review['review']}")
                    print(f"- {self._format_datetime(review['rated_at'])}")

            # Show statistics
            stats = self.service.get_event_statistics(event_id)
            print("\n\nStatistics:")
            print("-" * 60)
            print(f"RSVPs: {stats['rsvp_breakdown']}")
            print(f"Attended: {stats['attendance_count']}")
            print(f"Average Rating: {stats['average_rating'] or 'N/A'}")
            print(f"Reviews: {stats['text_review_count']}")
            print(f"Photos: {stats['photo_count']}")

        except Exception as e:
            print(f"\nError getting event details: {e}")

    def create_event(self):
        """Create a new event"""
        print("\n" + "="*60)
        print("CREATE NEW EVENT")
        print("="*60)

        try:
            title = input("\nEvent Title: ").strip()
            if not title:
                print("Title is required.")
                return

            description = input("Description: ").strip()

            print("\nCategories:")
            for i, category in enumerate(self.service.CATEGORIES, 1):
                print(f"{i}. {category}")

            cat_choice = input("\nSelect category: ").strip()
            if not cat_choice.isdigit() or not 1 <= int(cat_choice) <= len(self.service.CATEGORIES):
                print("Invalid category.")
                return

            category = self.service.CATEGORIES[int(cat_choice) - 1]

            start_datetime = input("\nStart date/time (YYYY-MM-DD HH:MM): ").strip()
            end_datetime = input("End date/time (YYYY-MM-DD HH:MM): ").strip()

            location = input("Location: ").strip()
            building = input("Building (optional): ").strip()
            room = input("Room (optional): ").strip()

            max_capacity = input("Max capacity (0 for unlimited): ").strip()
            max_capacity = int(max_capacity) if max_capacity.isdigit() else 0

            event_data = {
                'title': title,
                'description': description,
                'category': category,
                'start_datetime': start_datetime,
                'end_datetime': end_datetime,
                'location': location,
                'building': building,
                'room': room,
                'max_capacity': max_capacity,
                'organizer_name': self.auth.get_current_user_id()
            }

            user_id = self.auth.get_current_user_id()
            event_id = self.service.create_event(event_data, user_id)

            print(f"\nEvent created successfully!")
            print(f"Event ID: {event_id}")

        except Exception as e:
            print(f"\nError creating event: {e}")

    def view_my_statistics(self):
        """View user's event statistics"""
        print("\n" + "="*60)
        print("MY EVENT STATISTICS")
        print("="*60)

        user_id = self.auth.get_current_user_id()

        try:
            stats = self.service.get_user_statistics(user_id)

            print(f"\nTotal RSVPs: {stats['total_rsvps']}")
            print(f"Events Attended: {stats['total_attended']}")
            print(f"Reviews Written: {stats['reviews_written']}")
            print(f"Photos Uploaded: {stats['photos_uploaded']}")

            if stats['attendance_by_category']:
                print("\n\nAttendance by Category:")
                print("-" * 60)
                for category, count in sorted(
                    stats['attendance_by_category'].items(),
                    key=lambda x: x[1],
                    reverse=True
                ):
                    print(f"{category}: {count} events")

        except Exception as e:
            print(f"\nError getting statistics: {e}")

    # Helper methods

    def _print_event_summary(self, event):
        """Print a summary of an event"""
        print(f"\nID: {event['event_id']} | {event['title']}")
        print(f"   {event['category']} | {self._format_datetime(event['start_datetime'])}")
        print(f"   {event['location']}")
        print(f"   {event['rsvp_count']} going", end="")

        if event.get('average_rating'):
            stars = '★' * int(event['average_rating'])
            print(f" | {stars} ({event['rating_count']} reviews)", end="")

        print()

    def _print_event_details(self, event):
        """Print detailed event information"""
        print(f"\nEvent ID: {event['event_id']}")
        print(f"Title: {event['title']}")
        print(f"Category: {event['category']}")
        print(f"\nDescription:")
        print(f"{event['description'] or 'No description provided'}")
        print(f"\nWhen: {self._format_datetime(event['start_datetime'])}")
        print(f"      to {self._format_datetime(event['end_datetime'])}")
        print(f"\nWhere: {event['location']}")

        if event['building']:
            print(f"Building: {event['building']}")
        if event['room']:
            print(f"Room: {event['room']}")

        print(f"\nOrganizer: {event['organizer_name'] or event['organizer_id']}")

        if event['max_capacity'] > 0:
            print(f"Capacity: {event['rsvp_count']}/{event['max_capacity']}")
        else:
            print(f"RSVPs: {event['rsvp_count']}")

        if event.get('average_rating'):
            stars = '★' * int(round(event['average_rating']))
            print(f"\nRating: {stars} {event['average_rating']}/5 ({event['rating_count']} reviews)")

        if event['tags']:
            print(f"\nTags: {', '.join(event['tags'])}")

    def _format_datetime(self, dt_str: str) -> str:
        """Format datetime string for display"""
        try:
            dt = datetime.fromisoformat(dt_str)
            return dt.strftime("%a, %b %d, %Y at %I:%M %p")
        except:
            return dt_str

    def _format_date(self, date_str: str) -> str:
        """Format date string for display"""
        try:
            dt = datetime.fromisoformat(date_str)
            return dt.strftime("%A, %B %d, %Y")
        except:
            return date_str


def main():
    """Entry point for the Events CLI"""
    cli = EventsCLI()
    cli.run()


if __name__ == '__main__':
    main()
