"""Gamification system for attendance tracking."""

import datetime
import json
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.domain.academics.services.attendance.settings import get_setting


def update_gamification_points(student_id, action, bonus_multiplier=1.0):
    """Update student gamification points and achievements"""
    try:
        if get_setting('enable_gamification') != 'True':
            return

        conn = get_connection()
        cursor = conn.cursor()

        # Get current gamification data
        cursor.execute('''
        SELECT * FROM attendance_gamification WHERE student_id = ?
        ''', (student_id,))

        current_data = cursor.fetchone()

        if not current_data:
            # Create new record
            cursor.execute('''
            INSERT INTO attendance_gamification (student_id, last_attendance_date)
            VALUES (?, ?)
            ''', (student_id, datetime.date.today().isoformat()))
            current_data = (None, student_id, 0, 1, '[]', '[]', 0, 0,
                          datetime.date.today().isoformat(), 0, None, None)

        points_per_attendance = int(get_setting('points_per_attendance') or 10)
        streak_bonus_multiplier = float(get_setting('streak_bonus_multiplier') or 1.5)

        # Calculate new points
        base_points = points_per_attendance if action == 'attendance' else 0

        # Check for streak
        last_date = datetime.datetime.strptime(current_data[8], '%Y-%m-%d').date() if current_data[8] else None
        today = datetime.date.today()

        if last_date:
            days_diff = (today - last_date).days
            if days_diff == 1:
                # Continue streak
                new_streak = current_data[6] + 1
            elif days_diff == 0:
                # Same day, no streak change
                new_streak = current_data[6]
            else:
                # Streak broken
                new_streak = 1
        else:
            new_streak = 1

        # Apply streak bonus
        if new_streak > 1:
            streak_bonus = int(base_points * (streak_bonus_multiplier - 1) * min(new_streak / 7, 2))
            total_points = base_points + streak_bonus
        else:
            total_points = base_points

        total_points = int(total_points * bonus_multiplier)

        # Update best streak
        new_best_streak = max(current_data[7], new_streak)

        # Calculate new level (every 1000 points = 1 level)
        new_total_points = current_data[2] + total_points
        new_level = (new_total_points // 1000) + 1

        # Check for new achievements
        badges = json.loads(current_data[4]) if current_data[4] else []
        achievements = json.loads(current_data[5]) if current_data[5] else []

        # Award badges
        if new_streak >= 7 and 'week_streak' not in badges:
            badges.append('week_streak')
            achievements.append({'badge': 'week_streak', 'date': today.isoformat(), 'description': '7-day attendance streak'})

        if new_streak >= 30 and 'month_streak' not in badges:
            badges.append('month_streak')
            achievements.append({'badge': 'month_streak', 'date': today.isoformat(), 'description': '30-day attendance streak'})

        if new_total_points >= 1000 and 'point_master' not in badges:
            badges.append('point_master')
            achievements.append({'badge': 'point_master', 'date': today.isoformat(), 'description': '1000 points earned'})

        # Update database
        cursor.execute('''
        UPDATE attendance_gamification
        SET points = ?, level = ?, badges = ?, achievements = ?, streak_days = ?,
            best_streak = ?, last_attendance_date = ?, total_rewards = ?, updated_at = ?
        WHERE student_id = ?
        ''', (new_total_points, new_level, json.dumps(badges), json.dumps(achievements),
              new_streak, new_best_streak, today.isoformat(), current_data[9] + total_points,
              datetime.datetime.now().isoformat(), student_id))

        conn.commit()
        conn.close()

        if total_points > 0:
            print(f"Student {student_id} earned {total_points} points! Current level: {new_level}")

    except Exception as e:
        print(f"Error updating gamification points: {e}")
