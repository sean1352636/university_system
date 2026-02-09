#!/usr/bin/env python3
"""
Campus Navigation Module - Usage Examples

This file demonstrates how to use the Campus Navigation module's various features.
"""

from university_system.modules.domain.campus_navigation import NavigationService


def example_basic_search():
    """Example: Basic building search and retrieval."""
    print("\n" + "=" * 60)
    print("Example 1: Basic Building Search")
    print("=" * 60)

    service = NavigationService()

    # Get all buildings
    buildings = service.get_all_buildings()
    print(f"\nTotal buildings on campus: {len(buildings)}")

    # Search for a specific building
    results = service.search_buildings("Library")
    if results:
        library = results[0]
        print(f"\nFound: {library['building_name']}")
        print(f"Code: {library['building_code']}")
        print(f"Type: {library['building_type']}")
        print(f"Address: {library['address']}")
        print(f"Floors: {library['floors']}")
        print(f"Accessible: {'Yes' if library['is_accessible'] else 'No'}")


def example_route_planning():
    """Example: Calculate route between two buildings."""
    print("\n" + "=" * 60)
    print("Example 2: Route Planning")
    print("=" * 60)

    service = NavigationService()

    # Get start and end buildings
    library = service.get_building(building_code="LIB")
    union = service.get_building(building_code="UNION")

    if library and union:
        # Calculate standard route
        route = service.calculate_route(
            library['building_id'],
            union['building_id'],
            require_accessible=False
        )

        print(f"\nRoute from {library['building_name']} to {union['building_name']}")
        print(f"Distance: {route['distance_description']}")
        print(f"Estimated Time: {route['estimated_time_minutes']} minutes")
        print(f"\nDirections:")
        for i, direction in enumerate(route['directions'], 1):
            print(f"  {direction}")

        # Calculate accessible route
        print("\n--- Accessible Route ---")
        accessible_route = service.calculate_route(
            library['building_id'],
            union['building_id'],
            require_accessible=True
        )

        if accessible_route['accessibility_notes']:
            print("Accessibility Features:")
            for note in accessible_route['accessibility_notes']:
                print(f"  • {note}")


def example_find_nearest():
    """Example: Find nearest amenities."""
    print("\n" + "=" * 60)
    print("Example 3: Find Nearest Amenities")
    print("=" * 60)

    service = NavigationService()

    # Get current location (e.g., Library)
    library = service.get_building(building_code="LIB")

    if library:
        print(f"\nCurrent location: {library['building_name']}")

        # Find nearest study spaces
        print("\nFinding nearest study spaces...")
        study_spaces = service.find_nearest(
            'Study',
            library['latitude'],
            library['longitude'],
            limit=3
        )

        if study_spaces:
            print(f"Found {len(study_spaces)} study spaces:")
            for space in study_spaces:
                name = space.get('poi_name') or space.get('building_name', 'Unknown')
                print(f"  • {name}")
                print(f"    Distance: {space['distance_description']}")
                if space.get('operating_hours'):
                    print(f"    Hours: {space['operating_hours']}")
        else:
            print("No study spaces found nearby.")

        # Find nearest food options
        print("\nFinding nearest food options...")
        food = service.find_nearest(
            'Food',
            library['latitude'],
            library['longitude'],
            limit=3
        )

        if food:
            print(f"Found {len(food)} food options:")
            for option in food:
                name = option.get('poi_name') or option.get('building_name', 'Unknown')
                print(f"  • {name}")
                print(f"    Distance: {option['distance_description']}")


def example_points_of_interest():
    """Example: Explore points of interest."""
    print("\n" + "=" * 60)
    print("Example 4: Points of Interest")
    print("=" * 60)

    service = NavigationService()

    # Get POIs in a specific building
    library = service.get_building(building_code="LIB")

    if library:
        print(f"\nPoints of interest in {library['building_name']}:")

        pois = service.get_points_of_interest(building_id=library['building_id'])

        for poi in pois:
            print(f"\n  {poi['poi_name']} ({poi['poi_type']})")
            if poi.get('floor_number'):
                print(f"    Floor: {poi['floor_number']}")
            if poi.get('room_number'):
                print(f"    Room: {poi['room_number']}")
            if poi.get('description'):
                print(f"    {poi['description']}")
            if poi.get('operating_hours'):
                print(f"    Hours: {poi['operating_hours']}")

    # Search for specific POI types
    print("\n\nSearching for all dining options:")
    dining_pois = service.get_points_of_interest(poi_type="Dining")

    for poi in dining_pois:
        print(f"  • {poi['poi_name']}")
        if poi.get('operating_hours'):
            print(f"    Hours: {poi['operating_hours']}")


