"""
Advanced Search Infrastructure

Provides comprehensive search capabilities for the university system including:
- Full-text search across all entities
- Elasticsearch integration with SQLite fallback
- Real-time index updates
- Autocomplete and suggestions
- Faceted search (filtering by multiple criteria)
- Search analytics and tracking
- Advanced query syntax

Supports searching across:
- Students (name, email, major, courses)
- Courses (code, name, description, instructor)
- Staff (name, email, department, position)
- Faculty (name, email, department, courses)
- Research (title, abstract, authors)
- Events (title, description, location, date)

Usage:
    from education_system.university_system.infrastructure.search import get_search_service

    search = get_search_service()
    results = search.search("computer science", entity_type="students")
"""

from education_system.university_system.infrastructure.search.search_service import (
    SearchService,
    get_search_service,
    SearchResult,
    SearchQuery,
)

from education_system.university_system.infrastructure.search.autocomplete import (
    AutocompleteService,
    get_autocomplete_service,
)

from education_system.university_system.infrastructure.search.analytics import (
    SearchAnalytics,
    get_search_analytics,
)

from education_system.university_system.infrastructure.search.indexer import (
    SearchIndexer,
    get_search_indexer,
)

__all__ = [
    # Core search
    'SearchService',
    'get_search_service',
    'SearchResult',
    'SearchQuery',

    # Autocomplete
    'AutocompleteService',
    'get_autocomplete_service',

    # Analytics
    'SearchAnalytics',
    'get_search_analytics',

    # Indexing
    'SearchIndexer',
    'get_search_indexer',
]
