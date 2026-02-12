"""
Student Jobs CLI Interface

Command-line interface for the Student Job Board system.
Provides job search, application management, work-study tracking,
and skill-based matching features.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from typing import Optional

from university_system.infrastructure.shared_context import get_auth
from university_system.modules.domain.student_jobs.services.job_service import (
    JobPostingManager,
    JobApplicationManager,
    EmploymentManager,
    WorkHoursManager,
    SkillMatchingManager,
    PerformanceManager,
)


class StudentJobsCLI:
    """Command-line interface for Student Job Board"""

    def __init__(self):
        self.auth = get_auth()
        self.current_user = None
        if self.auth and self.auth.is_logged_in():
            self.current_user = self.auth.get_current_user()

    def run(self):
        """Main entry point for the CLI"""
        self.main_menu()

    def main_menu(self):
        """Display main menu"""
        while True:
            print("\n" + "=" * 60)
            print("STUDENT JOB BOARD - Main Menu".center(60))
            print("=" * 60)
            print("\n1. Browse Job Postings")
            print("2. My Applications")
            print("3. My Jobs & Work Hours")
            print("4. Skills & Matching")
            print("5. Work-Study Management")
            print("6. Performance Reviews")

            if self._is_admin_or_staff():
                print("\n--- Administration ---")
                print("7. Post New Job")
                print("8. Manage Job Postings")
                print("9. Review Applications")
                print("10. Hire Student")
                print("11. Manage Employment")
                print("12. Approve Hours")

            print("\n0. Return to Main Menu")

            choice = input("\nEnter your choice: ").strip()

            if choice == "0":
                break
            elif choice == "1":
                self.browse_jobs_menu()
            elif choice == "2":
                self.my_applications_menu()
            elif choice == "3":
                self.my_jobs_menu()
            elif choice == "4":
                self.skills_matching_menu()
            elif choice == "5":
                self.work_study_menu()
            elif choice == "6":
                self.performance_reviews_menu()
            elif choice == "7" and self._is_admin_or_staff():
                self.post_job()
            elif choice == "8" and self._is_admin_or_staff():
                self.manage_postings_menu()
            elif choice == "9" and self._is_admin_or_staff():
                self.review_applications_menu()
            elif choice == "10" and self._is_admin_or_staff():
                self.hire_student()
            elif choice == "11" and self._is_admin_or_staff():
                self.manage_employment_menu()
            elif choice == "12" and self._is_admin_or_staff():
                self.approve_hours_menu()
            else:
                print("\n❌ Invalid choice. Please try again.")

    def browse_jobs_menu(self):
        """Browse available job postings"""
        while True:
            print("\n" + "=" * 60)
            print("BROWSE JOB POSTINGS".center(60))
            print("=" * 60)
            print("\n1. View All Active Jobs")
            print("2. Filter by Category")
            print("3. Filter by Employment Type")
            print("4. Work-Study Jobs Only")
            print("5. Search by Location")
            print("6. View Job Details")
            print("7. Apply for Job")
            print("0. Back")

            choice = input("\nEnter your choice: ").strip()

            if choice == "0":
                break
            elif choice == "1":
                self.view_all_jobs()
            elif choice == "2":
                self.filter_by_category()
            elif choice == "3":
                self.filter_by_type()
            elif choice == "4":
                self.view_work_study_jobs()
            elif choice == "5":
                self.search_by_location()
            elif choice == "6":
                self.view_job_details()
            elif choice == "7":
                self.apply_for_job()

    def view_all_jobs(self):
        """Display all active job postings"""
        print("\n" + "-" * 60)
        print("All Active Job Postings")
        print("-" * 60)

        jobs = JobPostingManager.get_active_jobs()

        if not jobs:
            print("\n❌ No active job postings available.")
            return

        for job in jobs:
            self._display_job_summary(job)

        print(f"\nTotal jobs available: {len(jobs)}")

    def filter_by_category(self):
        """Filter jobs by category"""
        print("\nEnter job category (e.g., IT, Library, Food Service, Administrative): ")
        category = input("Category: ").strip()

        if not category:
            print("\n❌ Category cannot be empty.")
            return

        jobs = JobPostingManager.get_active_jobs({'job_category': category})

        if not jobs:
            print(f"\n❌ No jobs found in category '{category}'.")
            return

        print(f"\n{len(jobs)} jobs found in '{category}':")
        for job in jobs:
            self._display_job_summary(job)

    def filter_by_type(self):
        """Filter jobs by employment type"""
        print("\nEmployment Types:")
        print("1. Work-Study")
        print("2. Part-Time")
        print("3. Internship")
        print("4. Temporary")

        choice = input("\nSelect type: ").strip()

        type_map = {
            "1": "work-study",
            "2": "part-time",
            "3": "internship",
            "4": "temp"
        }

        if choice not in type_map:
            print("\n❌ Invalid choice.")
            return

        jobs = JobPostingManager.get_active_jobs({'employment_type': type_map[choice]})

        if not jobs:
            print(f"\n❌ No {type_map[choice]} jobs found.")
            return

        print(f"\n{len(jobs)} {type_map[choice]} jobs found:")
        for job in jobs:
            self._display_job_summary(job)

    def view_work_study_jobs(self):
        """Display work-study jobs only"""
        jobs = JobPostingManager.get_active_jobs({'is_work_study': 1})

        if not jobs:
            print("\n❌ No work-study jobs available.")
            return

        print("\n" + "-" * 60)
        print("Work-Study Job Opportunities")
        print("-" * 60)

        for job in jobs:
            self._display_job_summary(job)

        print(f"\nTotal work-study jobs: {len(jobs)}")

    def search_by_location(self):
        """Search jobs by location"""
        location = input("\nEnter location keyword: ").strip()

        if not location:
            print("\n❌ Location cannot be empty.")
            return

        jobs = JobPostingManager.get_active_jobs({'location': location})

        if not jobs:
            print(f"\n❌ No jobs found in location matching '{location}'.")
            return

        print(f"\n{len(jobs)} jobs found:")
        for job in jobs:
            self._display_job_summary(job)

    def view_job_details(self):
        """View detailed information about a specific job"""
        job_id = input("\nEnter Job ID: ").strip()

        if not job_id.isdigit():
            print("\n❌ Invalid Job ID.")
            return

        job = JobPostingManager.get_job_details(int(job_id))

        if not job:
            print("\n❌ Job not found.")
            return

        self._display_job_details(job)

    def apply_for_job(self):
        """Apply for a job posting"""
        if not self.current_user or self.current_user.get('role') != 'student':
            print("\n❌ Only students can apply for jobs.")
            return

        job_id = input("\nEnter Job ID: ").strip()

        if not job_id.isdigit():
            print("\n❌ Invalid Job ID.")
            return

        job = JobPostingManager.get_job_details(int(job_id))
        if not job:
            print("\n❌ Job not found.")
            return

        print(f"\nApplying for: {job['job_title']} at {job['employer_name']}")
        print("-" * 60)

        cover_letter = input("\nCover Letter (optional, press Enter to skip):\n").strip()
        resume_url = input("Resume URL (optional): ").strip()
        availability = input("Availability (e.g., 'Mon-Fri 2-6pm'): ").strip()
        expected_hours = input("Expected hours per week: ").strip()
        references = input("References (optional): ").strip()

        if not expected_hours.isdigit():
            expected_hours = "0"

        try:
            student_id = self.current_user.get('username', '')
            application_id = JobApplicationManager.apply_for_job(
                student_id=student_id,
                job_id=int(job_id),
                cover_letter=cover_letter,
                resume_url=resume_url,
                availability=availability,
                expected_hours=int(expected_hours),
                references=references
            )

            print(f"\n✓ Application submitted successfully! (Application ID: {application_id})")
            print(f"You will be notified of any updates regarding your application.")

        except Exception as e:
            print(f"\n❌ Error submitting application: {e}")

    def my_applications_menu(self):
        """Manage student's job applications"""
        if not self.current_user or self.current_user.get('role') != 'student':
            print("\n❌ Only students can view applications.")
            return

        while True:
            print("\n" + "=" * 60)
            print("MY APPLICATIONS".center(60))
            print("=" * 60)
            print("\n1. View All Applications")
            print("2. View Pending Applications")
            print("3. View Application Details")
            print("4. Withdraw Application")
            print("0. Back")

            choice = input("\nEnter your choice: ").strip()

            if choice == "0":
                break
            elif choice == "1":
                self.view_my_applications()
            elif choice == "2":
                self.view_pending_applications()
            elif choice == "3":
                self.view_application_details()
            elif choice == "4":
                self.withdraw_application()

    def view_my_applications(self):
        """View all student applications"""
        student_id = self.current_user.get('username', '')
        applications = JobApplicationManager.get_student_applications(student_id)

        if not applications:
            print("\n❌ You have no job applications.")
            return

        print("\n" + "-" * 60)
        print("Your Job Applications")
        print("-" * 60)

        for app in applications:
            self._display_application_summary(app)

        print(f"\nTotal applications: {len(applications)}")

    def view_pending_applications(self):
        """View pending applications"""
        student_id = self.current_user.get('username', '')
        applications = JobApplicationManager.get_student_applications(student_id, 'pending')

        if not applications:
            print("\n❌ You have no pending applications.")
            return

        print("\n" + "-" * 60)
        print("Pending Applications")
        print("-" * 60)

        for app in applications:
            self._display_application_summary(app)

    def view_application_details(self):
        """View detailed application information"""
        application_id = input("\nEnter Application ID: ").strip()

        if not application_id.isdigit():
            print("\n❌ Invalid Application ID.")
            return

        student_id = self.current_user.get('username', '')
        applications = JobApplicationManager.get_student_applications(student_id)

        app = next((a for a in applications if a['application_id'] == int(application_id)), None)

        if not app:
            print("\n❌ Application not found.")
            return

        self._display_application_details(app)

    def withdraw_application(self):
        """Withdraw a job application"""
        application_id = input("\nEnter Application ID to withdraw: ").strip()

        if not application_id.isdigit():
            print("\n❌ Invalid Application ID.")
            return

        confirm = input(f"Are you sure you want to withdraw application {application_id}? (yes/no): ").strip().lower()

        if confirm != 'yes':
            print("\n❌ Withdrawal cancelled.")
            return

        try:
            JobApplicationManager.update_application_status(
                int(application_id),
                'withdrawn',
                'Withdrawn by student'
            )
            print("\n✓ Application withdrawn successfully.")
        except Exception as e:
            print(f"\n❌ Error withdrawing application: {e}")

    def my_jobs_menu(self):
        """Manage student's current jobs and work hours"""
        if not self.current_user or self.current_user.get('role') != 'student':
            print("\n❌ Only students can view their jobs.")
            return

        while True:
            print("\n" + "=" * 60)
            print("MY JOBS & WORK HOURS".center(60))
            print("=" * 60)
            print("\n1. View My Current Jobs")
            print("2. View Employment History")
            print("3. Clock In")
            print("4. Clock Out")
            print("5. View My Hours")
            print("6. View Weekly Summary")
            print("0. Back")

            choice = input("\nEnter your choice: ").strip()

            if choice == "0":
                break
            elif choice == "1":
                self.view_my_jobs()
            elif choice == "2":
                self.view_employment_history()
            elif choice == "3":
                self.clock_in()
            elif choice == "4":
                self.clock_out()
            elif choice == "5":
                self.view_my_hours()
            elif choice == "6":
                self.view_weekly_summary()

    def view_my_jobs(self):
        """View current jobs"""
        student_id = self.current_user.get('username', '')
        jobs = EmploymentManager.get_student_employment(student_id, active_only=True)

        if not jobs:
            print("\n❌ You don't have any active jobs.")
            return

        print("\n" + "-" * 60)
        print("Your Current Jobs")
        print("-" * 60)

        for job in jobs:
            self._display_employment_summary(job)

    def view_employment_history(self):
        """View all employment records"""
        student_id = self.current_user.get('username', '')
        jobs = EmploymentManager.get_student_employment(student_id, active_only=False)

        if not jobs:
            print("\n❌ You don't have any employment history.")
            return

        print("\n" + "-" * 60)
        print("Employment History")
        print("-" * 60)

        for job in jobs:
            self._display_employment_summary(job)

    def clock_in(self):
        """Clock in for work"""
        student_id = self.current_user.get('username', '')
        jobs = EmploymentManager.get_student_employment(student_id, active_only=True)

        if not jobs:
            print("\n❌ You don't have any active jobs.")
            return

        print("\n" + "-" * 60)
        print("Your Active Jobs")
        print("-" * 60)

        for i, job in enumerate(jobs, 1):
            print(f"\n{i}. {job['position_title']} at {job['employer_name']}")
            print(f"   Employment ID: {job['employment_id']}")

        choice = input("\nSelect job number: ").strip()

        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(jobs):
            print("\n❌ Invalid choice.")
            return

        selected_job = jobs[int(choice) - 1]

        work_date = input("Work date (YYYY-MM-DD) [press Enter for today]: ").strip()
        if not work_date:
            work_date = datetime.now().strftime('%Y-%m-%d')

        clock_in_time = input("Clock in time (HH:MM) [press Enter for now]: ").strip()
        if not clock_in_time:
            clock_in_time = datetime.now().strftime('%H:%M')

        task_description = input("Task description (optional): ").strip()

        try:
            log_id = WorkHoursManager.clock_in(
                employment_id=selected_job['employment_id'],
                student_id=student_id,
                work_date=work_date,
                clock_in_time=clock_in_time,
                task_description=task_description
            )

            print(f"\n✓ Clocked in successfully! (Log ID: {log_id})")
            print(f"Work Date: {work_date}")
            print(f"Clock In Time: {clock_in_time}")

        except Exception as e:
            print(f"\n❌ Error clocking in: {e}")

    def clock_out(self):
        """Clock out from work"""
        student_id = self.current_user.get('username', '')

        log_id = input("\nEnter Log ID from when you clocked in: ").strip()

        if not log_id.isdigit():
            print("\n❌ Invalid Log ID.")
            return

        clock_out_time = input("Clock out time (HH:MM) [press Enter for now]: ").strip()
        if not clock_out_time:
            clock_out_time = datetime.now().strftime('%H:%M')

        break_duration = input("Break duration in minutes (0 if none): ").strip()
        if not break_duration.isdigit():
            break_duration = "0"

        try:
            WorkHoursManager.clock_out(
                log_id=int(log_id),
                clock_out_time=clock_out_time,
                break_duration_minutes=int(break_duration)
            )

            print(f"\n✓ Clocked out successfully!")
            print(f"Clock Out Time: {clock_out_time}")

        except Exception as e:
            print(f"\n❌ Error clocking out: {e}")

    def view_my_hours(self):
        """View work hours log"""
        student_id = self.current_user.get('username', '')

        print("\nFilter by date range? (yes/no): ", end="")
        filter_choice = input().strip().lower()

        start_date = None
        end_date = None

        if filter_choice == 'yes':
            start_date = input("Start date (YYYY-MM-DD): ").strip()
            end_date = input("End date (YYYY-MM-DD): ").strip()

        hours = WorkHoursManager.get_student_hours(student_id, start_date, end_date)

        if not hours:
            print("\n❌ No work hours found.")
            return

        print("\n" + "-" * 60)
        print("Your Work Hours")
        print("-" * 60)

        total_hours = 0
        total_earnings = 0

        for record in hours:
            print(f"\nLog ID: {record['log_id']}")
            print(f"Date: {record['work_date']}")
            print(f"Position: {record['position_title']} at {record['employer_name']}")
            print(f"Time: {record['clock_in_time']} - {record['clock_out_time'] or 'Still clocked in'}")

            if record['total_hours']:
                print(f"Hours: {record['total_hours']}")
                print(f"Earnings: ${record['earnings']:.2f}")
                print(f"Status: {record['status']}")
                total_hours += record['total_hours']
                total_earnings += record['earnings']

            if record['task_description']:
                print(f"Tasks: {record['task_description']}")

        print(f"\n{'=' * 60}")
        print(f"Total Hours: {total_hours:.2f}")
        print(f"Total Earnings: ${total_earnings:.2f}")

    def view_weekly_summary(self):
        """View weekly hours summary"""
        student_id = self.current_user.get('username', '')

        week_start = input("\nWeek start date (YYYY-MM-DD) [press Enter for this week]: ").strip()

        if not week_start:
            # Get Monday of current week
            today = datetime.now()
            monday = today - timedelta(days=today.weekday())
            week_start = monday.strftime('%Y-%m-%d')

        summary = WorkHoursManager.get_weekly_summary(student_id, week_start)

        print("\n" + "=" * 60)
        print("Weekly Hours Summary")
        print("=" * 60)
        print(f"\nWeek: {summary['week_start']} to {summary['week_end']}")
        print(f"Total Shifts: {summary['total_shifts'] or 0}")
        print(f"Total Hours: {summary['total_hours'] or 0:.2f}")
        print(f"Approved Hours: {summary['approved_hours'] or 0:.2f}")
        print(f"Pending Hours: {summary['pending_hours'] or 0:.2f}")
        print(f"Total Earnings: ${summary['total_earnings'] or 0:.2f}")

        if summary['total_work_study']:
            print(f"Work-Study Deduction: ${summary['total_work_study']:.2f}")

    def skills_matching_menu(self):
        """Manage skills and view matching jobs"""
        if not self.current_user or self.current_user.get('role') != 'student':
            print("\n❌ Only students can manage skills.")
            return

        while True:
            print("\n" + "=" * 60)
            print("SKILLS & JOB MATCHING".center(60))
            print("=" * 60)
            print("\n1. View My Skills")
            print("2. Add New Skill")
            print("3. Find Matching Jobs")
            print("4. View Skill Requirements for Job")
            print("0. Back")

            choice = input("\nEnter your choice: ").strip()

            if choice == "0":
                break
            elif choice == "1":
                self.view_my_skills()
            elif choice == "2":
                self.add_skill()
            elif choice == "3":
                self.find_matching_jobs()
            elif choice == "4":
                self.view_skill_requirements()

    def view_my_skills(self):
        """View student's skills"""
        student_id = self.current_user.get('username', '')
        skills = SkillMatchingManager.get_student_skills(student_id)

        if not skills:
            print("\n❌ You haven't added any skills yet.")
            return

        print("\n" + "-" * 60)
        print("Your Skills")
        print("-" * 60)

        for skill in skills:
            verified = "✓ Verified" if skill['verified'] else "Not verified"
            print(f"\n• {skill['skill_name']}")
            print(f"  Category: {skill['skill_category']}")
            print(f"  Proficiency: {skill['proficiency_level']}")
            print(f"  Experience: {skill['years_experience'] or 0} years")
            print(f"  Status: {verified}")

    def add_skill(self):
        """Add a new skill"""
        student_id = self.current_user.get('username', '')

        print("\n" + "-" * 60)
        print("Add New Skill")
        print("-" * 60)

        skill_name = input("\nSkill name: ").strip()

        if not skill_name:
            print("\n❌ Skill name cannot be empty.")
            return

        print("\nSkill Categories:")
        print("1. Technical")
        print("2. Language")
        print("3. Software")
        print("4. Certification")
        print("5. Soft Skill")
        print("6. Other")

        category_choice = input("\nSelect category: ").strip()
        category_map = {
            "1": "technical",
            "2": "language",
            "3": "software",
            "4": "certification",
            "5": "soft-skill",
            "6": "other"
        }

        skill_category = category_map.get(category_choice, "other")

        print("\nProficiency Levels:")
        print("1. Beginner")
        print("2. Intermediate")
        print("3. Advanced")
        print("4. Expert")

        prof_choice = input("\nSelect proficiency: ").strip()
        prof_map = {
            "1": "beginner",
            "2": "intermediate",
            "3": "advanced",
            "4": "expert"
        }

        proficiency_level = prof_map.get(prof_choice, "beginner")

        years_experience = input("Years of experience (0 if none): ").strip()
        if not years_experience or not years_experience.replace('.', '').isdigit():
            years_experience = "0"

        try:
            skill_id = SkillMatchingManager.add_student_skill(
                student_id=student_id,
                skill_name=skill_name,
                skill_category=skill_category,
                proficiency_level=proficiency_level,
                years_experience=float(years_experience)
            )

            print(f"\n✓ Skill added successfully! (Skill ID: {skill_id})")

        except Exception as e:
            print(f"\n❌ Error adding skill: {e}")

    def find_matching_jobs(self):
        """Find jobs matching student's skills"""
        student_id = self.current_user.get('username', '')

        min_match = input("\nMinimum match percentage (0-100) [default: 50]: ").strip()
        if not min_match.isdigit():
            min_match = "50"

        matching_jobs = SkillMatchingManager.find_matching_jobs(student_id, int(min_match))

        if not matching_jobs:
            print(f"\n❌ No jobs found matching your skills (minimum {min_match}% match).")
            return

        print("\n" + "=" * 60)
        print(f"Jobs Matching Your Skills (≥{min_match}% match)")
        print("=" * 60)

        for job in matching_jobs:
            print(f"\nJob ID: {job['job_id']} | Match: {job['match_percentage']}%")
            print(f"Title: {job['job_title']}")
            print(f"Employer: {job['employer_name']}")
            print(f"Rate: ${job['hourly_rate']:.2f}/hour")
            print(f"Skills Matched: {job['required_skills_matched']}/{job['total_required_skills']} required")

            if job['preferred_skills_matched']:
                print(f"Plus {job['preferred_skills_matched']} preferred skills")

    def view_skill_requirements(self):
        """View skill requirements for a job"""
        job_id = input("\nEnter Job ID: ").strip()

        if not job_id.isdigit():
            print("\n❌ Invalid Job ID.")
            return

        job = JobPostingManager.get_job_details(int(job_id))

        if not job:
            print("\n❌ Job not found.")
            return

        print(f"\n" + "=" * 60)
        print(f"Skill Requirements for: {job['job_title']}")
        print("=" * 60)

        if not job['skill_requirements']:
            print("\n❌ No specific skill requirements listed.")
            return

        required = [s for s in job['skill_requirements'] if s['is_required']]
        preferred = [s for s in job['skill_requirements'] if not s['is_required']]

        if required:
            print("\nRequired Skills:")
            for skill in required:
                print(f"  • {skill['skill_name']} (min: {skill['minimum_proficiency']})")

        if preferred:
            print("\nPreferred Skills:")
            for skill in preferred:
                print(f"  • {skill['skill_name']} (min: {skill['minimum_proficiency']})")

    def work_study_menu(self):
        """Work-study management"""
        if not self.current_user or self.current_user.get('role') != 'student':
            print("\n❌ Only students can view work-study information.")
            return

        student_id = self.current_user.get('username', '')
        jobs = EmploymentManager.get_student_employment(student_id, active_only=True)

        work_study_jobs = [j for j in jobs if j.get('is_work_study')]

        if not work_study_jobs:
            print("\n❌ You don't have any work-study positions.")
            return

        print("\n" + "=" * 60)
        print("WORK-STUDY MANAGEMENT".center(60))
        print("=" * 60)

        for job in work_study_jobs:
            print(f"\n{job['position_title']} at {job['employer_name']}")
            print("-" * 60)
            print(f"Allocation: ${job['work_study_allocation']:.2f}")
            print(f"Used: ${job['work_study_used']:.2f}")
            remaining = job['work_study_allocation'] - job['work_study_used']
            print(f"Remaining: ${remaining:.2f}")

            if job['hourly_rate']:
                remaining_hours = remaining / job['hourly_rate']
                print(f"Remaining Hours (approx): {remaining_hours:.1f} hours")

    def performance_reviews_menu(self):
        """View performance reviews"""
        if not self.current_user or self.current_user.get('role') != 'student':
            print("\n❌ Only students can view performance reviews.")
            return

        student_id = self.current_user.get('username', '')
        reviews = PerformanceManager.get_student_reviews(student_id)

        if not reviews:
            print("\n❌ You don't have any performance reviews yet.")
            return

        print("\n" + "=" * 60)
        print("PERFORMANCE REVIEWS".center(60))
        print("=" * 60)

        for review in reviews:
            print(f"\n{review['position_title']} at {review['employer_name']}")
            print(f"Review Date: {review['review_date']}")
            print(f"Period: {review['review_period_start']} to {review['review_period_end']}")
            print("-" * 60)
            print(f"Attendance: {review['attendance_rating']}/5")
            print(f"Quality: {review['quality_rating']}/5")
            print(f"Initiative: {review['initiative_rating']}/5")
            print(f"Teamwork: {review['teamwork_rating']}/5")
            print(f"Overall Rating: {review['overall_rating']:.2f}/5")

            if review['strengths']:
                print(f"\nStrengths: {review['strengths']}")

            if review['areas_for_improvement']:
                print(f"Areas for Improvement: {review['areas_for_improvement']}")

            if review['supervisor_comments']:
                print(f"Supervisor Comments: {review['supervisor_comments']}")

        # Show average ratings
        avg = PerformanceManager.get_average_performance(student_id)

        if avg['total_reviews']:
            print("\n" + "=" * 60)
            print("Average Performance Ratings")
            print("=" * 60)
            print(f"Total Reviews: {avg['total_reviews']}")
            print(f"Average Attendance: {avg['avg_attendance']:.2f}/5")
            print(f"Average Quality: {avg['avg_quality']:.2f}/5")
            print(f"Average Initiative: {avg['avg_initiative']:.2f}/5")
            print(f"Average Teamwork: {avg['avg_teamwork']:.2f}/5")
            print(f"Overall Average: {avg['avg_overall']:.2f}/5")

    # ======================== ADMIN/STAFF FUNCTIONS ========================

    def post_job(self):
        """Post a new job (admin/staff only)"""
        print("\n" + "=" * 60)
        print("POST NEW JOB".center(60))
        print("=" * 60)

        employer_name = input("\nEmployer/Department name: ").strip()
        job_title = input("Job title: ").strip()
        job_category = input("Job category (e.g., IT, Library, Food Service): ").strip()

        print("\nEmployment Type:")
        print("1. Work-Study")
        print("2. Part-Time")
        print("3. Internship")
        print("4. Temporary")

        type_choice = input("Select type: ").strip()
        type_map = {"1": "work-study", "2": "part-time", "3": "internship", "4": "temp"}
        employment_type = type_map.get(type_choice, "part-time")

        hourly_rate = input("Hourly rate ($): ").strip()
        if not hourly_rate.replace('.', '').isdigit():
            print("\n❌ Invalid hourly rate.")
            return

        job_description = input("Job description: ").strip()
        location = input("Location: ").strip()

        # Optional fields
        hours_per_week = input("Hours per week (optional): ").strip()
        total_positions = input("Number of positions (default: 1): ").strip()
        start_date = input("Start date YYYY-MM-DD (optional): ").strip()
        end_date = input("End date YYYY-MM-DD (optional): ").strip()
        application_deadline = input("Application deadline YYYY-MM-DD (optional): ").strip()
        contact_email = input("Contact email (optional): ").strip()
        contact_phone = input("Contact phone (optional): ").strip()

        kwargs = {}
        if hours_per_week:
            kwargs['hours_per_week'] = int(hours_per_week) if hours_per_week.isdigit() else None
        if total_positions:
            kwargs['total_positions'] = int(total_positions) if total_positions.isdigit() else 1
        if start_date:
            kwargs['start_date'] = start_date
        if end_date:
            kwargs['end_date'] = end_date
        if application_deadline:
            kwargs['application_deadline'] = application_deadline
        if contact_email:
            kwargs['contact_email'] = contact_email
        if contact_phone:
            kwargs['contact_phone'] = contact_phone

        kwargs['is_work_study'] = 1 if employment_type == 'work-study' else 0

        try:
            job_id = JobPostingManager.post_job(
                employer_name=employer_name,
                job_title=job_title,
                job_category=job_category,
                employment_type=employment_type,
                hourly_rate=float(hourly_rate),
                job_description=job_description,
                location=location,
                **kwargs
            )

            print(f"\n✓ Job posted successfully! (Job ID: {job_id})")

        except Exception as e:
            print(f"\n❌ Error posting job: {e}")

    def manage_postings_menu(self):
        """Manage job postings (admin/staff only)"""
        while True:
            print("\n" + "=" * 60)
            print("MANAGE JOB POSTINGS".center(60))
            print("=" * 60)
            print("\n1. View All Postings")
            print("2. Update Job Posting")
            print("3. Deactivate Job Posting")
            print("4. View Applications for Job")
            print("0. Back")

            choice = input("\nEnter your choice: ").strip()

            if choice == "0":
                break
            elif choice == "1":
                self.view_all_jobs()
            elif choice == "2":
                self.update_job_posting()
            elif choice == "3":
                self.deactivate_job_posting()
            elif choice == "4":
                self.view_job_applications()

    def update_job_posting(self):
        """Update a job posting"""
        job_id = input("\nEnter Job ID to update: ").strip()

        if not job_id.isdigit():
            print("\n❌ Invalid Job ID.")
            return

        job = JobPostingManager.get_job_details(int(job_id))
        if not job:
            print("\n❌ Job not found.")
            return

        print(f"\nUpdating: {job['job_title']}")
        print("Press Enter to keep current value")

        updates = {}

        new_title = input(f"New title [{job['job_title']}]: ").strip()
        if new_title:
            updates['job_title'] = new_title

        new_rate = input(f"New hourly rate [${job['hourly_rate']}]: ").strip()
        if new_rate and new_rate.replace('.', '').isdigit():
            updates['hourly_rate'] = float(new_rate)

        new_desc = input(f"New description [{job['job_description'][:50]}...]: ").strip()
        if new_desc:
            updates['job_description'] = new_desc

        if not updates:
            print("\n❌ No updates provided.")
            return

        try:
            JobPostingManager.update_job(int(job_id), **updates)
            print("\n✓ Job posting updated successfully.")
        except Exception as e:
            print(f"\n❌ Error updating job: {e}")

    def deactivate_job_posting(self):
        """Deactivate a job posting"""
        job_id = input("\nEnter Job ID to deactivate: ").strip()

        if not job_id.isdigit():
            print("\n❌ Invalid Job ID.")
            return

        confirm = input(f"Are you sure you want to deactivate job {job_id}? (yes/no): ").strip().lower()

        if confirm != 'yes':
            print("\n❌ Deactivation cancelled.")
            return

        try:
            JobPostingManager.deactivate_job(int(job_id))
            print("\n✓ Job posting deactivated successfully.")
        except Exception as e:
            print(f"\n❌ Error deactivating job: {e}")

    def view_job_applications(self):
        """View applications for a specific job"""
        job_id = input("\nEnter Job ID: ").strip()

        if not job_id.isdigit():
            print("\n❌ Invalid Job ID.")
            return

        applications = JobApplicationManager.get_job_applications(int(job_id))

        if not applications:
            print("\n❌ No applications found for this job.")
            return

        print("\n" + "-" * 60)
        print("Job Applications")
        print("-" * 60)

        for app in applications:
            print(f"\nApplication ID: {app['application_id']}")
            print(f"Student: {app['first_name']} {app['last_name']} ({app['student_id']})")
            print(f"Email: {app['email']}")
            print(f"Major: {app['major']} | GPA: {app['gpa']}")
            print(f"Applied: {app['application_date']}")
            print(f"Status: {app['status']}")
            print(f"Expected hours/week: {app['expected_hours_per_week']}")

            if app['availability']:
                print(f"Availability: {app['availability']}")

    def review_applications_menu(self):
        """Review and process applications (admin/staff only)"""
        while True:
            print("\n" + "=" * 60)
            print("REVIEW APPLICATIONS".center(60))
            print("=" * 60)
            print("\n1. View Pending Applications")
            print("2. View Application Details")
            print("3. Update Application Status")
            print("4. Schedule Interview")
            print("0. Back")

            choice = input("\nEnter your choice: ").strip()

            if choice == "0":
                break
            elif choice == "1":
                self.view_pending_apps_admin()
            elif choice == "2":
                self.view_app_details_admin()
            elif choice == "3":
                self.update_app_status()
            elif choice == "4":
                self.schedule_interview()

    def view_pending_apps_admin(self):
        """View all pending applications"""
        job_id = input("\nEnter Job ID (or press Enter for all jobs): ").strip()

        if job_id and job_id.isdigit():
            applications = JobApplicationManager.get_job_applications(int(job_id), 'pending')
        else:
            # Would need a method to get all pending applications
            print("\n❌ Job ID required.")
            return

        if not applications:
            print("\n❌ No pending applications found.")
            return

        for app in applications:
            print(f"\nApplication ID: {app['application_id']}")
            print(f"Student: {app['first_name']} {app['last_name']}")
            print(f"Applied: {app['application_date']}")

    def view_app_details_admin(self):
        """View application details (admin view)"""
        application_id = input("\nEnter Application ID: ").strip()

        if not application_id.isdigit():
            print("\n❌ Invalid Application ID.")
            return

        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                row = conn.execute('''
                    SELECT ja.*, jp.job_title, jp.employer_name, jp.hourly_rate, jp.location,
                           s.first_name, s.last_name, s.email_address, s.major, s.gpa
                    FROM campus_job_applications ja
                    JOIN campus_job_postings jp ON ja.job_id = jp.job_id
                    JOIN students s ON ja.student_id = s.student_id
                    WHERE ja.application_id = ?
                ''', (int(application_id),)).fetchone()

            if not row:
                print("\n❌ Application not found.")
                return

            app = dict(row)

            print("\n" + "=" * 60)
            print("APPLICATION DETAILS (Admin View)")
            print("=" * 60)

            print(f"\nApplication ID: {app['application_id']}")
            print(f"Status: {app['status'].upper()}")
            print(f"Applied: {app['application_date']}")

            print(f"\n--- Job Information ---")
            print(f"Job ID: {app['job_id']}")
            print(f"Title: {app['job_title']}")
            print(f"Employer: {app['employer_name']}")
            print(f"Location: {app.get('location', 'N/A')}")
            print(f"Rate: ${app.get('hourly_rate', 0):.2f}/hour")

            print(f"\n--- Applicant Information ---")
            print(f"Student ID: {app['student_id']}")
            print(f"Name: {app.get('first_name', '')} {app.get('last_name', '')}")
            print(f"Email: {app.get('email_address', 'N/A')}")
            print(f"Major: {app.get('major', 'N/A')}")
            print(f"GPA: {app.get('gpa', 'N/A')}")

            if app.get('expected_hours_per_week'):
                print(f"\nExpected hours/week: {app['expected_hours_per_week']}")
            if app.get('availability'):
                print(f"Availability: {app['availability']}")
            if app.get('cover_letter'):
                print(f"\n--- Cover Letter ---\n{app['cover_letter']}")
            if app.get('resume_url'):
                print(f"\nResume: {app['resume_url']}")
            if app.get('reference_contacts'):
                print(f"\nReferences:\n{app['reference_contacts']}")
            if app.get('notes'):
                print(f"\nReview Notes: {app['notes']}")
            if app.get('reviewed_by'):
                print(f"Reviewed by: {app['reviewed_by']} on {app.get('reviewed_date', 'N/A')}")
            if app.get('interview_date'):
                print(f"Interview scheduled: {app['interview_date']}")

            print("=" * 60)

        except Exception as e:
            print(f"\n❌ Error retrieving application details: {e}")

    def update_app_status(self):
        """Update application status"""
        application_id = input("\nEnter Application ID: ").strip()

        if not application_id.isdigit():
            print("\n❌ Invalid Application ID.")
            return

        print("\nNew Status:")
        print("1. Reviewed")
        print("2. Interview")
        print("3. Offered")
        print("4. Rejected")

        status_choice = input("Select status: ").strip()
        status_map = {
            "1": "reviewed",
            "2": "interview",
            "3": "offered",
            "4": "rejected"
        }

        if status_choice not in status_map:
            print("\n❌ Invalid choice.")
            return

        notes = input("Notes (optional): ").strip()

        try:
            JobApplicationManager.update_application_status(
                int(application_id),
                status_map[status_choice],
                notes
            )
            print("\n✓ Application status updated successfully.")
        except Exception as e:
            print(f"\n❌ Error updating status: {e}")

    def schedule_interview(self):
        """Schedule an interview"""
        application_id = input("\nEnter Application ID: ").strip()

        if not application_id.isdigit():
            print("\n❌ Invalid Application ID.")
            return

        interview_date = input("Interview date and time (YYYY-MM-DD HH:MM): ").strip()

        try:
            JobApplicationManager.schedule_interview(int(application_id), interview_date)
            print(f"\n✓ Interview scheduled for {interview_date}.")
        except Exception as e:
            print(f"\n❌ Error scheduling interview: {e}")

    def hire_student(self):
        """Hire a student for a position"""
        print("\n" + "=" * 60)
        print("HIRE STUDENT".center(60))
        print("=" * 60)

        application_id = input("\nApplication ID: ").strip()

        if not application_id.isdigit():
            print("\n❌ Invalid Application ID.")
            return

        # Get application details
        # For now, ask for required info
        student_id = input("Student ID: ").strip()
        job_id = input("Job ID: ").strip()
        start_date = input("Start date (YYYY-MM-DD): ").strip()
        hourly_rate = input("Hourly rate ($): ").strip()
        max_hours = input("Max hours per week: ").strip()
        position_title = input("Position title: ").strip()

        is_ws = input("Is this work-study? (yes/no): ").strip().lower() == 'yes'
        ws_allocation = "0"

        if is_ws:
            ws_allocation = input("Work-study allocation ($): ").strip()

        if not all([student_id, job_id, start_date, hourly_rate, max_hours, position_title]):
            print("\n❌ All fields are required.")
            return

        try:
            employment_id = EmploymentManager.hire_student(
                student_id=student_id,
                job_id=int(job_id),
                application_id=int(application_id),
                start_date=start_date,
                hourly_rate=float(hourly_rate),
                max_hours_per_week=int(max_hours),
                position_title=position_title,
                is_work_study=is_ws,
                work_study_allocation=float(ws_allocation) if is_ws else 0.0
            )

            print(f"\n✓ Student hired successfully! (Employment ID: {employment_id})")

        except Exception as e:
            print(f"\n❌ Error hiring student: {e}")

    def manage_employment_menu(self):
        """Manage employment records"""
        while True:
            print("\n" + "=" * 60)
            print("MANAGE EMPLOYMENT".center(60))
            print("=" * 60)
            print("\n1. View Student Employment")
            print("2. End Employment")
            print("3. Create Performance Review")
            print("0. Back")

            choice = input("\nEnter your choice: ").strip()

            if choice == "0":
                break
            elif choice == "1":
                self.view_student_employment_admin()
            elif choice == "2":
                self.end_employment()
            elif choice == "3":
                self.create_performance_review()

    def view_student_employment_admin(self):
        """View employment records for a student"""
        student_id = input("\nEnter Student ID: ").strip()

        jobs = EmploymentManager.get_student_employment(student_id, active_only=False)

        if not jobs:
            print("\n❌ No employment records found.")
            return

        for job in jobs:
            self._display_employment_summary(job)

    def end_employment(self):
        """End a student's employment"""
        employment_id = input("\nEnter Employment ID: ").strip()

        if not employment_id.isdigit():
            print("\n❌ Invalid Employment ID.")
            return

        end_date = input("End date (YYYY-MM-DD): ").strip()

        print("\nEnd Status:")
        print("1. Completed")
        print("2. Terminated")
        print("3. On Leave")

        status_choice = input("Select status: ").strip()
        status_map = {"1": "completed", "2": "terminated", "3": "on-leave"}

        status = status_map.get(status_choice, "completed")

        try:
            EmploymentManager.end_employment(int(employment_id), end_date, status)
            print("\n✓ Employment ended successfully.")
        except Exception as e:
            print(f"\n❌ Error ending employment: {e}")

    def create_performance_review(self):
        """Create a performance review"""
        print("\n" + "=" * 60)
        print("CREATE PERFORMANCE REVIEW".center(60))
        print("=" * 60)

        employment_id = input("\nEmployment ID: ").strip()
        student_id = input("Student ID: ").strip()
        review_date = input("Review date (YYYY-MM-DD): ").strip()
        period_start = input("Review period start (YYYY-MM-DD): ").strip()
        period_end = input("Review period end (YYYY-MM-DD): ").strip()

        print("\nRatings (1-5):")
        attendance = input("Attendance rating: ").strip()
        quality = input("Quality rating: ").strip()
        initiative = input("Initiative rating: ").strip()
        teamwork = input("Teamwork rating: ").strip()

        strengths = input("\nStrengths: ").strip()
        improvements = input("Areas for improvement: ").strip()
        comments = input("Supervisor comments: ").strip()

        try:
            review_id = PerformanceManager.create_performance_review(
                employment_id=int(employment_id),
                student_id=student_id,
                review_date=review_date,
                review_period_start=period_start,
                review_period_end=period_end,
                attendance_rating=int(attendance),
                quality_rating=int(quality),
                initiative_rating=int(initiative),
                teamwork_rating=int(teamwork),
                strengths=strengths,
                areas_for_improvement=improvements,
                supervisor_comments=comments
            )

            print(f"\n✓ Performance review created successfully! (Review ID: {review_id})")

        except Exception as e:
            print(f"\n❌ Error creating review: {e}")

    def approve_hours_menu(self):
        """Approve work hours"""
        student_id = input("\nEnter Student ID (or press Enter for all pending): ").strip()

        hours = WorkHoursManager.get_student_hours(student_id) if student_id else []

        if not hours:
            print("\n❌ No hours to approve.")
            return

        pending = [h for h in hours if h['status'] == 'pending']

        if not pending:
            print("\n❌ No pending hours found.")
            return

        print("\n" + "-" * 60)
        print("Pending Hours")
        print("-" * 60)

        for record in pending:
            print(f"\nLog ID: {record['log_id']}")
            print(f"Student: {record['student_id']}")
            print(f"Date: {record['work_date']}")
            print(f"Hours: {record['total_hours']}")
            print(f"Earnings: ${record['earnings']:.2f}")

        log_id = input("\nEnter Log ID to approve (or 'all' for all pending): ").strip()

        if log_id.lower() == 'all':
            for record in pending:
                try:
                    WorkHoursManager.approve_hours(record['log_id'])
                except Exception as e:
                    print(f"Error approving {record['log_id']}: {e}")
            print("\n✓ All pending hours approved.")
        elif log_id.isdigit():
            try:
                WorkHoursManager.approve_hours(int(log_id))
                print("\n✓ Hours approved successfully.")
            except Exception as e:
                print(f"\n❌ Error approving hours: {e}")

    # ======================== HELPER FUNCTIONS ========================

    def _is_admin_or_staff(self) -> bool:
        """Check if current user is admin or staff"""
        if not self.current_user:
            return False
        role = self.current_user.get('role', '').lower()
        return role in ['admin', 'staff', 'instructor']

    def _display_job_summary(self, job: dict):
        """Display job posting summary"""
        print(f"\n{'=' * 60}")
        print(f"Job ID: {job['job_id']}")
        print(f"Title: {job['job_title']}")
        print(f"Employer: {job['employer_name']}")
        print(f"Category: {job['job_category']}")
        print(f"Type: {job['employment_type']}")
        print(f"Rate: ${job['hourly_rate']:.2f}/hour")

        if job.get('hours_per_week'):
            print(f"Hours/week: {job['hours_per_week']}")

        print(f"Location: {job['location']}")

        available = job['total_positions'] - job['filled_positions']
        print(f"Positions: {available}/{job['total_positions']} available")

        if job.get('application_deadline'):
            print(f"Deadline: {job['application_deadline']}")

    def _display_job_details(self, job: dict):
        """Display detailed job information"""
        print("\n" + "=" * 60)
        print(f"JOB DETAILS - {job['job_title']}")
        print("=" * 60)

        print(f"\nJob ID: {job['job_id']}")
        print(f"Employer: {job['employer_name']}")
        print(f"Category: {job['job_category']}")
        print(f"Type: {job['employment_type']}")
        print(f"Rate: ${job['hourly_rate']:.2f}/hour")

        if job.get('hours_per_week'):
            print(f"Hours per week: {job['hours_per_week']}")

        print(f"\nLocation: {job['location']}")

        available = job['total_positions'] - job['filled_positions']
        print(f"Positions: {available}/{job['total_positions']} available")

        print(f"\nDescription:\n{job['job_description']}")

        if job.get('required_skills'):
            print(f"\nRequired Skills: {job['required_skills']}")

        if job.get('preferred_skills'):
            print(f"Preferred Skills: {job['preferred_skills']}")

        if job.get('minimum_gpa'):
            print(f"\nMinimum GPA: {job['minimum_gpa']}")

        if job.get('start_date'):
            print(f"Start Date: {job['start_date']}")

        if job.get('end_date'):
            print(f"End Date: {job['end_date']}")

        if job.get('application_deadline'):
            print(f"Application Deadline: {job['application_deadline']}")

        if job.get('contact_email'):
            print(f"\nContact Email: {job['contact_email']}")

        if job.get('contact_phone'):
            print(f"Contact Phone: {job['contact_phone']}")

        print(f"\nTotal Applications: {job.get('total_applications', 0)}")
        print(f"Posted: {job['posted_date']}")

    def _display_application_summary(self, app: dict):
        """Display application summary"""
        print(f"\n{'=' * 60}")
        print(f"Application ID: {app['application_id']}")
        print(f"Job: {app['job_title']} at {app['employer_name']}")
        print(f"Rate: ${app['hourly_rate']:.2f}/hour")
        print(f"Location: {app['location']}")
        print(f"Applied: {app['application_date']}")
        print(f"Status: {app['status'].upper()}")

    def _display_application_details(self, app: dict):
        """Display detailed application information"""
        print("\n" + "=" * 60)
        print("APPLICATION DETAILS")
        print("=" * 60)

        print(f"\nApplication ID: {app['application_id']}")
        print(f"Job: {app['job_title']}")
        print(f"Employer: {app['employer_name']}")
        print(f"Applied: {app['application_date']}")
        print(f"Status: {app['status'].upper()}")

        if app.get('expected_hours_per_week'):
            print(f"Expected hours/week: {app['expected_hours_per_week']}")

        if app.get('availability'):
            print(f"\nAvailability: {app['availability']}")

        if app.get('cover_letter'):
            print(f"\nCover Letter:\n{app['cover_letter']}")

        if app.get('resume_url'):
            print(f"\nResume: {app['resume_url']}")

        if app.get('references'):
            print(f"\nReferences:\n{app['references']}")

        if app.get('notes'):
            print(f"\nNotes: {app['notes']}")

        if app.get('interview_date'):
            print(f"\nInterview scheduled: {app['interview_date']}")

    def _display_employment_summary(self, job: dict):
        """Display employment record summary"""
        print(f"\n{'=' * 60}")
        print(f"Employment ID: {job['employment_id']}")
        print(f"Position: {job['position_title']}")
        print(f"Employer: {job['employer_name']}")
        print(f"Location: {job['location']}")
        print(f"Status: {job['employment_status'].upper()}")
        print(f"Rate: ${job['hourly_rate']:.2f}/hour")
        print(f"Max hours/week: {job['max_hours_per_week']}")
        print(f"Start Date: {job['start_date']}")

        if job.get('end_date'):
            print(f"End Date: {job['end_date']}")

        if job.get('is_work_study'):
            print(f"Work-Study: Yes")
            print(f"Allocation: ${job['work_study_allocation']:.2f}")
            print(f"Used: ${job['work_study_used']:.2f}")

        if job.get('performance_rating'):
            print(f"Performance Rating: {job['performance_rating']:.2f}/5")


def main():
    """Entry point for the CLI"""
    cli = StudentJobsCLI()
    cli.run()


if __name__ == "__main__":
    main()
