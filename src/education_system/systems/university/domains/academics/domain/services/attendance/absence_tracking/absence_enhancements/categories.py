"""Absence request categories and routing — #11."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Tuple

from .log import logger


# ===========================================================================
# RequestCategoryService — #11
# ===========================================================================

class RequestCategoryService:
    """Manage absence request categories + per-category routing."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def list(self) -> List[Tuple]:
        try:
            return self.conn.execute(
                """SELECT id, name, description, requires_evidence,
                          approval_route, auto_approve
                   FROM absence_request_categories
                   ORDER BY name""").fetchall()
        except sqlite3.Error:
            logger.exception("category list failed")
            return []

    def assign_to_request(self, request_id: int, category_id: int) -> None:
        try:
            self.conn.execute(
                "UPDATE absence_requests SET category_id=? WHERE id=?",
                (category_id, request_id))
            self.conn.commit()
        except sqlite3.Error:
            self.conn.rollback()
            logger.exception("category assign failed rid=%s", request_id)
            raise

    def route_for(self, request_id: int) -> Dict[str, Any]:
        try:
            row = self.conn.execute(
                """SELECT c.name, c.approval_route,
                          c.auto_approve, c.requires_evidence
                   FROM absence_requests r
                   LEFT JOIN absence_request_categories c
                     ON c.id = r.category_id
                   WHERE r.id = ?""", (request_id,)).fetchone()
        except sqlite3.Error:
            logger.exception("route_for failed rid=%s", request_id)
            return {}
        if not row:
            return {}
        name, route, auto, req_ev = row
        return {
            "category": name,
            "route": route or "instructor",
            "auto_approve": bool(auto),
            "requires_evidence": bool(req_ev),
        }


def list_categories(conn):
    return RequestCategoryService(conn).list()


def set_request_category(conn, request_id, category_id):
    RequestCategoryService(conn).assign_to_request(request_id, category_id)


def route_for_request(conn, request_id) -> Dict[str, Any]:
    return RequestCategoryService(conn).route_for(request_id)


__all__ = [
    "RequestCategoryService",
    "list_categories",
    "set_request_category",
    "route_for_request",
]
