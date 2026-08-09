from datetime import datetime, timedelta


def student_health_resources(auth):
    """Student-specific health resources"""
    print("\n===== Student Health Resources =====")

    resources = {
        "Campus Health Services": [
            "Student Health Center - Building A, Room 150",
            "Hours: Monday-Friday 8AM-5PM",
            "After-hours nurse line: (555) 123-NURSE",
            "Appointment scheduling: health.university.edu"
        ],
        "Mental Health Support": [
            "Counseling Center - Building B, Room 200",
            "Crisis support: Available 24/7",
            "Support groups: Anxiety, Depression, Stress Management",
            "Peer counseling program"
        ],
        "Health Education": [
            "Nutrition workshops: Healthy eating on a budget",
            "Fitness classes: Yoga, Zumba, Strength training",
            "Sleep hygiene seminars",
            "Substance abuse prevention programs"
        ],
        "Insurance & Financial": [
            "Student health insurance enrollment",
            "Financial assistance for medical care",
            "Prescription assistance programs",
            "Healthcare cost estimates"
        ],
        "Online Tools": [
            "Health risk assessments",
            "Symptom checker",
            "Medication interaction checker",
            "Health tracking apps"
        ]
    }

    for category, items in resources.items():
        print(f"\n📋 {category}:")
        for item in items:
            print(f"   • {item}")

    print("\n🔗 Quick Links:")
    print("   • Student Health Portal: health.university.edu")
    print("   • Mental Health Resources: counseling.university.edu")
    print("   • Campus Recreation: recreation.university.edu")
    print("   • Insurance Information: insurance.university.edu")



def view_health_resources(auth):
    """Display health resources and educational materials"""
    print("\n===== Health Resources =====")

    resources = {
        "Emergency Information": [
            "Campus Emergency: 911",
            "Health Center: (555) 123-4567",
            "Poison Control: 1-800-222-1222",
            "Crisis Hotline: 988",
            "Campus Safety: (555) 123-SAFE"
        ],
        "Health Services": [
            "Primary Care Clinic",
            "Mental Health Counseling",
            "Pharmacy Services",
            "Laboratory Services",
            "Immunization Clinic",
            "Health Education Programs"
        ],
        "Wellness Programs": [
            "Fitness Center Membership",
            "Nutrition Counseling",
            "Stress Management Workshops",
            "Sleep Health Programs",
            "Substance Abuse Prevention",
            "Mindfulness and Meditation"
        ],
        "Online Resources": [
            "Student Health Portal",
            "Health Assessment Tools",
            "Educational Videos",
            "Health Tips Newsletter",
            "Appointment Scheduling",
            "Prescription Refills"
        ]
    }

    for category, items in resources.items():
        print(f"\n{category}:")
        for item in items:
            print(f"  • {item}")

    print("\n" + "="*50)
    print("For more information, visit the Student Health Center")
    print("or call (555) 123-4567")



