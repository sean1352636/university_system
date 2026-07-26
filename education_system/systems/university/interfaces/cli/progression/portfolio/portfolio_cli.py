"""
Portfolio CLI Interface - Achievement & Portfolio System

Interactive command-line interface for managing student portfolios,
achievements, badges, skills, endorsements, and resumes.
"""

from typing import Optional
from datetime import datetime

from education_system.systems.university.domain.progression.portfolio.services.portfolio_service import PortfolioService
from education_system.systems.university.infrastructure.shared_context import get_auth


class PortfolioCLI:
    """
    CLI interface for portfolio management.

    Features:
    - Create and edit portfolio
    - Manage portfolio items
    - View badges and achievements
    - Manage skills and endorsements
    - Generate resumes
    - Configure public profile
    - View portfolio statistics
    """

    def __init__(self):
        """Initialize CLI interface."""
        self.service = PortfolioService()
        self.auth = get_auth()

    def main_menu(self):
        """Display main portfolio menu."""
        while True:
            print("\n" + "=" * 70)
            print("ACHIEVEMENT & PORTFOLIO SYSTEM")
            print("=" * 70)

            if not self.auth.is_logged_in():
                print("\nPlease log in to access portfolio features.")
                return

            user = self.auth.get_current_user()
            student_id = user.get('user_id')

            # Get portfolio stats
            stats = self.service.get_portfolio_stats(student_id)

            print(f"\nWelcome, {user.get('name', student_id)}!")
            print(f"\nPortfolio Completeness: {stats.get('completeness_score', 0)}%")
            print(f"Total Items: {stats.get('total_items', 0)}")
            print(f"Skills: {stats.get('total_skills', 0)}")
            print(f"Endorsements: {stats.get('total_endorsements', 0)}")
            print(f"Verified Badges: {stats.get('verified_badges', 0)}")
            print(f"Profile Views: {stats.get('profile_views', 0)}")

            print("\n1.  Portfolio Management")
            print("2.  Add Portfolio Item")
            print("3.  Edit Portfolio Item")
            print("4.  Delete Portfolio Item")
            print("5.  View My Portfolio")
            print("6.  Manage Skills")
            print("7.  View My Badges")
            print("8.  View Endorsements")
            print("9.  View Endorsement Details")
            print("10. Request Endorsement")
            print("11. Resume Builder")
            print("12. Public Profile Settings")
            print("13. Share Portfolio")
            print("14. Portfolio Statistics")
            print("0.  Back to Main Menu")

            choice = input("\nEnter your choice: ").strip()

            if choice == '1':
                self.portfolio_management_menu(student_id)
            elif choice == '2':
                self.add_portfolio_item(student_id)
            elif choice == '3':
                self.edit_portfolio_item(student_id)
            elif choice == '4':
                self.delete_portfolio_item(student_id)
            elif choice == '5':
                self.view_portfolio(student_id)
            elif choice == '6':
                self.manage_skills_menu(student_id)
            elif choice == '7':
                self.view_badges(student_id)
            elif choice == '8':
                self.view_endorsements(student_id)
            elif choice == '9':
                self.view_endorsement_details(student_id)
            elif choice == '10':
                self.request_endorsement(student_id)
            elif choice == '11':
                self.resume_builder_menu(student_id)
            elif choice == '12':
                self.public_profile_settings(student_id)
            elif choice == '13':
                self.share_portfolio(student_id)
            elif choice == '14':
                self.view_statistics(student_id)
            elif choice == '0':
                break
            else:
                print("Invalid choice. Please try again.")

    def portfolio_management_menu(self, student_id: str):
        """Portfolio creation and editing menu."""
        while True:
            print("\n" + "=" * 70)
            print("PORTFOLIO MANAGEMENT")
            print("=" * 70)

            # Check if portfolio exists
            portfolio = self.service.get_portfolio(student_id)

            if portfolio:
                print(f"\nPortfolio: {portfolio['title']}")
                print(f"Headline: {portfolio.get('headline', 'N/A')}")
                print(f"Public: {'Yes' if portfolio.get('is_public') else 'No'}")
                print(f"Last Updated: {portfolio.get('updated_at', 'N/A')}")

            print("\n1. Create Portfolio" if not portfolio else "1. Edit Portfolio")
            print("2. Update Bio")
            print("3. Update Links (LinkedIn, GitHub, Website)")
            print("4. Toggle Public Visibility")
            print("0. Back")

            choice = input("\nEnter your choice: ").strip()

            if choice == '1':
                if portfolio:
                    self.edit_portfolio(student_id, portfolio)
                else:
                    self.create_portfolio(student_id)
            elif choice == '2':
                self.update_bio(student_id)
            elif choice == '3':
                self.update_links(student_id)
            elif choice == '4':
                self.toggle_visibility(student_id)
            elif choice == '0':
                break
            else:
                print("Invalid choice.")

    def create_portfolio(self, student_id: str):
        """Create a new portfolio."""
        print("\n--- CREATE PORTFOLIO ---")

        title = input("Portfolio Title: ").strip()
        if not title:
            print("Title is required.")
            return

        headline = input("Professional Headline (e.g., 'Computer Science Student'): ").strip()
        bio = input("Bio/About (press Enter to skip): ").strip()
        linkedin_url = input("LinkedIn URL (press Enter to skip): ").strip()
        github_url = input("GitHub URL (press Enter to skip): ").strip()
        personal_website = input("Personal Website (press Enter to skip): ").strip()

        success, message, portfolio_id = self.service.create_portfolio(
            student_id=student_id,
            title=title,
            headline=headline,
            bio=bio if bio else None,
            linkedin_url=linkedin_url if linkedin_url else None,
            github_url=github_url if github_url else None,
            personal_website=personal_website if personal_website else None
        )

        print(f"\n{message}")

        if success:
            # Get public URL
            public_url = self.service.get_portfolio_url(student_id)
            print(f"Your portfolio URL: {public_url}")

    def edit_portfolio(self, student_id: str, portfolio: dict):
        """Edit existing portfolio."""
        print("\n--- EDIT PORTFOLIO ---")
        print("Press Enter to keep current value")

        title = input(f"Title [{portfolio['title']}]: ").strip()
        headline = input(f"Headline [{portfolio.get('headline', '')}]: ").strip()

        updates = {}
        if title:
            updates['title'] = title
        if headline:
            updates['headline'] = headline

        if updates:
            success, message = self.service.update_portfolio(
                portfolio['portfolio_id'],
                **updates
            )
            print(f"\n{message}")
        else:
            print("\nNo changes made.")

    def update_bio(self, student_id: str):
        """Update portfolio bio."""
        portfolio = self.service.get_portfolio(student_id)
        if not portfolio:
            print("\nPlease create a portfolio first.")
            return

        print("\n--- UPDATE BIO ---")
        print("Current bio:")
        print(portfolio.get('bio', 'N/A'))
        print("\nEnter new bio (or press Enter to cancel):")
        bio = input().strip()

        if bio:
            success, message = self.service.update_portfolio(
                portfolio['portfolio_id'],
                bio=bio
            )
            print(f"\n{message}")

    def update_links(self, student_id: str):
        """Update social/professional links."""
        portfolio = self.service.get_portfolio(student_id)
        if not portfolio:
            print("\nPlease create a portfolio first.")
            return

        print("\n--- UPDATE LINKS ---")
        print("Press Enter to keep current value")

        linkedin = input(f"LinkedIn [{portfolio.get('linkedin_url', '')}]: ").strip()
        github = input(f"GitHub [{portfolio.get('github_url', '')}]: ").strip()
        website = input(f"Website [{portfolio.get('personal_website', '')}]: ").strip()

        updates = {}
        if linkedin:
            updates['linkedin_url'] = linkedin
        if github:
            updates['github_url'] = github
        if website:
            updates['personal_website'] = website

        if updates:
            success, message = self.service.update_portfolio(
                portfolio['portfolio_id'],
                **updates
            )
            print(f"\n{message}")

    def toggle_visibility(self, student_id: str):
        """Toggle portfolio public visibility."""
        portfolio = self.service.get_portfolio(student_id)
        if not portfolio:
            print("\nPlease create a portfolio first.")
            return

        current = portfolio.get('is_public', False)
        new_value = not current

        success, message = self.service.update_portfolio(
            portfolio['portfolio_id'],
            is_public=new_value
        )

        print(f"\n{message}")
        print(f"Portfolio is now {'PUBLIC' if new_value else 'PRIVATE'}")

    def add_portfolio_item(self, student_id: str):
        """Add a new portfolio item."""
        portfolio = self.service.get_portfolio(student_id)
        if not portfolio:
            print("\nPlease create a portfolio first.")
            return

        print("\n--- ADD PORTFOLIO ITEM ---")
        print("\nCategories:")
        print("1. Project")
        print("2. Research")
        print("3. Leadership")
        print("4. Work Experience")
        print("5. Award")
        print("6. Certification")
        print("7. Publication")
        print("8. Presentation")

        cat_choice = input("\nSelect category: ").strip()
        category_map = {
            '1': 'project', '2': 'research', '3': 'leadership',
            '4': 'work_experience', '5': 'award', '6': 'certification',
            '7': 'publication', '8': 'presentation'
        }

        category = category_map.get(cat_choice)
        if not category:
            print("Invalid category.")
            return

        title = input("Title: ").strip()
        if not title:
            print("Title is required.")
            return

        description = input("Description: ").strip()
        organization = input("Organization (press Enter to skip): ").strip()
        role = input("Role/Position (press Enter to skip): ").strip()
        start_date = input("Start Date (YYYY-MM-DD, press Enter to skip): ").strip()
        end_date = input("End Date (YYYY-MM-DD, press Enter to skip): ").strip()

        is_current = False
        if not end_date and start_date:
            is_current = input("Is this current? (y/n): ").strip().lower() == 'y'

        technologies = input("Technologies/Skills used (comma-separated, press Enter to skip): ").strip()
        url = input("Project URL/Link (press Enter to skip): ").strip()

        is_featured = input("Feature this item? (y/n): ").strip().lower() == 'y'

        success, message, item_id = self.service.add_portfolio_item(
            portfolio_id=portfolio['portfolio_id'],
            category=category,
            title=title,
            description=description if description else None,
            organization=organization if organization else None,
            role=role if role else None,
            start_date=start_date if start_date else None,
            end_date=end_date if end_date else None,
            is_current=is_current,
            technologies=technologies if technologies else None,
            url=url if url else None,
            is_featured=is_featured
        )

        print(f"\n{message}")

    def _select_portfolio_item(self, student_id: str, action: str):
        """Prompt the user to pick a portfolio item; returns the item dict or None."""
        portfolio = self.service.get_portfolio(student_id)
        if not portfolio:
            print("\nPlease create a portfolio first.")
            return None

        items = self.service.get_portfolio_items(portfolio['portfolio_id'])
        if not items:
            print("\nNo portfolio items found.")
            return None

        print(f"\nSelect an item to {action}:")
        for i, item in enumerate(items, 1):
            category = item.get('category', '').replace('_', ' ').title()
            print(f"{i}. [{category}] {item['title']}")

        try:
            idx = int(input("\nEnter item number (0 to cancel): ")) - 1
        except ValueError:
            print("Invalid input.")
            return None

        if idx < 0 or idx >= len(items):
            return None
        return items[idx]

    def edit_portfolio_item(self, student_id: str):
        """Edit an existing portfolio item."""
        item = self._select_portfolio_item(student_id, "edit")
        if not item:
            return

        print(f"\n--- EDIT ITEM: {item['title']} ---")
        print("Press Enter to keep current value")

        title = input(f"Title [{item.get('title', '')}]: ").strip()
        description = input(f"Description [{item.get('description', '') or ''}]: ").strip()
        organization = input(f"Organization [{item.get('organization', '') or ''}]: ").strip()
        role = input(f"Role [{item.get('role', '') or ''}]: ").strip()

        updates = {}
        if title:
            updates['title'] = title
        if description:
            updates['description'] = description
        if organization:
            updates['organization'] = organization
        if role:
            updates['role'] = role

        if updates:
            success, message = self.service.update_portfolio_item(item['item_id'], **updates)
            print(f"\n{message}")
        else:
            print("\nNo changes made.")

    def delete_portfolio_item(self, student_id: str):
        """Delete a portfolio item."""
        item = self._select_portfolio_item(student_id, "delete")
        if not item:
            return

        confirm = input(f"Delete '{item['title']}'? (y/n): ").strip().lower()
        if confirm != 'y':
            print("\nCancelled.")
            return

        success, message = self.service.delete_portfolio_item(item['item_id'])
        print(f"\n{message}")

    def view_portfolio(self, student_id: str):
        """View complete portfolio."""
        portfolio = self.service.get_portfolio(student_id)
        if not portfolio:
            print("\nNo portfolio found. Please create one first.")
            return

        print("\n" + "=" * 70)
        print(f"PORTFOLIO: {portfolio['title']}")
        print("=" * 70)

        if portfolio.get('headline'):
            print(f"\n{portfolio['headline']}")

        if portfolio.get('bio'):
            print(f"\n{portfolio['bio']}")

        # Display links
        print("\nLinks:")
        if portfolio.get('linkedin_url'):
            print(f"  LinkedIn: {portfolio['linkedin_url']}")
        if portfolio.get('github_url'):
            print(f"  GitHub: {portfolio['github_url']}")
        if portfolio.get('personal_website'):
            print(f"  Website: {portfolio['personal_website']}")

        # Display items by category
        items_by_cat = portfolio.get('items_by_category', {})

        for category, items in items_by_cat.items():
            print(f"\n{category.upper().replace('_', ' ')}:")
            print("-" * 70)

            for item in items:
                print(f"\n  {item['title']}")
                if item.get('featured'):
                    print("  [FEATURED]")
                if item.get('organization'):
                    print(f"  Organization: {item['organization']}")
                if item.get('role'):
                    print(f"  Role: {item['role']}")
                if item.get('start_date'):
                    date_str = f"  {item['start_date']}"
                    if item.get('is_current'):
                        date_str += " - Present"
                    elif item.get('end_date'):
                        date_str += f" - {item['end_date']}"
                    print(date_str)
                if item.get('description'):
                    print(f"  {item['description']}")
                if item.get('technologies'):
                    print(f"  Technologies: {item['technologies']}")
                if item.get('url'):
                    print(f"  URL: {item['url']}")

        input("\nPress Enter to continue...")

    def manage_skills_menu(self, student_id: str):
        """Skills management menu."""
        while True:
            print("\n" + "=" * 70)
            print("SKILLS MANAGEMENT")
            print("=" * 70)

            skills = self.service.get_student_skills(student_id)

            if skills:
                print(f"\nYour Skills ({len(skills)}):")
                for i, skill in enumerate(skills, 1):
                    endorsements = skill.get('endorsement_count', 0)
                    featured = " [FEATURED]" if skill.get('is_featured') else ""
                    print(f"{i}. {skill['skill_name']}{featured}")
                    print(f"   Category: {skill.get('skill_category', 'N/A')}")
                    print(f"   Proficiency: {skill.get('proficiency_level', 'N/A')}")
                    print(f"   Endorsements: {endorsements}")
            else:
                print("\nNo skills added yet.")

            print("\n1. Add Skill")
            print("2. Update Skill")
            print("3. Remove Skill")
            print("4. Feature/Unfeature Skill")
            print("0. Back")

            choice = input("\nEnter your choice: ").strip()

            if choice == '1':
                self.add_skill(student_id)
            elif choice == '2':
                self.update_skill(student_id, skills)
            elif choice == '3':
                self.remove_skill(student_id, skills)
            elif choice == '4':
                self.toggle_featured_skill(student_id, skills)
            elif choice == '0':
                break

    def add_skill(self, student_id: str):
        """Add a new skill."""
        print("\n--- ADD SKILL ---")

        skill_name = input("Skill Name: ").strip()
        if not skill_name:
            print("Skill name is required.")
            return

        print("\nSkill Category:")
        print("1. Technical")
        print("2. Soft Skill")
        print("3. Language")
        print("4. Tool")
        print("5. Domain")

        cat_choice = input("Select category: ").strip()
        cat_map = {
            '1': 'technical', '2': 'soft_skill', '3': 'language',
            '4': 'tool', '5': 'domain'
        }
        skill_category = cat_map.get(cat_choice)

        print("\nProficiency Level:")
        print("1. Beginner")
        print("2. Intermediate")
        print("3. Advanced")
        print("4. Expert")

        prof_choice = input("Select proficiency: ").strip()
        prof_map = {
            '1': 'beginner', '2': 'intermediate', '3': 'advanced', '4': 'expert'
        }
        proficiency = prof_map.get(prof_choice)

        years_str = input("Years of experience (press Enter to skip): ").strip()
        years_experience = float(years_str) if years_str else None

        is_featured = input("Feature this skill? (y/n): ").strip().lower() == 'y'

        success, message, skill_id = self.service.add_skill(
            student_id=student_id,
            skill_name=skill_name,
            skill_category=skill_category,
            proficiency_level=proficiency,
            years_experience=years_experience,
            is_featured=is_featured
        )

        print(f"\n{message}")

    def update_skill(self, student_id: str, skills: list):
        """Update skill proficiency."""
        if not skills:
            print("\nNo skills to update.")
            return

        try:
            idx = int(input("Enter skill number to update: ")) - 1
            if idx < 0 or idx >= len(skills):
                print("Invalid selection.")
                return

            skill = skills[idx]

            print(f"\n--- UPDATE SKILL: {skill['skill_name']} ---")

            print("\nProficiency Level:")
            print("1. Beginner")
            print("2. Intermediate")
            print("3. Advanced")
            print("4. Expert")

            prof_choice = input("Select new proficiency (press Enter to skip): ").strip()
            prof_map = {
                '1': 'beginner', '2': 'intermediate', '3': 'advanced', '4': 'expert'
            }

            updates = {}
            if prof_choice in prof_map:
                updates['proficiency_level'] = prof_map[prof_choice]

            years_str = input("Years of experience (press Enter to skip): ").strip()
            if years_str:
                updates['years_experience'] = float(years_str)

            if updates:
                success, message = self.service.update_skill(skill['skill_id'], **updates)
                print(f"\n{message}")

        except ValueError:
            print("Invalid input.")

    def remove_skill(self, student_id: str, skills: list):
        """Remove a skill."""
        if not skills:
            print("\nNo skills to remove.")
            return

        try:
            idx = int(input("Enter skill number to remove: ")) - 1
            if idx < 0 or idx >= len(skills):
                print("Invalid selection.")
                return

            skill = skills[idx]
            confirm = input(f"Remove '{skill['skill_name']}'? (y/n): ").strip().lower()

            if confirm == 'y':
                success, message = self.service.remove_skill(skill['skill_id'])
                print(f"\n{message}")

        except ValueError:
            print("Invalid input.")

    def toggle_featured_skill(self, student_id: str, skills: list):
        """Toggle featured status of a skill."""
        if not skills:
            print("\nNo skills available.")
            return

        try:
            idx = int(input("Enter skill number to toggle featured: ")) - 1
            if idx < 0 or idx >= len(skills):
                print("Invalid selection.")
                return

            skill = skills[idx]
            new_featured = not skill.get('is_featured', False)

            success, message = self.service.update_skill(
                skill['skill_id'],
                is_featured=new_featured
            )
            print(f"\n{message}")

        except ValueError:
            print("Invalid input.")

    def view_badges(self, student_id: str):
        """View all badges."""
        badges = self.service.get_student_badges(student_id)

        print("\n" + "=" * 70)
        print("MY BADGES")
        print("=" * 70)

        if not badges:
            print("\nNo badges earned yet.")
        else:
            for badge in badges:
                print(f"\n{badge['badge_name']}")
                print(f"Type: {badge['badge_type'].replace('_', ' ').title()}")
                print(f"Issuer: {badge['issuer']}")
                print(f"Issued: {badge['issue_date']}")
                print(f"Status: {badge['verification_status'].upper()}")
                if badge.get('description'):
                    print(f"Description: {badge['description']}")
                print(f"Verification Code: {badge['verification_code']}")

        input("\nPress Enter to continue...")

    def view_endorsements(self, student_id: str):
        """View all endorsements received."""
        endorsements = self.service.get_student_endorsements(student_id)

        print("\n" + "=" * 70)
        print("ENDORSEMENTS RECEIVED")
        print("=" * 70)

        if not endorsements:
            print("\nNo endorsements received yet.")
        else:
            for e in endorsements:
                print(f"\n{e['skill_name']}")
                print(f"Endorsed by: {e['endorser_id']} ({e['endorser_role']})")
                if e.get('relationship'):
                    print(f"Relationship: {e['relationship']}")
                if e.get('comment'):
                    print(f"Comment: {e['comment']}")
                print(f"Date: {e['endorsed_at']}")

        input("\nPress Enter to continue...")

    def view_endorsement_details(self, student_id: str):
        """View full details of a single endorsement."""
        endorsements = self.service.get_student_endorsements(student_id)

        if not endorsements:
            print("\nNo endorsements received yet.")
            return

        print("\n--- VIEW ENDORSEMENT DETAILS ---")
        for i, e in enumerate(endorsements, 1):
            print(f"{i}. {e['skill_name']} - endorsed by {e['endorser_id']}")

        try:
            idx = int(input("\nSelect endorsement (0 to cancel): ")) - 1
        except ValueError:
            print("Invalid input.")
            return

        if idx < 0 or idx >= len(endorsements):
            return

        e = endorsements[idx]
        print("\n" + "=" * 70)
        print(f"Skill: {e['skill_name']}")
        print(f"Endorsed by: {e['endorser_id']} ({e['endorser_role']})")
        if e.get('relationship'):
            print(f"Relationship: {e['relationship']}")
        if e.get('comment'):
            print(f"Comment: {e['comment']}")
        print(f"Date: {e['endorsed_at']}")
        print("=" * 70)

        input("\nPress Enter to continue...")

    def request_endorsement(self, student_id: str):
        """Request skill endorsement."""
        skills = self.service.get_student_skills(student_id)

        if not skills:
            print("\nPlease add skills first.")
            return

        print("\n--- REQUEST ENDORSEMENT ---")
        print("\nYour Skills:")
        for i, skill in enumerate(skills, 1):
            print(f"{i}. {skill['skill_name']}")

        try:
            idx = int(input("\nSelect skill: ")) - 1
            if idx < 0 or idx >= len(skills):
                print("Invalid selection.")
                return

            skill = skills[idx]
            endorser_id = input("Endorser ID (email or username): ").strip()
            message = input("Message (optional): ").strip()

            success, msg = self.service.request_endorsement(
                skill['skill_id'],
                endorser_id,
                message if message else None
            )

            print(f"\n{msg}")

        except ValueError:
            print("Invalid input.")

    def resume_builder_menu(self, student_id: str):
        """Resume builder menu."""
        while True:
            print("\n" + "=" * 70)
            print("RESUME BUILDER")
            print("=" * 70)

            resumes = self.service.get_student_resumes(student_id)

            if resumes:
                print(f"\nYour Resumes ({len(resumes)}):")
                for i, resume in enumerate(resumes, 1):
                    print(f"{i}. {resume['resume_name']}")
                    print(f"   Generated: {resume['last_generated']}")

            print("\n1. Generate New Resume")
            print("2. View Resume")
            print("0. Back")

            choice = input("\nEnter your choice: ").strip()

            if choice == '1':
                self.generate_resume(student_id)
            elif choice == '2':
                self.view_resume(student_id, resumes)
            elif choice == '0':
                break

    def generate_resume(self, student_id: str):
        """Generate a new resume."""
        print("\n--- GENERATE RESUME ---")

        name = input("Resume Name: ").strip()
        if not name:
            print("Resume name is required.")
            return

        print("\nTemplate Type:")
        print("1. Traditional")
        print("2. Modern")
        print("3. Creative")
        print("4. Technical")
        print("5. Academic")

        template_choice = input("Select template: ").strip()
        template_map = {
            '1': 'traditional', '2': 'modern', '3': 'creative',
            '4': 'technical', '5': 'academic'
        }
        template_type = template_map.get(template_choice, 'traditional')

        success, message, resume_data = self.service.generate_resume(
            student_id=student_id,
            resume_name=name,
            template_type=template_type
        )

        print(f"\n{message}")

    def view_resume(self, student_id: str, resumes: list):
        """View a generated resume."""
        if not resumes:
            print("\nNo resumes generated yet.")
            return

        try:
            idx = int(input("Select resume number: ")) - 1
            if idx < 0 or idx >= len(resumes):
                print("Invalid selection.")
                return

            resume = self.service.get_resume(resumes[idx]['resume_id'])
            if not resume:
                print("Resume not found.")
                return

            content = resume['content']

            print("\n" + "=" * 70)
            print(f"RESUME: {resume['resume_name']}")
            print("=" * 70)
            print(f"Template: {content['template_type'].title()}")
            print(f"Generated: {content['generated_at']}")

            print("\n[Resume content would be formatted here]")

            input("\nPress Enter to continue...")

        except ValueError:
            print("Invalid input.")

    def public_profile_settings(self, student_id: str):
        """Configure public profile settings."""
        profile = self.service.get_public_profile(student_id)
        if not profile:
            print("\nPublic profile not found.")
            return

        print("\n" + "=" * 70)
        print("PUBLIC PROFILE SETTINGS")
        print("=" * 70)

        print(f"\nVisibility: {profile.get('visibility', 'private').upper()}")
        print(f"Show Contact: {profile.get('show_contact', False)}")
        print(f"Show GPA: {profile.get('show_gpa', False)}")
        print(f"Show Projects: {profile.get('show_projects', True)}")
        print(f"Show Skills: {profile.get('show_skills', True)}")
        print(f"Show Endorsements: {profile.get('show_endorsements', True)}")

        print("\nUpdate Settings:")
        print("1. Public")
        print("2. Unlisted")
        print("3. Private")

        vis_choice = input("Select visibility (or Enter to skip): ").strip()
        vis_map = {'1': 'public', '2': 'unlisted', '3': 'private'}

        updates = {}
        if vis_choice in vis_map:
            updates['visibility'] = vis_map[vis_choice]

        show_contact = input("Show contact info? (y/n/Enter to skip): ").strip().lower()
        if show_contact in ['y', 'n']:
            updates['show_contact'] = show_contact == 'y'

        show_gpa = input("Show GPA? (y/n/Enter to skip): ").strip().lower()
        if show_gpa in ['y', 'n']:
            updates['show_gpa'] = show_gpa == 'y'

        if updates:
            success, message = self.service.update_public_profile(student_id, **updates)
            print(f"\n{message}")

    def share_portfolio(self, student_id: str):
        """Display portfolio sharing options."""
        url = self.service.get_portfolio_url(student_id)

        if not url:
            print("\nPortfolio not found.")
            return

        print("\n" + "=" * 70)
        print("SHARE PORTFOLIO")
        print("=" * 70)

        print(f"\nYour Portfolio URL: {url}")
        print("\nShare this URL with:")
        print("- Employers")
        print("- Internship coordinators")
        print("- Academic advisors")
        print("- Professional networks")

        print("\nNote: Make sure your profile visibility is set to 'public' or 'unlisted'")

        input("\nPress Enter to continue...")

    def view_statistics(self, student_id: str):
        """View detailed portfolio statistics."""
        stats = self.service.get_portfolio_stats(student_id)

        print("\n" + "=" * 70)
        print("PORTFOLIO STATISTICS")
        print("=" * 70)

        print(f"\nCompleteness Score: {stats.get('completeness_score', 0)}%")
        print(f"Total Portfolio Items: {stats.get('total_items', 0)}")

        items_by_cat = stats.get('items_by_category', {})
        if items_by_cat:
            print("\nItems by Category:")
            for category, count in items_by_cat.items():
                print(f"  {category.replace('_', ' ').title()}: {count}")

        print(f"\nTotal Skills: {stats.get('total_skills', 0)}")
        print(f"Total Endorsements: {stats.get('total_endorsements', 0)}")
        print(f"Verified Badges: {stats.get('verified_badges', 0)}")
        print(f"Achievement Points: {stats.get('achievement_points', 0)}")

        print(f"\nProfile Visibility: {stats.get('profile_visibility', 'private').upper()}")
        print(f"Profile Views: {stats.get('profile_views', 0)}")

        input("\nPress Enter to continue...")


def main():
    """Run portfolio CLI."""
    cli = PortfolioCLI()
    cli.main_menu()


if __name__ == "__main__":
    main()
