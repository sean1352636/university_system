from __future__ import annotations

import logging
from datetime import datetime, timedelta

from university_system.modules.domain.commerce.services.restaurant.operations.restaurant_context import get_db_connection

def revenue_forecast():
    """Revenue forecast for next 3 months - FIXED"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get historical revenue data (last 12 months)
        cursor.execute('''
            SELECT 
                strftime('%Y-%m', order_time) as month,
                SUM(total_price) as monthly_revenue,
                COUNT(*) as order_count,
                AVG(total_price) as avg_order_value
            FROM restaurant_orders
            WHERE order_time >= date('now', '-12 months') AND status = 'Completed'
            GROUP BY strftime('%Y-%m', order_time)
            ORDER BY month
        ''')

        historical_data = cursor.fetchall()

        if len(historical_data) < 3:
            print("Insufficient historical data for forecasting (need at least 3 months).")
            conn.close()
            return

        print(f"\n" + "="*80)
        print("REVENUE FORECAST (Next 3 Months)")
        print("="*80)

        # Calculate trends
        revenues = [row[1] for row in historical_data]
        avg_revenue = sum(revenues) / len(revenues)

        # Simple growth rate calculation (last 3 months vs previous 3 months)
        if len(revenues) >= 6:
            recent_avg = sum(revenues[-3:]) / 3
            earlier_avg = sum(revenues[-6:-3]) / 3
            growth_rate = (recent_avg - earlier_avg) / earlier_avg if earlier_avg > 0 else 0
        else:
            growth_rate = 0.02  # Default 2% growth

        print(f"Historical Analysis:")
        print(f"Average Monthly Revenue: £{avg_revenue:,.2f}")
        print(f"Recent Growth Rate: {growth_rate*100:+.1f}%")

        # Generate forecasts
        current_date = datetime.now()
        print(f"\nRevenue Forecasts:")
        print("-"*60)
        print(f"{'Month':<15} {'Conservative':<15} {'Expected':<15} {'Optimistic':<15}")
        print("-"*60)

        total_conservative = 0
        total_expected = 0
        total_optimistic = 0

        for i in range(1, 4):
            forecast_date = current_date + timedelta(days=30*i)
            month_str = forecast_date.strftime('%Y-%m')

            # Conservative: Use average with small decline
            conservative = avg_revenue * 0.95

            # Expected: Use growth trend
            expected = avg_revenue * (1 + growth_rate)

            # Optimistic: Higher growth
            optimistic = avg_revenue * (1 + growth_rate * 1.5)

            total_conservative += conservative
            total_expected += expected
            total_optimistic += optimistic

            print(f"{month_str:<15} £{conservative:<14,.0f} £{expected:<14,.0f} £{optimistic:<14,.0f}")

        print("-"*60)
        print(f"{'3-Month Total':<15} £{total_conservative:<14,.0f} £{total_expected:<14,.0f} £{total_optimistic:<14,.0f}")

        # Key assumptions
        print(f"\nKey Assumptions:")
        print("• Conservative: 5% decline from historical average")
        print(f"• Expected: Historical growth rate of {growth_rate*100:+.1f}%")
        print(f"• Optimistic: 1.5x historical growth rate")
        print("• No major market changes or disruptions")

        conn.close()

    except Exception as e:
        logging.error(f"Error in revenue_forecast: {e}")
        print(f"An error occurred: {e}")

def expense_forecast():
    """Expense forecast for next 3 months - FIXED"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get historical expense data by category
        cursor.execute('''
            SELECT 
                category,
                strftime('%Y-%m', expense_date) as month,
                SUM(amount) as monthly_expense
            FROM restaurant_expenses
            WHERE expense_date >= date('now', '-6 months')
            GROUP BY category, strftime('%Y-%m', expense_date)
            ORDER BY category, month
        ''')

        historical_expenses = cursor.fetchall()

        # Calculate average by category
        category_averages = {}
        for row in historical_expenses:
            category = row[0]
            expense = row[2]

            if category not in category_averages:
                category_averages[category] = []
            category_averages[category].append(expense)

        print(f"\n" + "="*80)
        print("EXPENSE FORECAST (Next 3 Months)")
        print("="*80)

        print(f"{'Category':<20} {'Avg Monthly':<15} {'3-Month Forecast':<20}")
        print("-"*60)

        total_monthly_forecast = 0

        for category, expenses in category_averages.items():
            avg_monthly = sum(expenses) / len(expenses)
            three_month_forecast = avg_monthly * 3
            total_monthly_forecast += avg_monthly

            print(f"{category:<20} £{avg_monthly:<14,.2f} £{three_month_forecast:<19,.2f}")

        print("-"*60)
        print(f"{'TOTAL':<20} £{total_monthly_forecast:<14,.2f} £{total_monthly_forecast * 3:<19,.2f}")

        # Inflation adjustment
        inflation_rate = 0.05  # 5% annual inflation assumption
        monthly_inflation = inflation_rate / 12

        adjusted_forecast = total_monthly_forecast * (1 + monthly_inflation) * 3

        print(f"\nInflation-Adjusted Forecast:")
        print(f"Assumed annual inflation: {inflation_rate*100:.1f}%")
        print(f"3-Month forecast with inflation: £{adjusted_forecast:,.2f}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in expense_forecast: {e}")
        print(f"An error occurred: {e}")

