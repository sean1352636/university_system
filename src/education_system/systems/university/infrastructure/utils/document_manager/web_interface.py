from education_system.systems.university.infrastructure.utils.document_manager._common import datetime, sqlite3, get_connection


class WebInterfaceMixin:
    def web_interface_menu(self):
        """Web interface management menu"""
        print("\n🌐 WEB INTERFACE MANAGEMENT")
        print("1. Start Web Server")
        print("2. Generate Mobile Interface")
        print("3. Web Interface Settings")
        print("4. Mobile App QR Code")
        print("5. Return to Main Menu")

        choice = input("\nChoose option (1-5): ").strip()

        if choice == '1':
            self.start_web_server()
        elif choice == '2':
            self.generate_mobile_interface()
        elif choice == '3':
            self.web_interface_settings()
        elif choice == '4':
            self.mobile_app_qr_code()

    def start_web_server(self):
        """Start the web interface server"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT setting_name, setting_value
            FROM system_settings
            WHERE setting_name IN ('web_interface_host', 'web_interface_port', 'web_interface_ssl')
            ''')

            settings = dict(cursor.fetchall())

            host = settings.get('web_interface_host', '127.0.0.1')
            port = settings.get('web_interface_port', '5000')
            ssl = settings.get('web_interface_ssl', 'false') == 'true'

            print("\n🌐 Web Interface Configuration:")
            print(f"Host: {host}")
            print(f"Port: {port}")
            print(f"SSL: {'Enabled' if ssl else 'Disabled'}")
            print(f"URL: http{'s' if ssl else ''}://{host}:{port}")

            print("\nNote: The web server runs as a separate Flask application.")
            print("To start the web server, use:")
            print(f"  python -m university_system.web.server --port {port}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def generate_mobile_interface(self):
        """Install the bundled mobile-responsive document interface."""
        print("\n📱 GENERATE MOBILE INTERFACE")

        print("\nMobile interface generation creates:")
        print("1. Responsive HTML templates")
        print("2. Mobile-optimized CSS")
        print("3. Touch-friendly UI components")
        print("4. Progressive Web App (PWA) manifest")

        generate = input("\nGenerate basic mobile template? (y/n): ").strip().lower()

        if generate == 'y':
            from pathlib import Path
            from education_system import paths
            source = Path(__file__).resolve().parents[3] / "assets" / "web" / "mobile"
            destination = Path(paths.UNIVERSITY_DATA_DIR) / "document_manager" / "web" / "mobile"
            destination.mkdir(parents=True, exist_ok=True)
            for asset in source.iterdir():
                if asset.is_file():
                    (destination / asset.name).write_bytes(asset.read_bytes())
            print("\nMobile interface generated.")
            print(f"Files created in: {destination}")
            return destination

    def mobile_app_qr_code(self):
        """Generate QR code for mobile app access"""
        print("\n📱 MOBILE APP QR CODE")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get web interface settings
            cursor.execute('''
            SELECT setting_name, setting_value
            FROM system_settings
            WHERE setting_name IN ('web_interface_host', 'web_interface_port', 'web_interface_ssl')
            ''')

            settings = dict(cursor.fetchall())

            host = settings.get('web_interface_host', '127.0.0.1')
            port = settings.get('web_interface_port', '5000')
            ssl = settings.get('web_interface_ssl', 'false') == 'true'

            url = f"http{'s' if ssl else ''}://{host}:{port}"

            print(f"\nMobile Access URL: {url}")
            print("\nQR Code generation requires 'qrcode' library.")
            print("Install with: pip install qrcode[pil]")

            try:
                import qrcode

                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(url)
                qr.make(fit=True)

                qr.print_ascii(invert=True)

                save = input("\nSave QR code as image? (y/n): ").strip().lower()
                if save == 'y':
                    img = qr.make_image(fill_color="black", back_color="white")
                    filename = "mobile_access_qr.png"
                    img.save(filename)
                    print(f"✅ QR code saved as {filename}")

            except ImportError:
                print("\n❌ QR code library not installed.")
                print("Install with: pip install qrcode[pil]")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")
