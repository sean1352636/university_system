"""
Add Sample Menu Items to Restaurant Database

Run this script to populate the menu_items table with sample food items
for testing the order placement system.
"""

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.core.paths import DEFAULT_DB_PATH as DB_PATH

def add_sample_menu_items():
    """Add sample menu items to the database"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        # Sample menu items
        menu_items = [
            # Appetizers
            ('Garlic Bread', 'Toasted bread with garlic butter and herbs', 4.50, 'Appetizer', 'Gluten, Dairy', 1, 0, 1),
            ('Caesar Salad', 'Romaine lettuce, parmesan, croutons, Caesar dressing', 6.95, 'Appetizer', 'Gluten, Dairy, Egg', 1, 0, 1),
            ('Soup of the Day', 'Chef\'s special soup, served with bread', 5.50, 'Appetizer', 'Varies', 1, 1, 1),
            ('Bruschetta', 'Toasted bread with tomatoes, basil, olive oil', 5.95, 'Appetizer', 'Gluten', 1, 1, 1),
            ('Mozzarella Sticks', 'Deep-fried mozzarella with marinara sauce', 6.50, 'Appetizer', 'Gluten, Dairy', 1, 0, 1),

            # Main Courses
            ('Classic Burger', 'Beef patty, lettuce, tomato, onion, pickles', 11.95, 'Main Course', 'Gluten, Dairy', 0, 0, 1),
            ('Veggie Burger', 'Plant-based patty with all the trimmings', 10.95, 'Main Course', 'Gluten, Soy', 1, 1, 1),
            ('Fish & Chips', 'Beer-battered cod with chips and mushy peas', 13.50, 'Main Course', 'Gluten, Fish', 0, 0, 1),
            ('Chicken Tikka Masala', 'Curry with rice and naan bread', 12.95, 'Main Course', 'Gluten, Dairy', 0, 0, 1),
            ('Margherita Pizza', 'Tomato, mozzarella, basil on wood-fired base', 9.95, 'Main Course', 'Gluten, Dairy', 1, 0, 1),
            ('Vegan Pizza', 'Tomato, vegan cheese, vegetables on thin crust', 11.95, 'Main Course', 'Gluten', 0, 1, 1),
            ('Pasta Carbonara', 'Spaghetti with bacon, egg, parmesan, black pepper', 10.95, 'Main Course', 'Gluten, Dairy, Egg', 0, 0, 1),
            ('Thai Green Curry', 'Vegetables in coconut curry with jasmine rice', 11.50, 'Main Course', 'None', 1, 1, 1),
            ('Steak & Chips', '8oz sirloin steak with chips and salad', 16.95, 'Main Course', 'None', 0, 0, 1),
            ('Salmon Fillet', 'Grilled salmon with vegetables and new potatoes', 14.95, 'Main Course', 'Fish', 0, 0, 1),

            # Sides
            ('French Fries', 'Crispy golden fries', 3.50, 'Side', 'None', 1, 1, 1),
            ('Sweet Potato Fries', 'Crispy sweet potato fries', 4.00, 'Side', 'None', 1, 1, 1),
            ('Onion Rings', 'Battered and fried onion rings', 3.95, 'Side', 'Gluten', 1, 0, 1),
            ('Coleslaw', 'Fresh cabbage slaw', 2.95, 'Side', 'Egg', 1, 0, 1),
            ('Mixed Vegetables', 'Seasonal vegetables', 3.50, 'Side', 'None', 1, 1, 1),

            # Desserts
            ('Chocolate Brownie', 'Warm brownie with ice cream', 5.95, 'Dessert', 'Gluten, Dairy, Egg', 1, 0, 1),
            ('Tiramisu', 'Classic Italian coffee dessert', 6.50, 'Dessert', 'Gluten, Dairy, Egg', 1, 0, 1),
            ('Ice Cream Sundae', 'Three scoops with toppings', 5.50, 'Dessert', 'Dairy', 1, 0, 1),
            ('Fruit Salad', 'Fresh seasonal fruits', 4.95, 'Dessert', 'None', 1, 1, 1),
            ('Vegan Chocolate Cake', 'Rich chocolate cake, dairy-free', 5.95, 'Dessert', 'Gluten', 0, 1, 1),

            # Beverages
            ('Coffee', 'Freshly brewed coffee', 2.50, 'Beverage', 'None', 1, 1, 1),
            ('Tea', 'Selection of teas', 2.00, 'Beverage', 'None', 1, 1, 1),
            ('Soft Drink', 'Coca-Cola, Sprite, Fanta', 2.50, 'Beverage', 'None', 1, 1, 1),
            ('Orange Juice', 'Freshly squeezed', 3.50, 'Beverage', 'None', 1, 1, 1),
            ('Milkshake', 'Chocolate, vanilla, or strawberry', 4.50, 'Beverage', 'Dairy', 1, 0, 1),
        ]

        # Check if items already exist
        cursor.execute("SELECT COUNT(*) FROM menu_items")
        existing_count = cursor.fetchone()[0]

        if existing_count > 0:
            response = input(f"Database already has {existing_count} menu items. Add more anyway? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("Operation cancelled.")
                conn.close()
                return

        # Insert menu items
        cursor.executemany('''
            INSERT INTO menu_items (name, description, price, category, allergens, vegetarian, vegan, available)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', menu_items)

        conn.commit()
        print(f"✓ Successfully added {len(menu_items)} menu items!")
        print(f"✓ Total menu items in database: {existing_count + len(menu_items)}")

        # Show category summary
        cursor.execute('''
            SELECT category, COUNT(*) as count
            FROM menu_items
            WHERE available = 1
            GROUP BY category
            ORDER BY category
        ''')

        print("\nMenu Summary:")
        print("-" * 40)
        for row in cursor.fetchall():
            category, count = row
            print(f"  {category:20s}: {count:2d} items")

        conn.close()

    except sqlite3.Error as e:
        print(f"✗ Database error: {e}")
    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("Restaurant Menu Items Setup")
    print("=" * 60)
    print(f"Database: {DB_PATH}")
    print()

    add_sample_menu_items()

    print("\n" + "=" * 60)
    print("Setup complete! You can now use the Place Order feature.")
    print("=" * 60)