def cash_flow_projection():
    """Cash flow projection - FIXED"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get current month's data
        current_month = datetime.now().strftime('%Y-%m')

        # Current month revenue
        cursor.execute('''
            SELECT SUM(total_price) as current_revenue
            FROM restaurant_orders
            WHERE strftime('%Y-%m', order_time) = ? AND status = 'Completed'
        ''', (current_month,))

        current_revenue = cursor.fetchone()[0] or 0

        # Current month expenses
        cursor.execute('''
            SELECT SUM(amount) as current_expenses
            FROM restaurant_expenses
            WHERE strftime('%Y-%m', expense_date) = ?
        ''', (current_month,))

        current_expenses = cursor.fetchone()[0] or 0

        # Historical averages for projection
        cursor.execute('''
            SELECT AVG(monthly_revenue) as avg_revenue
            FROM (
                SELECT SUM(total_price) as monthly_revenue
                FROM restaurant_orders
                WHERE order_time >= date('now', '-6 months') AND status = 'Completed'
                GROUP BY strftime('%Y-%m', order_time)
            )
        ''')

        avg_revenue = cursor.fetchone()[0] or 0

        cursor.execute('''
            SELECT AVG(monthly_expenses) as avg_expenses
            FROM (
                SELECT SUM(amount) as monthly_expenses
                FROM restaurant_expenses
                WHERE expense_date >= date('now', '-6 months')
                GROUP BY strftime('%Y-%m', expense_date)
            )
        ''')

        avg_expenses = cursor.fetchone()[0] or 0

        print(f"\n" + "="*80)
        print("CASH FLOW PROJECTION (Next 6 Months)")
        print("="*80)

        # Starting cash (assumed - in real system would come from accounting)
        starting_cash = 50000  # This would be actual bank balance

        print(f"Starting Cash Position: £{starting_cash:,.2f}")
        print(f"Current Month Performance:")
        print(f"  Revenue to date: £{current_revenue:,.2f}")
        print(f"  Expenses to date: £{current_expenses:,.2f}")
        print(f"  Net cash flow: £{current_revenue - current_expenses:,.2f}")

        print(f"\nProjected Monthly Cash Flow:")
        print("-"*80)
        print(f"{'Month':<15} {'Revenue':<12} {'Expenses':<12} {'Net Flow':<12} {'Cash Balance':<15}")
        print("-"*80)

        cash_balance = starting_cash

        for i in range(1, 7):
            future_date = datetime.now() + timedelta(days=30*i)
            month_str = future_date.strftime('%Y-%m')

            # Use historical averages with small random variation
            projected_revenue = avg_revenue * (0.95 + (i * 0.01))  # Slight growth
            projected_expenses = avg_expenses * (1.02 ** i)  # Slight expense inflation

            net_flow = projected_revenue - projected_expenses
            cash_balance += net_flow

            print(f"{month_str:<15} £{projected_revenue:<11,.0f} £{projected_expenses:<11,.0f} £{net_flow:<11,.0f} £{cash_balance:<14,.0f}")

        print("-"*80)

        # Cash flow analysis
        print(f"\nCash Flow Analysis:")
        min_balance = min(cash_balance, starting_cash)

        if min_balance < 10000:
            print("⚠️  WARNING: Cash flow may become critically low")
            print("   Consider: Credit line, reduce expenses, increase sales")
        elif min_balance < 25000:
            print("⚠️  CAUTION: Cash flow requires monitoring")
            print("   Consider: Improve collection times, manage expenses")
        else:
            print("✅ Cash flow appears healthy")

        print(f"\nKey Metrics:")
        print(f"Average Monthly Net Flow: £{avg_revenue - avg_expenses:,.2f}")
        print(f"Projected 6-Month Cash Change: £{cash_balance - starting_cash:,.2f}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in cash_flow_projection: {e}")
        print(f"An error occurred: {e}")

def seasonal_analysis():
    """Seasonal analysis - FIXED"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print(f"\n" + "="*80)
        print("SEASONAL ANALYSIS")
        print("="*80)

        # Monthly revenue analysis
        cursor.execute('''
            SELECT 
                strftime('%m', order_time) as month,
                AVG(monthly_revenue) as avg_revenue,
                COUNT(DISTINCT strftime('%Y-%m', order_time)) as year_count
            FROM (
                SELECT 
                    order_time,
                    SUM(total_price) as monthly_revenue
                FROM restaurant_orders
                WHERE status = 'Completed'
                GROUP BY strftime('%Y-%m', order_time)
            )
            GROUP BY strftime('%m', order_time)
            ORDER BY month
        ''')

        monthly_data = cursor.fetchall()

        if not monthly_data:
            print("No historical data available for seasonal analysis.")
            conn.close()
            return

        # Calculate overall average
        total_avg = sum(row[1] for row in monthly_data) / len(monthly_data)

        print("Monthly Revenue Patterns:")
        print("-"*60)
        print(f"{'Month':<10} {'Avg Revenue':<15} {'vs Annual Avg':<15} {'Trend':<10}")
        print("-"*60)

        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

        peak_months = []
        low_months = []

        for month_num, avg_revenue, year_count in monthly_data:
            month_name = months[int(month_num) - 1]
            variance = ((avg_revenue - total_avg) / total_avg) * 100

            if variance > 10:
                trend = "📈 Peak"
                peak_months.append(month_name)
            elif variance < -10:
                trend = "📉 Low"
                low_months.append(month_name)
            else:
                trend = "➡️ Average"

            print(f"{month_name:<10} £{avg_revenue:<14,.0f} {variance:+6.1f}% {'':>7} {trend:<10}")

        print("-"*60)
        print(f"{'Annual Avg':<10} £{total_avg:<14,.0f}")

        # Seasonal insights
        print(f"\nSeasonal Insights:")
        print("-"*30)
        if peak_months:
            print(f"Peak Months: {', '.join(peak_months)}")
        if low_months:
            print(f"Low Months: {', '.join(low_months)}")

        # Day of week analysis
        cursor.execute('''
            SELECT 
                CASE strftime('%w', order_time)
                    WHEN '0' THEN 'Sunday'
                    WHEN '1' THEN 'Monday'
                    WHEN '2' THEN 'Tuesday'
                    WHEN '3' THEN 'Wednesday'
                    WHEN '4' THEN 'Thursday'
                    WHEN '5' THEN 'Friday'
                    WHEN '6' THEN 'Saturday'
                END as day_name,
                AVG(daily_revenue) as avg_daily_revenue
            FROM (
                SELECT 
                    order_time,
                    SUM(total_price) as daily_revenue
                FROM restaurant_orders
                WHERE status = 'Completed' AND order_time >= date('now', '-90 days')
                GROUP BY DATE(order_time)
            )
            GROUP BY strftime('%w', order_time)
            ORDER BY strftime('%w', order_time)
        ''')

        daily_data = cursor.fetchall()

        if daily_data:
            print(f"\nDay of Week Patterns (Last 90 Days):")
            print("-"*40)
            print(f"{'Day':<10} {'Avg Revenue':<15}")
            print("-"*40)

            for day, revenue in daily_data:
                print(f"{day:<10} £{revenue:<14,.0f}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in seasonal_analysis: {e}")
        print(f"An error occurred: {e}")

