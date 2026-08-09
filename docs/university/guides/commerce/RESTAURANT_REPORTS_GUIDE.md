# Restaurant Reports - User Guide

## Quick Start

All restaurant reports are now working with real data from your database. Here's how to use each report effectively.

---

## 📊 Sales Reports

### Daily Sales Report
**Access**: Reports Menu → Daily Sales Report

**What it shows**:
- Total orders for a specific date
- Total revenue
- Average order value

**How to use**:
1. Click "Daily Sales Report"
2. Enter date in format: YYYY-MM-DD (e.g., 2026-01-25)
3. Or leave empty to use today's date

**Export options**:
- Export as TXT file
- Email to admin

---

### Monthly Summary Report ✨ NEW
**Access**: Reports Menu → Monthly Summary Report

**What it shows**:
- Overall performance (orders, revenue, taxes, averages)
- Payment method breakdown with percentages
- Top 10 selling items
- Daily sales trend throughout the month

**How to use**:
1. Click "Monthly Summary Report"
2. Enter month in format: YYYY-MM (e.g., 2026-01)
3. Or leave empty to use current month
4. Review comprehensive monthly analytics

**Use cases**:
- End-of-month performance review
- Identify best-selling products
- Understand payment method preferences
- Track daily sales patterns

---

### Profit Analysis Report ✨ NEW
**Access**: Reports Menu → Profit Analysis Report

**What it shows**:
- Revenue breakdown (gross, net, tax)
- Cost analysis (COGS, refunds, discounts, waste)
- Gross profit and operating profit
- Profit margins (gross and operating)
- Performance indicators
- Smart recommendations

**How to use**:
1. Click "Profit Analysis Report"
2. Enter start date: YYYY-MM-DD
3. Enter end date: YYYY-MM-DD
4. Review profit analysis and recommendations

**Key metrics explained**:
- **Gross Profit** = Revenue - Cost of Goods Sold
- **Operating Profit** = Gross Profit - Refunds - Discounts - Waste
- **Gross Margin** = (Gross Profit / Revenue) × 100%
- **Operating Margin** = (Operating Profit / Revenue) × 100%

**Recommendations**:
- 🔴 <0%: Critical - immediate action needed
- 🟡 <10%: Low - review pricing and costs
- 🟢 10-20%: Good - maintain operations
- ✅ >20%: Excellent - consider expansion

---

### Menu Performance Report
**Access**: Reports Menu → Menu Performance Report

**What it shows**:
- Most popular menu items
- Sales by category
- Item revenue contribution

---

### Customer Analytics Report
**Access**: Reports Menu → Customer Analytics Report

**What it shows**:
- Total customers
- Average loyalty points
- Total revenue from customers
- Average spend per customer

---

## 💰 Financial Reports

### Sales Tax Summary ✅ WORKING
**Access**: Financial Reports → Tax Reports → Generate Sales Tax Summary

**What it shows**:
- Total transactions and tax collected
- Taxable amounts by payment method
- Tax breakdown for filing

**How to use**:
1. Select tax report type
2. Enter date range
3. Review tax summary
4. Use for VAT/tax filing purposes

---

### VAT Report ✅ FIXED
**Access**: Financial Reports → Tax Reports → Generate VAT Report

**What it shows**:
- VAT collected on sales (Output VAT)
- VAT paid on purchases (Input VAT) - if available
- Net VAT payable/reclaimable

**How to use**:
1. Enter date range
2. Review VAT calculations
3. Note: Consult accountant for official returns

**Notes**:
- Always calculates sales VAT
- Purchase VAT shown if purchase orders tracked
- Professional disclaimer included

---

### Financial Forecast ✅ FIXED
**Access**: Financial Reports → Financial Forecasting

**What it shows**:
- 12-month historical performance
- Monthly revenue and expense trends
- Average metrics and growth rate
- 3-month forward projection
- Key insights and recommendations

**How to use**:
1. Click "Financial Forecasting"
2. System automatically analyzes last 12 months
3. Review historical performance
4. Check projections
5. Read key insights

**Understanding the forecast**:
- Based on actual revenue data
- Expenses estimated if purchase orders unavailable
- Growth rate calculated from recent trends
- Projections are guidance only

---

### Expense Report ⚠ REQUIRES SETUP
**Access**: Financial Reports → Export Expense Report

**Status**: Requires `restaurant_purchase_orders` table

**When available, shows**:
- All supplier purchases
- Expense breakdown by status
- Payment method analysis

