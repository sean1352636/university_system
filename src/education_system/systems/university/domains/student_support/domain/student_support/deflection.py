"""Suggest help articles before a ticket is raised, and count what it saves.

:func:`suggest` searches every published self-help source — Student
Support's ``kb_articles``, ``faqs`` and ``support_resources`` and the
Helpdesk's ``knowledge_base`` — and ranks the matches by plain keyword
counts (title hits weigh most, then summary / keywords, then body; a
little extra for articles people found helpful).

The form that shows suggestions records the visit in ``search_analytics``
(``search_type`` 'deflection'): :func:`start` when suggestions are shown,
:func:`viewed` when the student opens one (``clicked_result_id``), and
:func:`finish` when they submit a ticket or leave. A visit where the student
read an article and did not submit is a deflection (``search_criteria``
outcome 'deflected'); the reports count them.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
from typing import Optional

from education_system.systems.university.domains.student_support.domain.student_support import (
    auth as _auth,
    store,
)
from education_system.systems.university.infrastructure.sql_safety import escape_like

logger = logging.getLogger(__name__)

SEARCH_TYPE = 'deflection'
OUTCOMES = ('deflected', 'submitted', 'abandoned')
_STOP = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
    'from', 'this', 'that', 'these', 'those', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
    'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'can', 'not', 'my',
    'me', 'i', 'im', 'you', 'your', 'it', 'its', 'how', 'what', 'when', 'where', 'why', 'who',
    'please', 'help', 'need', 'get', 'got', 'there', 'their', 'they', 'any', 'about', 'just',
}

# source -> (table, id, title, summary-ish, body, keywords, published filter, popularity)
_SOURCES = {
    'kb': ('kb_articles', 'article_id', 'title', 'summary', 'content', 'search_keywords',
           'is_published = 1', 'COALESCE(helpful_votes, 0) - COALESCE(not_helpful_votes, 0)'),
    'faq': ('faqs', 'faq_id', 'question', 'NULL', 'answer', 'tags',
            "COALESCE(status, 'published') = 'published'",
            'COALESCE(helpful_votes, 0) - COALESCE(not_helpful_votes, 0)'),
    'resource': ('support_resources', 'resource_id', 'title', 'NULL', 'description', 'tags',
                 'COALESCE(requires_auth, 0) = 0', 'COALESCE(access_count, 0) / 50'),
    'helpdesk_kb': ('knowledge_base', 'article_id', 'title', 'NULL', 'content', 'search_keywords',
                    "status = 'published'",
                    'COALESCE(helpful_votes, 0) - COALESCE(unhelpful_votes, 0)'),
}
_VIEW_COLUMN = {'kb': 'view_count', 'faq': 'view_count', 'resource': 'access_count',
                'helpdesk_kb': 'views'}


def keywords(text, limit: int = 12) -> list:
    """The words of ``text`` worth searching for (no stop words, no repeats)."""
    words = re.findall(r"[a-z0-9]+", str(text or '').lower())
    out = []
    for w in words:
        if len(w) > 2 and w not in _STOP and w not in out:
            out.append(w)
    return out[:limit]


def _table_columns(conn, table) -> set:
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}  # nosec B608


def _candidates(conn, source, words) -> list:
    table, key, title, summary, body, kw, published, popularity = _SOURCES[source]
    cols = _table_columns(conn, table)
    if not cols:
        return []
    if 'status' not in cols and 'status' in published:
        published = '1=1'
    if 'requires_auth' not in cols and 'requires_auth' in published:
        published = '1=1'
    if kw not in cols:
        kw = 'NULL'
    if summary != 'NULL' and summary not in cols:
        summary = 'NULL'
    if any(c not in cols for c in ('not_helpful_votes', 'unhelpful_votes', 'helpful_votes',
                                   'access_count') if c in popularity):
        popularity = '0'
    likes, params = [], []
    for w in words:
        term = f"%{escape_like(w)}%"
        likes.append(f"({title} LIKE ? ESCAPE '\\' OR {body} LIKE ? ESCAPE '\\'"
                     + (f" OR {kw} LIKE ? ESCAPE '\\'" if kw != 'NULL' else '') + ")")
        params += [term, term] + ([term] if kw != 'NULL' else [])
    # Every name above comes from _SOURCES; only the search terms are bound.
    sql = (f"SELECT {key}, {title}, {summary}, {body}, {kw}, {popularity} FROM {table} "  # nosec B608
           f"WHERE {published} AND ({' OR '.join(likes)}) LIMIT 200")
    return conn.execute(sql, params).fetchall()


def _score(words, title, summary, body, kw) -> float:
    title, summary, body, kw = (str(x or '').lower() for x in (title, summary, body, kw))
    score = 0.0
    for w in words:
        score += 3 * title.count(w) + 2 * (summary.count(w) + kw.count(w)) + min(body.count(w), 5)
    matched = sum(1 for w in words if w in title or w in summary or w in body or w in kw)
    return score * (matched / max(len(words), 1))


def suggest(text, limit: int = 5) -> list:
    """Ranked self-help matches for ``text`` from both knowledge bases:
    ``[{'key', 'source', 'id', 'title', 'snippet', 'score'}]``."""
    words = keywords(text)
    if not words:
        return []
    limit = max(1, min(int(limit or 5), 20))
    found = []
    with store.reading() as conn:
        for source in _SOURCES:
            try:
                rows = _candidates(conn, source, words)
            except Exception:
                logger.debug("No %s to search", source, exc_info=True)
                continue
            for ref, title, summary, body, kw, popularity in rows:
                score = _score(words, title, summary, body, kw)
                if score <= 0:
                    continue
                score += max(min(float(popularity or 0), 10), -10) * 0.1
                snippet = str(summary or body or '').strip().replace('\n', ' ')
                found.append({'key': f"{source}:{ref}", 'source': source, 'id': ref,
                              'title': str(title or ''), 'snippet': snippet[:200],
                              'score': round(score, 2)})
    found.sort(key=lambda f: (-f['score'], f['title']))
    return found[:limit]


# ── recording a visit ────────────────────────────────────────────────────


def _now() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def start(actor, text, suggestions) -> Optional[int]:
    """Record that ``suggestions`` were shown for ``text``; returns the visit id."""
    user = _auth.require_auth(actor)
    shown = [s['key'] for s in suggestions or []]
    with store.writing() as conn:
        cur = conn.execute(
            "INSERT INTO search_analytics (user_id, search_query, search_type, results_count, "
            "search_datetime, session_id, search_criteria) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user['username'], str(text or '')[:500], SEARCH_TYPE, len(shown), _now(),
             str(user.get('session_id') or ''), json.dumps({'shown': shown, 'outcome': None})))
        return cur.lastrowid


def _visit(conn, user, visit_id):
    row = conn.execute("SELECT search_id, user_id, clicked_result_id, search_criteria "
                       "FROM search_analytics WHERE search_id = ? AND search_type = ?",
                       (int(visit_id), SEARCH_TYPE)).fetchone()
    if row is None:
        raise ValueError(f"No suggestion visit {visit_id}")
    if str(row[1]) != str(user['username']):
        raise PermissionError("That suggestion visit is someone else's")
    try:
        criteria = json.loads(row[3] or '{}')
    except (TypeError, ValueError):
        criteria = {}
    return row, criteria


def viewed(actor, visit_id, key) -> bool:
    """The student opened suggestion ``key`` ('kb:12', 'helpdesk_kb:3' ...)."""
    user = _auth.require_auth(actor)
    source, _, ref = str(key or '').partition(':')
    if source not in _SOURCES or not ref.isdigit():
        raise ValueError(f"Unknown suggestion '{key}'")
    with store.writing() as conn:
        row, criteria = _visit(conn, user, visit_id)
        opened = list(dict.fromkeys((criteria.get('opened') or []) + [key]))
        criteria['opened'] = opened
        conn.execute("UPDATE search_analytics SET clicked_result_id = ?, search_criteria = ? "
                     "WHERE search_id = ?", (key, json.dumps(criteria), row[0]))
        table, id_col = _SOURCES[source][0], _SOURCES[source][1]
        column = _VIEW_COLUMN[source]
        if column in _table_columns(conn, table):
            conn.execute(f"UPDATE {table} SET {column} = COALESCE({column}, 0) + 1 "  # nosec B608
                         f"WHERE {id_col} = ?", (int(ref),))
    return True


def finish(actor, visit_id, ticket_id=None) -> str:
    """Close a visit: 'submitted' when a ticket was raised, 'deflected' when
    the student read a suggestion and did not, else 'abandoned'."""
    user = _auth.require_auth(actor)
    with store.writing() as conn:
        row, criteria = _visit(conn, user, visit_id)
        if ticket_id is not None:
            outcome = 'submitted'
            criteria['ticket_id'] = int(ticket_id)
        elif row[2] or criteria.get('opened'):
            outcome = 'deflected'
        else:
            outcome = 'abandoned'
        criteria['outcome'] = outcome
        criteria['finished_at'] = _now()
        conn.execute("UPDATE search_analytics SET search_criteria = ? WHERE search_id = ?",
                     (json.dumps(criteria), row[0]))
    return outcome


def stats(conn, date_from=None, date_to=None) -> dict:
    """``{'visits', 'with_suggestions', 'deflected', 'submitted', 'abandoned',
    'open', 'deflection_rate'}`` for the reports."""
    sql = ("SELECT results_count, search_criteria FROM search_analytics WHERE search_type = ?")
    params = [SEARCH_TYPE]
    if date_from:
        sql += " AND search_datetime >= ?"
        params.append(str(date_from))
    if date_to:
        sql += " AND search_datetime <= ?"
        params.append(str(date_to) if len(str(date_to)) > 10 else f"{date_to} 23:59:59")
    out = {'visits': 0, 'with_suggestions': 0, 'deflected': 0, 'submitted': 0, 'abandoned': 0,
           'open': 0}
    for count, criteria in conn.execute(sql, params).fetchall():
        out['visits'] += 1
        if count:
            out['with_suggestions'] += 1
        try:
            outcome = json.loads(criteria or '{}').get('outcome')
        except (TypeError, ValueError):
            outcome = None
        out[outcome if outcome in OUTCOMES else 'open'] += 1
    out['deflection_rate'] = round(100 * out['deflected'] / out['with_suggestions'], 1) \
        if out['with_suggestions'] else 0.0
    return out


__all__ = ['suggest', 'keywords', 'start', 'viewed', 'finish', 'stats']
