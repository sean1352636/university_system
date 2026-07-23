from datetime import datetime, timedelta
import numpy as np

from education_system.post_18.university_system.infrastructure.database.db import get_connection


class CashFlowForecaster:
    """Advanced cash flow forecasting with seasonal patterns"""

    def __init__(self):
        self.seasonal_factors = {
            '09': 1.5,  # September - high enrollment
            '10': 1.2,  # October
            '11': 1.0,  # November
            '12': 0.8,  # December - holidays
            '01': 1.3,  # January - spring enrollment
            '02': 1.1,  # February
            '03': 1.0,  # March
            '04': 0.9,  # April
            '05': 0.7,  # May - end of semester
            '06': 0.5,  # June - summer break
            '07': 0.4,  # July - summer break
            '08': 0.8   # August - pre-enrollment
        }

    def generate_cash_flow_forecast(self, months_ahead=12):
        """Generate detailed cash flow forecast"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get historical monthly payment data
            cursor.execute('''
            SELECT
                strftime('%Y-%m', payment_date) as month,
                SUM(amount) as total_payments,
                COUNT(*) as payment_count,
                AVG(amount) as avg_payment
            FROM payments
            WHERE payment_date > date('now', '-24 months')
            GROUP BY month
            ORDER BY month
            ''')

            historical_data = cursor.fetchall()

            if not historical_data:
                conn.close()
                return None

            # Calculate baseline and trends
            monthly_amounts = [row[1] for row in historical_data]
            baseline_monthly = np.mean(monthly_amounts)

            # Simple trend calculation
            months = list(range(len(monthly_amounts)))
            trend = np.polyfit(months, monthly_amounts, 1)[0] if len(months) > 1 else 0

            # Generate forecast
            forecast_data = []
            current_date = datetime.now()

            for i in range(months_ahead):
                forecast_month = current_date + timedelta(days=30 * i)
                month_key = forecast_month.strftime('%m')

                # Apply seasonal factor and trend
                seasonal_factor = self.seasonal_factors.get(month_key, 1.0)
                forecast_amount = (baseline_monthly + trend * i) * seasonal_factor

                # Add some randomness for realism (in production, use more sophisticated methods)
                forecast_amount *= np.random.normal(1.0, 0.1)
                forecast_amount = max(0, forecast_amount)  # Ensure non-negative

                forecast_data.append({
                    'month': forecast_month.strftime('%Y-%m'),
                    'forecast_amount': forecast_amount,
                    'seasonal_factor': seasonal_factor,
                    'confidence': max(0.5, 1.0 - (i * 0.05))  # Decreasing confidence over time
                })

            # Get current outstanding balance
            cursor.execute('''
            SELECT SUM(amount) FROM student_fees WHERE status != 'paid'
            ''')
            outstanding_balance = cursor.fetchone()[0] or 0

            # Calculate cumulative cash flow
            cumulative_cash = 0
            for item in forecast_data:
                cumulative_cash += item['forecast_amount']
                item['cumulative_cash'] = cumulative_cash
                item['collection_rate'] = min(100, (cumulative_cash / outstanding_balance * 100)) if outstanding_balance > 0 else 100

            conn.close()

            return {
                'forecast_data': forecast_data,
                'baseline_monthly': baseline_monthly,
                'trend': trend,
                'outstanding_balance': outstanding_balance,
                'historical_data': historical_data
            }

        except Exception as e:
            print(f"Error generating cash flow forecast: {e}")
            return None
