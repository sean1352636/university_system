from __future__ import annotations

from datetime import datetime
from university_system.infrastructure.database.db import sqlite3, get_connection
from university_system.modules.domain.student_affairs.student_union.services import context as ctx
from university_system.modules.domain.student_affairs.student_union.services.union_context import auto_award_points

def manage_green_initiatives():
    """Main green initiatives interface"""
    
    if not ctx.auth or not ctx.auth.current_user:
        print("You must be logged in to access green initiatives.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (ctx.auth.current_user['id'],))
        result = cursor.fetchone()

        if not result:
            print("No student record is associated with your account.")
            conn.close()
            return

        student_id = result[0]

        while True:
            print(f"\n🌱 Green Initiatives")
            print("1. Carbon footprint tracking")
            print("2. Sustainable events")
            print("3. Waste reduction programs")
            print("4. Green transport")
            print("5. Environmental reports")
            print("6. Eco-friendly suppliers")
            print("7. Green certifications")
            print("8. Return to main menu")

            choice = input("Choose an option: ").strip()

            if choice == '1':
                track_carbon_footprint(student_id, cursor, conn)
            elif choice == '2':
                manage_sustainable_events(student_id, cursor, conn)
            elif choice == '3':
                waste_reduction_tracking(student_id, cursor, conn)
            elif choice == '4':
                green_transport_tracking(student_id, cursor, conn)
            elif choice == '5':
                generate_environmental_reports(cursor)
            elif choice == '6':
                view_eco_suppliers(cursor)
            elif choice == '7':
                green_certification_system(student_id, cursor, conn)
            elif choice == '8':
                break
            else:
                print("Invalid choice.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def track_carbon_footprint(student_id, cursor, conn):
    """Track carbon footprint for events and activities"""
    try:
        print(f"\n🌍 Carbon Footprint Tracking")
        print("=" * 35)

        # Get recent events to track
        cursor.execute('''
        SELECT e.event_id, e.event_name, c.club_name, e.event_date, e.current_attendees
        FROM union_events e
        JOIN student_clubs c ON e.organizer_id = c.club_id
        WHERE e.event_date >= date('now', '-30 days')
        AND (c.president_id = ? OR c.treasurer_id = ? OR c.secretary_id = ?)
        ORDER BY e.event_date DESC
        ''', (student_id, student_id, student_id))

        events = cursor.fetchall()

        if not events:
            print("No recent events found to track.")
            return

        print("Recent events available for carbon tracking:")
        for i, event in enumerate(events):
            print(f"{i+1}. {event[1]} ({event[2]}) - {event[3]} - {event[4]} attendees")

        choice = input("Select event to track carbon footprint (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(events):
            print("Invalid selection.")
            return

        selected_event = events[int(choice)-1]
        event_id = selected_event[0]
        event_name = selected_event[1]
        attendees = selected_event[4]

        print(f"\nTracking carbon footprint for: {event_name}")

        # Transportation carbon calculation
        print("\nTransportation Impact:")
        transport_methods = {
            "walking": 0,
            "cycling": 0,
            "public_transport": 0.05,  # kg CO2 per km
            "car": 0.21,  # kg CO2 per km
            "taxi": 0.25   # kg CO2 per km
        }

        total_transport_carbon = 0
        for method, carbon_per_km in transport_methods.items():
            count = input(f"Number of attendees using {method}: ").strip()
            if count.isdigit():
                count = int(count)
                if count > 0:
                    avg_distance = input(f"Average distance traveled by {method} (km): ").strip()
                    if avg_distance.replace('.', '').isdigit():
                        distance = float(avg_distance)
                        carbon = count * distance * carbon_per_km * 2  # Round trip
                        total_transport_carbon += carbon
                        print(f"  {method}: {carbon:.2f} kg CO2")

        # Energy consumption
        print("\nEnergy Consumption:")
        venue_hours = input("Event duration (hours): ").strip()
        if venue_hours.replace('.', '').isdigit():
            venue_hours = float(venue_hours)

            # Estimate energy usage
            energy_per_person_hour = 0.5  # kWh per person per hour
            carbon_per_kwh = 0.233  # kg CO2 per kWh (UK average)

            energy_carbon = attendees * venue_hours * energy_per_person_hour * carbon_per_kwh
            print(f"Energy consumption: {energy_carbon:.2f} kg CO2")
        else:
            energy_carbon = 0

        # Catering impact
        print("\nCatering Impact:")
        catering_types = {
            "vegan": 1.5,      # kg CO2 per person
            "vegetarian": 2.5,  # kg CO2 per person
            "meat": 5.0        # kg CO2 per person
        }

        catering_carbon = 0
        for catering_type, carbon_per_person in catering_types.items():
            count = input(f"Number of {catering_type} meals: ").strip()
            if count.isdigit():
                count = int(count)
                carbon = count * carbon_per_person
                catering_carbon += carbon
                if count > 0:
                    print(f"  {catering_type} meals: {carbon:.2f} kg CO2")

        # Waste generated
        print("\nWaste Impact:")
        waste_kg = input("Total waste generated (kg): ").strip()
        if waste_kg.replace('.', '').isdigit():
            waste_kg = float(waste_kg)
            waste_carbon = waste_kg * 0.5  # Approximate CO2 per kg waste
            print(f"Waste impact: {waste_carbon:.2f} kg CO2")
        else:
            waste_carbon = 0

        # Calculate total
        total_carbon = total_transport_carbon + energy_carbon + catering_carbon + waste_carbon
        carbon_per_person = total_carbon / attendees if attendees > 0 else 0

        # Calculate sustainability score (lower carbon = higher score)
        max_score = 100
        sustainability_score = max(0, max_score - (carbon_per_person * 10))

        print(f"\n📊 Carbon Footprint Summary:")
        print(f"Transportation: {total_transport_carbon:.2f} kg CO2")
        print(f"Energy: {energy_carbon:.2f} kg CO2")
        print(f"Catering: {catering_carbon:.2f} kg CO2")
        print(f"Waste: {waste_carbon:.2f} kg CO2")
        print(f"Total Carbon Footprint: {total_carbon:.2f} kg CO2")
        print(f"Per Person: {carbon_per_person:.2f} kg CO2")
        print(f"Sustainability Score: {sustainability_score:.1f}/100")

        # Save to database
        notes = input("\nAdditional sustainability notes: ").strip()
        recorded_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Check if tracking already exists
        cursor.execute('''
        SELECT COUNT(*) FROM sustainability_tracking
        WHERE event_id = ?
        ''', (event_id,))

        if cursor.fetchone()[0] > 0:
            # Update existing record
            cursor.execute('''
            UPDATE sustainability_tracking 
            SET carbon_footprint = ?, sustainability_score = ?, notes = ?, recorded_date = ?
            WHERE event_id = ?
            ''', (total_carbon, sustainability_score, notes, recorded_date, event_id))
        else:
            # Create new record
            cursor.execute('''
            INSERT INTO sustainability_tracking (
                event_id, carbon_footprint, sustainability_score, notes, recorded_date
            ) VALUES (?, ?, ?, ?, ?)
            ''', (event_id, total_carbon, sustainability_score, notes, recorded_date))

        conn.commit()
        print("Carbon footprint data saved!")

        # Award points for tracking
        auto_award_points(student_id, "Green Initiatives", 15, 
                        f"Tracked carbon footprint for {event_name}", cursor, conn)

        # Suggest improvements
        print(f"\n💡 Sustainability Suggestions:")
        if total_transport_carbon > total_carbon * 0.5:
            print("- Encourage public transport or carpooling")
            print("- Consider virtual attendance options")

        if catering_carbon > total_carbon * 0.3:
            print("- Offer more plant-based meal options")
            print("- Source from local suppliers")

        if sustainability_score < 50:
            print("- This event had high environmental impact")
            print("- Consider green certification for future events")
        elif sustainability_score > 80:
            print("- Excellent sustainability performance!")
            print("- Consider applying for green event certification")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def waste_reduction_tracking(student_id, cursor, conn):
    """Track waste reduction efforts"""
    try:
        print(f"\n♻️ Waste Reduction Tracking")
        print("=" * 30)

        print("1. Log waste data for event")
        print("2. View waste statistics")
        print("3. Waste reduction challenges")
        print("4. Recycling programs")

        choice = input("Choose option: ").strip()

        if choice == '1':
            # Log waste data
            cursor.execute('''
            SELECT e.event_id, e.event_name, e.event_date
            FROM union_events e
            JOIN student_clubs c ON e.organizer_id = c.club_id
            WHERE e.event_date >= date('now', '-7 days')
            AND (c.president_id = ? OR c.treasurer_id = ? OR c.secretary_id = ?)
            ORDER BY e.event_date DESC
            ''', (student_id, student_id, student_id))

            recent_events = cursor.fetchall()

            if not recent_events:
                print("No recent events found.")
                return

            print("Recent events:")
            for i, event in enumerate(recent_events):
                print(f"{i+1}. {event[1]} - {event[2]}")

            event_choice = input("Select event to log waste data: ").strip()
            if not event_choice.isdigit() or int(event_choice) < 1 or int(event_choice) > len(recent_events):
                print("Invalid selection.")
                return

            selected_event = recent_events[int(event_choice)-1]
            event_id = selected_event[0]

            print(f"\nLogging waste data for: {selected_event[1]}")

            waste_generated = input("Total waste generated (kg): ").strip()
            waste_recycled = input("Amount recycled (kg): ").strip()

            try:
                waste_generated = float(waste_generated)
                waste_recycled = float(waste_recycled)

                if waste_recycled > waste_generated:
                    print("Recycled amount cannot exceed total waste.")
                    return

                recycling_rate = (waste_recycled / waste_generated * 100) if waste_generated > 0 else 0

                print(f"Recycling rate: {recycling_rate:.1f}%")

                # Update sustainability tracking
                cursor.execute('''
                UPDATE sustainability_tracking 
                SET waste_generated = ?, waste_recycled = ?
                WHERE event_id = ?
                ''', (waste_generated, waste_recycled, event_id))

                if cursor.rowcount == 0:
                    # Create new record if doesn't exist
                    cursor.execute('''
                    INSERT INTO sustainability_tracking (
                        event_id, waste_generated, waste_recycled, recorded_date
                    ) VALUES (?, ?, ?, ?)
                    ''', (event_id, waste_generated, waste_recycled, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                conn.commit()
                print("Waste data logged successfully!")

                # Award points based on recycling rate
                if recycling_rate >= 80:
                    points = 25
                    message = "Excellent waste management"
                elif recycling_rate >= 60:
                    points = 15
                    message = "Good waste management"
                else:
                    points = 10
                    message = "Waste management effort"

                auto_award_points(student_id, "Green Initiatives", points, message, cursor, conn)

            except ValueError:
                print("Invalid number format.")

        elif choice == '2':
            # View waste statistics
            cursor.execute('''
            SELECT 
                COUNT(*) as events_tracked,
                SUM(waste_generated) as total_waste,
                SUM(waste_recycled) as total_recycled,
                AVG(waste_recycled / NULLIF(waste_generated, 0) * 100) as avg_recycling_rate
            FROM sustainability_tracking
            WHERE waste_generated IS NOT NULL
            ''')

            stats = cursor.fetchone()

            print(f"\n📊 Waste Management Statistics")
            print("=" * 35)
            print(f"Events tracked: {stats[0]}")
            print(f"Total waste generated: {stats[1]:.1f} kg" if stats[1] else "No data")
            print(f"Total waste recycled: {stats[2]:.1f} kg" if stats[2] else "No data")
            print(f"Average recycling rate: {stats[3]:.1f}%" if stats[3] else "No data")

            # Monthly trends
            cursor.execute('''
            SELECT 
                strftime('%Y-%m', recorded_date) as month,
                SUM(waste_generated) as monthly_waste,
                SUM(waste_recycled) as monthly_recycled
            FROM sustainability_tracking
            WHERE waste_generated IS NOT NULL
            GROUP BY strftime('%Y-%m', recorded_date)
            ORDER BY month DESC
            LIMIT 6
            ''')

            monthly_data = cursor.fetchall()

            if monthly_data:
                print(f"\nMonthly Trends:")
                print(f"{'Month':<10} {'Generated (kg)':<15} {'Recycled (kg)':<15} {'Rate':<10}")
                print("-" * 55)

                for month_data in monthly_data:
                    rate = (month_data[2] / month_data[1] * 100) if month_data[1] > 0 else 0
                    print(f"{month_data[0]:<10} {month_data[1]:<15.1f} {month_data[2]:<15.1f} {rate:<10.1f}%")

        elif choice == '3':
            # Waste reduction challenges
            print(f"\n🏆 Waste Reduction Challenges")
            print("=" * 35)

            challenges = [
                ("Zero Waste Week", "Achieve 95% recycling rate", "50 points", "Weekly"),
                ("Plastic Free Event", "Host event with no single-use plastic", "40 points", "Per event"),
                ("Composting Champion", "Implement food waste composting", "30 points", "Monthly"),
                ("Waste Audit Master", "Complete detailed waste audit", "35 points", "Per audit"),
                ("Reduction Leader", "Reduce waste by 20% vs previous event", "45 points", "Per event")
            ]

            print(f"{'Challenge':<20} {'Description':<35} {'Reward':<12} {'Frequency':<10}")
            print("-" * 80)

            for challenge in challenges:
                print(f"{challenge[0]:<20} {challenge[1]:<35} {challenge[2]:<12} {challenge[3]:<10}")

            print(f"\nHow to participate:")
            print("- Track your waste data for all events")
            print("- Document reduction strategies")
            print("- Submit evidence for verification")
            print("- Earn points and recognition!")

        elif choice == '4':
            # Recycling programs
            print(f"\n♻️ Campus Recycling Programs")
            print("=" * 35)

            programs = [
                "Paper & Cardboard - Blue bins across campus",
                "Plastic Bottles & Containers - Yellow bins",
                "Glass - Green bins in main buildings",
                "Electronics - IT Services collection point",
                "Batteries - Student Union desk",
                "Clothing - Charity collection bins",
                "Food Waste - Composting bins in kitchens",
                "Furniture - Facilities Management"
            ]

            print("Available recycling streams:")
            for i, program in enumerate(programs, 1):
                print(f"{i}. {program}")

            print(f"\nSpecial collections:")
            print("- Mobile phone recycling drive (monthly)")
            print("- Textbook exchange program")
            print("- End-of-term move-out collection")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def green_transport_tracking(student_id, cursor, conn):
    """Track and encourage green transportation"""
    try:
        print(f"\n🚴 Green Transportation")
        print("=" * 25)

        print("1. Log sustainable transport")
        print("2. Transport challenges")
        print("3. Carpooling coordination")
        print("4. Public transport info")
        print("5. Cycling facilities")

        choice = input("Choose option: ").strip()

        if choice == '1':
            # Log sustainable transport
            print("Log your sustainable transport usage:")

            transport_methods = ["Walking", "Cycling", "Public transport", "Carpooling", "Electric vehicle"]

            print("Transport methods:")
            for i, method in enumerate(transport_methods, 1):
                print(f"{i}. {method}")

            method_choice = input("Select transport method: ").strip()
            if method_choice.isdigit() and 1 <= int(method_choice) <= len(transport_methods):
                selected_method = transport_methods[int(method_choice)-1]
            else:
                print("Invalid selection.")
                return

            distance = input("Distance traveled (km): ").strip()
            if not distance.replace('.', '').isdigit():
                print("Invalid distance.")
                return

            distance = float(distance)
            date_used = datetime.now().strftime('%Y-%m-%d')

            # Calculate carbon saved vs car use
            car_carbon_per_km = 0.21  # kg CO2 per km
            method_carbon = {
                "Walking": 0,
                "Cycling": 0,
                "Public transport": 0.05,
                "Carpooling": 0.105,  # Half of car
                "Electric vehicle": 0.05
            }

            carbon_used = distance * method_carbon[selected_method]
            carbon_saved = distance * (car_carbon_per_km - method_carbon[selected_method])

            print(f"Carbon footprint: {carbon_used:.2f} kg CO2")
            print(f"Carbon saved vs car: {carbon_saved:.2f} kg CO2")

            # Award points based on sustainability
            points_map = {
                "Walking": 5,
                "Cycling": 5,
                "Public transport": 3,
                "Carpooling": 2,
                "Electric vehicle": 3
            }

            points = points_map[selected_method] * max(1, int(distance))
            auto_award_points(student_id, "Green Transport", points, 
                            f"Used {selected_method} for {distance}km", cursor, conn)

            print(f"Earned {points} green transport points!")

        elif choice == '2':
            # Transport challenges
            print(f"\n🚲 Green Transport Challenges")
            print("=" * 35)

            challenges = [
                ("Bike to Work Week", "Cycle to campus every day for a week", "50 points"),
                ("Public Transport Champion", "Use only public transport for a month", "100 points"),
                ("Walk & Talk", "Walk 10km in a week", "30 points"),
                ("Carpool Coordinator", "Organize carpooling for 5+ people", "40 points"),
                ("Zero Emission Day", "No fossil fuel transport for 24 hours", "25 points")
            ]

            print(f"{'Challenge':<25} {'Description':<40} {'Reward':<10}")
            print("-" * 80)

            for challenge in challenges:
                print(f"{challenge[0]:<25} {challenge[1]:<40} {challenge[2]:<10}")

        elif choice == '3':
            # Carpooling coordination
            print(f"\n🚗 Carpooling Coordination")
            print("=" * 30)
            print("Connect with other students for shared rides!")
            print()
            print("Popular routes:")
            print("- Campus ↔ City Centre")
            print("- Campus ↔ Train Station")
            print("- Campus ↔ Shopping Centre")
            print("- Campus ↔ Airport")
            print()
            print("How to participate:")
            print("1. Post your regular travel routes")
            print("2. Contact other students with similar routes")
            print("3. Arrange shared travel")
            print("4. Split fuel costs")
            print("5. Earn green transport points!")

        elif choice == '4':
            # Public transport info
            print(f"\n🚌 Public Transport Information")
            print("=" * 40)

            print("Bus routes to campus:")
            print("- Route 25: City Centre → Campus (every 15 mins)")
            print("- Route 34: Train Station → Campus (every 20 mins)")
            print("- Route 42: Shopping Centre → Campus (every 30 mins)")
            print()
            print("Student discounts:")
            print("- 30% off annual bus passes")
            print("- Student train discount card")
            print("- Group travel discounts")
            print()
            print("Apps and tools:")
            print("- Local Bus Tracker app")
            print("- University transport map")
            print("- Real-time arrival information")

        elif choice == '5':
            # Cycling facilities
            print(f"\n🚴 Cycling Facilities")
            print("=" * 25)

            print("Campus cycling infrastructure:")
            print("- 200+ secure bike parking spaces")
            print("- Bike repair station (tools provided)")
            print("- Covered bike shelters")
            print("- Cycling route maps")
            print("- Bike sharing scheme")
            print()
            print("Safety features:")
            print("- Well-lit cycle paths")
            print("- CCTV monitoring")
            print("- Emergency call points")
            print("- Weather protection")
            print()
            print("Support services:")
            print("- Free bike safety checks")
            print("- Cycling proficiency courses")
            print("- Group rides and events")
            print("- Maintenance workshops")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def view_eco_suppliers(cursor):
    """View eco-friendly supplier directory"""
    try:
        print(f"\n🌿 Eco-Friendly Supplier Directory")
        print("=" * 40)

        suppliers = [
            {
                "name": "Green Events Catering",
                "category": "Catering",
                "certifications": ["Organic", "Local sourcing", "Zero waste"],
                "description": "100% organic catering with minimal packaging",
                "contact": "green@eventscatering.com",
                "rating": 4.8
            },
            {
                "name": "Sustainable Venues Ltd",
                "category": "Venues",
                "certifications": ["BREEAM Excellent", "Carbon neutral", "Renewable energy"],
                "description": "Solar-powered venues with rainwater harvesting",
                "contact": "bookings@sustainablevenues.co.uk",
                "rating": 4.9
            },
            {
                "name": "EcoSupplies Co",
                "category": "Equipment & Supplies",
                "certifications": ["FSC certified", "Biodegradable", "Recycled materials"],
                "description": "Compostable tableware and decorations",
                "contact": "orders@ecosupplies.co.uk",
                "rating": 4.6
            },
            {
                "name": "Zero Carbon Transport",
                "category": "Transportation",
                "certifications": ["Electric fleet", "Carbon offset", "Green accreditation"],
                "description": "Electric vehicle fleet for event transport",
                "contact": "booking@zerocarbontransport.com",
                "rating": 4.7
            }
        ]

        for supplier in suppliers:
            print(f"\n🏢 {supplier['name']}")
            print(f"Category: {supplier['category']}")
            print(f"Rating: {'⭐' * int(supplier['rating'])} ({supplier['rating']}/5)")
            print(f"Certifications: {', '.join(supplier['certifications'])}")
            print(f"Description: {supplier['description']}")
            print(f"Contact: {supplier['contact']}")
            print("-" * 50)

        print(f"\n📝 How to get listed:")
        print("1. Complete sustainability assessment")
        print("2. Provide certification documents")
        print("3. Submit references from previous events")
        print("4. Agree to sustainability standards")
        print("5. Contact: sustainability@studentunion.ac.uk")

    except Exception as e:
        print(f"An error occurred: {e}")

def green_certification_system(student_id, cursor, conn):
    """Green certification system for events and organizations"""
    try:
        print(f"\n🏅 Green Certification System")
        print("=" * 35)

        print("1. Event green certification")
        print("2. Club sustainability rating")
        print("3. Individual eco-champion status")
        print("4. Certification standards")

        choice = input("Choose option: ").strip()

        if choice == '1':
            # Event green certification
            print(f"\n🌟 Event Green Certification Levels")
            print("=" * 40)

            print("Bronze (70-79 points):")
            print("- Basic recycling implemented")
            print("- Some sustainable practices")
            print("- Carbon footprint measured")

            print("\nSilver (80-89 points):")
            print("- Comprehensive waste management")
            print("- 50%+ local/sustainable sourcing")
            print("- Public transport encouraged")

            print("\nGold (90-95 points):")
            print("- 90%+ waste diverted from landfill")
            print("- 80%+ sustainable/local sourcing")
            print("- Carbon offset program")

            print("\nPlatinum (95+ points):")
            print("- Zero waste to landfill")
            print("- 100% renewable energy")
            print("- Net carbon negative")

        elif choice == '2':
            # Club sustainability rating
            cursor.execute('''
            SELECT c.club_name, AVG(st.sustainability_score) as avg_score,
                   COUNT(st.event_id) as events_tracked
            FROM student_clubs c
            JOIN union_events e ON c.club_id = e.organizer_id
            JOIN sustainability_tracking st ON e.event_id = st.event_id
            WHERE st.sustainability_score IS NOT NULL
            GROUP BY c.club_id, c.club_name
            HAVING COUNT(st.event_id) >= 3
            ORDER BY avg_score DESC
            ''')

            club_ratings = cursor.fetchall()

            print(f"\n🏆 Club Sustainability Rankings")
            print("=" * 40)

            if club_ratings:
                print(f"{'Rank':<6} {'Club':<25} {'Avg Score':<12} {'Events':<8} {'Level':<10}")
                print("-" * 65)

                for i, club in enumerate(club_ratings, 1):
                    if club[1] >= 90:
                        level = "🥇 Gold"
                    elif club[1] >= 80:
                        level = "🥈 Silver"
                    elif club[1] >= 70:
                        level = "🥉 Bronze"
                    else:
                        level = "📈 Developing"

                    print(f"{i:<6} {club[0][:25]:<25} {club[1]:<12.1f} {club[2]:<8} {level:<10}")
            else:
                print("No clubs have enough sustainability data for ranking.")
                print("Clubs need at least 3 tracked events to be ranked.")

        elif choice == '3':
            # Individual eco-champion status
            cursor.execute('''
            SELECT SUM(points_earned) as green_points
            FROM student_points
            WHERE student_id = ? AND (
                activity_type LIKE '%Green%' OR 
                activity_type LIKE '%Environment%' OR
                activity_type LIKE '%Sustainab%'
            )
            ''', (student_id,))

            green_points = cursor.fetchone()[0] or 0

            print(f"\n🌱 Your Eco-Champion Status")
            print("=" * 30)
            print(f"Green points earned: {green_points}")

            if green_points >= 500:
                status = "🏆 Eco-Champion Elite"
                next_level = "Maximum level achieved!"
            elif green_points >= 250:
                status = "🥇 Eco-Champion Gold"
                next_level = f"{500 - green_points} points to Elite"
            elif green_points >= 100:
                status = "🥈 Eco-Champion Silver"
                next_level = f"{250 - green_points} points to Gold"
            elif green_points >= 50:
                status = "🥉 Eco-Champion Bronze"
                next_level = f"{100 - green_points} points to Silver"
            else:
                status = "🌱 Eco-Enthusiast"
                next_level = f"{50 - green_points} points to Bronze"

            print(f"Current status: {status}")
            print(f"Next level: {next_level}")

            print(f"\nBenefits of your status:")
            if green_points >= 250:
                print("- Priority access to sustainability events")
                print("- Eco-champion certificate")
                print("- Mentoring opportunities")
            elif green_points >= 100:
                print("- Recognition in sustainability newsletter")
                print("- Exclusive eco-champion events")
            elif green_points >= 50:
                print("- Eco-champion badge")
                print("- Early access to green initiatives")

        elif choice == '4':
            # Certification standards
            print(f"\n📋 Green Certification Standards")
            print("=" * 40)

            print("Environmental Management:")
            print("✓ Carbon footprint measurement")
            print("✓ Waste tracking and reduction")
            print("✓ Water conservation measures")
            print("✓ Energy efficiency practices")

            print("\nSustainable Sourcing:")
            print("✓ Local suppliers prioritized (within 50km)")
            print("✓ Organic/ethical products preferred")
            print("✓ Minimal packaging requirements")
            print("✓ Fair trade options available")

            print("\nTransport & Logistics:")
            print("✓ Public transport accessibility")
            print("✓ Cycling facilities provided")
            print("✓ Carpooling coordination")
            print("✓ Virtual attendance options")

            print("\nWaste & Materials:")
            print("✓ Comprehensive recycling system")
            print("✓ Compostable materials used")
            print("✓ Single-use plastic elimination")
            print("✓ Reusable item preference")

            print("\nCommunication & Education:")
            print("✓ Sustainability information shared")
            print("✓ Participant education provided")
            print("✓ Green practices promoted")
            print("✓ Impact reporting published")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