def growth_projections():
    """Growth projections - FIXED"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print(f"\n" + "="*80)
        print("GROWTH PROJECTIONS")
        print("="*80)

        # Calculate historical growth
        cursor.execute('''
            SELECT 
                strftime('%Y-%m', order_time) as month,
                SUM(total_price) as monthly_revenue,
                COUNT(*) as order_count,
                COUNT(DISTINCT customer_id) as unique_customers
            FROM restaurant_orders
            WHERE order_time >= date('now', '-12 months') AND status = 'Completed'
            GROUP BY strftime('%Y-%m', order_time)
            ORDER BY month
        ''')

        historical_data = cursor.fetchall()

        if len(historical_data) < 6:
            print("Insufficient data for growth projections (need at least 6 months).")
            conn.close()
            return

        # Calculate growth rates
        revenues = [row[1] for row in historical_data]
        orders = [row[2] for row in historical_data]
        customers = [row[3] for row in historical_data]

        # Calculate quarter-over-quarter growth
        if len(revenues) >= 6:
            q1_revenue = sum(revenues[-6:-3]) / 3
            q2_revenue = sum(revenues[-3:]) / 3
            revenue_growth = (q2_revenue - q1_revenue) / q1_revenue if q1_revenue > 0 else 0

            q1_orders = sum(orders[-6:-3]) / 3
            q2_orders = sum(orders[-3:]) / 3
            order_growth = (q2_orders - q1_orders) / q1_orders if q1_orders > 0 else 0

            q1_customers = sum(customers[-6:-3]) / 3
            q2_customers = sum(customers[-3:]) / 3
            customer_growth = (q2_customers - q1_customers) / q1_customers if q1_customers > 0 else 0
        else:
            revenue_growth = order_growth = customer_growth = 0.02

        print(f"Historical Growth Analysis:")
        print(f"Revenue Growth (quarterly): {revenue_growth*100:+.1f}%")
        print(f"Order Growth (quarterly): {order_growth*100:+.1f}%")
        print(f"Customer Growth (quarterly): {customer_growth*100:+.1f}%")

        # Project future growth scenarios
        current_revenue = revenues[-1] if revenues else 10000
        current_orders = orders[-1] if orders else 100
        current_customers = customers[-1] if customers else 50

        print(f"\n12-Month Growth Projections:")
        print("-"*80)
        print(f"{'Scenario':<15} {'Revenue Growth':<15} {'Projected Revenue':<20} {'Projected Orders':<15}")
        print("-"*80)

        scenarios = [
            ('Conservative', max(0, revenue_growth * 0.5)),
            ('Expected', revenue_growth),
            ('Optimistic', revenue_growth * 1.5),
            ('Aggressive', revenue_growth * 2.0)
        ]

        for scenario_name, growth_rate in scenarios:
            # Compound monthly growth
            monthly_growth = (1 + growth_rate) ** (1/3) - 1  # Quarterly to monthly
            projected_revenue = current_revenue * ((1 + monthly_growth) ** 12)
            projected_orders = current_orders * ((1 + order_growth/3) ** 12)

            print(f"{scenario_name:<15} {growth_rate*100:+6.1f}% {'':>8} £{projected_revenue:<19,.0f} {projected_orders:<14,.0f}")

        # Investment requirements
        print(f"\nGrowth Investment Analysis:")
        print("-"*50)

        target_growth = float(input("Enter target annual revenue growth (%, e.g., 25): ")) / 100

        # Estimate investment needed (simplified model)
        revenue_multiple = 1 + target_growth
        estimated_investment = current_revenue * target_growth * 0.3  # 30% of growth target

        print(f"\nTo achieve {target_growth*100:.0f}% revenue growth:")
        print(f"Target Revenue: £{current_revenue * revenue_multiple:,.0f}")
        print(f"Estimated Investment Needed: £{estimated_investment:,.0f}")
        print(f"\nInvestment areas to consider:")
        print("• Marketing and customer acquisition")
        print("• Staff expansion and training")
        print("• Equipment and infrastructure")
        print("• Menu development and innovation")
        print("• Technology improvements")

        conn.close()

    except Exception as e:
        logging.error(f"Error in growth_projections: {e}")
        print(f"An error occurred: {e}")
