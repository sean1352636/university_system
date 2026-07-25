from datetime import datetime, timedelta
from education_system.systems.university.domain.pastoral.health.records.student.wellness import quick_wellness_assessment


def wellness_resources(auth):
    print("\n===== Wellness Resources =====")

    wellness_categories = {
        "Physical Wellness": [
            "Campus Recreation Center - Free fitness classes",
            "Intramural Sports Programs",
            "Walking/Running Trails Map",
            "Bike Share Program",
            "Outdoor Adventure Club",
            "Personal Training Services"
        ],
        "Mental Health & Emotional Wellness": [
            "Counseling and Psychological Services (CAPS)",
            "Stress Management Workshops",
            "Mindfulness and Meditation Classes",
            "Support Groups",
            "Crisis Hotline: 988",
            "Mental Health First Aid Training"
        ],
        "Nutritional Wellness": [
            "Nutrition Counseling Services",
            "Healthy Cooking Classes",
            "Campus Farmers Market",
            "Meal Plan Consultations",
            "Food Allergy Support",
            "Eating Disorder Resources"
        ],
        "Social Wellness": [
            "Student Organizations Directory",
            "Volunteer Opportunities",
            "Leadership Development Programs",
            "Cultural Events Calendar",
            "Peer Mentoring Programs",
            "Community Service Projects"
        ],
        "Academic Wellness": [
            "Academic Success Center",
            "Study Skills Workshops",
            "Time Management Training",
            "Test Anxiety Support",
            "Tutoring Services",
            "Academic Coaching"
        ],
        "Financial Wellness": [
            "Financial Literacy Workshops",
            "Budget Planning Resources",
            "Emergency Financial Assistance",
            "Scholarship Information",
            "Student Employment Services",
            "Financial Counseling"
        ],
        "Sleep & Recovery": [
            "Sleep Hygiene Education",
            "Stress-Free Study Spaces",
            "Relaxation Techniques Training",
            "Campus Quiet Zones",
            "Nap Pods (Library)",
            "Recovery and Rest Guidelines"
        ],
        "Preventive Health": [
            "Annual Health Screenings",
            "Vaccination Clinics",
            "Health Education Workshops",
            "Disease Prevention Information",
            "Health Risk Assessments",
            "Wellness Coaching"
        ]
    }

    print("Available wellness resources and programs:")

    for category, resources in wellness_categories.items():
        print(f"\n🌟 {category}:")
        for resource in resources:
            print(f"   • {resource}")

    print("\n📞 Important Contacts:")
    print("   • Health Center: (555) 123-4567")
    print("   • Counseling Services: (555) 123-HELP")
    print("   • Crisis Line: 988")
    print("   • Campus Safety: (555) 123-SAFE")

    print("\n🌐 Online Resources:")
    print("   • Student Health Portal: health.university.edu")
    print("   • Wellness Blog: wellness.university.edu")
    print("   • Mental Health Resources: mentalhealth.university.edu")
    print("   • Fitness Class Schedule: recreation.university.edu")

    # Interactive resource finder
    find_resources = input("\nSearch for specific wellness resources? (y/n): ").lower()

    if find_resources == 'y':
        search_term = input("Enter wellness topic or keyword: ").lower()

        found_resources = []
        for category, resources in wellness_categories.items():
            for resource in resources:
                if search_term in resource.lower() or search_term in category.lower():
                    found_resources.append((category, resource))

        if found_resources:
            print(f"\nResources related to '{search_term}':")
            for category, resource in found_resources:
                print(f"   [{category}] {resource}")
        else:
            print(f"No resources found for '{search_term}'.")
            print("Try searching for: fitness, nutrition, mental health, stress, sleep, etc.")

    # Wellness assessment offer
    assessment = input("\nWould you like to take a quick wellness assessment? (y/n): ").lower()

    if assessment == 'y':
        quick_wellness_assessment(auth)



