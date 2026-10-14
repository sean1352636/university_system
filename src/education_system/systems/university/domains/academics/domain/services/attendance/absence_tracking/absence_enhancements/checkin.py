"""Check-in channels — #3 geofenced, #4 facial-recognition kiosk."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any, Callable, Optional, Tuple

from .log import logger
from .settings import EnhancementSettings


# ===========================================================================
# GeofenceService — #3
# ===========================================================================

class GeofenceService:
    """Wraps services.attendance.geofencing.GeofencingSystem with a
    DB-resolved campus centre."""

    _shared_instance: Any = None

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.settings = EnhancementSettings(conn)

    @classmethod
    def _get_system(cls):
        if cls._shared_instance is None:
            from education_system.systems.university.domains.academics.domain.services.attendance.geofencing import (  # noqa: E501
                GeofencingSystem,
            )
            cls._shared_instance = GeofencingSystem()
        return cls._shared_instance

    def _ensure_active_session(self, gs, module_code: str,
                               d: str) -> Optional[str]:
        try:
            row = self.conn.execute(
                "SELECT session_id, latitude, longitude, geofence_radius "
                "FROM attendance_sessions WHERE module_code=? AND date=? "
                "ORDER BY rowid DESC LIMIT 1",
                (module_code, d)).fetchone()
        except sqlite3.Error:
            logger.exception("session lookup failed mc=%s d=%s",
                             module_code, d)
            return None
        if row:
            sid, lat, lon, rad = row
            gs.active_locations[sid] = {
                "module_code": module_code, "date": d,
                "location": (lat, lon), "radius": rad or 50,
            }
            return sid
        raw_lat = self.settings.get("campus_lat")
        raw_lon = self.settings.get("campus_lon")
        if raw_lat in (None, "") or raw_lon in (None, ""):
            return None
        try:
            c_rad = float(self.settings.get("campus_radius_m", "500") or 500)
            lat = float(raw_lat)
            lon = float(raw_lon)
        except (TypeError, ValueError):
            logger.exception("campus geofence settings malformed")
            return None
        try:
            return gs.create_geofenced_session(
                module_code, d, "campus", lat, lon, c_rad)
        except Exception:
            logger.exception("create_geofenced_session failed mc=%s",
                             module_code)
            return None

    def record_checkin(self, student_id: str, module_code: str,
                       lat: float, lon: float, *,
                       device_id: str = "",
                       when: Optional[date] = None) -> Tuple[bool, str]:
        d = (when or date.today()).isoformat()
        try:
            gs = self._get_system()
        except Exception as e:
            logger.exception("GeofencingSystem unavailable")
            return False, f"geofencing unavailable: {e}"
        sid = self._ensure_active_session(gs, module_code, d)
        if not sid:
            return (False,
                    "no geofenced session and campus centre not configured")
        try:
            ok, msg = gs.check_location_attendance(
                student_id, lat, lon, session_id=sid)
        except Exception as e:
            logger.exception("check_location_attendance failed")
            return False, f"geofence check failed: {e}"
        return bool(ok), msg


def record_geofenced_checkin(conn, student_id, module_code, lat, lon,
                             device_id: str = "",
                             when=None) -> Tuple[bool, str]:
    return GeofenceService(conn).record_checkin(
        student_id, module_code, lat, lon,
        device_id=device_id, when=when)


# ===========================================================================
# FaceCheckinService — #4
# ===========================================================================

class FaceCheckinService:
    """Facial recognition kiosk wrapper."""

    _shared_instance: Any = None

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    @classmethod
    def _get_system(cls):
        if cls._shared_instance is None:
            from education_system.systems.university.domains.academics.domain.services.attendance.face_recognition_system import (  # noqa: E501
                FaceRecognitionSystem,
            )
            cls._shared_instance = FaceRecognitionSystem()
        return cls._shared_instance

    def register_kiosk(self, kiosk_id: str, room: str,
                       lat: float, lon: float,
                       radius_m: float = 50) -> None:
        try:
            self.conn.execute(
                """INSERT INTO attendance_kiosks
                     (kiosk_id, room, lat, lon, radius_m)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(kiosk_id) DO UPDATE SET
                     room=excluded.room, lat=excluded.lat,
                     lon=excluded.lon, radius_m=excluded.radius_m,
                     active=1""",
                (kiosk_id, room, lat, lon, radius_m))
            self.conn.commit()
        except sqlite3.Error:
            self.conn.rollback()
            logger.exception("kiosk register failed id=%s", kiosk_id)
            raise

    def checkin(self, kiosk_id: str, module_code: str,
                image_path: str,
                recogniser: Optional[Callable] = None
                ) -> Tuple[bool, str, Optional[str]]:
        if recogniser is not None:
            # Test / custom recogniser — bypass the real ML pipeline.
            try:
                student_id, conf = recogniser(image_path)
            except Exception as e:
                logger.exception("custom recogniser raised")
                return False, f"recogniser error: {e}", None
            if not student_id:
                return False, f"low confidence ({conf:.2f})", None
            d = date.today().isoformat()
            try:
                self.conn.execute(
                    """INSERT INTO attendance
                         (student_id, module_code, date, status, reason)
                       VALUES (?,?,?,?,?)""",
                    (student_id, module_code, d, "present",
                     f"face kiosk {kiosk_id}"))
                self.conn.commit()
            except sqlite3.Error as e:
                self.conn.rollback()
                logger.exception("face kiosk insert failed sid=%s",
                                 student_id)
                return False, str(e), None
            return True, "ok", student_id
        try:
            fs = self._get_system()
        except Exception as e:
            logger.exception("FaceRecognitionSystem unavailable")
            return False, f"face recognition unavailable: {e}", None
        d = date.today().isoformat()
        try:
            ok, msg, sid = fs.recognize_face_attendance(
                image_path, module_code, d)
        except Exception as e:
            logger.exception("recognize_face_attendance failed")
            return False, f"face recognition failed: {e}", None
        return bool(ok), msg, sid


def register_kiosk(conn, kiosk_id, room, lat, lon, radius_m=50):
    FaceCheckinService(conn).register_kiosk(kiosk_id, room, lat, lon,
                                            radius_m)


def facial_checkin(conn, kiosk_id, module_code, image_path,
                   recogniser=None) -> Tuple[bool, str, Optional[str]]:
    return FaceCheckinService(conn).checkin(
        kiosk_id, module_code, image_path, recogniser)


__all__ = [
    "GeofenceService",
    "record_geofenced_checkin",
    "FaceCheckinService",
    "register_kiosk",
    "facial_checkin",
]