def example_building_filters():
    """Example: Filter buildings by type."""
    print("\n" + "=" * 60)
    print("Example 5: Filter Buildings by Type")
    print("=" * 60)

    service = NavigationService()

    # Get academic buildings
    academic = service.get_all_buildings(building_type="Academic")
    print(f"\nAcademic Buildings ({len(academic)}):")
    for building in academic:
        print(f"  • {building['building_code']}: {building['building_name']}")

    # Get housing
    housing = service.get_all_buildings(building_type="Housing")
    print(f"\nHousing ({len(housing)}):")
    for building in housing:
        print(f"  • {building['building_code']}: {building['building_name']}")
        print(f"    Floors: {building['floors']}")
        print(f"    Accessible: {'Yes' if building['is_accessible'] else 'No'}")

    # Get athletic facilities
    athletic = service.get_all_buildings(building_type="Athletic")
    print(f"\nAthletic Facilities ({len(athletic)}):")
    for building in athletic:
        print(f"  • {building['building_code']}: {building['building_name']}")
        if building.get('amenities'):
            print(f"    Amenities: {building['amenities']}")


def example_accessibility_features():
    """Example: Find accessible buildings and features."""
    print("\n" + "=" * 60)
    print("Example 6: Accessibility Features")
    print("=" * 60)

    service = NavigationService()

    buildings = service.get_all_buildings()

    # Buildings with elevators
    print("\nBuildings with Elevators:")
    elevator_buildings = [b for b in buildings if b['has_elevator']]
    for building in elevator_buildings:
        print(f"  • {building['building_code']}: {building['building_name']}")

    # Buildings with wheelchair ramps
    print("\nBuildings with Wheelchair Ramps:")
    ramp_buildings = [b for b in buildings if b['has_ramp']]
    for building in ramp_buildings:
        print(f"  • {building['building_code']}: {building['building_name']}")

    # Buildings with automatic doors
    print("\nBuildings with Automatic Doors:")
    auto_door_buildings = [b for b in buildings if b['has_automatic_doors']]
    for building in auto_door_buildings:
        print(f"  • {building['building_code']}: {building['building_name']}")

    # Fully accessible buildings (all features)
    print("\nFully Accessible Buildings (all features):")
    fully_accessible = [
        b for b in buildings
        if b['is_accessible'] and b['has_elevator'] and
        b['has_ramp'] and b['has_automatic_doors']
    ]
    for building in fully_accessible:
        print(f"  • {building['building_code']}: {building['building_name']}")


def example_building_stats():
    """Example: View building statistics."""
    print("\n" + "=" * 60)
    print("Example 7: Building Statistics")
    print("=" * 60)

    service = NavigationService()

    # Get stats for Library
    library = service.get_building(building_code="LIB")

    if library:
        print(f"\nStatistics for {library['building_name']}:")

        stats = service.get_building_stats(library['building_id'])

        print(f"\nPoints of Interest: {stats['points_of_interest']}")

        if stats['navigation']:
            nav_stats = stats['navigation']
            if nav_stats.get('total_navigations'):
                print(f"Total Navigations: {nav_stats['total_navigations']}")
            if nav_stats.get('avg_visit_duration'):
                print(f"Average Visit Duration: {nav_stats['avg_visit_duration']:.1f} minutes")


def run_all_examples():
    """Run all example functions."""
    print("\n" + "=" * 60)
    print("Campus Navigation Module - Usage Examples")
    print("=" * 60)

    example_basic_search()
    example_route_planning()
    example_find_nearest()
    example_points_of_interest()
    example_building_filters()
    example_accessibility_features()
    example_building_stats()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60 + "\n")


if __name__ == '__main__':
    run_all_examples()
