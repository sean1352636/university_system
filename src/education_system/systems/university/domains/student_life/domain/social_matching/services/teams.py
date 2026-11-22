"""Team formation mixin for the Social Matching Service."""

from education_system.systems.university.infrastructure.database.db import sqlite3
from typing import Dict, List

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity


class TeamMixin:
    """Methods for intramural sports team formation."""

    def create_team(self, creator_id: str, team_name: str, sport_type: str,
                   team_size: int, skill_level: str, description: str = "") -> int:
        """
        Create a new intramural sports team.

        Args:
            creator_id: Team creator
            team_name: Team name
            sport_type: Type of sport
            team_size: Target team size
            skill_level: Skill level (Beginner, Intermediate, Advanced)
            description: Team description

        Returns:
            Team ID
        """
        with transaction() as conn:
            # Create team
            cursor = conn.execute("""
                INSERT INTO team_formations
                (team_name, sport_type, creator_id, team_size, skill_level, description)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (team_name, sport_type, creator_id, team_size, skill_level, description))

            team_id = cursor.lastrowid

            # Add creator as first member
            conn.execute("""
                INSERT INTO team_members (team_id, user_id, role)
                VALUES (?, ?, 'captain')
            """, (team_id, creator_id))

        log_activity('create', 'team_formation', user_id=creator_id,
                    details={'team_name': team_name, 'sport': sport_type})
        return team_id

    def join_team(self, team_id: int, user_id: str) -> bool:
        """Join an existing team."""
        with transaction() as conn:
            # Check team capacity
            cursor = conn.execute("""
                SELECT current_members, team_size
                FROM team_formations
                WHERE team_id = ? AND status = 'recruiting'
            """, (team_id,))

            row = cursor.fetchone()
            if not row:
                return False

            current, max_size = row
            if current >= max_size:
                return False

            # Add member
            try:
                conn.execute("""
                    INSERT INTO team_members (team_id, user_id)
                    VALUES (?, ?)
                """, (team_id, user_id))

                # Update member count
                conn.execute("""
                    UPDATE team_formations
                    SET current_members = current_members + 1
                    WHERE team_id = ?
                """, (team_id,))

                log_activity('create', 'team_member', user_id=user_id,
                           details={'team_id': team_id})
                return True
            except sqlite3.IntegrityError:
                return False

    def get_available_teams(self, sport_type: str = "", skill_level: str = "") -> List[Dict]:
        """Get available teams looking for members."""
        with get_connection() as conn:
            query = """
                SELECT team_id, team_name, sport_type, creator_id,
                       team_size, current_members, skill_level, description, created_at
                FROM team_formations
                WHERE status = 'recruiting'
                AND current_members < team_size
            """
            params = []

            if sport_type:
                query += " AND sport_type = ?"
                params.append(sport_type)

            if skill_level:
                query += " AND skill_level = ?"
                params.append(skill_level)

            query += " ORDER BY created_at DESC"

            cursor = conn.execute(query, params)

            teams = []
            for row in cursor.fetchall():
                teams.append({
                    'team_id': row[0],
                    'team_name': row[1],
                    'sport_type': row[2],
                    'creator_id': row[3],
                    'team_size': row[4],
                    'current_members': row[5],
                    'skill_level': row[6],
                    'description': row[7],
                    'created_at': row[8]
                })
            return teams

    def get_team_members(self, team_id: int) -> List[Dict]:
        """Get members of a team."""
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT user_id, role, joined_at
                FROM team_members
                WHERE team_id = ?
                ORDER BY joined_at
            """, (team_id,))

            members = []
            for row in cursor.fetchall():
                members.append({
                    'user_id': row[0],
                    'role': row[1],
                    'joined_at': row[2]
                })
            return members
