"""
Campus Navigation CLI Interface

Provides command-line interface for campus navigation and wayfinding.
"""

from typing import Optional
from education_system.university_system.modules.domain.campus.campus_navigation.services.navigation_service import (
    NavigationService
)
from education_system.university_system.infrastructure.shared_context import get_auth


class NavigationCLI:
    """CLI interface for Campus Navigation."""

    def __init__(self):
        """Initialize the Campus Navigation CLI."""
        self.service = NavigationService()
        self.auth = get_auth()

    def run(self):
        """Run the CLI (alias for display_menu)."""
        self.display_menu()

    def display_menu(self):
        """Display the main navigation menu."""
        while True:
            print("\n" + "=" * 60)
            print("Campus Navigation System".center(60))
            print("=" * 60)
            print("\n[1] Building Directory")
            print("[2] Search Locations")
            print("[3] Get Directions")
            print("[4] Find Nearest Amenity")
            print("[5] View Points of Interest")
            print("[6] My Favorites")
            print("[7] Report Accessibility Issue")
            print("[8] View Campus Map")
            print("[0] Back to Main Menu")

            choice = input("\nEnter your choice: ").strip()

            if choice == "1":
                self.building_directory()
            elif choice == "2":
                self.search_locations()
            elif choice == "3":
                self.get_directions()
            elif choice == "4":
                self.find_nearest()
            elif choice == "5":
                self.view_points_of_interest()
            elif choice == "6":
                self.manage_favorites()
            elif choice == "7":
                self.report_accessibility_issue()
            elif choice == "8":
                self.view_campus_map()
            elif choice == "0":
                break
            else:
                print("\nInvalid choice. Please try again.")

    def building_directory(self):
        """Display building directory."""
        print("\n" + "=" * 60)
        print("Building Directory".center(60))
        print("=" * 60)

        print("\n[1] View All Buildings")
        print("[2] Filter by Type")
        print("[3] Search by Name")
        print("[0] Back")

        choice = input("\nEnter your choice: ").strip()

        if choice == "1":
            buildings = self.service.get_all_buildings()
            self._display_buildings(buildings)

        elif choice == "2":
            print("\nBuilding Types:")
            print("[1] Academic")
            print("[2] Housing")
            print("[3] Athletic")
            print("[4] Administrative")
            print("[5] Student Services")
            print("[6] Medical")

            type_choice = input("\nSelect type: ").strip()
            type_map = {
                "1": "Academic",
                "2": "Housing",
                "3": "Athletic",
                "4": "Administrative",
                "5": "Student Services",
                "6": "Medical"
            }

            if type_choice in type_map:
                buildings = self.service.get_all_buildings(type_map[type_choice])
                self._display_buildings(buildings)
            else:
                print("\nInvalid type.")

        elif choice == "3":
            search_term = input("\nEnter search term: ").strip()
            if search_term:
                buildings = self.service.search_buildings(search_term)
                self._display_buildings(buildings)

    def _display_buildings(self, buildings):
        """Display a list of buildings."""
        if not buildings:
            print("\nNo buildings found.")
            return

        print(f"\n{'Code':<8} {'Building Name':<30} {'Type':<20} {'Address':<30}")
        print("-" * 88)

        for building in buildings:
            print(f"{building['building_code']:<8} "
                  f"{building['building_name']:<30} "
                  f"{building['building_type']:<20} "
                  f"{building.get('address', 'N/A'):<30}")

        # Option to view details
        code = input("\nEnter building code for details (or press Enter to skip): ").strip()
        if code:
            building = self.service.get_building(building_code=code.upper())
            if building:
                self._display_building_details(building)
            else:
                print("\nBuilding not found.")

    def _display_building_details(self, building):
        """Display detailed information about a building."""
        print("\n" + "=" * 60)
        print(f"{building['building_name']} ({building['building_code']})".center(60))
        print("=" * 60)

        print(f"\nType: {building['building_type']}")
        print(f"Address: {building.get('address', 'N/A')}")
        print(f"Floors: {building['floors']}")

        print(f"\nAccessibility Features:")
        print(f"  - Accessible: {'Yes' if building['is_accessible'] else 'No'}")
        print(f"  - Elevator: {'Yes' if building['has_elevator'] else 'No'}")
        print(f"  - Ramp: {'Yes' if building['has_ramp'] else 'No'}")
        print(f"  - Automatic Doors: {'Yes' if building['has_automatic_doors'] else 'No'}")

        if building.get('operating_hours'):
            print(f"\nOperating Hours: {building['operating_hours']}")

        if building.get('amenities'):
            print(f"\nAmenities: {building['amenities']}")

        if building.get('description'):
            print(f"\nDescription: {building['description']}")

        # Show POIs in this building
        pois = self.service.get_points_of_interest(building_id=building['building_id'])
        if pois:
            print(f"\nPoints of Interest ({len(pois)}):")
            for poi in pois[:5]:  # Show first 5
                print(f"  - {poi['poi_name']} ({poi['poi_type']})")
                if poi.get('room_number'):
                    print(f"    Room: {poi['room_number']}")

        # Show stats
        stats = self.service.get_building_stats(building['building_id'])
        if stats.get('navigation', {}).get('total_navigations', 0) > 0:
            print(f"\nNavigation Stats:")
            print(f"  - Total visits: {stats['navigation']['total_navigations']}")

    def search_locations(self):
        """Search for buildings and points of interest."""
        print("\n" + "=" * 60)
        print("Search Locations".center(60))
        print("=" * 60)

        search_term = input("\nEnter search term: ").strip()
        if not search_term:
            return

        # Search buildings
        buildings = self.service.search_buildings(search_term)

        # Search POIs
        pois = self.service.search_points_of_interest(search_term)

        print(f"\n--- Buildings ({len(buildings)}) ---")
        if buildings:
            for building in buildings[:10]:  # Show first 10
                print(f"  [{building['building_code']}] {building['building_name']} "
                      f"- {building['building_type']}")
        else:
            print("  No buildings found.")

        print(f"\n--- Points of Interest ({len(pois)}) ---")
        if pois:
            for poi in pois[:10]:  # Show first 10
                building_info = f" in {poi['building_name']}" if poi.get('building_name') else ""
                print(f"  {poi['poi_name']} ({poi['poi_type']}){building_info}")
                if poi.get('room_number'):
                    print(f"    Room: {poi['room_number']}")
        else:
            print("  No points of interest found.")

    def get_directions(self):
        """Get directions between two locations."""
        print("\n" + "=" * 60)
        print("Get Directions".center(60))
        print("=" * 60)

        # Get start location
        print("\nSelect starting location:")
        start_code = input("Enter building code: ").strip().upper()
        start_building = self.service.get_building(building_code=start_code)

        if not start_building:
            print("\nStarting building not found.")
            return

        # Get end location
        print("\nSelect destination:")
        end_code = input("Enter building code: ").strip().upper()
        end_building = self.service.get_building(building_code=end_code)

        if not end_building:
            print("\nDestination building not found.")
            return

        # Check if same building
        if start_building['building_id'] == end_building['building_id']:
            print("\nStart and destination are the same building!")
            return

        # Ask about accessibility
        accessible = input("\nRequire accessible route? (y/n): ").strip().lower() == 'y'

        try:
            route = self.service.calculate_route(
                start_building['building_id'],
                end_building['building_id'],
                accessible
            )

            self._display_route(route)

            # Save to history if logged in
            if self.auth.is_logged_in():
                user = self.auth.get_current_user()
                self.service.save_navigation_history(
                    user_id=user.username,
                    start_location=start_building['building_name'],
                    end_location=end_building['building_name'],
                    route_taken=f"{start_code} to {end_code}",
                    duration_minutes=route['estimated_time_minutes'],
                    accessibility_required=accessible
                )

        except ValueError as e:
            print(f"\nError: {e}")

    def _display_route(self, route):
        """Display route information."""
        print("\n" + "=" * 60)
        print("Route Information".center(60))
        print("=" * 60)

        print(f"\nFrom: {route['start_building']['building_name']}")
        print(f"To: {route['end_building']['building_name']}")
        print(f"\nDistance: {route['distance_description']}")
        print(f"Estimated Time: {route['estimated_time_minutes']} minutes")

        if route['is_accessible']:
            print("\n*** ACCESSIBLE ROUTE ***")

        print("\n--- Turn-by-Turn Directions ---")
        for direction in route['directions']:
            print(f"  {direction}")

        if route['accessibility_notes']:
            print("\n--- Accessibility Notes ---")
            for note in route['accessibility_notes']:
                print(f"  • {note}")

    def find_nearest(self):
        """Find nearest amenities."""
        print("\n" + "=" * 60)
        print("Find Nearest Amenity".center(60))
        print("=" * 60)

        print("\nWhat are you looking for?")
        print("[1] Restroom")
        print("[2] Printer/Computer Lab")
        print("[3] Study Space")
        print("[4] Coffee/Food")
        print("[5] ATM/Banking")
        print("[6] Medical Services")
        print("[7] Custom Search")
        print("[0] Back")

        choice = input("\nEnter your choice: ").strip()

        amenity_map = {
            "1": "Restroom",
            "2": "Computer",
            "3": "Study",
            "4": "Food",
            "5": "ATM",
            "6": "Medical"
        }

        location_type = None
        if choice == "7":
            location_type = input("Enter amenity type: ").strip()
        elif choice in amenity_map:
            location_type = amenity_map[choice]
        elif choice == "0":
            return
        else:
            print("\nInvalid choice.")
            return

        if not location_type:
            return

        # Get current location
        print("\nEnter your current location:")
        current_code = input("Building code (or press Enter for Library): ").strip().upper()

        if not current_code:
            current_code = "LIB"

        current_building = self.service.get_building(building_code=current_code)
        if not current_building:
            print("\nCurrent building not found.")
            return

        # Find nearest
        results = self.service.find_nearest(
            location_type,
            current_building['latitude'],
            current_building['longitude'],
            limit=5
        )

        if not results:
            print(f"\nNo {location_type} found nearby.")
            return

        print(f"\n--- Nearest {location_type} ({len(results)} results) ---\n")

        for i, result in enumerate(results, 1):
            if result.get('result_type') == 'building':
                print(f"{i}. {result['building_name']} ({result['building_code']})")
            else:
                print(f"{i}. {result['poi_name']}")
                if result.get('building_name'):
                    print(f"   Location: {result['building_name']}")
                if result.get('room_number'):
                    print(f"   Room: {result['room_number']}")

            print(f"   Distance: {result['distance_description']}")

            if result.get('operating_hours'):
                print(f"   Hours: {result['operating_hours']}")
            print()

    def view_points_of_interest(self):
        """View points of interest."""
        print("\n" + "=" * 60)
        print("Points of Interest".center(60))
        print("=" * 60)

        print("\n[1] View All POIs")
        print("[2] Filter by Type")
        print("[3] Filter by Building")
        print("[0] Back")

        choice = input("\nEnter your choice: ").strip()

        pois = []

        if choice == "1":
            pois = self.service.get_points_of_interest()

        elif choice == "2":
            print("\nPOI Types:")
            print("[1] Service")
            print("[2] Study Space")
            print("[3] Dining")
            print("[4] Athletic")
            print("[5] Retail")

            type_choice = input("\nSelect type: ").strip()
            type_map = {
                "1": "Service",
                "2": "Study Space",
                "3": "Dining",
                "4": "Athletic",
                "5": "Retail"
            }

            if type_choice in type_map:
                pois = self.service.get_points_of_interest(poi_type=type_map[type_choice])

        elif choice == "3":
            building_code = input("\nEnter building code: ").strip().upper()
            building = self.service.get_building(building_code=building_code)
            if building:
                pois = self.service.get_points_of_interest(
                    building_id=building['building_id']
                )
            else:
                print("\nBuilding not found.")
                return

        if not pois:
            print("\nNo points of interest found.")
            return

        print(f"\n{'POI Name':<30} {'Type':<20} {'Location':<20}")
        print("-" * 70)

        for poi in pois:
            location = poi.get('room_number', 'N/A')
            if poi.get('floor_number'):
                location = f"Floor {poi['floor_number']}, {location}"

            print(f"{poi['poi_name']:<30} "
                  f"{poi['poi_type']:<20} "
                  f"{location:<20}")

    def manage_favorites(self):
        """Manage favorite locations."""
        if not self.auth.is_logged_in():
            print("\nPlease log in to use favorites.")
            return

        user = self.auth.get_current_user()

        print("\n" + "=" * 60)
        print("My Favorite Locations".center(60))
        print("=" * 60)

        print("\n[1] View Favorites")
        print("[2] Add Favorite")
        print("[3] Remove Favorite")
        print("[0] Back")

        choice = input("\nEnter your choice: ").strip()

        if choice == "1":
            favorites = self.service.get_favorites(user.username)

            if not favorites:
                print("\nNo favorites saved.")
                return

            print(f"\n{'Nickname':<20} {'Location':<30} {'Type':<15}")
            print("-" * 65)

            for fav in favorites:
                nickname = fav.get('nickname', 'N/A')
                location = fav.get('location_name', 'N/A')
                loc_type = fav['location_type']

                print(f"{nickname:<20} {location:<30} {loc_type:<15}")

        elif choice == "2":
            print("\n[1] Add Building")
            print("[2] Add Point of Interest")

            add_choice = input("\nEnter your choice: ").strip()

            if add_choice == "1":
                code = input("Enter building code: ").strip().upper()
                building = self.service.get_building(building_code=code)

                if building:
                    nickname = input("Enter nickname (optional): ").strip()
                    self.service.add_favorite(
                        user.username,
                        'building',
                        building['building_id'],
                        nickname
                    )
                    print("\nBuilding added to favorites!")
                else:
                    print("\nBuilding not found.")

            elif add_choice == "2":
                search = input("Search for POI: ").strip()
                pois = self.service.search_points_of_interest(search)

                if not pois:
                    print("\nNo POIs found.")
                    return

                # Show options
                for i, poi in enumerate(pois[:10], 1):
                    print(f"[{i}] {poi['poi_name']} - {poi.get('building_name', 'N/A')}")

                poi_choice = input("\nSelect POI number: ").strip()
                try:
                    poi_idx = int(poi_choice) - 1
                    if 0 <= poi_idx < len(pois):
                        selected_poi = pois[poi_idx]
                        nickname = input("Enter nickname (optional): ").strip()
                        self.service.add_favorite(
                            user.username,
                            'poi',
                            selected_poi['poi_id'],
                            nickname
                        )
                        print("\nPOI added to favorites!")
                    else:
                        print("\nInvalid selection.")
                except ValueError:
                    print("\nInvalid input.")

        elif choice == "3":
            favorites = self.service.get_favorites(user.username)

            if not favorites:
                print("\nNo favorites to remove.")
                return

            for i, fav in enumerate(favorites, 1):
                nickname = fav.get('nickname', 'N/A')
                location = fav.get('location_name', 'N/A')
                print(f"[{i}] {nickname} - {location}")

            remove_choice = input("\nEnter number to remove: ").strip()
            try:
                remove_idx = int(remove_choice) - 1
                if 0 <= remove_idx < len(favorites):
                    self.service.remove_favorite(favorites[remove_idx]['favorite_id'])
                    print("\nFavorite removed!")
                else:
                    print("\nInvalid selection.")
            except ValueError:
                print("\nInvalid input.")

    def report_accessibility_issue(self):
        """Report an accessibility issue."""
        print("\n" + "=" * 60)
        print("Report Accessibility Issue".center(60))
        print("=" * 60)

        building_code = input("\nEnter building code: ").strip().upper()
        building = self.service.get_building(building_code=building_code)

        if not building:
            print("\nBuilding not found.")
            return

        print(f"\nReporting issue for: {building['building_name']}")

        print("\nIssue Type:")
        print("[1] Elevator not working")
        print("[2] Ramp blocked/damaged")
        print("[3] Automatic door malfunction")
        print("[4] Other accessibility issue")

        issue_type = input("\nSelect type: ").strip()
        description = input("Describe the issue: ").strip()

        if description:
            # In a real system, this would create a ticket
            print("\nThank you for your report!")
            print("Issue has been forwarded to facilities management.")
            print("Reference number: ACC-" + str(building['building_id']) + "-001")
        else:
            print("\nReport cancelled.")

    def view_campus_map(self):
        """Display a simple text-based campus map."""
        print("\n" + "=" * 60)
        print("Campus Map".center(60))
        print("=" * 60)

        buildings = self.service.get_all_buildings()

        # Create a simple grid representation
        print("\n    North Campus")
        print("    ╔══════════╗")

        # Group by rough coordinates
        north_buildings = [b for b in buildings if b['latitude'] > 40.713]
        central_buildings = [b for b in buildings if 40.712 <= b['latitude'] <= 40.713]
        south_buildings = [b for b in buildings if b['latitude'] < 40.712]

        print("    ║", end="")
        for b in north_buildings[:3]:
            print(f" [{b['building_code']}]", end="")
        print(" ║")

        print("    ╠══════════╣")
        print("    ║", end="")
        for b in central_buildings[:3]:
            print(f" [{b['building_code']}]", end="")
        print(" ║")

        print("    ╠══════════╣")
        print("    ║", end="")
        for b in south_buildings[:3]:
            print(f" [{b['building_code']}]", end="")
        print(" ║")

        print("    ╚══════════╝")
        print("    South Campus\n")

        print("Legend:")
        for building in buildings:
            print(f"  [{building['building_code']}] {building['building_name']}")


def main():
    """Main entry point for CLI."""
    cli = NavigationCLI()
    cli.display_menu()


if __name__ == '__main__':
    main()


# Alias for compatibility with main CLI
CampusNavigationCLI = NavigationCLI
