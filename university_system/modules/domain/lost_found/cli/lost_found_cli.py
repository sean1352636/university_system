"""
Lost & Found CLI Interface

Command-line interface for lost and found item management.
"""

from typing import Optional
from datetime import datetime
import os

from university_system.infrastructure.shared_context import get_auth
from university_system.modules.domain.lost_found.services.lost_found_service import LostFoundService


class LostFoundCLI:
    """CLI interface for Lost & Found functionality."""

    # Item categories
    CATEGORIES = [
        'Electronics',
        'Clothing',
        'Books',
        'Keys',
        'Bags',
        'Wallets',
        'Jewelry',
        'Sports Equipment',
        'Documents',
        'Other'
    ]

    def __init__(self):
        """Initialize the Lost & Found CLI."""
        self.service = LostFoundService()
        self.auth = get_auth()

    def display_menu(self):
        """Display the main lost & found menu."""
        if not self.auth.is_logged_in():
            print("\nYou must be logged in to use the Lost & Found system.")
            return

        while True:
            print("\n" + "=" * 70)
            print(" " * 25 + "LOST & FOUND SYSTEM")
            print("=" * 70)

            print("\n[Report Items]")
            print("1. Report Lost Item")
            print("2. Report Found Item")

            print("\n[Search & Browse]")
            print("3. Search Lost Items")
            print("4. Search Found Items")
            print("5. View All Lost Items")
            print("6. View All Found Items")

            print("\n[My Reports]")
            print("7. View My Lost Items")
            print("8. View My Found Items")
            print("9. Update Item Status")

            print("\n[Claims]")
            print("10. View Potential Matches")
            print("11. Submit Claim for Found Item")
            print("12. View My Claims")
            print("13. Review Claims (Staff Only)")

            print("\n[Statistics]")
            print("14. View System Statistics")

            print("\n0. Back to Main Menu")
            print("=" * 70)

            choice = input("\nEnter your choice: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self.report_lost_item()
            elif choice == '2':
                self.report_found_item()
            elif choice == '3':
                self.search_items('lost')
            elif choice == '4':
                self.search_items('found')
            elif choice == '5':
                self.view_all_items('lost')
            elif choice == '6':
                self.view_all_items('found')
            elif choice == '7':
                self.view_my_items('lost')
            elif choice == '8':
                self.view_my_items('found')
            elif choice == '9':
                self.update_item_status()
            elif choice == '10':
                self.view_matches()
            elif choice == '11':
                self.submit_claim()
            elif choice == '12':
                self.view_my_claims()
            elif choice == '13':
                self.review_claims()
            elif choice == '14':
                self.view_statistics()
            else:
                print("\nInvalid choice. Please try again.")

    def report_lost_item(self):
        """Report a lost item."""
        user = self.auth.get_current_user()
        if not user:
            print("\nError: User not found.")
            return

        student_id = user['username']

        print("\n" + "=" * 70)
        print("REPORT LOST ITEM")
        print("=" * 70)

        # Basic information
        item_name = input("\nItem Name: ").strip()
        if not item_name:
            print("\nItem name is required.")
            return

        # Category selection
        print("\nSelect Category:")
        for idx, cat in enumerate(self.CATEGORIES, 1):
            print(f"  {idx}. {cat}")

        cat_choice = input("\nCategory number: ").strip()
        try:
            category = self.CATEGORIES[int(cat_choice) - 1]
        except (ValueError, IndexError):
            print("\nInvalid category selection.")
            return

        description = input("\nDetailed Description: ").strip()
        if not description:
            print("\nDescription is required.")
            return

        lost_date = input("Date Lost (YYYY-MM-DD): ").strip()
        if not lost_date:
            lost_date = datetime.now().strftime('%Y-%m-%d')

        lost_location = input("Location Where Lost: ").strip()
        if not lost_location:
            print("\nLocation is required.")
            return

        # Optional details
        lost_time = input("Approximate Time Lost (HH:MM, optional): ").strip()
        distinctive_features = input("Distinctive Features (optional): ").strip()
        color = input("Primary Color (optional): ").strip()
        brand = input("Brand/Manufacturer (optional): ").strip()

        estimated_value_str = input("Estimated Value ($ optional): ").strip()
        estimated_value = 0.0
        if estimated_value_str:
            try:
                estimated_value = float(estimated_value_str)
            except ValueError:
                print("Invalid value, setting to 0.")

        contact_email = input("Contact Email (optional): ").strip()
        contact_phone = input("Contact Phone (optional): ").strip()

        # Confirm
        print("\n" + "-" * 70)
        print("Please confirm:")
        print(f"Item: {item_name}")
        print(f"Category: {category}")
        print(f"Description: {description}")
        print(f"Lost on: {lost_date} at {lost_location}")
        print("-" * 70)

        confirm = input("\nSubmit this report? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("\nReport cancelled.")
            return

        try:
            item_id = self.service.report_lost_item(
                reporter_id=student_id,
                item_name=item_name,
                category=category,
                description=description,
                lost_date=lost_date,
                lost_location=lost_location,
                lost_time=lost_time,
                distinctive_features=distinctive_features,
                color=color,
                brand=brand,
                estimated_value=estimated_value,
                contact_email=contact_email,
                contact_phone=contact_phone
            )

            print(f"\n✓ Lost item reported successfully! Item ID: {item_id}")
            print("The system will automatically search for potential matches.")

        except Exception as e:
            print(f"\n✗ Error reporting lost item: {e}")

    def report_found_item(self):
        """Report a found item."""
        user = self.auth.get_current_user()
        if not user:
            print("\nError: User not found.")
            return

        student_id = user['username']

        print("\n" + "=" * 70)
        print("REPORT FOUND ITEM")
        print("=" * 70)

        # Basic information
        item_name = input("\nItem Name: ").strip()
        if not item_name:
            print("\nItem name is required.")
            return

        # Category selection
        print("\nSelect Category:")
        for idx, cat in enumerate(self.CATEGORIES, 1):
            print(f"  {idx}. {cat}")

        cat_choice = input("\nCategory number: ").strip()
        try:
            category = self.CATEGORIES[int(cat_choice) - 1]
        except (ValueError, IndexError):
            print("\nInvalid category selection.")
            return

        description = input("\nDetailed Description: ").strip()
        if not description:
            print("\nDescription is required.")
            return

        found_date = input("Date Found (YYYY-MM-DD): ").strip()
        if not found_date:
            found_date = datetime.now().strftime('%Y-%m-%d')

        found_location = input("Location Where Found: ").strip()
        if not found_location:
            print("\nLocation is required.")
            return

        # Optional details
        found_time = input("Approximate Time Found (HH:MM, optional): ").strip()
        distinctive_features = input("Distinctive Features (optional): ").strip()
        color = input("Primary Color (optional): ").strip()
        brand = input("Brand/Manufacturer (optional): ").strip()

        current_location = input("Current Location/Storage (optional): ").strip()
        storage_info = input("Storage Details (optional): ").strip()

        contact_email = input("Contact Email (optional): ").strip()
        contact_phone = input("Contact Phone (optional): ").strip()

        # Confirm
        print("\n" + "-" * 70)
        print("Please confirm:")
        print(f"Item: {item_name}")
        print(f"Category: {category}")
        print(f"Description: {description}")
        print(f"Found on: {found_date} at {found_location}")
        print("-" * 70)

        confirm = input("\nSubmit this report? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("\nReport cancelled.")
            return

        try:
            item_id = self.service.report_found_item(
                finder_id=student_id,
                item_name=item_name,
                category=category,
                description=description,
                found_date=found_date,
                found_location=found_location,
                found_time=found_time,
                distinctive_features=distinctive_features,
                color=color,
                brand=brand,
                current_location=current_location,
                storage_info=storage_info,
                contact_email=contact_email,
                contact_phone=contact_phone
            )

            print(f"\n✓ Found item reported successfully! Item ID: {item_id}")
            print("The system will automatically search for potential matches.")

            # Ask if they want to add verification questions
            add_questions = input("\nWould you like to add verification questions? (yes/no): ").strip().lower()
            if add_questions == 'yes':
                self._add_verification_questions(item_id, student_id)

        except Exception as e:
            print(f"\n✗ Error reporting found item: {e}")

    def _add_verification_questions(self, found_item_id: int, creator_id: str):
        """Add verification questions for a found item."""
        print("\n" + "-" * 70)
        print("Add Verification Questions")
        print("These help verify the rightful owner when someone claims this item.")
        print("-" * 70)

        questions = []
        while True:
            question = input("\nEnter a verification question (or 'done' to finish): ").strip()
            if question.lower() == 'done':
                break
            if question:
                questions.append(question)
                print(f"  Question {len(questions)} added.")

        if questions:
            try:
                self.service.create_verification_questions(
                    found_item_id=found_item_id,
                    created_by=creator_id,
                    questions=questions
                )
                print(f"\n✓ Added {len(questions)} verification questions.")
            except Exception as e:
                print(f"\n✗ Error adding questions: {e}")

    def search_items(self, item_type: str):
        """Search lost or found items."""
        print("\n" + "=" * 70)
        print(f"SEARCH {item_type.upper()} ITEMS")
        print("=" * 70)

        search_term = input("\nSearch term (name, description, features, brand): ").strip()
        if not search_term:
            print("\nSearch term required.")
            return

        # Optional filters
        print("\nOptional Filters (press Enter to skip):")

        print("\nSelect Category (or press Enter for all):")
        for idx, cat in enumerate(self.CATEGORIES, 1):
            print(f"  {idx}. {cat}")
        cat_choice = input("Category number: ").strip()
        category = None
        if cat_choice:
            try:
                category = self.CATEGORIES[int(cat_choice) - 1]
            except (ValueError, IndexError):
                pass

        date_from = input("Date from (YYYY-MM-DD): ").strip() or None
        date_to = input("Date to (YYYY-MM-DD): ").strip() or None

        try:
            items = self.service.search_items(
                item_type=item_type,
                search_term=search_term,
                category=category,
                date_from=date_from,
                date_to=date_to
            )

            if not items:
                print(f"\nNo {item_type} items found matching your search.")
                return

            print(f"\n{'=' * 70}")
            print(f"Found {len(items)} matching items:")
            print('=' * 70)

            for item in items:
                self._display_item_summary(item, item_type)
                print("-" * 70)

        except Exception as e:
            print(f"\n✗ Error searching items: {e}")

    def view_all_items(self, item_type: str):
        """View all active lost or found items."""
        print("\n" + "=" * 70)
        print(f"ALL {item_type.upper()} ITEMS")
        print("=" * 70)

        try:
            if item_type == 'lost':
                items = self.service.get_lost_items(status='Active')
            else:
                items = self.service.get_found_items(status='Available')

            if not items:
                print(f"\nNo {item_type} items found.")
                return

            print(f"\nTotal: {len(items)} items")
            print('=' * 70)

            for item in items:
                self._display_item_summary(item, item_type)
                print("-" * 70)

            # Option to view details
            view_detail = input("\nEnter item ID to view details (or press Enter to continue): ").strip()
            if view_detail:
                self._view_item_detail(int(view_detail), item_type)

        except Exception as e:
            print(f"\n✗ Error retrieving items: {e}")

    def view_my_items(self, item_type: str):
        """View items reported by current user."""
        user = self.auth.get_current_user()
        if not user:
            print("\nError: User not found.")
            return

        student_id = user['username']

        print("\n" + "=" * 70)
        print(f"MY {item_type.upper()} ITEMS")
        print("=" * 70)

        try:
            if item_type == 'lost':
                items = self.service.get_lost_items(reporter_id=student_id)
            else:
                items = self.service.get_found_items(finder_id=student_id)

            if not items:
                print(f"\nYou haven't reported any {item_type} items.")
                return

            print(f"\nTotal: {len(items)} items")
            print('=' * 70)

            for item in items:
                self._display_item_summary(item, item_type)
                print("-" * 70)

            # Option to view details
            view_detail = input("\nEnter item ID to view details (or press Enter to continue): ").strip()
            if view_detail:
                self._view_item_detail(int(view_detail), item_type)

        except Exception as e:
            print(f"\n✗ Error retrieving items: {e}")

    def _display_item_summary(self, item: dict, item_type: str):
        """Display summary of an item."""
        date_field = 'lost_date' if item_type == 'lost' else 'found_date'
        location_field = 'lost_location' if item_type == 'lost' else 'found_location'

        print(f"\nID: {item['item_id']} | {item['item_name']} ({item['category']})")
        print(f"Date: {item[date_field]} | Location: {item[location_field]}")
        print(f"Description: {item['description'][:100]}...")
        if item.get('color'):
            print(f"Color: {item['color']}", end="")
        if item.get('brand'):
            print(f" | Brand: {item['brand']}", end="")
        print(f"\nStatus: {item['status']}")

    def _view_item_detail(self, item_id: int, item_type: str):
        """View detailed information about an item."""
        try:
            if item_type == 'lost':
                item = self.service.get_lost_item(item_id)
            else:
                item = self.service.get_found_item(item_id)

            if not item:
                print("\nItem not found.")
                return

            print("\n" + "=" * 70)
            print(f"{item_type.upper()} ITEM DETAILS")
            print("=" * 70)

            print(f"\nItem ID: {item['item_id']}")
            print(f"Name: {item['item_name']}")
            print(f"Category: {item['category']}")
            print(f"Status: {item['status']}")

            date_field = 'lost_date' if item_type == 'lost' else 'found_date'
            location_field = 'lost_location' if item_type == 'lost' else 'found_location'
            time_field = 'lost_time' if item_type == 'lost' else 'found_time'

            print(f"\nDate: {item[date_field]}")
            if item.get(time_field):
                print(f"Time: {item[time_field]}")
            print(f"Location: {item[location_field]}")

            print(f"\nDescription: {item['description']}")

            if item.get('distinctive_features'):
                print(f"Distinctive Features: {item['distinctive_features']}")
            if item.get('color'):
                print(f"Color: {item['color']}")
            if item.get('brand'):
                print(f"Brand: {item['brand']}")

            if item_type == 'lost' and item.get('estimated_value'):
                print(f"Estimated Value: ${item['estimated_value']:.2f}")

            if item_type == 'found':
                if item.get('current_location'):
                    print(f"Current Location: {item['current_location']}")
                if item.get('storage_info'):
                    print(f"Storage Info: {item['storage_info']}")

                # Display verification questions
                if item.get('verification_questions'):
                    print("\nVerification Questions:")
                    for q in item['verification_questions']:
                        print(f"  - {q['question_text']}")

            if item.get('contact_email'):
                print(f"\nContact Email: {item['contact_email']}")
            if item.get('contact_phone'):
                print(f"Contact Phone: {item['contact_phone']}")

            print(f"\nReported: {item['reported_at']}")
            print(f"Last Updated: {item['updated_at']}")

            # Show photos if any
            if item.get('photos'):
                print(f"\nPhotos: {len(item['photos'])} attached")
                for photo in item['photos']:
                    print(f"  - {photo['photo_path']}")

            print("=" * 70)

        except Exception as e:
            print(f"\n✗ Error retrieving item details: {e}")

    def update_item_status(self):
        """Update status of a lost or found item."""
        user = self.auth.get_current_user()
        if not user:
            print("\nError: User not found.")
            return

        print("\n" + "=" * 70)
        print("UPDATE ITEM STATUS")
        print("=" * 70)

        item_type = input("\nItem type (lost/found): ").strip().lower()
        if item_type not in ['lost', 'found']:
            print("\nInvalid item type.")
            return

        item_id_str = input("Item ID: ").strip()
        try:
            item_id = int(item_id_str)
        except ValueError:
            print("\nInvalid item ID.")
            return

        # Show available statuses
        if item_type == 'lost':
            statuses = ['Active', 'Found', 'Closed']
        else:
            statuses = ['Available', 'Claimed', 'Donated', 'Discarded']

        print("\nAvailable statuses:")
        for idx, status in enumerate(statuses, 1):
            print(f"  {idx}. {status}")

        status_choice = input("\nStatus number: ").strip()
        try:
            new_status = statuses[int(status_choice) - 1]
        except (ValueError, IndexError):
            print("\nInvalid status selection.")
            return

        notes = input("Notes (optional): ").strip()

        try:
            if item_type == 'lost':
                self.service.update_lost_item_status(item_id, new_status, notes)
            else:
                self.service.update_found_item_status(item_id, new_status, notes)

            print(f"\n✓ Item status updated to: {new_status}")

        except Exception as e:
            print(f"\n✗ Error updating status: {e}")

    def view_matches(self):
        """View potential matches for an item."""
        print("\n" + "=" * 70)
        print("VIEW POTENTIAL MATCHES")
        print("=" * 70)

        item_type = input("\nItem type (lost/found): ").strip().lower()
        if item_type not in ['lost', 'found']:
            print("\nInvalid item type.")
            return

        item_id_str = input("Item ID: ").strip()
        try:
            item_id = int(item_id_str)
        except ValueError:
            print("\nInvalid item ID.")
            return

        try:
            matches = self.service.get_matches(item_type, item_id)

            if not matches:
                print("\nNo potential matches found.")
                return

            print(f"\nFound {len(matches)} potential matches:")
            print('=' * 70)

            for match in matches:
                print(f"\nMatch Score: {match['match_score']:.1f}%")
                print(f"Item: {match['item_name']}")
                print(f"Description: {match['description'][:100]}...")

                location_field = 'found_location' if item_type == 'lost' else 'lost_location'
                date_field = 'found_date' if item_type == 'lost' else 'lost_date'

                print(f"Location: {match[location_field]}")
                print(f"Date: {match[date_field]}")

                if match.get('match_reasons'):
                    import json
                    reasons = json.loads(match['match_reasons'])
                    print("Match Reasons:")
                    for reason in reasons:
                        print(f"  - {reason}")

                print("-" * 70)

        except Exception as e:
            print(f"\n✗ Error retrieving matches: {e}")

    def submit_claim(self):
        """Submit a claim for a found item."""
        user = self.auth.get_current_user()
        if not user:
            print("\nError: User not found.")
            return

        student_id = user['username']

        print("\n" + "=" * 70)
        print("SUBMIT CLAIM FOR FOUND ITEM")
        print("=" * 70)

        item_id_str = input("\nFound Item ID: ").strip()
        try:
            found_item_id = int(item_id_str)
        except ValueError:
            print("\nInvalid item ID.")
            return

        # Get item details and verification questions
        try:
            item = self.service.get_found_item(found_item_id)
            if not item:
                print("\nItem not found.")
                return

            print(f"\nItem: {item['item_name']}")
            print(f"Description: {item['description']}")
            print(f"Found at: {item['found_location']} on {item['found_date']}")

            claim_description = input("\nWhy do you believe this is your item? ").strip()
            if not claim_description:
                print("\nClaim description is required.")
                return

            verification_answers = {}

            # Answer verification questions if any
            if item.get('verification_questions'):
                print("\nPlease answer the following verification questions:")
                for q in item['verification_questions']:
                    answer = input(f"\n{q['question_text']}\nYour answer: ").strip()
                    verification_answers[q['question_id']] = answer

            supporting_evidence = input("\nAdditional supporting evidence (optional): ").strip()

            # Confirm
            confirm = input("\nSubmit this claim? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("\nClaim cancelled.")
                return

            claim_id = self.service.submit_claim(
                found_item_id=found_item_id,
                claimant_id=student_id,
                claim_description=claim_description,
                verification_answers=verification_answers if verification_answers else None,
                supporting_evidence=supporting_evidence
            )

            print(f"\n✓ Claim submitted successfully! Claim ID: {claim_id}")
            print("Your claim will be reviewed by staff.")

        except Exception as e:
            print(f"\n✗ Error submitting claim: {e}")

    def view_my_claims(self):
        """View claims submitted by current user."""
        user = self.auth.get_current_user()
        if not user:
            print("\nError: User not found.")
            return

        student_id = user['username']

        print("\n" + "=" * 70)
        print("MY CLAIMS")
        print("=" * 70)

        try:
            claims = self.service.get_claims(claimant_id=student_id)

            if not claims:
                print("\nYou haven't submitted any claims.")
                return

            print(f"\nTotal: {len(claims)} claims")
            print('=' * 70)

            for claim in claims:
                print(f"\nClaim ID: {claim['claim_id']}")
                print(f"Found Item ID: {claim['found_item_id']}")
                print(f"Status: {claim['status']}")
                print(f"Submitted: {claim['submitted_at']}")
                print(f"Description: {claim['claim_description'][:100]}...")

                if claim.get('reviewed_at'):
                    print(f"Reviewed: {claim['reviewed_at']}")
                    if claim.get('resolution_notes'):
                        print(f"Notes: {claim['resolution_notes']}")

                print("-" * 70)

        except Exception as e:
            print(f"\n✗ Error retrieving claims: {e}")

    def review_claims(self):
        """Review and approve/reject claims (staff only)."""
        user = self.auth.get_current_user()
        if not user:
            print("\nError: User not found.")
            return

        # Check if user has permission (admin/staff)
        user_role = user.get('role', '').lower()
        if user_role not in ['admin', 'staff']:
            print("\n✗ Only staff members can review claims.")
            return

        reviewer_id = user['username']

        print("\n" + "=" * 70)
        print("REVIEW CLAIMS")
        print("=" * 70)

        try:
            # Get pending claims
            claims = self.service.get_claims(status='Pending')

            if not claims:
                print("\nNo pending claims to review.")
                return

            print(f"\nPending claims: {len(claims)}")
            print('=' * 70)

            for claim in claims:
                print(f"\nClaim ID: {claim['claim_id']}")
                print(f"Found Item ID: {claim['found_item_id']}")
                print(f"Claimant: {claim['claimant_id']}")
                print(f"Submitted: {claim['submitted_at']}")
                print(f"Description: {claim['claim_description']}")

                if claim.get('verification_answers'):
                    import json
                    print("\nVerification Answers:")
                    answers = json.loads(claim['verification_answers'])
                    for qid, answer in answers.items():
                        print(f"  Q{qid}: {answer}")

                if claim.get('supporting_evidence'):
                    print(f"\nSupporting Evidence: {claim['supporting_evidence']}")

                print("-" * 70)

                # Review decision
                decision = input("\nReview this claim? (approve/reject/skip): ").strip().lower()

                if decision in ['approve', 'reject']:
                    notes = input("Resolution notes: ").strip()

                    approved = (decision == 'approve')
                    self.service.review_claim(
                        claim_id=claim['claim_id'],
                        reviewer_id=reviewer_id,
                        approved=approved,
                        resolution_notes=notes
                    )

                    print(f"\n✓ Claim {decision}d successfully.")
                elif decision == 'skip':
                    continue
                else:
                    print("\nInvalid option, skipping.")

        except Exception as e:
            print(f"\n✗ Error reviewing claims: {e}")

    def view_statistics(self):
        """View system statistics."""
        print("\n" + "=" * 70)
        print("LOST & FOUND STATISTICS")
        print("=" * 70)

        try:
            stats = self.service.get_statistics()

            print("\nLost Items:")
            if stats.get('lost_items'):
                lost = stats['lost_items']
                print(f"  Total: {lost.get('total', 0)}")
                print(f"  Active: {lost.get('active', 0)}")
                print(f"  Found: {lost.get('found', 0)}")

            print("\nFound Items:")
            if stats.get('found_items'):
                found = stats['found_items']
                print(f"  Total: {found.get('total', 0)}")
                print(f"  Available: {found.get('available', 0)}")
                print(f"  Claimed: {found.get('claimed', 0)}")

            print("\nClaims:")
            if stats.get('claims'):
                claims = stats['claims']
                print(f"  Total: {claims.get('total', 0)}")
                print(f"  Pending: {claims.get('pending', 0)}")
                print(f"  Approved: {claims.get('approved', 0)}")
                print(f"  Rejected: {claims.get('rejected', 0)}")

            print("\nMatches:")
            if stats.get('matches'):
                matches = stats['matches']
                print(f"  Total Matches: {matches.get('total_matches', 0)}")
                avg_score = matches.get('avg_score', 0)
                if avg_score:
                    print(f"  Average Match Score: {avg_score:.1f}%")

            # Category breakdown
            category_stats = self.service.get_category_breakdown()

            print("\n" + "-" * 70)
            print("Category Breakdown:")
            print("-" * 70)

            print("\nLost Items by Category:")
            if category_stats.get('lost'):
                for cat in category_stats['lost']:
                    print(f"  {cat['category']}: {cat['count']}")

            print("\nFound Items by Category:")
            if category_stats.get('found'):
                for cat in category_stats['found']:
                    print(f"  {cat['category']}: {cat['count']}")

            print("=" * 70)

        except Exception as e:
            print(f"\n✗ Error retrieving statistics: {e}")


def display_lost_found_menu():
    """Entry point for the Lost & Found CLI menu."""
    cli = LostFoundCLI()
    cli.display_menu()
