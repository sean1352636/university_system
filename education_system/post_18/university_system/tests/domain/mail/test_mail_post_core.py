"""
Tests for mail/post system core services.
Tests package management, PO boxes, forwarding, transactions, and reports.
"""

import pytest
import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from contextlib import contextmanager

from education_system.post_18.university_system.modules.domain.operations.communications.mail.services.mail_post_core import (
    PackageManager, POBoxManager, ForwardingManager, TransactionManager,
    ReportManager, generate_tracking_number, generate_reference,
    STORAGE_FEES, DAILY_STORAGE_FEE, FREE_STORAGE_DAYS, FORWARDING_FEES,
)

PATCH_BASE = 'education_system.post_18.university_system.modules.domain.operations.communications.mail.services.mail_post_core'


class _UnclosableConn:
    """Wrapper that prevents close() from actually closing the connection."""
    def __init__(self, conn):
        object.__setattr__(self, '_conn', conn)

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __setattr__(self, name, value):
        if name == '_conn':
            object.__setattr__(self, name, value)
        else:
            setattr(self._conn, name, value)

    def close(self):
        pass

    def cursor(self):
        return self._conn.cursor()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


def _connect(path):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_tables(conn):
    """Create all tables needed by the mail post core service."""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS mail_packages (
            package_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_number TEXT UNIQUE NOT NULL,
            recipient_id TEXT NOT NULL,
            recipient_name TEXT NOT NULL,
            recipient_email TEXT,
            recipient_phone TEXT,
            sender_name TEXT,
            sender_address TEXT,
            package_type TEXT NOT NULL,
            description TEXT,
            weight_kg DECIMAL(10,2),
            dimensions TEXT,
            status TEXT DEFAULT 'received',
            storage_location TEXT,
            received_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notification_sent INTEGER DEFAULT 0,
            notification_date TIMESTAMP,
            collected_date TIMESTAMP,
            collected_by TEXT,
            storage_fee DECIMAL(10,2) DEFAULT 0.00,
            total_charges DECIMAL(10,2) DEFAULT 0.00,
            payment_status TEXT DEFAULT 'pending',
            notes TEXT,
            created_by TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS mail_po_boxes (
            box_id INTEGER PRIMARY KEY AUTOINCREMENT,
            box_number TEXT UNIQUE NOT NULL,
            holder_id TEXT,
            holder_name TEXT,
            holder_email TEXT,
            size TEXT DEFAULT 'standard',
            monthly_fee DECIMAL(10,2) DEFAULT 10.00,
            status TEXT DEFAULT 'available',
            rental_start DATE,
            rental_end DATE,
            auto_renew INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS mail_forwarding (
            forwarding_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            user_name TEXT NOT NULL,
            forward_address TEXT NOT NULL,
            forward_type TEXT DEFAULT 'domestic',
            start_date DATE NOT NULL,
            end_date DATE,
            status TEXT DEFAULT 'active',
            fee DECIMAL(10,2) DEFAULT 0.00,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT,
            reference_number TEXT,
            student_id TEXT,
            transaction_type TEXT,
            reference_id INTEGER,
            reference_type TEXT,
            amount DECIMAL(10,2),
            payment_method TEXT,
            processed_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT,
            entity_type TEXT,
            package_id INTEGER,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()


def _seed_po_boxes(conn, count=5):
    """Insert some available PO boxes."""
    for i in range(1, count + 1):
        conn.execute(
            "INSERT INTO mail_po_boxes (box_number, size, monthly_fee, status) VALUES (?, 'standard', 10.00, 'available')",
            (f"PO-{i:03d}",),
        )
    conn.commit()


@contextmanager
def _patched_env(path):
    """Patch both get_connection and transaction to use the temp database."""
    conn = _connect(path)
    wrapper = _UnclosableConn(conn)

    @contextmanager
    def fake_get_connection():
        yield wrapper

    @contextmanager
    def fake_transaction():
        yield wrapper

    with patch(f'{PATCH_BASE}.get_connection', fake_get_connection), \
         patch(f'{PATCH_BASE}.transaction', fake_transaction), \
         patch(f'{PATCH_BASE}.log_activity'):
        yield wrapper

    conn.close()


# ---------------------------------------------------------------------------
# generate_tracking_number / generate_reference
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_generate_tracking_number_format(self):
        tn = generate_tracking_number()
        assert tn.startswith("UNI-")
        parts = tn.split("-")
        assert len(parts) == 3

    def test_generate_tracking_number_unique(self):
        a = generate_tracking_number()
        b = generate_tracking_number()
        assert a != b

    def test_generate_reference_format(self):
        ref = generate_reference()
        assert ref.startswith("REF-")
        assert len(ref) == 16  # REF- + 12 hex chars

    def test_generate_reference_unique(self):
        a = generate_reference()
        b = generate_reference()
        assert a != b


# ---------------------------------------------------------------------------
# PackageManager
# ---------------------------------------------------------------------------

class TestPackageManager:
    def test_receive_package(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            result = PackageManager.receive_package(
                recipient_id='STU001', recipient_name='Alice Smith',
                recipient_email='alice@uni.ac.uk', package_type='small_parcel',
                sender_name='Amazon', storage_location='Shelf A1',
            )
            assert result is not None
            assert 'package_id' in result
            assert 'tracking_number' in result
            assert result['storage_fee'] == STORAGE_FEES['small_parcel']

    def test_get_package_by_id(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            pkg = PackageManager.receive_package(
                recipient_id='STU001', recipient_name='Alice',
                recipient_email='a@b.com', package_type='letter',
            )
            fetched = PackageManager.get_package(package_id=pkg['package_id'])
            assert fetched is not None
            assert fetched['recipient_name'] == 'Alice'

    def test_get_package_by_tracking(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            pkg = PackageManager.receive_package(
                recipient_id='STU001', recipient_name='Bob',
                recipient_email='b@b.com', package_type='express',
            )
            fetched = PackageManager.get_package(tracking_number=pkg['tracking_number'])
            assert fetched is not None
            assert fetched['package_id'] == pkg['package_id']

    def test_get_packages_for_recipient(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            PackageManager.receive_package(
                recipient_id='STU002', recipient_name='Carol',
                recipient_email='c@b.com', package_type='letter',
            )
            PackageManager.receive_package(
                recipient_id='STU002', recipient_name='Carol',
                recipient_email='c@b.com', package_type='small_parcel',
            )
            packages = PackageManager.get_packages_for_recipient('STU002')
            assert len(packages) == 2

    def test_get_packages_for_recipient_with_status(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            pkg = PackageManager.receive_package(
                recipient_id='STU003', recipient_name='Dave',
                recipient_email='d@b.com', package_type='letter',
            )
            PackageManager.update_package_status(pkg['package_id'], 'collected')
            received = PackageManager.get_packages_for_recipient('STU003', status='received')
            assert len(received) == 0
            collected = PackageManager.get_packages_for_recipient('STU003', status='collected')
            assert len(collected) == 1

    def test_get_pending_packages(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            PackageManager.receive_package(
                recipient_id='STU001', recipient_name='Eve',
                recipient_email='e@b.com', package_type='letter',
            )
            pending = PackageManager.get_pending_packages()
            assert len(pending) >= 1

    def test_update_package_status(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            pkg = PackageManager.receive_package(
                recipient_id='STU001', recipient_name='Frank',
                recipient_email='f@b.com', package_type='registered',
            )
            ok = PackageManager.update_package_status(pkg['package_id'], 'stored', notes='Moved to locker')
            assert ok is True
            updated = PackageManager.get_package(package_id=pkg['package_id'])
            assert updated['status'] == 'stored'
            assert updated['notes'] == 'Moved to locker'

    def test_mark_collected(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            pkg = PackageManager.receive_package(
                recipient_id='STU001', recipient_name='Grace',
                recipient_email='g@b.com', package_type='small_parcel',
            )
            ok = PackageManager.mark_collected(pkg['package_id'], collected_by='Grace')
            assert ok is True
            updated = PackageManager.get_package(package_id=pkg['package_id'])
            assert updated['status'] == 'collected'
            assert updated['collected_by'] == 'Grace'

    def test_calculate_storage_fees_within_free_period(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            pkg = PackageManager.receive_package(
                recipient_id='STU001', recipient_name='Hank',
                recipient_email='h@b.com', package_type='large_parcel',
            )
            fee = PackageManager.calculate_storage_fees(pkg['package_id'])
            # Within free period, should equal base fee
            assert fee == STORAGE_FEES['large_parcel']

    def test_search_packages_by_recipient(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            PackageManager.receive_package(
                recipient_id='STU001', recipient_name='Ivy Jones',
                recipient_email='i@b.com', package_type='letter',
            )
            results = PackageManager.search_packages('Ivy')
            assert len(results) >= 1
            assert results[0]['recipient_name'] == 'Ivy Jones'

    def test_search_packages_by_sender(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            PackageManager.receive_package(
                recipient_id='STU001', recipient_name='Jack',
                recipient_email='j@b.com', package_type='letter',
                sender_name='Royal Mail',
            )
            results = PackageManager.search_packages('Royal')
            assert len(results) >= 1


# ---------------------------------------------------------------------------
# POBoxManager
# ---------------------------------------------------------------------------

class TestPOBoxManager:
    def test_get_available_boxes(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        _seed_po_boxes(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            boxes = POBoxManager.get_available_boxes()
            assert len(boxes) == 5

    def test_rent_box(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        _seed_po_boxes(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            boxes = POBoxManager.get_available_boxes()
            box_id = boxes[0]['box_id']
            result = POBoxManager.rent_box(box_id, 'STU001', 'Alice', 'alice@uni.ac.uk', months=3)
            assert result is not None
            assert result['rental_fee'] == 30.00
            assert 'start_date' in result

    def test_rent_box_unavailable(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        _seed_po_boxes(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            boxes = POBoxManager.get_available_boxes()
            box_id = boxes[0]['box_id']
            POBoxManager.rent_box(box_id, 'STU001', 'Alice', 'a@b.com')
            result = POBoxManager.rent_box(box_id, 'STU002', 'Bob', 'b@b.com')
            assert result is None

    def test_get_user_box(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        _seed_po_boxes(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            boxes = POBoxManager.get_available_boxes()
            POBoxManager.rent_box(boxes[0]['box_id'], 'STU010', 'Zara', 'z@b.com')
            user_box = POBoxManager.get_user_box('STU010')
            assert user_box is not None
            assert user_box['holder_name'] == 'Zara'

    def test_release_box(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        _seed_po_boxes(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            boxes = POBoxManager.get_available_boxes()
            box_id = boxes[0]['box_id']
            POBoxManager.rent_box(box_id, 'STU001', 'Alice', 'a@b.com')
            ok = POBoxManager.release_box(box_id)
            assert ok is True
            user_box = POBoxManager.get_user_box('STU001')
            assert user_box is None


# ---------------------------------------------------------------------------
# ForwardingManager
# ---------------------------------------------------------------------------

class TestForwardingManager:
    def test_setup_forwarding_domestic(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            result = ForwardingManager.setup_forwarding(
                user_id='STU001', user_name='Alice',
                forward_address='10 High St, London',
            )
            assert result is not None
            assert result['fee'] == FORWARDING_FEES['domestic']

    def test_setup_forwarding_international(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            result = ForwardingManager.setup_forwarding(
                user_id='STU002', user_name='Bob',
                forward_address='123 Broadway, NY',
                forward_type='international',
            )
            assert result is not None
            assert result['fee'] == FORWARDING_FEES['international']

    def test_get_user_forwarding(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            ForwardingManager.setup_forwarding(
                user_id='STU003', user_name='Carol',
                forward_address='5 Park Ave',
            )
            fwd = ForwardingManager.get_user_forwarding('STU003')
            assert fwd is not None
            assert fwd['forward_address'] == '5 Park Ave'

    def test_cancel_forwarding(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            result = ForwardingManager.setup_forwarding(
                user_id='STU004', user_name='Dave',
                forward_address='99 Elm St',
            )
            ok = ForwardingManager.cancel_forwarding(result['forwarding_id'])
            assert ok is True
            fwd = ForwardingManager.get_user_forwarding('STU004')
            assert fwd is None


# ---------------------------------------------------------------------------
# TransactionManager
# ---------------------------------------------------------------------------

class TestTransactionManager:
    def test_record_payment(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            pkg = PackageManager.receive_package(
                recipient_id='STU001', recipient_name='Alice',
                recipient_email='a@b.com', package_type='large_parcel',
            )
            result = TransactionManager.record_payment(
                user_id='STU001', transaction_type='storage_fee',
                amount=2.50, payment_method='card',
                package_id=pkg['package_id'],
            )
            assert result is not None
            assert result['amount'] == 2.50
            assert 'reference' in result

    def test_record_payment_updates_package_status(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            pkg = PackageManager.receive_package(
                recipient_id='STU001', recipient_name='Alice',
                recipient_email='a@b.com', package_type='registered',
            )
            TransactionManager.record_payment(
                user_id='STU001', transaction_type='storage_fee',
                amount=1.00, payment_method='cash',
                package_id=pkg['package_id'],
            )
            updated = PackageManager.get_package(package_id=pkg['package_id'])
            assert updated['payment_status'] == 'paid'

    def test_get_user_transactions(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            TransactionManager.record_payment(
                user_id='STU005', transaction_type='po_box',
                amount=10.00, payment_method='card',
            )
            txns = TransactionManager.get_user_transactions('STU005')
            assert len(txns) == 1


# ---------------------------------------------------------------------------
# ReportManager
# ---------------------------------------------------------------------------

class TestReportManager:
    def test_get_daily_report_empty(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            report = ReportManager.get_daily_report()
            assert report['packages_received'] == 0
            assert report['packages_collected'] == 0

    def test_get_daily_report_with_data(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            PackageManager.receive_package(
                recipient_id='STU001', recipient_name='Alice',
                recipient_email='a@b.com', package_type='letter',
            )
            today = datetime.now().date().isoformat()
            report = ReportManager.get_daily_report(date=today)
            assert report['packages_received'] >= 1

    def test_get_monthly_summary(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        _seed_po_boxes(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            PackageManager.receive_package(
                recipient_id='STU001', recipient_name='Alice',
                recipient_email='a@b.com', package_type='letter',
            )
            now = datetime.now()
            summary = ReportManager.get_monthly_summary(year=now.year, month=now.month)
            assert 'packages_by_type' in summary
            assert summary['active_po_boxes'] == 0

    def test_get_pending_notifications(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with _patched_env(temp_db) as w:
            PackageManager.receive_package(
                recipient_id='STU001', recipient_name='Alice',
                recipient_email='a@b.com', package_type='letter',
            )
            pending = ReportManager.get_pending_notifications()
            assert len(pending) >= 1
            assert pending[0]['notification_sent'] == 0
