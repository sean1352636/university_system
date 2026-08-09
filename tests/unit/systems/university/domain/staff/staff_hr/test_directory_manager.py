"""Tests for DirectoryManager: expertise and office-hours management, and
combined profile retrieval. (Directory search relies on the shared auth DB
join and is exercised only for its empty/graceful path.)"""

from education_system.systems.university.domain.staff.staff_hr.services.managers.directory_manager import (
    DirectoryManager as M,
)


class TestExpertise:
    def test_add_get_search(self, hr_db):
        eid = M.add_expertise('U1', 'Machine Learning', category='research',
                              keywords='ml,ai')
        assert eid > 0
        rows = M.get_expertise('U1')
        assert len(rows) == 1
        assert rows[0]['expertise_area'] == 'Machine Learning'

        hits = M.search_by_expertise('Machine')
        assert len(hits) == 1
        assert hits[0]['user_id'] == 'U1'
        # Keyword column is also searched.
        assert len(M.search_by_expertise('ai')) == 1

    def test_update_and_remove(self, hr_db):
        eid = M.add_expertise('U1', 'Stats')
        M.update_expertise(eid, proficiency='expert')
        assert M.get_expertise('U1')[0]['proficiency'] == 'expert'
        M.remove_expertise(eid)
        assert M.get_expertise('U1') == []

    def test_search_empty(self, hr_db):
        assert M.search_by_expertise('nothing') == []


class TestOfficeHours:
    def test_set_get_update_remove(self, hr_db):
        hid = M.set_office_hours('U1', 'Monday', '09:00', '11:00',
                                 location='Room 1')
        assert hid > 0
        hours = M.get_office_hours('U1')
        assert len(hours) == 1
        assert hours[0]['day_of_week'] == 'Monday'
        assert hours[0]['is_by_appointment'] == 0

        M.update_office_hours(hid, location='Room 2')
        assert M.get_office_hours('U1')[0]['location'] == 'Room 2'

        M.remove_office_hours(hid)
        assert M.get_office_hours('U1') == []


class TestCombinedProfile:
    def test_full_profile_structure(self, hr_db):
        M.add_expertise('U1', 'HCI')
        M.set_office_hours('U1', 'Tuesday', '10:00', '12:00')
        full = M.get_full_profile('U1')
        assert set(full.keys()) == {'profile', 'expertise', 'office_hours'}
        assert len(full['expertise']) == 1
        assert len(full['office_hours']) == 1
        # No staff_profiles row was created, so profile is None.
        assert full['profile'] is None

    def test_search_directory_graceful_empty(self, hr_db):
        assert M.search_directory(query='ghost') == []
