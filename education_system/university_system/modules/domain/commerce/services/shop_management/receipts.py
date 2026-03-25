from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.domain.commerce.services.shop_management import config


def generate_pdf_receipt(transaction_id):
    """Generate a PDF receipt for a transaction"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to generate receipts.")
        return False

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get transaction details
        cursor.execute(
            '''
            SELECT t.*, u.username, u.email
            FROM transactions t
            LEFT JOIN users u ON t.customer_id = u.id
            WHERE t.source_type = 'shop' AND t.source_transaction_id = ?
            ''',
            [transaction_id]
        )

        transaction = cursor.fetchone()

        if not transaction:
            print(f"Transaction {transaction_id} not found.")
            conn.close()
            return False

        # Get transaction items
        cursor.execute(
            '''
            SELECT ti.*, p.name, p.category
            FROM shop_transaction_items ti
            JOIN products p ON ti.product_id = p.source_product_id AND p.source_type = 'shop'
            WHERE ti.transaction_id = ?
            ''',
            [transaction_id]
        )

        items = cursor.fetchall()

        if not items:
            print(f"No items found for transaction {transaction_id}.")
            conn.close()
            return False

        # Create PDF receipt
        filename = f"receipt_{transaction_id}.pdf"
        doc = SimpleDocTemplate(filename, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()

        # Header
        story.append(Paragraph("University Shop Receipt", styles['Title']))
        story.append(Paragraph("<br/><br/>", styles['Normal']))

        # Transaction details
        story.append(Paragraph(f"<b>Transaction ID:</b> {transaction['source_transaction_id']}", styles['Normal']))
        story.append(Paragraph(f"<b>Date:</b> {transaction['created_at']}", styles['Normal']))
        story.append(Paragraph(f"<b>Customer:</b> {transaction['username']}", styles['Normal']))
        if transaction['student_id']:
            story.append(Paragraph(f"<b>Student ID:</b> {transaction['student_id']}", styles['Normal']))
        story.append(Paragraph(f"<b>Payment Method:</b> {transaction['payment_method']}", styles['Normal']))
        story.append(Paragraph("<br/>", styles['Normal']))

        # Items table
        table_data = [['Item', 'Quantity', 'Price', 'Subtotal']]

        for item in items:
            table_data.append([
                item['name'],
                str(item['quantity']),
                f"\u00a3{item['price_per_item']:.2f}",
                f"\u00a3{item['subtotal']:.2f}"
            ])

        # Add total row
        table_data.append(['', '', 'Total:', f"\u00a3{transaction['total_amount']:.2f}"])

        # Create table
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey)
        ]))

        story.append(table)
        story.append(Paragraph("<br/><br/>", styles['Normal']))
        story.append(Paragraph("Thank you for your purchase!", styles['Normal']))

        # Build PDF
        doc.build(story)

        print(f"Receipt generated: {filename}")
        conn.close()
        return True

    except Exception as e:
        print(f"Error generating receipt: {e}")
        if 'conn' in locals():
            conn.close()
        return False


def generate_barcode(product_id):
    """Generate a barcode using python-barcode library or fallback to text representation."""
    try:
        # Try to use python-barcode library for actual barcode generation
        from barcode import Code128
        from barcode.writer import ImageWriter
        import io
        import base64

        # Generate Code128 barcode
        barcode_class = Code128(str(product_id), writer=ImageWriter())
        buffer = io.BytesIO()
        barcode_class.write(buffer)

        # Return base64 encoded image data
        buffer.seek(0)
        barcode_data = base64.b64encode(buffer.getvalue()).decode()
        return {
            'type': 'image',
            'format': 'png',
            'data': barcode_data,
            'text': str(product_id)
        }

    except ImportError:
        # Fallback to text representation if barcode library not available
        barcode_chars = {
            '0': '||  | ||',
            '1': '| |  |||',
            '2': '| || | |',
            '3': '||||   |',
            '4': '|   ||||',
            '5': '||   |||',
            '6': '| |||  |',
            '7': '| | |||',
            '8': '|||  | |',
            '9': '|||  |||',
            'P': '|||| | |',
            'A': '| ||||||',
            'B': '|||| |||',
            'C': '| | ||||',
            'D': '||||| ||',
            'E': '|| |||||',
            'F': '|||||| |'
        }

        barcode = "| "  # Start
        for char in str(product_id):
            if char.upper() in barcode_chars:
                barcode += barcode_chars[char.upper()] + " "
            else:
                barcode += "| | | | "  # Default pattern
        barcode += "|"  # End

        return {
            'type': 'text',
            'data': barcode,
            'text': str(product_id)
        }


def print_product_labels(product_ids=None):
    """Print product labels with barcodes"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to print labels.")
        return

    if not config.auth.check_permission('manage_products'):
        print("You don't have permission to print labels.")
        return

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if product_ids:
            # Print specific products
            placeholders = ','.join(['?'] * len(product_ids))
            cursor.execute(
                f'''
                SELECT p.*, i.quantity
                FROM products p
                JOIN shop_inventory i ON p.source_product_id = i.product_id
                WHERE p.source_type = 'shop'
                WHERE p.product_id IN ({placeholders})
                ORDER BY p.name
                ''',
                product_ids
            )
        else:
            # Print all active products
            cursor.execute(
                '''
                SELECT p.*, i.quantity
                FROM products p
                JOIN shop_inventory i ON p.source_product_id = i.product_id
                WHERE p.source_type = 'shop'
                WHERE p.is_active = 1
                ORDER BY p.name
                '''
            )

        products = cursor.fetchall()

        if not products:
            print("No products found for label printing.")
            conn.close()
            return

        print(f"\nProduct Labels ({len(products)} products)")
        print("=" * 80)

        for product in products:
            print(f"\n+{'─' * 60}+")
            print(f"| {product['name'][:56]:<56} |")
            print(f"| ID: {product['product_id']:<8} Price: \u00a3{product['price']:<8.2f} Stock: {product['quantity']:<8} |")
            print(f"| Category: {product['category']:<46} |")
            print(f"| {generate_barcode(product['product_id']):<56} |")
            print(f"+{'─' * 60}+")

        conn.close()

        # In a real system, this would send to a label printer
        print(f"\n{len(products)} labels ready for printing!")
        input("\nPress Enter to continue...")

    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"Error printing labels: {e}")
