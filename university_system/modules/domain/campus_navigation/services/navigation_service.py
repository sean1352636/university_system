"""
Campus Navigation Service

Provides interactive campus maps, accessible route planning, and location finding.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import json
import math

from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.utils.activity_logger import log_activity


class NavigationService:
    """Service for campus navigation and wayfinding."""

    def __init__(self):
        """Initialize the Campus Navigation Service."""
        self._ensure_tables_exist()

    def _ensure_tables_exist(self):
        """Create database tables if they don't exist."""
        with transaction() as conn:
            # Campus Buildings table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS campus_buildings (
                    building_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    building_code TEXT UNIQUE NOT NULL,
                    building_name TEXT NOT NULL,
                    building_type TEXT NOT NULL,
                    description TEXT,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    address TEXT,
                    floors INTEGER DEFAULT 1,
                    is_accessible BOOLEAN DEFAULT 1,
                    has_elevator BOOLEAN DEFAULT 0,
                    has_ramp BOOLEAN DEFAULT 0,
                    has_automatic_doors BOOLEAN DEFAULT 0,
                    operating_hours TEXT,
                    amenities TEXT,
                    image_url TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Points of Interest table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS points_of_interest (
                    poi_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    building_id INTEGER,
                    poi_name TEXT NOT NULL,
                    poi_type TEXT NOT NULL,
                    floor_number INTEGER,
                    room_number TEXT,
                    description TEXT,
                    latitude REAL,
                    longitude REAL,
                    is_accessible BOOLEAN DEFAULT 1,
                    operating_hours TEXT,
                    contact_info TEXT,
                    tags TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (building_id) REFERENCES campus_buildings(building_id) ON DELETE CASCADE
                )
            """)

            # Routes table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS campus_routes (
                    route_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    route_name TEXT NOT NULL,
                    start_location_id INTEGER NOT NULL,
                    end_location_id INTEGER NOT NULL,
                    route_type TEXT DEFAULT 'Walking',
                    is_accessible BOOLEAN DEFAULT 1,
                    distance_meters REAL NOT NULL,
                    estimated_time_minutes INTEGER NOT NULL,
                    waypoints TEXT,
                    description TEXT,
                    elevation_change REAL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (start_location_id) REFERENCES campus_buildings(building_id),
                    FOREIGN KEY (end_location_id) REFERENCES campus_buildings(building_id)
                )
            """)

            # Navigation History table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS navigation_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    start_location TEXT NOT NULL,
                    end_location TEXT NOT NULL,
                    route_taken TEXT,
                    duration_minutes INTEGER,
                    accessibility_required BOOLEAN DEFAULT 0,
                    navigation_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    rating INTEGER,
                    feedback TEXT
                )
            """)

            # User Favorites table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS navigation_favorites (
                    favorite_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    location_type TEXT NOT NULL,
                    location_id INTEGER NOT NULL,
                    nickname TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Initialize sample campus data
            self._initialize_sample_data(conn)

            log_activity('create', 'campus_navigation_tables',
                        details={'status': 'Campus Navigation tables created'})

    def _initialize_sample_data(self, conn):
        """Initialize sample campus buildings and points of interest."""
        # Check if data already exists
        existing = conn.execute(
            "SELECT COUNT(*) as count FROM campus_buildings"
        ).fetchone()

        if existing['count'] > 0:
            return

        # Sample buildings
        buildings = [
            ("MAIN", "Main Administration Building", "Administrative", "Central campus hub",
             40.7128, -74.0060, "100 Campus Drive", 4, 1, 1, 1, 1,
             "Mon-Fri: 8am-6pm", "WiFi,Restrooms,Cafe", None),
            ("LIB", "University Library", "Academic", "Main campus library",
             40.7130, -74.0058, "200 Campus Drive", 5, 1, 1, 1, 1,
             "Mon-Thu: 7am-11pm, Fri-Sat: 9am-9pm, Sun: 10am-10pm",
             "WiFi,Study Rooms,Computers,Cafe,Restrooms", None),
            ("SCI", "Science Building", "Academic", "Science labs and classrooms",
             40.7125, -74.0065, "300 Campus Drive", 3, 1, 1, 1, 0,
             "Mon-Fri: 7am-10pm, Sat: 9am-5pm", "WiFi,Labs,Restrooms", None),
            ("ENG", "Engineering Hall", "Academic", "Engineering departments",
             40.7132, -74.0070, "400 Campus Drive", 4, 1, 1, 1, 1,
             "Mon-Fri: 7am-10pm, Sat: 9am-5pm", "WiFi,Labs,Maker Space,Restrooms", None),
            ("GYM", "Recreation Center", "Athletic", "Sports and fitness facilities",
             40.7120, -74.0055, "500 Campus Drive", 2, 1, 1, 1, 1,
             "Mon-Fri: 6am-11pm, Sat-Sun: 8am-9pm",
             "Gym,Pool,Courts,Locker Rooms,Cafe", None),
            ("DORM1", "North Residence Hall", "Housing", "Student housing",
             40.7135, -74.0050, "600 Campus Drive", 6, 1, 1, 1, 1,
             "24/7", "Laundry,Study Lounges,Kitchen", None),
            ("DORM2", "South Residence Hall", "Housing", "Student housing",
             40.7115, -74.0062, "700 Campus Drive", 8, 1, 1, 1, 1,
             "24/7", "Laundry,Study Lounges,Kitchen", None),
            ("UNION", "Student Union", "Student Services", "Student activities center",
             40.7128, -74.0052, "800 Campus Drive", 3, 1, 1, 1, 1,
             "Mon-Fri: 7am-11pm, Sat-Sun: 9am-10pm",
             "Food Court,Game Room,Meeting Rooms,Bookstore", None),
            ("MED", "Health Center", "Medical", "Student health services",
             40.7122, -74.0048, "900 Campus Drive", 2, 1, 1, 1, 1,
             "Mon-Fri: 8am-5pm", "Pharmacy,Counseling,Medical Care", None),
            ("ART", "Arts Building", "Academic", "Art and music departments",
             40.7138, -74.0068, "1000 Campus Drive", 3, 1, 1, 1, 0,
             "Mon-Fri: 8am-10pm, Sat: 10am-6pm",
             "Studios,Gallery,Performance Hall,Practice Rooms", None),
        ]

        for building in buildings:
            conn.execute("""
                INSERT INTO campus_buildings
                (building_code, building_name, building_type, description,
                 latitude, longitude, address, floors, is_accessible,
                 has_elevator, has_ramp, has_automatic_doors,
                 operating_hours, amenities, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, building)

        # Sample points of interest
        pois = [
            # Library POIs
            (2, "Reference Desk", "Service", 1, "101", "Get research help", None, None, 1,
             "Mon-Thu: 8am-10pm", "reference@university.edu", "help,research"),
            (2, "Silent Study Area", "Study Space", 3, "301", "Quiet study zone", None, None, 1,
             "Mon-Thu: 7am-11pm", None, "quiet,study"),
            (2, "Group Study Rooms", "Study Space", 2, "200-210", "Reservable group rooms",
             None, None, 1, "Mon-Thu: 8am-10pm", "library@university.edu", "group,study"),

            # Student Union POIs
            (8, "Food Court", "Dining", 1, "Center", "Multiple food vendors", None, None, 1,
             "Mon-Fri: 7am-9pm", None, "food,dining"),
            (8, "Bookstore", "Retail", 1, "East Wing", "Textbooks and merchandise", None, None, 1,
             "Mon-Fri: 9am-6pm, Sat: 10am-4pm", "bookstore@university.edu", "books,shopping"),
            (8, "Career Services", "Service", 2, "201", "Career counseling and job search",
             None, None, 1, "Mon-Fri: 9am-5pm", "careers@university.edu", "jobs,career"),

            # Recreation Center POIs
            (5, "Fitness Center", "Athletic", 1, "Main Floor", "Cardio and weight equipment",
             None, None, 1, "Mon-Fri: 6am-11pm", None, "gym,fitness"),
            (5, "Swimming Pool", "Athletic", 1, "West Wing", "Olympic-size pool", None, None, 1,
             "Mon-Fri: 6am-9pm", None, "pool,swimming"),
            (5, "Basketball Courts", "Athletic", 2, "Upper Level", "Indoor basketball courts",
             None, None, 1, "Mon-Fri: 6am-11pm", None, "basketball,sports"),

            # Other buildings
            (9, "Counseling Services", "Service", 1, "110", "Mental health support", None, None, 1,
             "Mon-Fri: 8am-5pm", "counseling@university.edu", "health,counseling"),
            (9, "Pharmacy", "Service", 1, "105", "Student pharmacy", None, None, 1,
             "Mon-Fri: 9am-5pm", "pharmacy@university.edu", "pharmacy,health"),
        ]

        for poi in pois:
            conn.execute("""
                INSERT INTO points_of_interest
                (building_id, poi_name, poi_type, floor_number, room_number,
                 description, latitude, longitude, is_accessible,
                 operating_hours, contact_info, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, poi)

    # ========== Building Management ==========

    def get_all_buildings(self, building_type: Optional[str] = None) -> List[Dict]:
        """
        Get all campus buildings.

        Args:
            building_type: Filter by type (Academic, Housing, Athletic, etc.)

        Returns:
            List of building dictionaries
        """
        with get_connection() as conn:
            if building_type:
                buildings = conn.execute("""
                    SELECT * FROM campus_buildings
                    WHERE building_type = ?
                    ORDER BY building_name
                """, (building_type,)).fetchall()
            else:
                buildings = conn.execute("""
                    SELECT * FROM campus_buildings
                    ORDER BY building_name
                """).fetchall()

            return [dict(b) for b in buildings]

    def get_building(self, building_id: int = None,
                    building_code: str = None) -> Optional[Dict]:
        """Get building by ID or code."""
        with get_connection() as conn:
            if building_id:
                building = conn.execute("""
                    SELECT * FROM campus_buildings WHERE building_id = ?
                """, (building_id,)).fetchone()
            elif building_code:
                building = conn.execute("""
                    SELECT * FROM campus_buildings WHERE building_code = ?
                """, (building_code,)).fetchone()
            else:
                return None

            return dict(building) if building else None

    def search_buildings(self, search_term: str) -> List[Dict]:
        """Search buildings by name, code, or type."""
        with get_connection() as conn:
            buildings = conn.execute("""
                SELECT * FROM campus_buildings
                WHERE building_name LIKE ?
                   OR building_code LIKE ?
                   OR building_type LIKE ?
                   OR description LIKE ?
                ORDER BY building_name
            """, (f"%{search_term}%", f"%{search_term}%",
                  f"%{search_term}%", f"%{search_term}%")).fetchall()

            return [dict(b) for b in buildings]

    # ========== Points of Interest ==========

    def get_points_of_interest(self, building_id: Optional[int] = None,
                               poi_type: Optional[str] = None) -> List[Dict]:
        """Get points of interest, optionally filtered by building or type."""
        with get_connection() as conn:
            query = "SELECT * FROM points_of_interest WHERE 1=1"
            params = []

            if building_id:
                query += " AND building_id = ?"
                params.append(building_id)

            if poi_type:
                query += " AND poi_type = ?"
                params.append(poi_type)

            query += " ORDER BY poi_name"

            pois = conn.execute(query, params).fetchall()
            return [dict(p) for p in pois]

    def search_points_of_interest(self, search_term: str,
                                  tags: Optional[List[str]] = None) -> List[Dict]:
        """Search points of interest by name, type, or tags."""
        with get_connection() as conn:
            query = """
                SELECT poi.*, b.building_name, b.building_code
                FROM points_of_interest poi
                LEFT JOIN campus_buildings b ON poi.building_id = b.building_id
                WHERE poi.poi_name LIKE ?
                   OR poi.poi_type LIKE ?
                   OR poi.description LIKE ?
            """
            params = [f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"]

            if tags:
                for tag in tags:
                    query += " OR poi.tags LIKE ?"
                    params.append(f"%{tag}%")

            query += " ORDER BY poi.poi_name"

            pois = conn.execute(query, params).fetchall()
            return [dict(p) for p in pois]

    def find_nearest(self, location_type: str, latitude: float,
                    longitude: float, limit: int = 5) -> List[Dict]:
        """
        Find nearest locations of a specific type.

        Args:
            location_type: Type of location (building type or POI type)
            latitude: User's latitude
            longitude: User's longitude
            limit: Maximum number of results

        Returns:
            List of locations sorted by distance
        """
        with get_connection() as conn:
            # Search buildings
            buildings = conn.execute("""
                SELECT *, 'building' as result_type
                FROM campus_buildings
                WHERE building_type LIKE ?
            """, (f"%{location_type}%",)).fetchall()

            # Search POIs
            pois = conn.execute("""
                SELECT poi.*, b.building_name, b.latitude, b.longitude,
                       'poi' as result_type
                FROM points_of_interest poi
                LEFT JOIN campus_buildings b ON poi.building_id = b.building_id
                WHERE poi.poi_type LIKE ?
            """, (f"%{location_type}%",)).fetchall()

            # Calculate distances
            results = []

            for building in buildings:
                distance = self._calculate_distance(
                    latitude, longitude,
                    building['latitude'], building['longitude']
                )
                result = dict(building)
                result['distance_meters'] = distance
                result['distance_description'] = self._format_distance(distance)
                results.append(result)

            for poi in pois:
                # Use building coordinates if POI doesn't have its own
                # POI table has latitude/longitude columns that reference the building
                # Fall back to building coordinates from the JOIN
                poi_lat = poi['latitude']
                poi_lon = poi['longitude']

                # Skip POIs without valid coordinates
                if poi_lat is None or poi_lon is None:
                    continue

                distance = self._calculate_distance(
                    latitude, longitude, poi_lat, poi_lon
                )
                result = dict(poi)
                result['distance_meters'] = distance
                result['distance_description'] = self._format_distance(distance)
                results.append(result)

            # Sort by distance and limit
            results.sort(key=lambda x: x['distance_meters'])

            log_activity('search', 'nearest_locations',
                        details={'type': location_type, 'results': len(results[:limit])})

            return results[:limit]

    def _calculate_distance(self, lat1: float, lon1: float,
                           lat2: float, lon2: float) -> float:
        """Calculate distance between two coordinates using Haversine formula."""
        # Earth radius in meters
        R = 6371000

        # Convert to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        # Haversine formula
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))

        return R * c

    def _format_distance(self, meters: float) -> str:
        """Format distance in human-readable form."""
        if meters < 1000:
            return f"{int(meters)}m"
        else:
            km = meters / 1000
            return f"{km:.1f}km"

    # ========== Route Planning ==========

    def calculate_route(self, start_location_id: int, end_location_id: int,
                       require_accessible: bool = False) -> Dict:
        """
        Calculate route between two locations.

        Args:
            start_location_id: Starting building ID
            end_location_id: Destination building ID
            require_accessible: Whether route must be accessible

        Returns:
            Route information dictionary
        """
        with get_connection() as conn:
            # Get building locations
            start = conn.execute("""
                SELECT * FROM campus_buildings WHERE building_id = ?
            """, (start_location_id,)).fetchone()

            end = conn.execute("""
                SELECT * FROM campus_buildings WHERE building_id = ?
            """, (end_location_id,)).fetchone()

            if not start or not end:
                raise ValueError("Building not found")

            # Check if accessible route is possible
            if require_accessible:
                if not start['is_accessible'] or not end['is_accessible']:
                    raise ValueError("One or both buildings are not accessible")

            # Calculate distance
            distance = self._calculate_distance(
                start['latitude'], start['longitude'],
                end['latitude'], end['longitude']
            )

            # Estimate walking time (average walking speed: 1.4 m/s)
            time_minutes = int(distance / 1.4 / 60)

            # Create simple waypoints (direct path for now)
            waypoints = [
                {
                    'latitude': start['latitude'],
                    'longitude': start['longitude'],
                    'description': f"Start at {start['building_name']}"
                },
                {
                    'latitude': end['latitude'],
                    'longitude': end['longitude'],
                    'description': f"Arrive at {end['building_name']}"
                }
            ]

            # Add accessibility notes
            accessibility_notes = []
            if require_accessible:
                if start['has_elevator']:
                    accessibility_notes.append(f"{start['building_name']}: Elevator available")
                if start['has_ramp']:
                    accessibility_notes.append(f"{start['building_name']}: Ramp entrance available")
                if end['has_elevator']:
                    accessibility_notes.append(f"{end['building_name']}: Elevator available")
                if end['has_ramp']:
                    accessibility_notes.append(f"{end['building_name']}: Ramp entrance available")

            route = {
                'start_building': dict(start),
                'end_building': dict(end),
                'distance_meters': distance,
                'distance_description': self._format_distance(distance),
                'estimated_time_minutes': time_minutes,
                'is_accessible': require_accessible,
                'waypoints': waypoints,
                'accessibility_notes': accessibility_notes,
                'directions': self._generate_directions(start, end, require_accessible)
            }

            # Save route to database
            with transaction() as conn:
                conn.execute("""
                    INSERT INTO campus_routes
                    (route_name, start_location_id, end_location_id,
                     is_accessible, distance_meters, estimated_time_minutes, waypoints)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (f"{start['building_code']} to {end['building_code']}",
                      start_location_id, end_location_id, require_accessible,
                      distance, time_minutes, json.dumps(waypoints)))

            log_activity('create', 'campus_route',
                        details={'from': start['building_code'],
                                'to': end['building_code'],
                                'accessible': require_accessible})

            return route

    def _generate_directions(self, start: Dict, end: Dict,
                            accessible: bool) -> List[str]:
        """Generate turn-by-turn directions."""
        directions = []

        # Start
        if accessible and start['has_ramp']:
            directions.append(f"1. Exit {start['building_name']} via accessible ramp entrance")
        else:
            directions.append(f"1. Exit {start['building_name']}")

        # Simple cardinal direction
        lat_diff = end['latitude'] - start['latitude']
        lon_diff = end['longitude'] - start['longitude']

        if abs(lat_diff) > abs(lon_diff):
            direction = "north" if lat_diff > 0 else "south"
        else:
            direction = "east" if lon_diff > 0 else "west"

        directions.append(f"2. Head {direction} along campus pathways")
        directions.append(f"3. Continue for approximately {self._format_distance(self._calculate_distance(start['latitude'], start['longitude'], end['latitude'], end['longitude']))}")

        # Arrival
        if accessible and end['has_ramp']:
            directions.append(f"4. Arrive at {end['building_name']} - use accessible ramp entrance")
        else:
            directions.append(f"4. Arrive at {end['building_name']}")

        if accessible and end['has_elevator']:
            directions.append(f"5. Elevator available inside {end['building_name']}")

        return directions

    # ========== Navigation History ==========

    def save_navigation_history(self, user_id: str, start_location: str,
                               end_location: str, route_taken: str,
                               duration_minutes: int,
                               accessibility_required: bool = False) -> int:
        """Save navigation history for analytics."""
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO navigation_history
                (user_id, start_location, end_location, route_taken,
                 duration_minutes, accessibility_required)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, start_location, end_location, route_taken,
                  duration_minutes, accessibility_required))

            return cursor.lastrowid

    def rate_navigation(self, history_id: int, rating: int,
                       feedback: str = "") -> bool:
        """Rate a navigation experience (1-5 stars)."""
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")

        with transaction() as conn:
            conn.execute("""
                UPDATE navigation_history
                SET rating = ?, feedback = ?
                WHERE history_id = ?
            """, (rating, feedback, history_id))

            log_activity('update', 'navigation_rating',
                        details={'history_id': history_id, 'rating': rating})

        return True

    # ========== Favorites ==========

    def add_favorite(self, user_id: str, location_type: str,
                    location_id: int, nickname: str = "") -> int:
        """Add a location to user's favorites."""
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO navigation_favorites
                (user_id, location_type, location_id, nickname)
                VALUES (?, ?, ?, ?)
            """, (user_id, location_type, location_id, nickname))

            favorite_id = cursor.lastrowid

            log_activity('create', 'navigation_favorite',
                        details={'favorite_id': favorite_id, 'user_id': user_id, 'type': location_type})

            return favorite_id

    def get_favorites(self, user_id: str) -> List[Dict]:
        """Get all favorites for a user."""
        with get_connection() as conn:
            favorites = conn.execute("""
                SELECT nf.*,
                    CASE
                        WHEN nf.location_type = 'building' THEN b.building_name
                        WHEN nf.location_type = 'poi' THEN p.poi_name
                    END as location_name
                FROM navigation_favorites nf
                LEFT JOIN campus_buildings b ON nf.location_type = 'building'
                    AND nf.location_id = b.building_id
                LEFT JOIN points_of_interest p ON nf.location_type = 'poi'
                    AND nf.location_id = p.poi_id
                WHERE nf.user_id = ?
                ORDER BY nf.created_at DESC
            """, (user_id,)).fetchall()

            return [dict(f) for f in favorites]

    def remove_favorite(self, favorite_id: int) -> bool:
        """Remove a favorite location."""
        with transaction() as conn:
            conn.execute("""
                DELETE FROM navigation_favorites WHERE favorite_id = ?
            """, (favorite_id,))

            log_activity('delete', 'navigation_favorite', details={'favorite_id': favorite_id})

        return True

    # ========== Analytics ==========

    def get_popular_routes(self, limit: int = 10) -> List[Dict]:
        """Get most popular navigation routes."""
        with get_connection() as conn:
            routes = conn.execute("""
                SELECT
                    start_location,
                    end_location,
                    COUNT(*) as usage_count,
                    AVG(duration_minutes) as avg_duration,
                    AVG(rating) as avg_rating
                FROM navigation_history
                WHERE rating IS NOT NULL
                GROUP BY start_location, end_location
                ORDER BY usage_count DESC
                LIMIT ?
            """, (limit,)).fetchall()

            return [dict(r) for r in routes]

    def get_building_stats(self, building_id: int) -> Dict:
        """Get statistics for a building."""
        with get_connection() as conn:
            # Navigation stats
            nav_stats = conn.execute("""
                SELECT
                    COUNT(*) as total_navigations,
                    AVG(duration_minutes) as avg_visit_duration
                FROM navigation_history nh
                JOIN campus_buildings cb ON nh.end_location = cb.building_name
                WHERE cb.building_id = ?
            """, (building_id,)).fetchone()

            # POI count
            poi_count = conn.execute("""
                SELECT COUNT(*) as count
                FROM points_of_interest
                WHERE building_id = ?
            """, (building_id,)).fetchone()

            return {
                'navigation': dict(nav_stats) if nav_stats else {},
                'points_of_interest': poi_count['count'] if poi_count else 0
            }
