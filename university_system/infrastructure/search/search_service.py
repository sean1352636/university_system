"""
Unified search service with Elasticsearch and SQLite FTS fallback
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from university_system.infrastructure.search.elasticsearch_service import (
    get_elasticsearch_service,
    ELASTICSEARCH_AVAILABLE
)
from university_system.infrastructure.search.fallback_search import FallbackSearchService
from university_system.core.sql_safety import validate_table_name

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Search result item"""
    id: str
    score: float
    source: Dict[str, Any]
    highlights: Optional[Dict[str, List[str]]] = None


@dataclass
class SearchQuery:
    """Search query configuration"""
    query: str
    entity_type: str = "students"
    filters: Optional[Dict[str, Any]] = None
    size: int = 10
    offset: int = 0
    sort: Optional[List[Dict[str, str]]] = None
    include_facets: bool = False
    facet_fields: Optional[List[str]] = None


class SearchService:
    """
    Unified search service with automatic fallback

    Attempts to use Elasticsearch for advanced search features.
    Falls back to SQLite FTS when Elasticsearch unavailable.

    Features:
    - Full-text search across all entities
    - Fuzzy matching (Elasticsearch only)
    - Faceted search
    - Real-time indexing
    - Autocomplete suggestions
    - Search analytics
    """

    def __init__(self, elasticsearch_hosts: Optional[List[str]] = None):
        """
        Initialize search service

        Args:
            elasticsearch_hosts: List of Elasticsearch hosts (optional)
        """
        self.es_service = None
        self.fallback_service = FallbackSearchService()
        self.using_elasticsearch = False

        # Try to initialize Elasticsearch
        if ELASTICSEARCH_AVAILABLE:
            self.es_service = get_elasticsearch_service(elasticsearch_hosts)
            if self.es_service and self.es_service.connected:
                self.using_elasticsearch = True
                logger.info("Search service initialized with Elasticsearch")
            else:
                logger.warning("Elasticsearch unavailable, using SQLite FTS fallback")
        else:
            logger.info("Search service initialized with SQLite FTS fallback")

    def search(
        self,
        query: str,
        entity_type: str = "students",
        filters: Optional[Dict[str, Any]] = None,
        size: int = 10,
        offset: int = 0,
        sort: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Search documents

        Args:
            query: Search query string
            entity_type: Entity type to search (students, courses, staff, etc.)
            filters: Filter criteria
            size: Number of results
            offset: Pagination offset
            sort: Sort criteria

        Returns:
            Search results with hits and metadata
        """
        if self.using_elasticsearch:
            result = self.es_service.search(
                index=entity_type,
                query=query,
                filters=filters,
                size=size,
                from_=offset,
                sort=sort
            )
        else:
            result = self.fallback_service.search(
                index=entity_type,
                query=query,
                filters=filters,
                size=size,
                from_=offset
            )

        # Convert to SearchResult objects
        hits = []
        for hit in result.get('hits', {}).get('hits', []):
            hits.append(SearchResult(
                id=hit['_id'],
                score=hit.get('_score', 0.0),
                source=hit['_source'],
                highlights=hit.get('highlight')
            ))

        return {
            'results': hits,
            'total': result.get('hits', {}).get('total', {}).get('value', 0),
            'query': query,
            'entity_type': entity_type,
            'using_elasticsearch': self.using_elasticsearch
        }

    def index_document(
        self,
        entity_type: str,
        doc_id: str,
        document: Dict[str, Any]
    ) -> bool:
        """
        Index a document for search

        Args:
            entity_type: Entity type (students, courses, etc.)
            doc_id: Document ID
            document: Document data

        Returns:
            True if successful
        """
        # Index in both services for redundancy
        success = True

        if self.using_elasticsearch:
            success = self.es_service.index_document(entity_type, doc_id, document)

        # Always index in fallback for redundancy
        fallback_success = self.fallback_service.index_document(entity_type, doc_id, document)

        return success or fallback_success

    def bulk_index(
        self,
        entity_type: str,
        documents: List[Dict[str, Any]],
        id_field: str = 'id'
    ) -> Dict[str, int]:
        """
        Bulk index multiple documents

        Args:
            entity_type: Entity type
            documents: List of documents
            id_field: Field to use as document ID

        Returns:
            Success and error counts
        """
        if self.using_elasticsearch:
            return self.es_service.bulk_index(entity_type, documents, id_field)
        else:
            # Fallback doesn't have bulk operation, index one by one
            success_count = 0
            for doc in documents:
                doc_id = doc.get(id_field)
                if doc_id and self.fallback_service.index_document(entity_type, doc_id, doc):
                    success_count += 1

            return {
                'success': success_count,
                'errors': len(documents) - success_count
            }

    def delete_document(self, entity_type: str, doc_id: str) -> bool:
        """Delete a document from search index"""
        success = True

        if self.using_elasticsearch:
            success = self.es_service.delete_document(entity_type, doc_id)

        fallback_success = self.fallback_service.delete_document(entity_type, doc_id)

        return success or fallback_success

    def autocomplete(
        self,
        entity_type: str,
        field: str,
        prefix: str,
        size: int = 10
    ) -> List[str]:
        """
        Get autocomplete suggestions

        Args:
            entity_type: Entity type
            field: Field to autocomplete
            prefix: Text prefix
            size: Number of suggestions

        Returns:
            List of suggestions
        """
        if self.using_elasticsearch:
            return self.es_service.autocomplete(entity_type, field, prefix, size)
        else:
            # Fallback: simple prefix search
            return self._fallback_autocomplete(entity_type, field, prefix, size)

    def _fallback_autocomplete(
        self,
        entity_type: str,
        field: str,
        prefix: str,
        size: int
    ) -> List[str]:
        """Fallback autocomplete using simple search"""
        result = self.fallback_service.search(entity_type, prefix, size=size)
        suggestions = []

        for hit in result.get('hits', {}).get('hits', []):
            value = hit.get('_source', {}).get(field)
            if value and value not in suggestions:
                suggestions.append(value)

        return suggestions[:size]

    def faceted_search(
        self,
        entity_type: str,
        query: str,
        facets: List[str],
        filters: Optional[Dict[str, Any]] = None,
        size: int = 10
    ) -> Dict[str, Any]:
        """
        Faceted search with aggregations

        Args:
            entity_type: Entity type
            query: Search query
            facets: Fields to aggregate
            filters: Filter criteria
            size: Number of results

        Returns:
            Search results with facet aggregations
        """
        if self.using_elasticsearch:
            return self.es_service.faceted_search(entity_type, query, facets, filters, size)
        else:
            # Fallback: just return regular search
            # (facet aggregation not supported in fallback)
            return self.fallback_service.search(entity_type, query, filters, size)

    def count(self, entity_type: str, query: Optional[str] = None) -> int:
        """Count documents matching query"""
        if self.using_elasticsearch:
            return self.es_service.count(entity_type, query)
        else:
            return self.fallback_service.count(entity_type, query)

    def reindex_all(self, entity_type: str) -> Dict[str, int]:
        """
        Reindex all documents of a given type

        Args:
            entity_type: Entity type to reindex

        Returns:
            Success and error counts
        """
        from university_system.infrastructure.database.db import get_connection

        # Map entity types to tables
        table_map = {
            'students': ('students', 'student_id'),
            'courses': ('courses', 'course_id'),
            'staff': ('staff_members', 'staff_id'),
            'events': ('campus_events', 'event_id')
        }

        if entity_type not in table_map:
            logger.error(f"Unknown entity type: {entity_type}")
            return {'success': 0, 'errors': 0}

        table, id_field = table_map[entity_type]

        try:
            with get_connection() as conn:
                safe_tbl = validate_table_name(table, conn=conn)
                cursor = conn.execute("SELECT * FROM [" + safe_tbl + "]")
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()

            documents = []
            for row in rows:
                doc = dict(zip(columns, row))
                documents.append(doc)

            result = self.bulk_index(entity_type, documents, id_field)
            logger.info(
                f"Reindexed {entity_type}: "
                f"{result['success']} success, {result['errors']} errors"
            )

            return result

        except Exception as e:
            logger.error(f"Error reindexing {entity_type}: {e}")
            return {'success': 0, 'errors': 0}


# Singleton instance
_search_service: Optional[SearchService] = None


def get_search_service(elasticsearch_hosts: Optional[List[str]] = None) -> SearchService:
    """
    Get the global search service instance

    Args:
        elasticsearch_hosts: Elasticsearch hosts (optional)

    Returns:
        SearchService instance
    """
    global _search_service
    if _search_service is None:
        _search_service = SearchService(elasticsearch_hosts)
    return _search_service
