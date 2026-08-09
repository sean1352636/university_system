# Music Shop - User Guide

## Overview

The Music Shop system manages the university's on-campus music store, including product inventory (vinyl records, CDs, cassettes, instruments, sheet music, merchandise, and audio equipment), order processing with shopping cart and wishlist features, payment processing with student finance integration, and comprehensive sales analytics. It supports rare/collectible item tracking, genre-based browsing, and full refund management.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Browsing the Catalog](#browsing-the-catalog)
3. [Shopping Cart & Wishlist](#shopping-cart--wishlist)
4. [Placing an Order](#placing-an-order)
5. [Payments & Refunds](#payments--refunds)
6. [Inventory Management](#inventory-management)
7. [Reports & Analytics](#reports--analytics)
8. [Administration](#administration)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)
11. [Contact Information](#contact-information)

---

## Getting Started

### Accessing the Music Shop

**GUI Mode:**
1. Launch the application → **Campus Services** → **Music Shop**
2. Login with university credentials
3. Multi-tab interface loads: Catalog, Orders, Inventory, Reports, Refunds

**CLI Mode:**
1. Navigate to **Main Menu** → **Music Shop**
2. Select from the available menu options

### First-Time Setup

1. Log in with your university credentials
2. Browse the catalog by category or genre
3. Add items to your cart or wishlist
4. Proceed to checkout and select a payment method

---

## Browsing the Catalog

### Product Categories

| Category | Description | Examples |
|----------|-------------|---------|
| **Vinyl Records** | LP and single vinyl records | Classic rock LPs, limited editions |
| **CDs** | Compact discs | Albums, compilations, box sets |
| **Cassettes** | Cassette tapes | Retro releases, mixtapes |
| **Instruments** | Musical instruments | Guitars, keyboards, ukuleles |
| **Sheet Music** | Printed music scores | Classical, pop arrangements |
| **Merchandise** | Band and music merch | T-shirts, posters, accessories |
| **Audio Equipment** | Listening equipment | Turntables, speakers, headphones |
| **Accessories** | Music accessories | Strings, picks, cables, stands |

### Genres

The shop supports 14 genres for filtering: Rock, Pop, Jazz, Classical, Hip-Hop, Electronic, Country, R&B, Metal, Folk, Blues, Indie, World, and Soundtracks.

### Product Conditions

| Condition | Description |
|-----------|-------------|
| **New** | Factory sealed, unused |
| **Mint** | Opened but like new |
| **Excellent** | Minor signs of use |
| **Good** | Normal wear, fully functional |
| **Fair** | Noticeable wear |
| **Poor** | Heavy wear, still playable |

### Searching & Filtering

1. Navigate to the **Catalog** tab
2. Use the **Category** dropdown to filter by product type
3. Use the **Genre** dropdown to filter by music genre
4. Use the **Search** bar to find items by title, artist, genre, or SKU
5. Double-click a product to select it for your cart

### Rare & Collectible Items

Special items are flagged as **Rare/Collectible** in the inventory. These can be browsed in the Inventory tab's dedicated rare items panel.

---

## Shopping Cart & Wishlist

### Adding to Cart

1. Select a product from the catalog
2. Set the desired quantity (1-99)
3. Click **Add to Cart**
4. The system validates stock availability before adding

### Managing Your Cart

1. Click **View Cart** to open the cart window
2. Review items with: Product, Price, Quantity, Subtotal
3. **Remove Item** — remove a selected item
4. **Clear Cart** — empty the entire cart
5. Enter a shipping address (optional)
6. View the running total (Subtotal + 20% VAT)
7. Click **Proceed to Payment** when ready

### Wishlist

1. Select a product and click **Add to Wishlist**
2. View your wishlist items in the wishlist panel
3. Click **Add to Cart** from the wishlist to move items to your cart
4. Each customer has a personal wishlist (no duplicates allowed)

---

## Placing an Order

### Order Process

1. Review your cart and click **Proceed to Payment**
2. Confirm your shipping address
3. Select payment method (see [Payments](#payments--refunds))
4. Confirm the purchase
5. System generates a unique order number (format: `MUS-YYYYMMDDHHMMSS`)
6. Confirmation email sent automatically
7. Stock levels updated immediately

### Order Pricing

| Component | Calculation |
|-----------|-------------|
| **Subtotal** | Sum of (quantity x unit price) per item |
| **Tax** | 20% VAT on subtotal |
| **Shipping** | Optional fee |
| **Discount** | If applicable |
| **Total** | Subtotal + Tax + Shipping - Discount |

### Order Statuses

| Status | Description |
|--------|-------------|
| **Pending** | Order created, awaiting payment |
| **Confirmed** | Payment received |
| **Processing** | Order being prepared |
| **Shipped** | Order dispatched |
| **Delivered** | Order received by customer |
| **Cancelled** | Order cancelled (stock restored) |
| **Refunded** | Refund issued |

---

## Payments & Refunds

### Payment Methods

| Method | Description |
|--------|-------------|
| **Cash** | Pay at the music shop counter |
| **Card** | Debit or credit card |
| **Student Account** | Deduct from university finance account (balance verified) |

For student account payments, the system checks your balance before processing and displays your current available funds.

### Processing Refunds

1. Navigate to the **Refunds** tab
2. Search for the transaction by ID, order ID, or customer ID
3. Select the transaction and click **Process Refund**
4. Choose the refund method:
   - **Cash** — refund in cash
   - **Card** — refund to original card
   - **Student Account** — credit back to finance account
5. Refund reference generated (format: `MUSIC-REFUND-YYYYMMDDHHMMSS`)
6. Refund receipt sent via email
7. Click **Export to CSV** to download transaction records

---

## Inventory Management

### Managing Products (Admin/Staff)

1. Navigate to the **Inventory** tab
2. Fill in the product form:
   - SKU (unique identifier), Title, Artist
   - Label, Release Year
   - Price, Cost Price, Stock Quantity
   - Category, Genre, Condition
   - Rare/Collectible flag
3. Click **Add Product** to add or **Update Product** to modify

### Low Stock Alerts

- Products at or below the minimum stock level (default: 3 units) appear in the low stock alerts panel
- Monitor these regularly and restock as needed

### Rare Items Tracking

- Flag products as **Rare/Collectible** when adding or editing
- View all rare items in the dedicated panel with pricing details
- Useful for tracking limited editions and collector's items

---

## Reports & Analytics

### Available Reports

| Report | Content |
|--------|---------|
| **Sales Summary** | Total orders, revenue, average order value, pending/completed counts |
| **Inventory Report** | Total products, stock units, inventory value, low stock and rare item counts |
| **Top 10 Products** | Best-selling products by quantity and revenue |
| **Top 10 Artists** | Best-selling artists by orders, items sold, and revenue |
| **Genre Analysis** | Sales breakdown by genre with items sold and revenue |
| **Admin Report** | Comprehensive combined report of all metrics |

### Generating Reports

1. Navigate to the **Reports** tab
2. Click the desired report button
3. Report displays in the text area
4. Click **Email Admin Report** to send the full report to administrators

---

## Administration

### Order Management

- View all orders filtered by status
- View detailed order information (items, customer, totals)
- Cancel orders (automatically restores stock)
- Process refunds from the Orders or Refunds tab

### Product Lifecycle

- Add new products with full metadata
- Update pricing, stock levels, and conditions
- Deactivate products without deleting (soft delete)
- Track cost price for margin analysis

---

## Best Practices

1. **Check stock alerts regularly** — restock items before they sell out
2. **Flag rare items** — helps collectors find limited editions
3. **Use the wishlist** — save items for later without holding stock
4. **Review genre analytics** — stock more of what sells well
5. **Export transactions** — keep CSV records for accounting
6. **Process refunds promptly** — maintains customer satisfaction

---

## Troubleshooting

### Common Issues

**Cannot add to cart:**
- Verify the product has available stock
- Ensure you are logged in
- Check that the requested quantity does not exceed stock

**Payment failed:**
- If using student account, check your balance
- Try an alternative payment method
- Contact the music shop counter for manual processing

**Product not found:**
- Try searching by title, artist, or SKU
- Check category and genre filters are set to "All"
- The product may be deactivated — contact staff

**Order not showing:**
- Use the status filter on the Orders tab
- Check that you are logged in with the correct account

---

## Contact Information

**University Music Shop**
- **Phone**: (555) 123-MUSIC
- **Email**: musicshop@university.edu
- **Location**: Student Centre, Ground Floor

**Shop Hours**
- Monday-Friday: 9:00 AM - 6:00 PM
- Saturday: 10:00 AM - 4:00 PM
- Sunday: Closed

---

**Last Updated**: February 2026
**Module**: `university_system/modules/domain/musicshop/`
**Support**: musicshop@university.edu | (555) 123-MUSIC