**Current status**:
- Table not created yet
- Will show informative message
- Contact admin to enable expense tracking

---

### Payroll Report ⚠ REQUIRES SETUP
**Access**: Financial Reports → Export Payroll Report

**Status**: Requires `restaurant_shifts` table

**When available, shows**:
- Staff hours worked
- Shift counts
- Gross pay calculations

**Current status**:
- Table not created yet
- Will show informative message
- Contact admin to enable shift tracking

---

## 📤 Export Functions

### Export Complete Financial Data ✅ FIXED
**Access**: Financial Reports → Export Financial Data → Export Complete Financial Data

**What it exports**:
- ✅ Sales revenue (all orders)
- ⚠ Purchase expenses (if available)
- ⚠ Waste costs (if available)
- ✅ Financial summary

**File format**: CSV (Excel compatible)

**How to use**:
1. Enter date range
2. Choose save location
3. Open in Excel or similar
4. Note: Some sections may be unavailable

---

### Export Sales Data ✅ FIXED
**Access**: Financial Reports → Export Financial Data → Export Sales Data Only

**What it exports**:
- All sales transactions
- Item-level sales details
- Sales summary statistics

**File format**: CSV (Excel compatible)

**How to use**:
1. Enter date range
2. Choose save location
3. Review detailed sales data

**Columns included**:
- Order ID, Customer ID, Date/Time
- Subtotal, Tax, Total
- Payment method, Status
- Item-level breakdown

---

## 📋 Report Comparison

| Report | Real Data | Date Range | Export | Email | Estimation |
|--------|-----------|------------|--------|-------|------------|
| Daily Sales | ✅ | Single day | ✅ | ✅ | No |
| Monthly Summary | ✅ | Month | ✅ | ✅ | No |
| Profit Analysis | ✅ | Custom | ✅ | ✅ | COGS if needed |
| Sales Tax | ✅ | Custom | ✅ | ❌ | No |
| VAT Report | ✅ | Custom | ✅ | ❌ | Purchase VAT if needed |
| Financial Forecast | ✅ | Auto (12mo) | ✅ | ❌ | Expenses if needed |
| Export Financial | ✅ | Custom | ✅ (CSV) | ❌ | No |
| Export Sales | ✅ | Custom | ✅ (CSV) | ❌ | No |
| Expense Report | ⚠ | Custom | ⚠ | ❌ | N/A |
| Payroll Report | ⚠ | Custom | ⚠ | ❌ | N/A |

✅ = Available and working
⚠ = Requires additional table setup

---

## 🎯 Best Practices

### Daily Operations
1. **Morning**: Run Daily Sales Report for yesterday
2. **Evening**: Check today's performance

### Weekly Review
1. Run Weekly Sales Report
2. Review top-selling items
3. Check payment method trends

### Monthly Review
1. **First of month**: Run Monthly Summary for previous month
2. **Profit Analysis**: Review margins and recommendations
3. **Tax Reports**: Prepare for tax filing
4. **Forecast**: Check projections vs. actuals

### Quarter-End
1. Export Complete Financial Data (3 months)
2. Run Profit Analysis for quarter
3. Review VAT position
4. Update forecasts

---

## ❓ Troubleshooting

### "Table Not Available" Message

**What it means**: Some advanced features require additional database tables

**For Expense Reports**:
- Requires: `restaurant_purchase_orders` table
- Purpose: Track supplier purchases
- Action: Contact admin to enable expense tracking

**For Payroll Reports**:
- Requires: `restaurant_shifts` table
- Purpose: Track employee hours
- Action: Contact admin to enable shift tracking

### Estimated Data Notice

**Why you see it**: Some reports estimate certain metrics when detailed data unavailable

**Common estimates**:
- **COGS**: 30% of revenue (industry standard)
- **Expenses**: 70% of revenue (30% profit margin)

**What to do**:
- Use estimates as guidance
- Set up detailed tracking for accurate reporting
- Contact admin about enabling missing tables

### Empty or Zero Data

**Possible reasons**:
1. Date range has no transactions
2. Database is new
3. Data not in 'Completed' or 'Paid' status

**Solutions**:
- Check date range
- Verify orders exist for that period
- Ensure orders are marked as completed

---

## 📞 Support

**For questions about**:
- Report data: Check this guide first
- Missing tables: Contact system administrator
- Tax calculations: Consult with accountant
- Custom reports: Contact IT support

---

**Last Updated**: 2026-01-25
**Version**: 1.0
**Status**: All core reports working ✅
