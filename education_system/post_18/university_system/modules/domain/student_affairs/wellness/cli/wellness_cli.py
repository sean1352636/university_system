"""
Mental Health & Wellness CLI Interface

Provides command-line interface for wellness tracking and mental health support.
"""

from datetime import datetime, timedelta
from typing import Optional
import sys

from education_system.post_18.university_system.modules.domain.student_affairs.wellness.services.wellness_service import WellnessService
from education_system.post_18.university_system.infrastructure.shared_context import get_auth


class WellnessCLI:
    """Command-line interface for Mental Health & Wellness Hub."""

    def __init__(self):
        """Initialize the Wellness CLI."""
        self.service = WellnessService()
        self.auth = get_auth()

    def main_menu(self):
        """Display main wellness menu."""
        while True:
            self._clear_screen()
            print("\n" + "=" * 70)
            print("  MENTAL HEALTH & WELLNESS HUB".center(70))
            print("=" * 70)

            # Show crisis resources prominently
            print("\n" + "-" * 70)
            print("  CRISIS RESOURCES - AVAILABLE 24/7".center(70))
            print("-" * 70)
            self._display_crisis_resources_compact()
            print("-" * 70)

            if not self.auth.is_logged_in():
                print("\n\nPlease log in to access wellness features.")
                input("\nPress Enter to return...")
                return

            student_id = self.auth.get_current_user()['user_id']

            # Show wellness score
            total_points = self.service.get_total_wellness_points(student_id)
            print(f"\n  Your Wellness Points: {total_points}".center(70))

            print("\n" + "=" * 70)
            print("\nWELLNESS TRACKING:")
            print("  1. Log Mood Entry")
            print("  2. Complete Wellness Check-in")
            print("  3. View Mood Trends & Insights")
            print("  4. Track Sleep")
            print("  5. View Sleep Analytics")

            print("\nWELLNESS ACTIVITIES:")
            print("  6. Log Exercise Activity")
            print("  7. Log Hydration")
            print("  8. Set Wellness Goal")
            print("  9. View Active Goals")

            print("\nSUPPORT & RESOURCES:")
            print("  10. Book Counseling Appointment")
            print("  11. View My Appointments")
            print("  12. View All Crisis Resources")
            print("  13. View Wellness Points & Achievements")
            print("  14. View Comprehensive Wellness Report")

            print("\n  0. Back to Main Menu")
            print("=" * 70)

            choice = input("\nSelect an option: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self.log_mood_entry()
            elif choice == '2':
                self.complete_wellness_checkin()
            elif choice == '3':
                self.view_mood_trends()
            elif choice == '4':
                self.track_sleep()
            elif choice == '5':
                self.view_sleep_analytics()
            elif choice == '6':
                self.log_exercise()
            elif choice == '7':
                self.log_hydration()
            elif choice == '8':
                self.set_wellness_goal()
            elif choice == '9':
                self.view_active_goals()
            elif choice == '10':
                self.book_counseling()
            elif choice == '11':
                self.view_appointments()
            elif choice == '12':
                self.view_crisis_resources()
            elif choice == '13':
                self.view_wellness_achievements()
            elif choice == '14':
                self.view_comprehensive_report()
            else:
                print("\nInvalid option. Please try again.")
                input("\nPress Enter to continue...")

    def _clear_screen(self):
        """Clear the screen."""
        print("\033[2J\033[H", end="")

    def _display_crisis_resources_compact(self):
        """Display crisis resources in compact format."""
        resources = self.service.get_crisis_resources()
        for resource in resources[:4]:  # Show top 4
            print(f"  {resource['resource_name']}: {resource['contact_info']}")

    # ========== Mood Tracking ==========

    def log_mood_entry(self):
        """Log a mood entry."""
        print("\n" + "=" * 70)
        print("  LOG MOOD ENTRY".center(70))
        print("=" * 70)

        print("\nMood Types:")
        mood_types = ['Happy', 'Sad', 'Anxious', 'Stressed', 'Calm', 'Excited',
                     'Angry', 'Content', 'Overwhelmed', 'Peaceful']
        for i, mood in enumerate(mood_types, 1):
            print(f"  {i}. {mood}")

        try:
            mood_choice = int(input("\nSelect mood type (1-10): "))
            if not 1 <= mood_choice <= 10:
                raise ValueError
            mood_type = mood_types[mood_choice - 1]
        except (ValueError, IndexError):
            print("\nInvalid mood type.")
            input("\nPress Enter to continue...")
            return

        try:
            intensity = int(input("Intensity (1=Mild, 5=Intense): "))
            if not 1 <= intensity <= 5:
                raise ValueError
        except ValueError:
            print("\nInvalid intensity. Please enter 1-5.")
            input("\nPress Enter to continue...")
            return

        triggers = input("What triggered this mood? (optional): ").strip() or None
        activities = input("What activities helped/hurt? (optional): ").strip() or None
        notes = input("Additional notes (optional): ").strip() or None

        student_id = self.auth.get_current_user()['user_id']
        mood_id = self.service.log_mood(student_id, mood_type, intensity,
                                       triggers, activities, notes)

        print(f"\n✓ Mood entry logged successfully! (ID: {mood_id})")
        print("  +5 Wellness Points earned!")
        input("\nPress Enter to continue...")

    def complete_wellness_checkin(self):
        """Complete a wellness check-in."""
        print("\n" + "=" * 70)
        print("  WELLNESS CHECK-IN".center(70))
        print("=" * 70)

        print("\nRate each area from 1 (Poor) to 10 (Excellent):")

        try:
            overall_mood = int(input("\n1. Overall Mood (1-10): "))
            stress_level = int(input("2. Stress Level (1=Low, 10=High): "))
            sleep_quality = int(input("3. Sleep Quality (1-10): "))
            energy_level = int(input("4. Energy Level (1-10): "))
            anxiety_level = int(input("5. Anxiety Level (1=Low, 10=High): "))

            if not all(1 <= x <= 10 for x in [overall_mood, stress_level,
                                              sleep_quality, energy_level, anxiety_level]):
                raise ValueError
        except ValueError:
            print("\nInvalid input. Please enter values between 1 and 10.")
            input("\nPress Enter to continue...")
            return

        notes = input("\nAny additional notes? (optional): ").strip() or None

        student_id = self.auth.get_current_user()['user_id']
        checkin_id = self.service.create_checkin(
            student_id, overall_mood, stress_level, sleep_quality,
            energy_level, anxiety_level, notes
        )

        print(f"\n✓ Wellness check-in completed! (ID: {checkin_id})")
        print("  +10 Wellness Points earned!")

        # Show immediate insights
        if stress_level >= 8 or anxiety_level >= 8:
            print("\n⚠ We noticed you're experiencing high stress or anxiety.")
            print("  Consider booking a counseling appointment or reviewing crisis resources.")

        input("\nPress Enter to continue...")

    def view_mood_trends(self):
        """View mood trends and insights."""
        print("\n" + "=" * 70)
        print("  MOOD TRENDS & INSIGHTS".center(70))
        print("=" * 70)

        try:
            days = int(input("\nAnalyze past how many days? (default 30): ") or "30")
        except ValueError:
            days = 30

        student_id = self.auth.get_current_user()['user_id']

        # Get wellness patterns
        patterns = self.service.analyze_wellness_patterns(student_id, days)

        if 'message' in patterns:
            print(f"\n{patterns['message']}")
            input("\nPress Enter to continue...")
            return

        print(f"\n{'=' * 70}")
        print(f"  WELLNESS ANALYSIS - PAST {patterns['period_days']} DAYS".center(70))
        print(f"{'=' * 70}")
        print(f"\nTotal Check-ins: {patterns['total_checkins']}")

        print("\nAVERAGE SCORES (1-10 scale):")
        avgs = patterns['averages']
        print(f"  Overall Mood:   {avgs['mood']:.1f} {self._get_mood_emoji(avgs['mood'])}")
        print(f"  Stress Level:   {avgs['stress']:.1f} {self._get_stress_emoji(avgs['stress'])}")
        print(f"  Sleep Quality:  {avgs['sleep_quality']:.1f} {self._get_quality_emoji(avgs['sleep_quality'])}")
        print(f"  Energy Level:   {avgs['energy']:.1f} {self._get_quality_emoji(avgs['energy'])}")
        print(f"  Anxiety Level:  {avgs['anxiety']:.1f} {self._get_stress_emoji(avgs['anxiety'])}")

        if patterns['concerns']:
            print("\n⚠ AREAS OF CONCERN:")
            for concern in patterns['concerns']:
                print(f"  - {concern}")

        print("\nRECOMMENDATION:")
        print(f"  {patterns['recommendation']}")

        # Get mood history
        moods = self.service.get_mood_history(student_id, days)
        if moods:
            print(f"\n{'=' * 70}")
            print("  RECENT MOOD ENTRIES".center(70))
            print(f"{'=' * 70}")
            for mood in moods[:5]:
                print(f"\n{mood['mood_date']} - {mood['mood_type']} (Intensity: {mood['intensity']}/5)")
                if mood['triggers']:
                    print(f"  Triggers: {mood['triggers']}")
                if mood['notes']:
                    print(f"  Notes: {mood['notes']}")

        input("\nPress Enter to continue...")

    def _get_mood_emoji(self, score: float) -> str:
        """Get emoji for mood score."""
        if score >= 8:
            return "😊"
        elif score >= 6:
            return "🙂"
        elif score >= 4:
            return "😐"
        else:
            return "☹️"

    def _get_stress_emoji(self, score: float) -> str:
        """Get emoji for stress/anxiety score."""
        if score >= 8:
            return "😰"
        elif score >= 6:
            return "😟"
        elif score >= 4:
            return "😐"
        else:
            return "😌"

    def _get_quality_emoji(self, score: float) -> str:
        """Get emoji for quality score."""
        if score >= 8:
            return "⭐"
        elif score >= 6:
            return "✓"
        elif score >= 4:
            return "~"
        else:
            return "✗"

    # ========== Sleep Tracking ==========

    def track_sleep(self):
        """Track sleep data."""
        print("\n" + "=" * 70)
        print("  TRACK SLEEP".center(70))
        print("=" * 70)

        sleep_date = input("\nSleep date (YYYY-MM-DD, default today): ").strip()
        if not sleep_date:
            sleep_date = datetime.now().strftime('%Y-%m-%d')

        bedtime = input("Bedtime (HH:MM, e.g., 23:00): ").strip()
        wake_time = input("Wake time (HH:MM, e.g., 07:00): ").strip()

        try:
            hours_slept = float(input("Hours slept: "))
            sleep_quality = int(input("Sleep quality (1=Poor, 5=Excellent): "))
            interruptions = int(input("Number of interruptions: ") or "0")

            if not (0 <= hours_slept <= 24 and 1 <= sleep_quality <= 5):
                raise ValueError
        except ValueError:
            print("\nInvalid input.")
            input("\nPress Enter to continue...")
            return

        notes = input("Notes (optional): ").strip() or None

        student_id = self.auth.get_current_user()['user_id']
        sleep_id = self.service.log_sleep(
            student_id, sleep_date, bedtime, wake_time,
            hours_slept, sleep_quality, interruptions, notes
        )

        print(f"\n✓ Sleep tracked successfully! (ID: {sleep_id})")
        points = 5
        if hours_slept >= 7 and sleep_quality >= 4:
            points += 10
            print("  +15 Wellness Points earned (5 + 10 bonus for quality sleep)!")
        else:
            print("  +5 Wellness Points earned!")

        if hours_slept < 7:
            print("\n💡 TIP: Aim for 7-9 hours of sleep per night for optimal health.")

        input("\nPress Enter to continue...")

    def view_sleep_analytics(self):
        """View sleep analytics."""
        print("\n" + "=" * 70)
        print("  SLEEP ANALYTICS".center(70))
        print("=" * 70)

        try:
            days = int(input("\nAnalyze past how many days? (default 30): ") or "30")
        except ValueError:
            days = 30

        student_id = self.auth.get_current_user()['user_id']
        analytics = self.service.get_sleep_analytics(student_id, days)

        if 'message' in analytics:
            print(f"\n{analytics['message']}")
            input("\nPress Enter to continue...")
            return

        print(f"\n{'=' * 70}")
        print(f"  SLEEP ANALYSIS - PAST {analytics['period_days']} DAYS".center(70))
        print(f"{'=' * 70}")

        print(f"\nNights Tracked: {analytics['nights_tracked']}")
        print(f"Average Hours: {analytics['average_hours']:.1f} hours/night")
        print(f"Average Quality: {analytics['average_quality']:.1f}/5")
        print(f"Total Interruptions: {analytics['total_interruptions']}")

        print("\nRECOMMENDATION:")
        print(f"  {analytics['recommendation']}")

        input("\nPress Enter to continue...")

    # ========== Exercise & Hydration ==========

    def log_exercise(self):
        """Log exercise activity."""
        print("\n" + "=" * 70)
        print("  LOG EXERCISE ACTIVITY".center(70))
        print("=" * 70)

        print("\nExercise Types:")
        exercise_types = ['Running', 'Walking', 'Cycling', 'Swimming', 'Gym Workout',
                         'Yoga', 'Sports', 'Dancing', 'Hiking', 'Other']
        for i, ex_type in enumerate(exercise_types, 1):
            print(f"  {i}. {ex_type}")

        try:
            type_choice = int(input("\nSelect exercise type (1-10): "))
            if not 1 <= type_choice <= 10:
                raise ValueError

            if type_choice == 10:
                exercise_type = input("Enter exercise type: ").strip()
            else:
                exercise_type = exercise_types[type_choice - 1]
        except (ValueError, IndexError):
            print("\nInvalid exercise type.")
            input("\nPress Enter to continue...")
            return

        try:
            duration = int(input("Duration (minutes): "))
        except ValueError:
            print("\nInvalid duration.")
            input("\nPress Enter to continue...")
            return

        print("\nIntensity: 1=Light, 2=Moderate, 3=Vigorous")
        intensity_map = {1: 'Light', 2: 'Moderate', 3: 'Vigorous'}
        try:
            intensity_choice = int(input("Intensity (1-3): "))
            intensity = intensity_map.get(intensity_choice, 'Moderate')
        except ValueError:
            intensity = 'Moderate'

        try:
            calories = int(input("Calories burned (optional, press Enter to skip): ") or "0") or None
        except ValueError:
            calories = None

        notes = input("Notes (optional): ").strip() or None

        student_id = self.auth.get_current_user()['user_id']
        exercise_id = self.service.log_exercise(
            student_id, exercise_type, duration, intensity, calories, notes
        )

        points = min(duration // 10, 30)
        print(f"\n✓ Exercise logged successfully! (ID: {exercise_id})")
        print(f"  +{points} Wellness Points earned!")

        input("\nPress Enter to continue...")

    def log_hydration(self):
        """Log hydration."""
        print("\n" + "=" * 70)
        print("  LOG HYDRATION".center(70))
        print("=" * 70)

        student_id = self.auth.get_current_user()['user_id']

        # Show current status
        status = self.service.get_hydration_status(student_id)
        print(f"\nToday's Progress: {status['glasses_consumed']}/{status['daily_goal']} glasses")
        print(f"Completion: {status['percentage']:.1f}%")

        try:
            glasses = int(input("\nHow many glasses to add? "))
            if glasses < 0:
                raise ValueError
        except ValueError:
            print("\nInvalid input.")
            input("\nPress Enter to continue...")
            return

        self.service.log_hydration(student_id, glasses)

        # Show updated status
        new_status = self.service.get_hydration_status(student_id)
        print(f"\n✓ Hydration logged! New total: {new_status['glasses_consumed']}/{new_status['daily_goal']} glasses")
        print(f"  +{min(glasses, 10)} Wellness Points earned!")

        if new_status['goal_met']:
            print("\n🎉 Daily hydration goal achieved! Great job!")

        input("\nPress Enter to continue...")

    # ========== Wellness Goals ==========

    def set_wellness_goal(self):
        """Set a wellness goal."""
        print("\n" + "=" * 70)
        print("  SET WELLNESS GOAL".center(70))
        print("=" * 70)

        print("\nGoal Types:")
        goal_types = ['Sleep Hours', 'Exercise Minutes', 'Hydration', 'Meditation Minutes',
                     'Stress Reduction', 'Weight', 'Steps', 'Custom']
        for i, g_type in enumerate(goal_types, 1):
            print(f"  {i}. {g_type}")

        try:
            type_choice = int(input("\nSelect goal type (1-8): "))
            if not 1 <= type_choice <= 8:
                raise ValueError

            if type_choice == 8:
                goal_type = input("Enter custom goal type: ").strip()
            else:
                goal_type = goal_types[type_choice - 1]
        except (ValueError, IndexError):
            print("\nInvalid goal type.")
            input("\nPress Enter to continue...")
            return

        goal_description = input("Goal description: ").strip()

        try:
            target_value = float(input("Target value: "))
        except ValueError:
            print("\nInvalid target value.")
            input("\nPress Enter to continue...")
            return

        end_date = input("End date (YYYY-MM-DD, optional): ").strip() or None

        student_id = self.auth.get_current_user()['user_id']
        goal_id = self.service.create_wellness_goal(
            student_id, goal_type, goal_description, target_value, end_date
        )

        print(f"\n✓ Wellness goal created! (ID: {goal_id})")
        print("  Keep tracking your progress to earn bonus points!")

        input("\nPress Enter to continue...")

    def view_active_goals(self):
        """View active wellness goals."""
        print("\n" + "=" * 70)
        print("  ACTIVE WELLNESS GOALS".center(70))
        print("=" * 70)

        student_id = self.auth.get_current_user()['user_id']
        goals = self.service.get_active_goals(student_id)

        if not goals:
            print("\nNo active goals. Set a goal to start tracking your progress!")
            input("\nPress Enter to continue...")
            return

        for goal in goals:
            print(f"\n{'=' * 70}")
            print(f"Goal ID: {goal['goal_id']}")
            print(f"Type: {goal['goal_type']}")
            print(f"Description: {goal['goal_description']}")
            print(f"Progress: {goal['current_value']:.1f} / {goal['target_value']:.1f}")

            percentage = (goal['current_value'] / goal['target_value']) * 100 if goal['target_value'] > 0 else 0
            print(f"Completion: {percentage:.1f}%")

            if goal['end_date']:
                print(f"Target Date: {goal['end_date']}")
            print(f"Started: {goal['start_date']}")

        input("\nPress Enter to continue...")

    # ========== Counseling ==========

    def book_counseling(self):
        """Book a counseling appointment."""
        print("\n" + "=" * 70)
        print("  BOOK COUNSELING APPOINTMENT".center(70))
        print("=" * 70)

        print("\nAll appointments are confidential and private.")

        appointment_date = input("\nAppointment date (YYYY-MM-DD): ").strip()
        appointment_time = input("Preferred time (HH:MM, e.g., 14:00): ").strip()

        print("\nAppointment Types:")
        appt_types = ['Individual Counseling', 'Group Therapy', 'Crisis Intervention',
                     'Academic Stress', 'Relationship Issues', 'Anxiety/Depression',
                     'General Consultation']
        for i, a_type in enumerate(appt_types, 1):
            print(f"  {i}. {a_type}")

        try:
            type_choice = int(input("\nSelect appointment type (1-7): "))
            if not 1 <= type_choice <= 7:
                raise ValueError
            appointment_type = appt_types[type_choice - 1]
        except (ValueError, IndexError):
            print("\nInvalid appointment type.")
            input("\nPress Enter to continue...")
            return

        notes = input("Any specific concerns? (optional, confidential): ").strip() or None

        student_id = self.auth.get_current_user()['user_id']
        appointment_id = self.service.schedule_counseling(
            student_id, appointment_date, appointment_time, appointment_type, notes
        )

        print(f"\n✓ Counseling appointment booked! (ID: {appointment_id})")
        print(f"\nDate: {appointment_date} at {appointment_time}")
        print(f"Type: {appointment_type}")
        print("\nYou will receive a confirmation. All information is confidential.")

        input("\nPress Enter to continue...")

    def view_appointments(self):
        """View counseling appointments."""
        print("\n" + "=" * 70)
        print("  MY COUNSELING APPOINTMENTS".center(70))
        print("=" * 70)

        student_id = self.auth.get_current_user()['user_id']
        appointments = self.service.get_counseling_appointments(student_id)

        if not appointments:
            print("\nNo appointments scheduled.")
            input("\nPress Enter to continue...")
            return

        for appt in appointments:
            print(f"\n{'=' * 70}")
            print(f"Appointment ID: {appt['appointment_id']}")
            print(f"Date: {appt['appointment_date']} at {appt['appointment_time']}")
            print(f"Type: {appt['appointment_type']}")
            print(f"Status: {appt['status']}")
            if appt['counselor_name']:
                print(f"Counselor: {appt['counselor_name']}")

        input("\nPress Enter to continue...")

    def view_crisis_resources(self):
        """View all crisis resources."""
        print("\n" + "=" * 70)
        print("  CRISIS RESOURCES - AVAILABLE 24/7".center(70))
        print("=" * 70)

        resources = self.service.get_crisis_resources()

        for resource in resources:
            print(f"\n{'=' * 70}")
            print(f"{resource['resource_name']}")
            print(f"Type: {resource['resource_type']}")
            print(f"Contact: {resource['contact_info']}")
            if resource['description']:
                print(f"Description: {resource['description']}")
            print(f"Availability: {resource['availability']}")

        print("\n" + "=" * 70)
        print("\nIf you are in immediate danger, please call 911 or go to your")
        print("nearest emergency room. These resources are here to help you.")

        input("\nPress Enter to continue...")

    # ========== Points & Achievements ==========

    def view_wellness_achievements(self):
        """View wellness points and achievements."""
        print("\n" + "=" * 70)
        print("  WELLNESS POINTS & ACHIEVEMENTS".center(70))
        print("=" * 70)

        student_id = self.auth.get_current_user()['user_id']
        total_points = self.service.get_total_wellness_points(student_id)

        print(f"\nYour Total Wellness Points: {total_points}")

        # Determine achievement level
        if total_points >= 1000:
            level = "Wellness Champion"
            emoji = "🏆"
        elif total_points >= 500:
            level = "Wellness Master"
            emoji = "⭐"
        elif total_points >= 250:
            level = "Wellness Expert"
            emoji = "💎"
        elif total_points >= 100:
            level = "Wellness Warrior"
            emoji = "🎖️"
        elif total_points >= 50:
            level = "Wellness Enthusiast"
            emoji = "✨"
        else:
            level = "Wellness Beginner"
            emoji = "🌱"

        print(f"\nCurrent Level: {level} {emoji}")

        # Show leaderboard
        print(f"\n{'=' * 70}")
        print("  WELLNESS LEADERBOARD - TOP 10".center(70))
        print(f"{'=' * 70}")

        leaderboard = self.service.get_wellness_leaderboard(10)
        for i, entry in enumerate(leaderboard, 1):
            marker = "👑" if i == 1 else f"{i}."
            your_marker = " (YOU)" if entry['student_id'] == student_id else ""
            print(f"{marker:4} Student {entry['student_id']:10} - {entry['total_points']:5} points " +
                  f"({entry['activities']} activities){your_marker}")

        input("\nPress Enter to continue...")

    def view_comprehensive_report(self):
        """View comprehensive wellness report."""
        print("\n" + "=" * 70)
        print("  COMPREHENSIVE WELLNESS REPORT".center(70))
        print("=" * 70)

        try:
            days = int(input("\nAnalyze past how many days? (default 30): ") or "30")
        except ValueError:
            days = 30

        student_id = self.auth.get_current_user()['user_id']
        report = self.service.get_comprehensive_wellness_report(student_id, days)

        # Wellness Patterns
        patterns = report['wellness_patterns']
        if 'message' not in patterns:
            print(f"\n{'=' * 70}")
            print("  WELLNESS CHECK-IN SUMMARY".center(70))
            print(f"{'=' * 70}")
            print(f"\nTotal Check-ins: {patterns['total_checkins']}")

            print("\nAverage Scores:")
            avgs = patterns['averages']
            print(f"  Overall Mood:   {avgs['mood']:.1f}/10")
            print(f"  Stress Level:   {avgs['stress']:.1f}/10")
            print(f"  Sleep Quality:  {avgs['sleep_quality']:.1f}/10")
            print(f"  Energy Level:   {avgs['energy']:.1f}/10")
            print(f"  Anxiety Level:  {avgs['anxiety']:.1f}/10")

            if patterns['concerns']:
                print("\nAreas of Concern:")
                for concern in patterns['concerns']:
                    print(f"  - {concern}")

        # Sleep Analytics
        sleep = report['sleep_analytics']
        if 'message' not in sleep:
            print(f"\n{'=' * 70}")
            print("  SLEEP SUMMARY".center(70))
            print(f"{'=' * 70}")
            print(f"\nNights Tracked: {sleep['nights_tracked']}")
            print(f"Average Hours: {sleep['average_hours']:.1f} hours/night")
            print(f"Average Quality: {sleep['average_quality']:.1f}/5")

        # Goals
        print(f"\n{'=' * 70}")
        print("  ACTIVE GOALS".center(70))
        print(f"{'=' * 70}")
        print(f"\nActive Goals: {report['active_goals_count']}")

        for goal in report['active_goals']:
            percentage = (goal['current_value'] / goal['target_value']) * 100 if goal['target_value'] > 0 else 0
            print(f"\n  {goal['goal_type']}: {percentage:.1f}% complete")
            print(f"  ({goal['current_value']:.1f} / {goal['target_value']:.1f})")

        # Points
        print(f"\n{'=' * 70}")
        print("  GAMIFICATION".center(70))
        print(f"{'=' * 70}")
        print(f"\nTotal Wellness Points: {report['total_wellness_points']}")

        input("\nPress Enter to continue...")


def main():
    """Main entry point for wellness CLI."""
    cli = WellnessCLI()
    cli.main_menu()


if __name__ == '__main__':
    main()
