"""Library adapter — reading lists & recommendations for a module/student.

The library service files (``services/library/reading_lists.py`` and
``recommendations.py``) bundle SQL with interactive ``input()`` menus,
so the GUI cannot call them directly. This module exposes a single
data-only entry point.
"""

from __future__ import annotations

import logging

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core.paths import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


def fetch_module_resources(
    module_code: str,
    *,
    student_id: str | int | None = None,
    list_limit: int = 5,
    item_limit: int = 25,
    rec_limit: int = 5,
) -> dict:
    """Return reading-list items + personalised recommendations for a module.

    Reading lists are matched by ``reading_lists.category`` equalling
    either the module code or the module name (the existing schema has
    no direct module_id FK). Recommendations are pulled from
    ``book_recommendations`` for the student when supplied.

    Returned shape:
        {
            "lists":           [ {list_id, name, description, item_count}, ... ],
            "items":           [ {item_id, list_id, list_name, book_id, title,
                                   author, notes, order_index}, ... ],
            "recommendations": [ {book_id, title, author, confidence_score,
                                   recommendation_type}, ... ],
        }
    """
    out = {"lists": [], "items": [], "recommendations": []}
    if not module_code:
        return out

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            tables = {
                r[0]
                for r in cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }

            module_name = None
            if "modules" in tables:
                row = cur.execute(
                    "SELECT module_name FROM modules WHERE module_code = ?",
                    (module_code,),
                ).fetchone()
                if row:
                    module_name = row["module_name"]

            categories = [module_code]
            if module_name:
                categories.append(module_name)

            if "reading_lists" in tables:
                placeholders = ",".join("?" * len(categories))
                cur.execute(
                    f"""
                    SELECT rl.list_id, rl.name, rl.description,
                           COUNT(rli.item_id) AS item_count
                    FROM reading_lists rl
                    LEFT JOIN reading_list_items rli ON rl.list_id = rli.list_id
                    WHERE rl.category IN ({placeholders})
                    GROUP BY rl.list_id
                    ORDER BY rl.created_date DESC
                    LIMIT ?
                    """,
                    (*categories, list_limit),
                )
                out["lists"] = [dict(r) for r in cur.fetchall()]

                if out["lists"] and "reading_list_items" in tables:
                    list_ids = [row["list_id"] for row in out["lists"]]
                    placeholders_li = ",".join("?" * len(list_ids))
                    book_join = (
                        "LEFT JOIN books b ON b.book_id = rli.book_id"
                        if "books" in tables
                        else ""
                    )
                    title_col = "b.title" if "books" in tables else "rli.book_id"
                    author_col = "b.author" if "books" in tables else "''"
                    cur.execute(
                        f"""
                        SELECT rli.item_id, rli.list_id, rl.name AS list_name,
                               rli.book_id, {title_col} AS title,
                               {author_col} AS author,
                               rli.notes, rli.order_index
                        FROM reading_list_items rli
                        JOIN reading_lists rl ON rl.list_id = rli.list_id
                        {book_join}
                        WHERE rli.list_id IN ({placeholders_li})
                        ORDER BY rli.list_id, rli.order_index
                        LIMIT ?
                        """,
                        (*list_ids, item_limit),
                    )
                    out["items"] = [dict(r) for r in cur.fetchall()]

            if student_id and "book_recommendations" in tables:
                book_join = (
                    "LEFT JOIN books b ON b.book_id = br.book_id"
                    if "books" in tables
                    else ""
                )
                title_col = "b.title" if "books" in tables else "br.book_id"
                author_col = "b.author" if "books" in tables else "''"
                cur.execute(
                    f"""
                    SELECT br.book_id, {title_col} AS title, {author_col} AS author,
                           br.confidence_score, br.recommendation_type
                    FROM book_recommendations br
                    {book_join}
                    WHERE br.user_id = ?
                      AND COALESCE(br.status, 'pending') != 'dismissed'
                    ORDER BY br.confidence_score DESC, br.generated_date DESC
                    LIMIT ?
                    """,
                    (str(student_id), rec_limit),
                )
                out["recommendations"] = [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception as exc:
        logger.warning(
            "fetch_module_resources failed for module=%s student=%s: %s",
            module_code, student_id, exc,
        )
    return out
