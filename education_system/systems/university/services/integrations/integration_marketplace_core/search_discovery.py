"""Search & Discovery Manager and CLI functions"""

from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.services.integrations.integration_marketplace_core._imports import re, Any, Dict, List, get_connection


class SearchDiscoveryManager:
    """Manages search and discovery operations for integrations"""

    @staticmethod
    def search_catalog(query: str, highlight: bool = True) -> List[Dict[str, Any]]:
        """Full-text search across integration names, providers, and descriptions with highlighting"""
        with get_connection() as conn:
            cursor = conn.cursor()
            search_pattern = f"%{escape_like(query)}%"
            cursor.execute('''
                SELECT integration_id, integration_name, provider_name, description,
                       category, integration_type, version, rating, install_count
                FROM integration_catalog
                WHERE is_active = 1 AND (
                    integration_name LIKE ? OR
                    provider_name LIKE ? OR
                    description LIKE ?
                )
                ORDER BY rating DESC, install_count DESC
            ''', (search_pattern, search_pattern, search_pattern))

            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if highlight and query:
                    # Add highlighting markers
                    for field in ['integration_name', 'provider_name', 'description']:
                        if result.get(field):
                            result[f'{field}_highlighted'] = re.sub(
                                f'({re.escape(query)})',
                                r'**\1**',
                                result[field],
                                flags=re.IGNORECASE
                            )
                results.append(result)
            return results

    @staticmethod
    def filter_by_rating(min_rating: float) -> List[Dict[str, Any]]:
        """Filter catalog by minimum star rating threshold"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM integration_catalog
                WHERE is_active = 1 AND rating >= ?
                ORDER BY rating DESC, install_count DESC
            ''', (min_rating,))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def filter_by_compatibility(system_version: str) -> List[Dict[str, Any]]:
        """Show only integrations compatible with current system version"""
        with get_connection() as conn:
            cursor = conn.cursor()
            # Parse major.minor from version
            major_minor = '.'.join(system_version.split('.')[:2])
            cursor.execute('''
                SELECT * FROM integration_catalog
                WHERE is_active = 1 AND (
                    min_version IS NULL OR min_version <= ? OR
                    min_version LIKE ?
                )
                ORDER BY rating DESC
            ''', (system_version, f"{major_minor}%"))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def find_similar_integrations(integration_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Suggest similar integrations based on selected one's category/features"""
        with get_connection() as conn:
            cursor = conn.cursor()
            # Get the source integration's category and type
            cursor.execute('''
                SELECT category, integration_type FROM integration_catalog
                WHERE integration_id = ?
            ''', (integration_id,))
            source = cursor.fetchone()

            if not source:
                return []

            cursor.execute('''
                SELECT * FROM integration_catalog
                WHERE is_active = 1 AND integration_id != ?
                    AND (category = ? OR integration_type = ?)
                ORDER BY
                    CASE WHEN category = ? AND integration_type = ? THEN 0
                         WHEN category = ? THEN 1
                         ELSE 2 END,
                    rating DESC
                LIMIT ?
            ''', (integration_id, source['category'], source['integration_type'],
                  source['category'], source['integration_type'], source['category'], limit))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def search_sync_logs(start_date: str = None, end_date: str = None,
                        status: str = None, error_contains: str = None) -> List[Dict[str, Any]]:
        """Search logs by date range, status, or error message content"""
        with get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM integration_sync_logs WHERE 1=1"
            params = []

            if start_date:
                query += " AND sync_start_time >= ?"
                params.append(start_date)
            if end_date:
                query += " AND sync_start_time <= ?"
                params.append(end_date)
            if status:
                query += " AND sync_status = ?"
                params.append(status)
            if error_contains:
                query += " AND error_details LIKE ?"
                params.append(f"%{escape_like(error_contains)}%")

            query += " ORDER BY sync_start_time DESC LIMIT 500"
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def advanced_filter(filters: Dict[str, Any], logic: str = 'AND') -> List[Dict[str, Any]]:
        """Multi-criteria filter with AND/OR logic"""
        with get_connection() as conn:
            cursor = conn.cursor()
            conditions = []
            params = []

            if filters.get('category'):
                conditions.append("category = ?")
                params.append(filters['category'])
            if filters.get('integration_type'):
                conditions.append("integration_type = ?")
                params.append(filters['integration_type'])
            if filters.get('min_rating'):
                conditions.append("rating >= ?")
                params.append(filters['min_rating'])
            if filters.get('is_official') is not None:
                conditions.append("is_official = ?")
                params.append(1 if filters['is_official'] else 0)
            if filters.get('provider_name'):
                conditions.append("provider_name LIKE ?")
                params.append(f"%{escape_like(filters['provider_name'])}%")
            if filters.get('min_installs'):
                conditions.append("install_count >= ?")
                params.append(filters['min_installs'])

            if not conditions:
                conditions = ["1=1"]

            # Validate logic operator to prevent injection
            safe_logic = logic.upper() if logic.upper() in ('AND', 'OR') else 'AND'
            joiner = " " + safe_logic + " "
            query = "SELECT * FROM integration_catalog WHERE is_active = 1 AND (" + joiner.join(conditions) + ") ORDER BY rating DESC"
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]


# =============================================================================
# CLI FUNCTIONS
# =============================================================================

