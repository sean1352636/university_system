"""Extracted class implementation."""

from .. import train_station_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class Database:
    """Handle all database operations using university system database"""

    def __init__(self):
        self.db_path = paths.DEFAULT_DB_PATH
        self.create_tables()
        self.populate_sample_services()

    def get_connection(self):
        """Get database connection"""
        return get_db_connection()

    def create_tables(self):
        """Create necessary database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Train station services table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS train_station_services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_number TEXT UNIQUE NOT NULL,
                departure_station TEXT NOT NULL,
                arrival_station TEXT NOT NULL,
                departure_time TEXT NOT NULL,
                arrival_time TEXT NOT NULL,
                price REAL NOT NULL,
                available_seats INTEGER NOT NULL
            )
        ''')

        # Train station tickets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS train_station_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_number TEXT UNIQUE NOT NULL,
                service_id INTEGER NOT NULL,
                passenger_name TEXT NOT NULL,
                payment_method TEXT NOT NULL,
                price_paid REAL NOT NULL,
                purchase_date TEXT NOT NULL,
                FOREIGN KEY (service_id) REFERENCES train_station_services (id)
            )
        ''')

        # Train station receipts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS train_station_receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_number TEXT UNIQUE NOT NULL,
                ticket_id INTEGER NOT NULL,
                total_amount REAL NOT NULL,
                payment_method TEXT NOT NULL,
                transaction_date TEXT NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES train_station_tickets (id)
            )
        ''')

        # Note: refunds now use the unified_refunds table (no local train_refunds table)

        conn.commit()
        conn.close()

    def populate_sample_services(self):
        """Add sample train services if table is empty"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM train_station_services")
        if cursor.fetchone()[0] == 0:
            services = [
                ("EXP001", "London Kings Cross", "Edinburgh", "06:00", "10:30", 89.50, 150),
                ("EXP002", "London Euston", "Manchester", "07:15", "09:30", 65.00, 200),
                ("EXP003", "London Paddington", "Bristol", "08:00", "09:45", 45.00, 180),
                ("EXP004", "London Victoria", "Brighton", "09:30", "10:30", 25.00, 250),
                ("EXP005", "London St Pancras", "Paris", "10:00", "13:00", 120.00, 300),
                ("REG001", "Birmingham", "Liverpool", "11:00", "13:15", 35.00, 120),
                ("REG002", "Leeds", "Sheffield", "12:30", "13:15", 18.50, 100),
                ("REG003", "Glasgow", "Edinburgh", "14:00", "15:00", 22.00, 90),
                ("EXP006", "Newcastle", "London Kings Cross", "15:30", "18:45", 95.00, 175),
                ("REG004", "Cardiff", "Swansea", "16:00", "17:00", 15.00, 80),
            ]
            cursor.executemany('''
                INSERT INTO train_station_services
                (service_number, departure_station, arrival_station, departure_time, arrival_time, price, available_seats)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', services)
            conn.commit()
        conn.close()

    def get_all_services(self):
        """Retrieve all train services"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, service_number, departure_station, arrival_station,
                   departure_time, arrival_time, price, available_seats
            FROM train_station_services
        ''')
        result = cursor.fetchall()
        conn.close()
        return result

    def get_service_by_id(self, service_id):
        """Get a specific service by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM train_station_services WHERE id = ?", (service_id,))
        result = cursor.fetchone()
        conn.close()
        return result

    def purchase_ticket(self, service_id, passenger_name, payment_method, price_paid):
        """Create a new ticket purchase"""
        conn = self.get_connection()
        cursor = conn.cursor()

        ticket_number = "TKT" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        purchase_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute('''
            INSERT INTO train_station_tickets (ticket_number, service_id, passenger_name, payment_method, price_paid, purchase_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (ticket_number, service_id, passenger_name, payment_method, price_paid, purchase_date))

        ticket_id = cursor.lastrowid

        # Update available seats
        cursor.execute('''
            UPDATE train_station_services SET available_seats = available_seats - 1 WHERE id = ?
        ''', (service_id,))

        # Create receipt
        receipt_number = "RCP" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        cursor.execute('''
            INSERT INTO train_station_receipts (receipt_number, ticket_id, total_amount, payment_method, transaction_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (receipt_number, ticket_id, price_paid, payment_method, purchase_date))

        conn.commit()
        conn.close()
        return ticket_number, receipt_number

    def get_all_tickets(self):
        """Retrieve all purchased tickets with service details"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.ticket_number, t.passenger_name, ts.service_number,
                   ts.departure_station, ts.arrival_station, ts.departure_time,
                   t.payment_method, t.price_paid, t.purchase_date
            FROM train_station_tickets t
            JOIN train_station_services ts ON t.service_id = ts.id
            ORDER BY t.purchase_date DESC
        ''')
        result = cursor.fetchall()
        conn.close()
        return result

    def get_receipt(self, ticket_number):
        """Get receipt for a specific ticket"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT r.receipt_number, r.total_amount, r.payment_method, r.transaction_date,
                   t.ticket_number, t.passenger_name, ts.service_number,
                   ts.departure_station, ts.arrival_station, ts.departure_time, ts.arrival_time
            FROM train_station_receipts r
            JOIN train_station_tickets t ON r.ticket_id = t.id
            JOIN train_station_services ts ON t.service_id = ts.id
            WHERE t.ticket_number = ?
        ''', (ticket_number,))
        result = cursor.fetchone()
        conn.close()
        return result

    def close(self):
        """Close database connection (no-op for connection-per-query pattern)"""
        pass
