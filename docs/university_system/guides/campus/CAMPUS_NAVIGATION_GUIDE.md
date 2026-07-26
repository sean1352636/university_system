# Campus Navigation & Wayfinding Guide

This guide covers the campus navigation system including building directory, route planning, points of interest, accessibility features, and wayfinding within the University Management System.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Building Directory](#building-directory)
- [Points of Interest](#points-of-interest)
- [Route Planning](#route-planning)
- [Find Nearest Location](#find-nearest-location)
- [Favorites & History](#favorites--history)
- [Accessibility Features](#accessibility-features)
- [Analytics](#analytics)
- [GUI Interface](#gui-interface)
- [CLI Interface](#cli-interface)
- [Sample Data](#sample-data)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## Overview

The Campus Navigation module provides building directory search, route planning with step-by-step directions, proximity-based location discovery using the Haversine formula, accessibility-aware routing, user favorites, navigation history, and analytics on popular routes.

**Key files:**
- Navigation Service: `modules/domain/campus_navigation/services/navigation_service.py`
- Navigation GUI: `modules/domain/campus_navigation/gui/navigation_gui.py`
- Navigation CLI: `modules/domain/campus_navigation/cli/navigation_cli.py`
- Examples: `modules/domain/campus_navigation/examples.py`
- Public API: `modules/domain/campus_navigation/__init__.py`

## Architecture

```
┌──────────────────────────────────────────────────┐
│           Campus Navigation System                │
├──────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌──────────┐  ┌────────────┐  │
│  │   GUI       │  │   CLI    │  │   API      │  │
│  │  (Tkinter)  │  │  (Menu)  │  │  (Service) │  │
│  └──────┬──────┘  └────┬─────┘  └─────┬──────┘  │
│         │              │               │          │
│         ▼              ▼               ▼          │
│  ┌──────────────────────────────────────────┐    │
│  │          NavigationService                │    │
│  ├──────────────────────────────────────────┤    │
│  │ Buildings │ POIs │ Routes │ Favorites     │    │
│  │ Search    │ Find │ Plan   │ History       │    │
│  │ Filter    │ Near │ Direct │ Analytics     │    │
│  └──────────────────────────────────────────┘    │
│         │                                         │
│         ▼                                         │
│  ┌──────────────────────────────────────────┐    │
│  │  Database (student_records.db)            │    │
│  │  campus_buildings | points_of_interest    │    │
│  │  campus_routes | navigation_history       │    │
│  │  navigation_favorites                     │    │
│  └──────────────────────────────────────────┘    │
└──────────────────────────────────────────────────┘
```

## Building Directory

### Viewing All Buildings

```python
from university_system.modules.domain.campus_navigation.services.navigation_service import (
    NavigationService
)

service = NavigationService()

# Get all buildings
buildings = service.get_all_buildings()

# Filter by type
academic = service.get_all_buildings(building_type='Academic')
housing = service.get_all_buildings(building_type='Housing')
```

### Building Types

| Type | Examples |
|------|----------|
| Academic | Lecture halls, labs, classrooms |
| Administrative | Admissions, registrar, offices |
| Housing | Dormitories, residence halls |
| Athletic | Gymnasium, recreation center, fields |
| Student Services | Student union, career center |
| Medical | Health center, counseling |
| Dining | Cafeterias, food courts |

### Searching Buildings

```python
# Full-text search across name, code, type, and description
results = service.search_buildings('library')
results = service.search_buildings('engineering')
results = service.search_buildings('dorm')
```

### Getting Building Details

```python
# By building ID
building = service.get_building(building_id=1)

# By building code
building = service.get_building(code='LIB')

# Building details include:
# - building_code, building_name, building_type
# - description, address
# - latitude, longitude
# - floors, operating_hours
# - amenities (WiFi, Restrooms, Cafe, etc.)
# - accessibility features (elevator, ramp, automatic doors)
# - image_url
```

### Building Database Schema

| Column | Type | Description |
|--------|------|-------------|
| building_id | INTEGER (PK) | Auto-incrementing ID |
| building_code | TEXT (UNIQUE) | Short code (e.g., "LIB", "SCI") |
| building_name | TEXT | Full building name |
| building_type | TEXT | Category (Academic, Housing, etc.) |
| description | TEXT | Building description |
| latitude | REAL | GPS latitude coordinate |
| longitude | REAL | GPS longitude coordinate |
| address | TEXT | Street address |
| floors | INTEGER | Number of floors (default: 1) |
| is_accessible | BOOLEAN | General accessibility status |
| has_elevator | BOOLEAN | Elevator availability |
| has_ramp | BOOLEAN | Wheelchair ramp availability |
| has_automatic_doors | BOOLEAN | Automatic door availability |
| operating_hours | TEXT | Hours of operation |
| amenities | TEXT | Comma-separated amenity list |
| image_url | TEXT | Building photo URL |
| created_at | TIMESTAMP | Record creation date |
| updated_at | TIMESTAMP | Last update date |

## Points of Interest

### Viewing POIs

```python
# Get POIs in a specific building
pois = service.get_points_of_interest(building_id=2)

# Search POIs across entire campus
results = service.search_points_of_interest('food court')
results = service.search_points_of_interest('study')
```

### POI Types

| Type | Examples |
|------|----------|
| Service | Reference desk, help desk, advising |
| Dining | Food court, cafe, vending |
| Study Space | Library, quiet rooms, group study |
| Recreation | Gym, pool, game room |
| Office | Department offices, administrative |
| Retail | Bookstore, convenience store |

### POI Database Schema

| Column | Type | Description |
|--------|------|-------------|
| poi_id | INTEGER (PK) | Auto-incrementing ID |
| building_id | INTEGER (FK) | Parent building |
| poi_name | TEXT | Name of the point of interest |
| poi_type | TEXT | Category (Service, Dining, etc.) |
| floor_number | INTEGER | Floor within the building |
| room_number | TEXT | Room identifier |
| description | TEXT | Description of the POI |
| latitude | REAL | Optional GPS coordinate |
| longitude | REAL | Optional GPS coordinate |
| is_accessible | BOOLEAN | Accessibility status |
| operating_hours | TEXT | Hours of operation |
| contact_info | TEXT | Contact email/phone |
| tags | TEXT | Comma-separated searchable tags |
| created_at | TIMESTAMP | Record creation date |

## Route Planning

### Calculating a Route

```python
route = service.calculate_route(
    start_id=1,           # Starting building ID
    end_id=2,             # Destination building ID
    accessibility=False   # Set True for accessible routes
)

# Route includes:
# - distance_meters (calculated via Haversine formula)
# - estimated_time_minutes
# - route_type (Walking, Accessible)
# - waypoints (JSON array of coordinates)
# - elevation_change
# - step-by-step directions
```

### Step-by-Step Directions

```python
directions = service._generate_directions(
    start=building_a,
    end=building_b,
    route_type='Walking'
)

# Example output:
# 1. Exit Main Administration Building heading east
# 2. Walk along University Avenue for approximately 200 meters
# 3. Turn right at the intersection near the fountain
# 4. University Library will be on your left
# 5. Enter through the main entrance
```

### Accessible Routes

When `accessibility=True`, the route planner:
- Prioritizes buildings with elevators and ramps
- Avoids stairs and uneven terrain
- Selects routes with automatic doors
- May choose longer but fully accessible paths

### Route Database Schema

| Column | Type | Description |
|--------|------|-------------|
| route_id | INTEGER (PK) | Auto-incrementing ID |
| route_name | TEXT | Route display name |
| start_location_id | INTEGER (FK) | Starting building |
| end_location_id | INTEGER (FK) | Destination building |
| route_type | TEXT | Walking or Accessible |
| is_accessible | BOOLEAN | Accessibility rating |
| distance_meters | REAL | Haversine-calculated distance |
| estimated_time_minutes | INTEGER | Walking time estimate |
| waypoints | TEXT | JSON array of coordinates |
| description | TEXT | Route description |
| elevation_change | REAL | Elevation difference (meters) |
| created_at | TIMESTAMP | Record creation date |

### Distance Calculation

The system uses the **Haversine formula** for accurate distance calculation between GPS coordinates:

```
a = sin²(Δlat/2) + cos(lat1) × cos(lat2) × sin²(Δlon/2)
c = 2 × atan2(√a, √(1-a))
d = R × c
```

Where R = 6,371,000 meters (Earth's radius).

Distances are formatted for readability:
- Under 1,000m: displayed in meters (e.g., "450 m")
- Over 1,000m: displayed in kilometers (e.g., "1.2 km")

## Find Nearest Location

### Proximity Search

Find the closest locations of a given type from your current position:

```python
# Find the nearest dining locations
nearest = service.find_nearest(
    location_type='Dining',
    lat=40.7128,            # Current latitude
    lon=-74.0060,           # Current longitude
    limit=5                 # Number of results (default: 5)
)

for location in nearest:
    print(f"{location['name']} - {location['distance']}")
```

### Location Types for Proximity Search

Any building type can be used for proximity search:
- Academic, Administrative, Housing, Athletic
- Student Services, Medical, Dining
- Or search by specific building name/code

## Favorites & History

### Managing Favorites

```python
# Add a location to favorites
service.add_favorite(
    user_id='S-12345',
    location_type='building',   # building or poi
    location_id=2,
    nickname='My Library'
)

# Get user's favorites
favorites = service.get_favorites(user_id='S-12345')

# Remove a favorite
service.remove_favorite(favorite_id=1)
```

### Navigation History

```python
# History is automatically saved after route navigation
service.save_navigation_history(
    user_id='S-12345',
    start_location='Main Building',
    end_location='Library',
    duration_minutes=8,
    feedback=None
)

# Rate a navigation experience
service.rate_navigation(
    history_id=1,
    rating=4,           # 1-5 stars
    feedback='Clear directions, easy to follow.'
)
```

### Favorites Database Schema

| Column | Type | Description |
|--------|------|-------------|
| favorite_id | INTEGER (PK) | Auto-incrementing ID |
| user_id | TEXT | User who saved the favorite |
| location_type | TEXT | "building" or "poi" |
| location_id | INTEGER | Building or POI ID |
| nickname | TEXT | Custom name (e.g., "My Class") |
| created_at | TIMESTAMP | When favorited |

### History Database Schema

| Column | Type | Description |
|--------|------|-------------|
| history_id | INTEGER (PK) | Auto-incrementing ID |
| user_id | TEXT | User who navigated |
| start_location | TEXT | Starting point |
| end_location | TEXT | Destination |
| route_taken | TEXT | Route details |
| duration_minutes | INTEGER | Actual navigation time |
| accessibility_required | BOOLEAN | Accessible route used |
| navigation_date | TIMESTAMP | When navigation occurred |
| rating | INTEGER | User rating (1-5) |
| feedback | TEXT | User comments |

## Accessibility Features

### Building Accessibility Data

Each building tracks:

| Feature | Description |
|---------|-------------|
| is_accessible | General accessibility rating |
| has_elevator | Elevator available for multi-floor access |
| has_ramp | Wheelchair ramp at entrances |
| has_automatic_doors | Powered door openers |

### Accessible Route Planning

```python
# Plan an accessible route
route = service.calculate_route(
    start_id=1,
    end_id=6,
    accessibility=True
)
# Routes avoid stairs, prefer elevators, and use accessible entrances
```

### Accessibility Issue Reporting

Via the CLI interface, users can report accessibility issues:

```python
# CLI: Report accessibility issues for buildings or routes
cli.report_accessibility_issue()
# Prompts for: building, issue type, description
```

### POI Accessibility

Each Point of Interest also has an `is_accessible` flag indicating whether it can be reached without stairs or barriers.

## Analytics

### Popular Routes

```python
# Get the most frequently used routes
popular = service.get_popular_routes(limit=10)

for route in popular:
    print(f"{route['start']} → {route['end']}: {route['usage_count']} times")
```

### Building Statistics

```python
# Get usage metrics for a building
stats = service.get_building_stats(building_id=2)
# Returns: visit count, average navigation time, user ratings,
#          most common origin/destination pairings
```

## GUI Interface

The `NavigationGUI` provides a Tkinter interface with a split-panel layout:

### Left Panel (Controls)

| Tab | Features |
|-----|----------|
| **Directory** | Building list with search and type filter |
| **Route** | Start/end selection, route planning, directions display |
| **Nearest** | Amenity type selector, proximity results |
| **Favorites** | Saved locations with add/remove |

### Right Panel (Display)

- Building details panel
- Route visualization
- Map display
- Directions text

### GUI Features

- **Search bar** - Real-time building search with regex support
- **Type filter** - Radio buttons to filter by building type
- **Building details popup** - Full information on click
- **Route planner** - Select start/end, view step-by-step directions
- **Route visualization** - Visual route display
- **Favorites management** - Add/remove favorite locations
- **Nearby amenities** - Find closest facilities by type
- **Building hours** - View operating hours
- **Amenities list** - View available amenities per building
- **Route rating** - Rate navigation experience via dialog

## CLI Interface

```
Campus Navigation
1. Building Directory
2. Search Locations
3. Get Directions
4. Find Nearest
5. View Points of Interest
6. Manage Favorites
7. Report Accessibility Issue
8. View Campus Map
0. Return to Main Menu
```

### CLI Features

Each menu option provides interactive prompts:

1. **Building Directory** - View all buildings or filter by type
2. **Search Locations** - Search buildings and POIs by keyword
3. **Get Directions** - Interactive route planner with step-by-step output
4. **Find Nearest** - Enter coordinates and location type for proximity search
5. **View Points of Interest** - Browse POIs by building
6. **Manage Favorites** - Add, view, and remove favorite locations
7. **Report Accessibility Issue** - Submit accessibility concerns
8. **View Campus Map** - Text-based campus map visualization

## Sample Data

The system initializes with 10 sample buildings:

| Code | Name | Type | Floors |
|------|------|------|--------|
| MAIN | Main Administration Building | Administrative | - |
| LIB | University Library | Academic | 5 |
| SCI | Science Building | Academic | 3 |
| ENG | Engineering Hall | Academic | 4 |
| GYM | Recreation Center | Athletic | - |
| DORM1 | North Residence Hall | Housing | 6 |
| DORM2 | South Residence Hall | Housing | 8 |
| UNION | Student Union | Student Services | 3 |
| MED | Health Center | Medical | 2 |
| ART | Arts Building | Academic | 3 |

### Sample Points of Interest

| Building | POI | Type | Room |
|----------|-----|------|------|
| Library | Reference Desk | Service | Lobby |
| Library | Silent Study Area | Study Space | 3rd Floor |
| Library | Group Study Rooms | Study Space | 2nd Floor |
| Union | Food Court | Dining | Center |
| Union | Bookstore | Retail | 1st Floor |
| Union | Career Services | Service | 200-210 |

Each POI includes operating hours, contact info, and searchable tags.

## Configuration

### Database

Navigation data is stored in the main `student_records.db` database. Tables are created on first service initialization with sample data.

### Integration Points

| System | Usage |
|--------|-------|
| Authentication | `get_auth()` for user identity |
| Activity Logging | `log_activity()` for navigation actions |
| Database | `get_connection()` for data access |
| i18n | `get_translation()` for multi-language support |

### Customizing Sample Data

To add buildings or POIs, use the service directly or modify the `_initialize_sample_data()` method in `NavigationService`. Buildings require at minimum a code, name, type, and GPS coordinates.

## Troubleshooting

### Buildings Not Loading

1. Verify the database tables exist (`campus_buildings`)
2. Run the service initialization to create tables and sample data
3. Check database connection using `get_connection()`

### Route Calculation Returns No Results

1. Ensure both start and end buildings have valid coordinates (latitude/longitude)
2. Verify building IDs exist in the database
3. Check that a route record exists between the buildings, or that the system can generate one

### Distance Seems Incorrect

1. Verify GPS coordinates are accurate for both buildings
2. The Haversine formula calculates straight-line distance, not walking path
3. Actual walking distance may be longer due to pathways and obstacles

### Favorites Not Saving

1. Ensure the user is authenticated (`get_auth()` returns a valid user)
2. Verify the location_type is "building" or "poi"
3. Check that the location_id exists in the corresponding table

### Accessibility Route Not Available

1. Not all buildings may have accessibility data populated
2. Check `is_accessible`, `has_elevator`, `has_ramp` flags
3. Report missing accessibility data via the accessibility issue reporter

### GUI Map Not Displaying

1. The map visualization requires the display panel to be active
2. Resize the window if panels are collapsed
3. Check for Tkinter rendering issues on your platform