def search_catalog():
    """Full-text search across integration names, providers, and descriptions with highlighting"""
    print("\n" + "="*50)
    print("      SEARCH INTEGRATION CATALOG")
    print("="*50)

    query = input("Enter search term: ").strip()
    if not query:
        print("No search term provided.")
        return

    results = SearchDiscoveryManager.search_catalog(query, highlight=True)

    if not results:
        print(f"\nNo integrations found matching '{query}'")
        return

    print(f"\nFound {len(results)} integration(s):\n")
    for i, r in enumerate(results, 1):
        name = r.get('integration_name_highlighted', r.get('integration_name', 'N/A'))
        provider = r.get('provider_name_highlighted', r.get('provider_name', 'N/A'))
        desc = r.get('description_highlighted', r.get('description', ''))[:80]
        rating = r.get('rating', 0)
        installs = r.get('install_count', 0)
        print(f"{i}. {name} by {provider}")
        print(f"   Rating: {'*' * int(rating)} ({rating:.1f}) | Installs: {installs}")
        print(f"   {desc}...")
        print()


def filter_by_rating():
    """Filter catalog by minimum star rating threshold"""
    print("\n" + "="*50)
    print("      FILTER BY RATING")
    print("="*50)

    try:
        min_rating = float(input("Enter minimum rating (0-5): ").strip())
        if min_rating < 0 or min_rating > 5:
            print("Rating must be between 0 and 5.")
            return
    except ValueError:
        print("Invalid rating value.")
        return

    results = SearchDiscoveryManager.filter_by_rating(min_rating)

    if not results:
        print(f"\nNo integrations found with rating >= {min_rating}")
        return

    print(f"\nFound {len(results)} integration(s) with rating >= {min_rating}:\n")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r.get('integration_name')} - Rating: {r.get('rating', 0):.1f} | Installs: {r.get('install_count', 0)}")


def filter_by_compatibility():
    """Show only integrations compatible with current system version"""
    print("\n" + "="*50)
    print("      FILTER BY COMPATIBILITY")
    print("="*50)

    system_version = input("Enter system version (e.g., 5.0.0): ").strip() or "5.0.0"

    results = SearchDiscoveryManager.filter_by_compatibility(system_version)

    if not results:
        print(f"\nNo integrations compatible with version {system_version}")
        return

    print(f"\nFound {len(results)} integration(s) compatible with v{system_version}:\n")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r.get('integration_name')} v{r.get('version', '1.0')} by {r.get('provider_name')}")


def find_similar_integrations():
    """Suggest similar integrations based on selected one's category/features"""
    print("\n" + "="*50)
    print("      FIND SIMILAR INTEGRATIONS")
    print("="*50)

    try:
        integration_id = int(input("Enter integration ID to find similar: ").strip())
    except ValueError:
        print("Invalid integration ID.")
        return

    limit = input("Max results (default 5): ").strip()
    limit = int(limit) if limit.isdigit() else 5

    results = SearchDiscoveryManager.find_similar_integrations(integration_id, limit)

    if not results:
        print(f"\nNo similar integrations found for ID {integration_id}")
        return

    print(f"\nFound {len(results)} similar integration(s):\n")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r.get('integration_name')} - {r.get('category')} | {r.get('integration_type')}")
        print(f"   Rating: {r.get('rating', 0):.1f} | Installs: {r.get('install_count', 0)}")


def search_sync_logs():
    """Search logs by date range, status, or error message content"""
    print("\n" + "="*50)
    print("      SEARCH SYNC LOGS")
    print("="*50)

    start_date = input("Start date (YYYY-MM-DD, or blank): ").strip() or None
    end_date = input("End date (YYYY-MM-DD, or blank): ").strip() or None
    status = input("Status filter (success/failed/running, or blank): ").strip() or None
    error_contains = input("Error message contains (or blank): ").strip() or None

    results = SearchDiscoveryManager.search_sync_logs(start_date, end_date, status, error_contains)

    if not results:
        print("\nNo sync logs found matching criteria.")
        return

    print(f"\nFound {len(results)} log(s):\n")
    for log in results[:20]:  # Limit display
        print(f"Log #{log.get('log_id')} | Install: {log.get('install_id')} | Status: {log.get('sync_status')}")
        print(f"  Time: {log.get('sync_start_time')} | Records: {log.get('records_synced', 0)} | Errors: {log.get('errors_encountered', 0)}")
        if log.get('error_details'):
            print(f"  Error: {log.get('error_details')[:100]}...")
        print()

    if len(results) > 20:
        print(f"... and {len(results) - 20} more logs")


def advanced_filter_dialog():
    """Multi-criteria filter dialog with AND/OR logic"""
    print("\n" + "="*50)
    print("      ADVANCED FILTER")
    print("="*50)

    filters = {}

    category = input("Category (or blank): ").strip()
    if category:
        filters['category'] = category

    integration_type = input("Type (API/Webhook/File, or blank): ").strip()
    if integration_type:
        filters['integration_type'] = integration_type

    min_rating = input("Minimum rating (or blank): ").strip()
    if min_rating:
        try:
            filters['min_rating'] = float(min_rating)
        except ValueError:
            pass

    is_official = input("Official only? (y/n/blank): ").strip().lower()
    if is_official == 'y':
        filters['is_official'] = True
    elif is_official == 'n':
        filters['is_official'] = False

    provider = input("Provider name contains (or blank): ").strip()
    if provider:
        filters['provider_name'] = provider

    min_installs = input("Minimum installs (or blank): ").strip()
    if min_installs:
        try:
            filters['min_installs'] = int(min_installs)
        except ValueError:
            pass

    logic = input("Logic (AND/OR, default AND): ").strip().upper() or 'AND'

    results = SearchDiscoveryManager.advanced_filter(filters, logic)

    if not results:
        print("\nNo integrations found matching criteria.")
        return

    print(f"\nFound {len(results)} integration(s):\n")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r.get('integration_name')} by {r.get('provider_name')}")
        print(f"   Category: {r.get('category')} | Type: {r.get('integration_type')} | Rating: {r.get('rating', 0):.1f}")
