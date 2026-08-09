"""Extracted class implementation."""

from .. import taxi_booking_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class Database:
    """Handle all database operations using university system database"""

    def __init__(self):
        self.db_path = paths.DEFAULT_DB_PATH
        self.init_database()

    def get_connection(self):
        return get_db_connection()

    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Create taxi booking services table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS taxi_booking_services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_name TEXT NOT NULL,
                vehicle_type TEXT NOT NULL,
                capacity INTEGER NOT NULL,
                price_per_km REAL NOT NULL,
                base_fare REAL NOT NULL,
                description TEXT,
                available INTEGER DEFAULT 1
            )
        ''')

        # Create taxi booking tickets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS taxi_booking_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_number TEXT UNIQUE NOT NULL,
                service_id INTEGER NOT NULL,
                customer_name TEXT NOT NULL,
                pickup_location TEXT NOT NULL,
                dropoff_location TEXT NOT NULL,
                distance_km REAL NOT NULL,
                total_fare REAL NOT NULL,
                payment_method TEXT NOT NULL,
                payment_status TEXT DEFAULT 'Completed',
                booking_date TEXT NOT NULL,
                booking_time TEXT NOT NULL,
                FOREIGN KEY (service_id) REFERENCES taxi_booking_services (id)
            )
        ''')

        # Insert default taxi services if none exist
        cursor.execute("SELECT COUNT(*) FROM taxi_booking_services")
        if cursor.fetchone()[0] == 0:
            default_services = [
                ("City Express", "Sedan", 4, 2.50, 5.00, "Comfortable city rides with AC"),
                ("Premium Luxury", "SUV", 6, 4.00, 10.00, "Luxury SUV for premium travel"),
                ("Budget Saver", "Hatchback", 4, 1.75, 3.00, "Affordable rides for short trips"),
                ("Family Van", "Minivan", 8, 3.50, 8.00, "Spacious van for family outings"),
                ("Eco Green", "Electric", 4, 2.00, 4.00, "Eco-friendly electric vehicle"),
                ("Executive Class", "Luxury Sedan", 4, 5.00, 15.00, "Top-tier business class service"),
                ("Airport Shuttle", "Van", 10, 3.00, 20.00, "Dedicated airport transfers"),
                ("Night Owl", "Sedan", 4, 3.00, 7.00, "24/7 night service with safety features"),
            ]
            cursor.executemany('''
                INSERT INTO taxi_booking_services (service_name, vehicle_type, capacity, price_per_km, base_fare, description)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', default_services)

        conn.commit()
        conn.close()

    def get_all_services(self):
        """Get all available taxi services"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM taxi_booking_services WHERE available = 1")
        services = cursor.fetchall()
        conn.close()
        return services

    def get_service_by_id(self, service_id):
        """Get a specific service by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM taxi_booking_services WHERE id = ?", (service_id,))
        service = cursor.fetchone()
        conn.close()
        return service

    def create_ticket(self, service_id, customer_name, pickup, dropoff, distance, total_fare, payment_method):
        """Create a new ticket"""
        conn = self.get_connection()
        cursor = conn.cursor()

        ticket_number = self.generate_ticket_number()
        now = datetime.now()

        cursor.execute('''
            INSERT INTO taxi_booking_tickets (ticket_number, service_id, customer_name, pickup_location,
                               dropoff_location, distance_km, total_fare, payment_method,
                               booking_date, booking_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ticket_number, service_id, customer_name, pickup, dropoff, distance,
              total_fare, payment_method, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")))

        ticket_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return ticket_id, ticket_number

    def get_all_tickets(self):
        """Get all tickets with service details"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.*, s.service_name, s.vehicle_type
            FROM taxi_booking_tickets t
            JOIN taxi_booking_services s ON t.service_id = s.id
            ORDER BY t.id DESC
        ''')
        tickets = cursor.fetchall()
        conn.close()
        return tickets

    def get_ticket_by_id(self, ticket_id):
        """Get a specific ticket with full details"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.*, s.service_name, s.vehicle_type, s.description
            FROM taxi_booking_tickets t
            JOIN taxi_booking_services s ON t.service_id = s.id
            WHERE t.id = ?
        ''', (ticket_id,))
        ticket = cursor.fetchone()
        conn.close()
        return ticket

    @staticmethod
    def generate_ticket_number():
        """Generate a unique ticket number"""
        prefix = "TXI"
        timestamp = datetime.now().strftime("%Y%m%d")
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"{prefix}-{timestamp}-{random_suffix}"
