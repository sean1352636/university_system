"""
Student Marketplace CLI Interface

Provides command-line interface for:
- Creating and managing listings
- Browsing marketplace by category
- Searching items
- Contacting sellers
- Managing transactions and reviews
"""

import os
from datetime import datetime
from typing import Optional, List
from pathlib import Path

from education_system.university_system.modules.domain.commerce.marketplace.services.marketplace_service import (
    MarketplaceService
)
from education_system.university_system.infrastructure.shared_context import get_current_user

# Categories are stored as strings in the database
MARKETPLACE_CATEGORIES = [
    'Electronics', 'Books', 'Furniture', 'Clothing',
    'School Supplies', 'Sports Equipment', 'Other'
]

# Listing statuses
LISTING_STATUSES = ['Active', 'Sold', 'Deleted']
ITEM_STATUSES = ['Available', 'Claimed']
CONDITION_STATUSES = ['New', 'Like New', 'Good', 'Fair', 'Poor']


class MarketplaceCLI:
    """CLI interface for Student Marketplace."""

    def __init__(self, user_id: Optional[str] = None):
        """
        Initialize the Marketplace CLI.

        Args:
            user_id: Optional user ID (uses current authenticated user if not provided)
        """
        self.service = MarketplaceService()
        self.user_id = user_id
        if not self.user_id:
            current_user = get_current_user()
            if current_user:
                self.user_id = str(current_user.get('id', ''))

    def display_menu(self):
        """Display the main marketplace menu."""
        print("\n" + "=" * 70)
        print("STUDENT MARKETPLACE".center(70))
        print("=" * 70)
        print("\n1. Browse All Listings")
        print("2. Browse by Category")
        print("3. Search Marketplace")
        print("4. Create New Listing")
        print("5. My Listings")
        print("6. My Favorites")
        print("7. My Messages")
        print("8. View Listing Details")
        print("9. My Reviews")
        print("10. Marketplace Statistics")
        print("0. Back to Main Menu")
        print("=" * 70)

    def run(self):
        """Run the marketplace CLI main loop."""
        while True:
            self.display_menu()
            choice = input("\nEnter your choice: ").strip()

            if choice == '1':
                self.browse_all_listings()
            elif choice == '2':
                self.browse_by_category()
            elif choice == '3':
                self.search_marketplace()
            elif choice == '4':
                self.create_listing()
            elif choice == '5':
                self.view_my_listings()
            elif choice == '6':
                self.view_favorites()
            elif choice == '7':
                self.view_messages()
            elif choice == '8':
                self.view_listing_details()
            elif choice == '9':
                self.view_my_reviews()
            elif choice == '10':
                self.show_statistics()
            elif choice == '0':
                print("\nReturning to main menu...")
                break
            else:
                print("\nInvalid choice. Please try again.")

            input("\nPress Enter to continue...")

    def browse_all_listings(self):
        """Browse all active listings."""
        print("\n" + "=" * 70)
        print("ALL ACTIVE LISTINGS".center(70))
        print("=" * 70)

        listings = self.service.get_listings(status='Active', limit=20)

        if not listings:
            print("\nNo active listings found.")
            return

        self._display_listings(listings)

    def browse_by_category(self):
        """Browse listings by category."""
        print("\n" + "=" * 70)
        print("BROWSE BY CATEGORY".center(70))
        print("=" * 70)

        categories = self.service.get_categories()
        print("\nAvailable Categories:")
        for idx, category in enumerate(categories, 1):
            print(f"{idx}. {category}")
        print("0. Cancel")

        choice = input("\nSelect category: ").strip()

        try:
            choice_idx = int(choice)
            if choice_idx == 0:
                return
            if 1 <= choice_idx <= len(categories):
                category = categories[choice_idx - 1]
                listings = self.service.get_listings(category=category, status='Active')

                print(f"\n{'=' * 70}")
                print(f"{category.upper()} LISTINGS".center(70))
                print("=" * 70)

                if not listings:
                    print(f"\nNo active {category} listings found.")
                else:
                    self._display_listings(listings)
            else:
                print("\nInvalid category selection.")
        except ValueError:
            print("\nInvalid input. Please enter a number.")

    def search_marketplace(self):
        """Search marketplace listings."""
        print("\n" + "=" * 70)
        print("SEARCH MARKETPLACE".center(70))
        print("=" * 70)

        search_term = input("\nEnter search term (title/description): ").strip()

        if not search_term:
            print("\nSearch term cannot be empty.")
            return

        # Optional filters
        print("\nOptional Filters (press Enter to skip):")
        category = input("Category: ").strip() or None
        min_price_str = input("Minimum price: ").strip()
        max_price_str = input("Maximum price: ").strip()

        min_price = float(min_price_str) if min_price_str else None
        max_price = float(max_price_str) if max_price_str else None

        listings = self.service.search_listings(
            search_term=search_term,
            category=category,
            min_price=min_price,
            max_price=max_price
        )

        print(f"\n{'=' * 70}")
        print(f"SEARCH RESULTS FOR '{search_term}'".center(70))
        print("=" * 70)

        if not listings:
            print("\nNo listings found matching your search.")
        else:
            print(f"\nFound {len(listings)} listing(s):")
            self._display_listings(listings)

    def create_listing(self):
        """Create a new marketplace listing."""
        if not self.user_id:
            print("\nError: You must be logged in to create a listing.")
            return

        print("\n" + "=" * 70)
        print("CREATE NEW LISTING".center(70))
        print("=" * 70)

        # Get category
        categories = self.service.get_categories()
        print("\nSelect Category:")
        for idx, category in enumerate(categories, 1):
            print(f"{idx}. {category}")

        try:
            cat_choice = int(input("\nCategory: ").strip())
            if cat_choice < 1 or cat_choice > len(categories):
                print("\nInvalid category selection.")
                return
            category = categories[cat_choice - 1]
        except ValueError:
            print("\nInvalid input.")
            return

        # Get listing details
        print("\nEnter Listing Details:")
        title = input("Title: ").strip()
        description = input("Description: ").strip()
        price_str = input("Price (0 for free): ").strip()
        condition = input("Condition (New/Like New/Good/Fair/Poor): ").strip()
        location = input("Location (optional): ").strip() or None

        try:
            price = float(price_str)
        except ValueError:
            print("\nInvalid price.")
            return

        # Category-specific fields
        course_code = None
        isbn = None
        lease_start = None
        lease_end = None

        if category == "Textbooks":
            course_code = input("Course Code (optional): ").strip() or None
            isbn = input("ISBN (optional): ").strip() or None
        elif category == "Housing":
            lease_start = input("Lease Start Date (YYYY-MM-DD, optional): ").strip() or None
            lease_end = input("Lease End Date (YYYY-MM-DD, optional): ").strip() or None

        # Create listing
        listing_data = {
            'seller_id': self.user_id,
            'listing_type': 'For Sale' if price > 0 else 'Free',
            'title': title,
            'description': description,
            'category': category,
            'price': price,
            'condition_status': condition,
            'location': location,
        }

        # Add category-specific fields
        if course_code:
            listing_data['metadata'] = {'course_code': course_code}
        if isbn:
            if 'metadata' not in listing_data:
                listing_data['metadata'] = {}
            listing_data['metadata']['isbn'] = isbn
        if lease_start:
            if 'metadata' not in listing_data:
                listing_data['metadata'] = {}
            listing_data['metadata']['lease_start_date'] = lease_start
        if lease_end:
            if 'metadata' not in listing_data:
                listing_data['metadata'] = {}
            listing_data['metadata']['lease_end_date'] = lease_end

        listing_id = self.service.create_listing(**listing_data)

        if listing_id:
            print(f"\n✓ Listing created successfully! (ID: {listing_id})")
            print("\nYour listing is now active in the marketplace.")
        else:
            print("\n✗ Failed to create listing. Please try again.")

    def view_my_listings(self):
        """View current user's listings."""
        if not self.user_id:
            print("\nError: You must be logged in to view your listings.")
            return

        print("\n" + "=" * 70)
        print("MY LISTINGS".center(70))
        print("=" * 70)

        print("\n1. Active Listings")
        print("2. Sold Listings")
        print("3. All My Listings")
        print("0. Cancel")

        choice = input("\nSelect option: ").strip()

        status = None
        if choice == '1':
            status = 'Active'
        elif choice == '2':
            status = 'Sold'
        elif choice == '3':
            status = None
        elif choice == '0':
            return
        else:
            print("\nInvalid choice.")
            return

        listings = self.service.get_user_listings(self.user_id, status=status)

        if not listings:
            print("\nYou don't have any listings.")
            return

        self._display_listings(listings, show_actions=True)

        # Listing management options
        print("\nListing Management:")
        print("1. Mark as Sold")
        print("2. Edit Listing")
        print("3. Delete Listing")
        print("0. Back")

        action = input("\nSelect action: ").strip()

        if action == '1':
            self._mark_as_sold(listings)
        elif action == '2':
            self._edit_listing(listings)
        elif action == '3':
            self._delete_listing(listings)

    def _mark_as_sold(self, listings: List[dict]):
        """Mark a listing as sold."""
        listing_id = input("\nEnter Listing ID to mark as sold: ").strip()

        # Verify listing belongs to user
        listing = next((l for l in listings if str(l.get('listing_id')) == listing_id), None)
        if not listing:
            print("\nInvalid listing ID or listing doesn't belong to you.")
            return

        if self.service.mark_listing_sold(listing_id, self.user_id):
            print("\n✓ Listing marked as sold successfully!")
        else:
            print("\n✗ Failed to mark listing as sold.")

    def _edit_listing(self, listings: List[dict]):
        """Edit a listing."""
        listing_id = input("\nEnter Listing ID to edit: ").strip()

        # Verify listing belongs to user
        listing = next((l for l in listings if str(l.get('listing_id')) == listing_id), None)
        if not listing:
            print("\nInvalid listing ID or listing doesn't belong to you.")
            return

        print("\nWhat would you like to update? (press Enter to skip)")
        title = input(f"Title [{listing.get('title')}]: ").strip()
        description = input(f"Description [{listing.get('description')}]: ").strip()
        price_str = input(f"Price [{listing.get('price')}]: ").strip()

        updates = {}
        if title:
            updates['title'] = title
        if description:
            updates['description'] = description
        if price_str:
            try:
                updates['price'] = float(price_str)
            except ValueError:
                print("\nInvalid price format.")
                return

        if updates and self.service.update_listing(listing_id, self.user_id, **updates):
            print("\n✓ Listing updated successfully!")
        else:
            print("\n✗ Failed to update listing.")

    def _delete_listing(self, listings: List[dict]):
        """Delete a listing."""
        listing_id = input("\nEnter Listing ID to delete: ").strip()

        # Verify listing belongs to user
        listing = next((l for l in listings if str(l.get('listing_id')) == listing_id), None)
        if not listing:
            print("\nInvalid listing ID or listing doesn't belong to you.")
            return

        confirm = input(f"\nAre you sure you want to delete '{listing.get('title')}'? (yes/no): ").strip().lower()

        if confirm == 'yes':
            if self.service.delete_listing(listing_id, self.user_id):
                print("\n✓ Listing deleted successfully!")
            else:
                print("\n✗ Failed to delete listing.")
        else:
            print("\nDeletion cancelled.")

    def view_listing_details(self):
        """View detailed information about a listing."""
        listing_id = input("\nEnter Listing ID: ").strip()

        listing = self.service.get_listing(listing_id)

        if not listing:
            print("\nListing not found.")
            return

        print("\n" + "=" * 70)
        print("LISTING DETAILS".center(70))
        print("=" * 70)

        print(f"\nID: {listing.get('listing_id')}")
        print(f"Title: {listing.get('title')}")
        print(f"Category: {listing.get('category')}")
        print(f"Price: £{listing.get('price', 0):.2f}" if listing.get('price') else "FREE")
        print(f"Condition: {listing.get('condition_status', 'N/A')}")
        print(f"Location: {listing.get('location', 'Not specified')}")
        print(f"\nDescription:\n{listing.get('description')}")
        print(f"\nSeller: {listing.get('seller_id')}")
        print(f"Status: {listing.get('status')}")
        print(f"Views: {listing.get('view_count', 0)}")
        print(f"Posted: {listing.get('created_at')}")

        # Show metadata if available
        metadata = listing.get('metadata')
        if metadata:
            print("\nAdditional Information:")
            if isinstance(metadata, dict):
                for key, value in metadata.items():
                    print(f"  {key.replace('_', ' ').title()}: {value}")

        # Contact seller option
        if self.user_id and str(listing.get('seller_id')) != self.user_id:
            print("\n" + "-" * 70)
            contact = input("\nWould you like to contact the seller? (yes/no): ").strip().lower()
            if contact == 'yes':
                self._contact_seller(listing)

        # Add to favorites option
        if self.user_id:
            print("\n" + "-" * 70)
            favorite = input("\nAdd to favorites? (yes/no): ").strip().lower()
            if favorite == 'yes':
                if self.service.add_favorite(self.user_id, listing_id):
                    print("\n✓ Added to favorites!")
                else:
                    print("\n✗ Failed to add to favorites.")

    def _contact_seller(self, listing: dict):
        """Send a message to the seller."""
        print("\n" + "=" * 70)
        print("CONTACT SELLER".center(70))
        print("=" * 70)

        message = input("\nEnter your message: ").strip()

        if not message:
            print("\nMessage cannot be empty.")
            return

        message_id = self.service.send_message(
            listing_id=listing.get('listing_id'),
            sender_id=self.user_id,
            message_text=message
        )

        if message_id:
            print("\n✓ Message sent successfully!")
            print("The seller will see your message in their inbox.")
        else:
            print("\n✗ Failed to send message.")

    def view_favorites(self):
        """View user's favorite listings."""
        if not self.user_id:
            print("\nError: You must be logged in to view favorites.")
            return

        print("\n" + "=" * 70)
        print("MY FAVORITES".center(70))
        print("=" * 70)

        favorites = self.service.get_user_favorites(self.user_id)

        if not favorites:
            print("\nYou don't have any favorite listings.")
            return

        self._display_listings(favorites)

        # Option to remove from favorites
        remove = input("\nRemove a listing from favorites? (yes/no): ").strip().lower()
        if remove == 'yes':
            listing_id = input("Enter Listing ID: ").strip()
            if self.service.remove_favorite(self.user_id, listing_id):
                print("\n✓ Removed from favorites!")
            else:
                print("\n✗ Failed to remove from favorites.")

    def view_messages(self):
        """View user's messages."""
        if not self.user_id:
            print("\nError: You must be logged in to view messages.")
            return

        print("\n" + "=" * 70)
        print("MY MESSAGES".center(70))
        print("=" * 70)

        messages = self.service.get_user_messages(self.user_id)

        if not messages:
            print("\nYou don't have any messages.")
            return

        # Group messages by conversation
        conversations = {}
        for msg in messages:
            listing_id = msg.get('listing_id')
            if listing_id not in conversations:
                conversations[listing_id] = {
                    'listing': self.service.get_listing(listing_id),
                    'messages': []
                }
            conversations[listing_id]['messages'].append(msg)

        # Display conversations
        conv_list = list(conversations.items())
        for idx, (listing_id, conv) in enumerate(conv_list, 1):
            listing = conv['listing']
            msg_count = len(conv['messages'])
            last_msg = conv['messages'][-1]
            unread = sum(1 for m in conv['messages']
                        if not m.get('is_read') and m.get('receiver_id') == self.user_id)

            print(f"\n{idx}. Listing: {listing.get('title') if listing else 'Unknown'}")
            print(f"   Messages: {msg_count} {'(' + str(unread) + ' unread)' if unread else ''}")
            print(f"   Last: {last_msg.get('created_at')}")

        # View conversation
        choice = input("\nSelect conversation to view (0 to cancel): ").strip()

        try:
            choice_idx = int(choice)
            if choice_idx == 0:
                return
            if 1 <= choice_idx <= len(conv_list):
                listing_id = conv_list[choice_idx - 1][0]
                self._view_conversation(listing_id)
            else:
                print("\nInvalid selection.")
        except ValueError:
            print("\nInvalid input.")

    def _view_conversation(self, listing_id: str):
        """View messages for a specific listing."""
        listing = self.service.get_listing(listing_id)
        messages = self.service.get_conversation_messages(listing_id, self.user_id)

        print("\n" + "=" * 70)
        print(f"CONVERSATION: {listing.get('title') if listing else 'Unknown'}".center(70))
        print("=" * 70)

        for msg in messages:
            sender = "You" if msg.get('sender_id') == self.user_id else "Seller"
            timestamp = msg.get('created_at', '')
            print(f"\n[{timestamp}] {sender}:")
            print(f"  {msg.get('message_text')}")

        # Reply option
        reply = input("\nReply? (yes/no): ").strip().lower()
        if reply == 'yes':
            message = input("Your message: ").strip()
            if message:
                # Determine recipient
                recipient_id = listing.get('seller_id') if listing else None
                if recipient_id == self.user_id:
                    # User is seller, find buyer from messages
                    for msg in messages:
                        if msg.get('sender_id') != self.user_id:
                            recipient_id = msg.get('sender_id')
                            break

                if recipient_id:
                    msg_id = self.service.send_message(
                        listing_id=listing_id,
                        sender_id=self.user_id,
                        message_text=message
                    )
                    if msg_id:
                        print("\n✓ Reply sent!")
                    else:
                        print("\n✗ Failed to send reply.")

    def view_my_reviews(self):
        """View reviews for the current user."""
        if not self.user_id:
            print("\nError: You must be logged in to view reviews.")
            return

        print("\n" + "=" * 70)
        print("MY REVIEWS".center(70))
        print("=" * 70)

        reviews = self.service.get_user_reviews(self.user_id)

        if not reviews:
            print("\nYou don't have any reviews yet.")
            return

        # Calculate average rating
        total_rating = sum(r.get('rating', 0) for r in reviews)
        avg_rating = total_rating / len(reviews) if reviews else 0

        print(f"\nAverage Rating: {'★' * int(avg_rating)}{'☆' * (5 - int(avg_rating))} ({avg_rating:.1f}/5.0)")
        print(f"Total Reviews: {len(reviews)}\n")

        for idx, review in enumerate(reviews, 1):
            print(f"{idx}. Rating: {'★' * review.get('rating', 0)}{'☆' * (5 - review.get('rating', 0))}")
            print(f"   From: {review.get('reviewer_id', 'Anonymous')}")
            print(f"   Date: {review.get('created_at', 'Unknown')}")
            if review.get('review_text'):
                print(f"   Comment: {review.get('review_text')}")
            print()

    def show_statistics(self):
        """Display marketplace statistics."""
        print("\n" + "=" * 70)
        print("MARKETPLACE STATISTICS".center(70))
        print("=" * 70)

        stats = self.service.get_statistics()

        if not stats:
            print("\nNo statistics available.")
            return

        print(f"\nTotal Active Listings: {stats.get('total_active', 0)}")
        print(f"Total Sold Items: {stats.get('total_sold', 0)}")
        print(f"Total Transactions: {stats.get('total_transactions', 0)}")

        # Listings by category
        category_stats = stats.get('by_category', {})
        if category_stats:
            print("\nListings by Category:")
            for category, count in category_stats.items():
                print(f"  {category}: {count}")

        # Recent activity
        print(f"\nListings Created Today: {stats.get('created_today', 0)}")
        print(f"Listings Created This Week: {stats.get('created_this_week', 0)}")

    def _display_listings(self, listings: List[dict], show_actions: bool = False):
        """Display a list of listings in a formatted table."""
        if not listings:
            return

        print(f"\n{'ID':<6} {'Title':<30} {'Category':<15} {'Price':<10} {'Status':<10}")
        print("-" * 70)

        for listing in listings:
            listing_id = listing.get('listing_id', 'N/A')
            title = listing.get('title', 'No title')[:28]
            category = listing.get('category', 'N/A')[:13]
            price = listing.get('price', 0)
            price_str = f"£{price:.2f}" if price else "FREE"
            status = listing.get('status', 'Unknown')[:8]

            print(f"{listing_id:<6} {title:<30} {category:<15} {price_str:<10} {status:<10}")


def main():
    """Main entry point for the marketplace CLI."""
    cli = MarketplaceCLI()
    cli.run()


if __name__ == "__main__":
    main()
