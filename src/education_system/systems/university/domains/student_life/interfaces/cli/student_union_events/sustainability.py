"""Workflow extracted from the legacy event-management module."""
from __future__ import annotations
from education_system.systems.university.domains.student_life.domain.student_life.student_union.events.application.ports import (
    AcademicCalendarManager, DatabaseManager, HAS_AUTH, UserAuth, datetime,
    get_connection, get_events_support_phone, os, random,
    send_confirmation_email, set_auth_instance, sqlite3, string,
)
from education_system.systems.university.domains.student_life.interfaces.cli.student_union_events.context import auth

def manage_sustainable_events(student_id, cursor, conn):
    """Manage sustainable event planning"""
    from education_system.systems.university.domains.student_life.domain.student_life.student_union.services.points import auto_award_points
    try:
        print("\n🌿 Sustainable Event Planning")
        print("=" * 35)

        print("1. Plan sustainable event")
        print("2. Green event checklist")
        print("3. Sustainable vendor directory")
        print("4. View green certified events")
        print("5. Apply for green certification")

        choice = input("Choose option: ").strip()

        if choice == '1':
            # Plan sustainable event
            print("\nSustainable Event Planning Wizard")
            print("=================================")

            event_name = input("Event name: ").strip()
            expected_attendees = input("Expected attendees: ").strip()

            if not expected_attendees.isdigit():
                print("Invalid attendee count.")
                return

            expected_attendees = int(expected_attendees)

            print(f"\nSustainability recommendations for {expected_attendees} attendees:")

            # Venue recommendations
            print("\n🏢 Venue Selection:")
            print("- Choose venues with public transport access")
            print("- Select venues with renewable energy")
            print("- Consider outdoor venues to reduce energy needs")
            print("- Look for venues with recycling facilities")

            # Catering recommendations
            print("\n🍽️ Sustainable Catering:")
            print("- Offer 70% plant-based options")
            print("- Source from local suppliers (within 50km)")
            print("- Use reusable or compostable materials")
            print("- Avoid single-use plastics")

            # Transport recommendations
            print("\n🚌 Green Transportation:")
            print("- Provide public transport information")
            print("- Organize group travel from campus")
            print("- Offer bicycle parking")
            print("- Consider hybrid/virtual attendance")

            # Waste reduction
            print("\n♻️ Waste Reduction:")
            print("- Set up recycling stations")
            print("- Use digital materials instead of printed")
            print("- Implement food waste reduction strategies")
            print("- Provide water refill stations")

            # Calculate estimated carbon footprint
            estimated_carbon = expected_attendees * 2.5  # Conservative estimate
            print(f"\n📊 Estimated Carbon Footprint: {estimated_carbon:.1f} kg CO2")
            print("Target: Reduce by 30% through sustainable practices")

        elif choice == '2':
            # Green event checklist
            print("\n✅ Green Event Checklist")
            print("=" * 25)

            checklist_items = [
                "Venue accessible by public transport",
                "Renewable energy powered venue",
                "70%+ plant-based catering options",
                "Local suppliers (within 50km)",
                "Reusable or compostable materials",
                "No single-use plastics",
                "Recycling stations available",
                "Digital materials instead of printed",
                "Water refill stations",
                "Waste sorting system",
                "Carbon offset for unavoidable emissions",
                "Sustainability information for attendees"
            ]

            print("Pre-event planning:")
            for i, item in enumerate(checklist_items[:6], 1):
                print(f"{i:2}. ☐ {item}")

            print("\nDuring event:")
            for i, item in enumerate(checklist_items[6:9], 7):
                print(f"{i:2}. ☐ {item}")

            print("\nPost-event:")
            for i, item in enumerate(checklist_items[9:], 10):
                print(f"{i:2}. ☐ {item}")

        elif choice == '3':
            # Sustainable vendor directory
            print("\n🌱 Eco-Friendly Supplier Directory")
            print("=" * 40)

            suppliers = [
                ("Green Catering Co.", "Catering", "100% organic, local ingredients", "⭐⭐⭐⭐⭐"),
                ("EcoVenue Spaces", "Venues", "Solar-powered event spaces", "⭐⭐⭐⭐⭐"),
                ("Sustainable Supplies", "Equipment", "Biodegradable party supplies", "⭐⭐⭐⭐"),
                ("Carbon Neutral Transport", "Transport", "Electric vehicle fleet", "⭐⭐⭐⭐⭐"),
                ("Zero Waste Solutions", "Waste Management", "Complete recycling service", "⭐⭐⭐⭐"),
            ]

            print(f"{'Supplier':<25} {'Category':<15} {'Specialty':<30} {'Rating':<10}")
            print("-" * 85)

            for supplier in suppliers:
                print(f"{supplier[0]:<25} {supplier[1]:<15} {supplier[2]:<30} {supplier[3]:<10}")

            print("\nTo add your eco-friendly supplier:")
            print("- Contact Student Union sustainability team")
            print("- Provide sustainability certifications")
            print("- Complete environmental impact assessment")

        elif choice == '4':
            # View green certified events
            cursor.execute('''
            SELECT e.event_name, c.club_name, e.event_date, st.sustainability_score
            FROM (SELECT event_id, title AS event_name, description, organizer_id, event_date, start_time, end_time, location, event_category AS category, max_capacity AS max_attendees, (SELECT COUNT(*) FROM unified_event_registrations ur WHERE ur.event_id = ue.event_id) AS current_attendees, status, created_at, start_time AS event_time FROM unified_events ue WHERE ue.source_type = 'union') e
            JOIN student_clubs c ON e.organizer_id = c.club_id
            JOIN sustainability_tracking st ON e.event_id = st.event_id
            WHERE st.sustainability_score >= 80
            ORDER BY st.sustainability_score DESC, e.event_date DESC
            ''')

            green_events = cursor.fetchall()

            if not green_events:
                print("No green certified events found.")
                return

            print("\n🏆 Green Certified Events")
            print("=" * 30)
            print(f"{'Event':<30} {'Organizer':<20} {'Date':<12} {'Score':<8}")
            print("-" * 75)

            for event in green_events:
                print(f"{event[0][:30]:<30} {event[1][:20]:<20} {event[2]:<12} {event[3]:.1f}/100")

        elif choice == '5':
            # Apply for green certification
            print("\n🏅 Green Event Certification")
            print("=" * 30)

            # Get events eligible for certification
            cursor.execute('''
            SELECT e.event_id, e.event_name, st.sustainability_score
            FROM (SELECT event_id, title AS event_name, description, organizer_id, event_date, start_time, end_time, location, event_category AS category, max_capacity AS max_attendees, (SELECT COUNT(*) FROM unified_event_registrations ur WHERE ur.event_id = ue.event_id) AS current_attendees, status, created_at, start_time AS event_time FROM unified_events ue WHERE ue.source_type = 'union') e
            JOIN sustainability_tracking st ON e.event_id = st.event_id
            WHERE st.sustainability_score >= 70
            AND e.organizer_id IN (
                SELECT club_id FROM student_clubs
                WHERE president_id = ? OR treasurer_id = ? OR secretary_id = ?
            )
            ORDER BY st.sustainability_score DESC
            ''', (student_id, student_id, student_id))

            eligible_events = cursor.fetchall()

            if not eligible_events:
                print("No events eligible for green certification.")
                print("Events need a sustainability score of 70+ to qualify.")
                return

            print("Events eligible for green certification:")
            for i, event in enumerate(eligible_events):
                print(f"{i+1}. {event[1]} (Score: {event[2]:.1f})")

            event_choice = input("Select event to certify (enter number): ").strip()
            if event_choice.isdigit() and 1 <= int(event_choice) <= len(eligible_events):
                selected = eligible_events[int(event_choice)-1]

                print(f"\nApplying for certification for: {selected[1]}")
                print("Certification levels:")

                if selected[2] >= 90:
                    level = "Platinum"
                    points = 50
                elif selected[2] >= 80:
                    level = "Gold"
                    points = 35
                else:
                    level = "Silver"
                    points = 25

                print(f"Your event qualifies for: {level} Green Certification")
                print(f"Sustainability score: {selected[2]:.1f}/100")

                confirm = input("Submit certification application? (y/n): ").strip().lower()
                if confirm == 'y':
                    print("Green certification application submitted!")
                    print(f"Certificate level: {level}")

                    # Award points
                    auto_award_points(student_id, "Green Initiatives", points,
                                    f"{level} green certification for {selected[1]}", cursor, conn)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
