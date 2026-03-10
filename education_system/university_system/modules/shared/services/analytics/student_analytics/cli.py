from .config import GUI_AVAILABLE


class CLIMixin:
    def display_main_menu(self):
        """Display the enhanced analytics dashboard menu"""
        if not GUI_AVAILABLE:
            print("\n" + "="*80)
            print("NOTE: GUI display not available in this environment.")
            print(f"All plots will be automatically saved to '{self.plots_dir}' folder.")
            print("="*80)

        while True:
            print("\n" + "="*80)
            print("🎓 ENHANCED STUDENT ANALYTICS DASHBOARD 🎓")
            print("="*80)
            print("📊 BASIC ANALYTICS")
            print("1.  Student Demographics")
            print("2.  Module Popularity Analysis")
            print("3.  Course Enrollment Statistics")
            print("4.  Registration Timeline")

            print("\n📈 PERFORMANCE ANALYTICS")
            print("5.  Grade Distribution Analysis")
            print("6.  Academic Risk Assessment")
            print("7.  Module Difficulty Analysis")
            print("8.  Student Performance Trends")

            print("\n🔍 ADVANCED ANALYTICS")
            print("9.  Correlation Analysis")
            print("10. Cohort Analysis")
            print("11. Engagement Scoring")
            print("12. Predictive Analytics")

            print("\n📋 REPORTING & EXPORT")
            print("13. Generate Complete Report")
            print("14. Custom Report Builder")
            print("15. Export Data")
            print("16. Email Reports")

            print("\n🔧 UTILITIES")
            print("17. Data Quality Check")
            print("18. Advanced Filtering")
            print("19. Configuration Settings")
            print("20. Exit")

            choice = input("\nEnter your choice (1-20): ")

            try:
                if choice == '1':
                    self.analyze_student_demographics()
                elif choice == '2':
                    self.analyze_module_popularity()
                elif choice == '3':
                    self.analyze_course_enrollments()
                elif choice == '4':
                    self.analyze_registration_timeline()
                elif choice == '5':
                    self.analyze_grade_distribution()
                elif choice == '6':
                    self.analyze_academic_risk()
                elif choice == '7':
                    self.analyze_module_difficulty()
                elif choice == '8':
                    self.analyze_performance_trends()
                elif choice == '9':
                    self.analyze_correlations()
                elif choice == '10':
                    self.analyze_cohorts()
                elif choice == '11':
                    self.analyze_engagement()
                elif choice == '12':
                    self.predictive_analytics()
                elif choice == '13':
                    self.generate_complete_report()
                elif choice == '14':
                    self.custom_report_builder()
                elif choice == '15':
                    self.export_data()
                elif choice == '16':
                    self.email_reports()
                elif choice == '17':
                    self.data_quality_check()
                elif choice == '18':
                    self.advanced_filtering()
                elif choice == '19':
                    self.configuration_settings()
                elif choice == '20':
                    print("Thank you for using Enhanced Student Analytics Dashboard!")
                    break
                else:
                    print("Invalid choice. Please try again.")
            except Exception as e:
                print(f"An error occurred: {e}")
                print("Please try again or contact support.")

    def advanced_filtering(self):
        """Advanced filtering interface"""
        print("\n" + "="*60)
        print("ADVANCED FILTERING OPTIONS")
        print("="*60)

        students_df = self.get_all_students()

        print("Available filter criteria:")
        print("1. Age range")
        print("2. GPA range")
        print("3. Engagement score range")
        print("4. Course selection")
        print("5. Gender")
        print("6. Completion status")
        print("7. Registration date range")
        print("8. Clear all filters")
        print("9. Apply current filters and return")

        while True:
            choice = input("\nSelect filter option (1-9): ")

            if choice == '1':
                min_age = int(input("Minimum age: "))
                max_age = int(input("Maximum age: "))
                self.custom_filters['age_range'] = [min_age, max_age]
                print(f"Age filter applied: {min_age}-{max_age}")

            elif choice == '2':
                min_gpa = float(input("Minimum GPA: "))
                max_gpa = float(input("Maximum GPA: "))
                self.custom_filters['gpa_range'] = [min_gpa, max_gpa]
                print(f"GPA filter applied: {min_gpa}-{max_gpa}")

            elif choice == '3':
                min_engagement = float(input("Minimum engagement score: "))
                max_engagement = float(input("Maximum engagement score: "))
                self.custom_filters['engagement_range'] = [min_engagement, max_engagement]
                print(f"Engagement filter applied: {min_engagement}-{max_engagement}")

            elif choice == '4':
                courses = students_df['course'].unique()
                print("Available courses:", ', '.join(courses))
                selected_courses = input("Enter courses (comma-separated): ").split(',')
                selected_courses = [c.strip() for c in selected_courses if c.strip() in courses]
                if selected_courses:
                    self.custom_filters['course'] = selected_courses
                    print(f"Course filter applied: {', '.join(selected_courses)}")

            elif choice == '5':
                genders = students_df['gender'].unique()
                print("Available genders:", ', '.join(genders))
                selected_gender = input("Select gender: ")
                if selected_gender in genders:
                    self.custom_filters['gender'] = selected_gender
                    print(f"Gender filter applied: {selected_gender}")

            elif choice == '6':
                statuses = students_df['completion_status'].unique()
                print("Available statuses:", ', '.join(statuses))
                selected_status = input("Select completion status: ")
                if selected_status in statuses:
                    self.custom_filters['completion_status'] = selected_status
                    print(f"Completion status filter applied: {selected_status}")

            elif choice == '7':
                start_date = input("Start date (YYYY-MM-DD): ")
                end_date = input("End date (YYYY-MM-DD): ")
                try:
                    self.custom_filters['date_range'] = [start_date, end_date]
                    print(f"Date range filter applied: {start_date} to {end_date}")
                except (ValueError, KeyError):
                    print("Invalid date format")

            elif choice == '8':
                self.custom_filters.clear()
                print("All filters cleared")

            elif choice == '9':
                filtered_count = len(self.get_all_students(self.custom_filters))
                print(f"Filters applied. {filtered_count} students match criteria.")
                break

            else:
                print("Invalid choice")
