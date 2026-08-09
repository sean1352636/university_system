# Butcher Shop - User Guide

## Overview

The University Butcher Shop provides fresh meat, poultry, seafood, deli products, and prepared meals to students and staff. The system manages product inventory with 12 meat categories, order processing with custom cut requests, payment processing with student finance integration, stock management with expiry tracking, and supplier orders. It supports counter, pre-order, and custom order types.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Product Inventory](#product-inventory)
3. [Placing an Order](#placing-an-order)
4. [Payments & Refunds](#payments--refunds)
5. [Inventory Management](#inventory-management)
6. [Reports & Analytics](#reports--analytics)
7. [Administration](#administration)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)
10. [Contact Information](#contact-information)

---

## Getting Started

### Accessing the Butcher Shop

**GUI Mode:**
1. Launch the application → **Commerce & Dining** → **Butcher Shop**
2. Login with university credentials
3. Multi-tab interface loads: Products, Orders, Inventory, Reports, Refunds

**CLI Mode:**
1. Navigate to **Main Menu** → **Butcher Shop**
2. Select from: Browse Products, Place Order, View Orders, Inventory Management, Reports, Analytics

---

## Product Inventory

### Meat Categories

| Category | Description |
|----------|-------------|
| **Beef** | Steaks, mince, joints |
| **Pork** | Chops, sausages, bacon |
| **Lamb** | Chops, leg, mince |
| **Chicken** | Breast, whole, thighs |
| **Turkey** | Breast, whole |
| **Duck** | Whole, breast |
| **Game** | Venison, pheasant |
| **Sausages** | Various meat sausages |
| **Mince** | Ground meats |
| **Deli Meats** | Bacon, ham, sliced meats |
| **Prepared Meals** | Ready-to-cook meals |
| **Specialty Items** | Specialty cuts and products |

### Sample Products

| Product | Category | Price per kg | Stock |
|---------|----------|-------------|-------|
| Ribeye Steak | Beef | £24.99 | 15 kg |
| Sirloin Steak | Beef | £19.99 | 20 kg |
| Beef Mince | Beef | £8.99 | 30 kg |
| Pork Chops | Pork | £12.99 | 18 kg |
| Pork Sausages | Pork | £7.99 | 25 kg |
| Chicken Breast | Chicken | £10.99 | 22 kg |
| Whole Chicken | Chicken | £6.99 | 15 kg |
| Lamb Chops | Lamb | £18.99 | 12 kg |
| Leg of Lamb | Lamb | £16.99 | 10 kg |
| Salmon Fillet | Seafood | £22.99 | 8 kg |
| Cod Fillet | Seafood | £16.99 | 10 kg |
| Bacon Rashers | Deli | £9.99 | 20 kg |
| Ham Slices | Deli | £11.99 | 15 kg |

### Unit Types

Products are sold in various units: **kg** (kilograms), **g** (grams), **lb** (pounds), **oz** (ounces), **each** (individual pieces), or **pack** (multi-item packs).

### Browsing Products

1. Navigate to the **Products** tab
2. Filter by category using the dropdown (12 categories)
3. View product details: Name, Category, Price, Stock, Unit Type
4. Select a product to add to your order

---

## Placing an Order

### Order Types

| Type | Description |
|------|-------------|
| **Counter** | Walk-in purchase at the counter |
| **Pre-order** | Advance order for later collection |
| **Custom** | Custom cut or preparation request |

### Ordering via GUI

1. Navigate to the **Orders** tab (or **Products** tab)
2. Select a product from the dropdown
3. Enter the quantity (in the product's unit type)
4. Add **special cut instructions** if needed (e.g., "thick cut", "bone in", "diced")
5. Click **Add to Order** — item appears in the order list
6. Repeat to add more items
7. Review the running total
8. Click **Submit Order**
9. Process payment (see [Payments](#payments--refunds))
10. Order number generated (format: `BTR-YYYYMMDDHHMMSS-###`)
11. Receipt email sent automatically

### Ordering via CLI

1. Select **Place Order**
2. Browse available products
3. Select product and enter quantity (supports unit conversion: "2.5 kg", "500 g")
4. Add items to cart and review
5. Set pickup date and add notes
6. Confirm and pay

### Order Statuses

| Status | Description |
|--------|-------------|
| **Pending** | Order placed, awaiting processing |
| **Processing** | Staff preparing the order |
| **Ready** | Order ready for collection |
| **Collected** | Customer picked up the order |
| **Cancelled** | Order cancelled (stock restored) |

### Custom Cuts

When ordering, you can specify special cut instructions for each item:
- **Thick cut** or **thin cut**
- **Bone in** or **boneless**
- **Diced**, **minced**, or **sliced**
- Any other preparation notes

---

## Payments & Refunds

### Payment Methods

| Method | Description |
|--------|-------------|
| **Cash** | Pay at the counter |
| **Card** | Debit or credit card |
| **Student Account** | Deduct from university finance account (balance verified) |

### Payment Processing

1. After submitting your order, the payment dialog appears
2. View the total amount
3. Select your payment method
4. For student accounts: balance is checked before deduction
5. Transaction recorded with reference number
6. Receipt email sent automatically

### Processing Refunds (Admin/Staff)

1. Navigate to the **Refunds** tab
2. Search by order number, order ID, customer name, or customer ID
3. Select the paid order and click **Process Refund**
4. Choose the refund method:
   - **Cash** — refund in cash
   - **Card** — refund to original card
   - **Student Account** — credit back to finance account
5. Refund reference generated (format: `BUTCH-REFUND-XXXXXXXX`)
6. Refund receipt sent via email
7. Export orders to CSV via **Export to CSV**

---

## Inventory Management

### Stock Levels

1. Navigate to the **Inventory** tab
2. View current stock levels with: Product, Category, Stock, Min Level, Unit, Status
3. Items below minimum stock level are highlighted in **red**
4. Status shows **OK** or **LOW**

### Stock Adjustments (Staff/Admin)

1. Select a product
2. Enter the adjustment amount (positive to add, negative to reduce)
3. Enter the reason (Restocking, Wastage, Damage, Correction, Other)
4. Click **Apply**
5. Inventory log updated with previous and new quantities

### Low Stock Alerts

- Products at or below the minimum stock level trigger alerts
- The alerts panel shows the count of low-stock items
- Monitor regularly and coordinate with suppliers

### Expiry Tracking (CLI)

- Track product batches with expiry dates
- View products expiring within a configurable number of days (default: 7)
- Mark expired batches as disposed
- Helps maintain food safety standards

### Supplier Orders (CLI)

- Track supplier orders with expected and actual delivery dates
- Monitor order status (pending, delivered)
- Record delivery costs and notes

---

## Reports & Analytics

### Available Reports

**GUI Reports:**
- **Admin Report**: Today's sales (transactions, revenue, refunds, net), weekly summary (orders, revenue, average), top 5 products, inventory status

**CLI Reports:**
- **Sales Reports**: Today, this week, this month, or custom date range — total orders, revenue, average order value, sales by category, top 10 products
- **Inventory Valuation**: Stock value by category
- **Popular Products**: Top products by order count, quantity sold, and revenue (last 30 days)
- **Customer History**: Total orders, spending, average order, favourite products (admin only)

### Generating Reports

1. Navigate to the **Reports** tab
2. Set the date range (from/to)
3. Click **Generate Admin Report**
4. Report displays in the text area
5. Click **Email Report** to send to all administrators

---

## Administration

### Order Management (Staff/Admin)

- View all orders filtered by status
- Change order status: Pending → Processing → Ready → Collected
- Update payment status for orders
- Cancel orders (stock automatically restored)

### Product Management (Staff/Admin)

- Add new products with category, pricing, unit type, origin, storage temperature, and shelf life
- Update existing product details and pricing
- Manage stock levels with reason tracking

### Role-Based Access

| Feature | Student | Staff | Admin |
|---------|---------|-------|-------|
| Browse products | Yes | Yes | Yes |
| Place orders | Yes | Yes | Yes |
| View own orders | Yes | Yes | Yes |
| Cancel own pending orders | Yes | Yes | Yes |
| Process refunds | — | Yes | Yes |
| Add/update products | — | Yes | Yes |
| Adjust inventory | — | Yes | Yes |
| View all orders | — | Yes | Yes |
| Change order status | — | Yes | Yes |
| View reports | — | Yes | Yes |

---

## Best Practices

1. **Order fresh** — check stock levels for the freshest products
2. **Specify cuts** — use the special cut instructions for exactly what you need
3. **Pre-order for events** — place pre-orders in advance for large quantities
4. **Collect promptly** — pick up orders when notified they are ready
5. **Check expiry dates** — fresh meat should be used within the shelf life
6. **Report quality issues** — contact the shop immediately if there are any concerns

---

## Troubleshooting

### Common Issues

**Cannot place order:**
- Verify the product has sufficient stock
- Ensure you are logged in
- Check all required fields are completed

**Payment failed:**
- If using student account, check your balance
- Try an alternative payment method
- Contact the counter for manual processing

**Order not ready:**
- Check the order status — it may still be in "Processing"
- Contact the shop for an update on preparation time

**Product not available:**
- The item may be out of stock — check back later
- Ask staff about expected restock dates

---

## Contact Information

**University Butcher Shop**
- **Phone**: (555) 123-MEAT
- **Email**: butcher@university.edu
- **Location**: Student Services Building, Ground Floor

**Shop Hours**
- Monday-Friday: 8:00 AM - 6:00 PM
- Saturday: 8:00 AM - 2:00 PM
- Sunday: Closed

---

**Last Updated**: February 2026
**Module**: `university_system/modules/domain/butcher/`
**Support**: butcher@university.edu | (555) 123-MEAT
