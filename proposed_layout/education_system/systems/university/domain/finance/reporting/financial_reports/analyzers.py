from datetime import datetime

from education_system.systems.university.infrastructure.database.db import get_connection


class StudentLifecycleAnalyzer:
    """Analyze student financial behavior throughout their lifecycle"""

    def analyze_student_lifecycle(self):
        """Comprehensive student lifecycle financial analysis"""
        import pandas as pd
        try:
            conn = get_connection()

            # Use a simpler query that doesn't rely on columns that may not exist
            query = '''
            SELECT
                s.student_id,
                s.first_name,
                s.last_name,
                COALESCE(s.status, 'active') as status,
                COALESCE(SUM(sf.amount), 0) as total_fees,
                COALESCE(SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END), 0) as paid_fees,
                COALESCE(COUNT(p.payment_id), 0) as payment_count,
                COALESCE(AVG(p.amount), 0) as avg_payment,
                COALESCE(SUM(ss.amount), 0) as scholarship_amount,
                365 as days_enrolled
            FROM students s
            LEFT JOIN student_fees sf ON s.student_id = sf.student_id
            LEFT JOIN payments p ON s.student_id = p.student_id
            LEFT JOIN student_scholarships ss ON s.student_id = ss.student_id
            GROUP BY s.student_id
            HAVING total_fees > 0
            '''

            df = pd.read_sql_query(query, conn)
            conn.close()

            if len(df) == 0:
                return None

            # Calculate lifecycle metrics
            df['collection_rate'] = (df['paid_fees'] / df['total_fees'] * 100).fillna(0)
            df['payment_frequency'] = (df['payment_count'] / (df['days_enrolled'] / 365)).fillna(0)
            df['scholarship_percentage'] = (df['scholarship_amount'] / df['total_fees'] * 100).fillna(0)
            df['years_enrolled'] = df['days_enrolled'] / 365

            # Categorize students by lifecycle stage
            def get_lifecycle_stage(row):
                if row['status'] == 'graduated':
                    return 'Graduated'
                elif row['status'] == 'dropped':
                    return 'Dropped Out'
                elif row['years_enrolled'] > 4:
                    return 'Extended Stay'
                elif row['years_enrolled'] > 2:
                    return 'Mid-Program'
                else:
                    return 'Early Program'

            df['lifecycle_stage'] = df.apply(get_lifecycle_stage, axis=1)

            # Analyze by lifecycle stage
            lifecycle_analysis = df.groupby('lifecycle_stage').agg({
                'collection_rate': ['mean', 'std', 'count'],
                'payment_frequency': 'mean',
                'scholarship_percentage': 'mean',
                'total_fees': 'mean',
                'avg_payment': 'mean'
            }).round(2)

            return {
                'student_data': df,
                'lifecycle_analysis': lifecycle_analysis,
                'summary_stats': {
                    'total_students': len(df),
                    'avg_collection_rate': df['collection_rate'].mean(),
                    'high_risk_students': len(df[df['collection_rate'] < 50]),
                    'scholarship_recipients': len(df[df['scholarship_amount'] > 0])
                }
            }

        except Exception as e:
            print(f"Error analyzing student lifecycle: {e}")
            return None


class ComparativeAnalyzer:
    """Comparative analysis tools for financial performance"""

    def year_over_year_analysis(self):
        """Compare financial performance year over year"""
        try:
            conn = get_connection()

            # Get data for last 3 academic years
            current_year = datetime.now().year
            years = [f"{current_year-2}-{current_year-1}", f"{current_year-1}-{current_year}", f"{current_year}-{current_year+1}"]

            yoy_data = {}

            for year in years:
                cursor = conn.cursor()

                # Revenue data
                cursor.execute('''
                SELECT
                    SUM(sf.amount) as total_expected,
                    SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as total_collected
                FROM student_fees sf
                JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                WHERE ft.academic_year = ?
                ''', (year,))

                revenue_data = cursor.fetchone()

                # Student count
                cursor.execute('''
                SELECT COUNT(DISTINCT sf.student_id)
                FROM student_fees sf
                JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                WHERE ft.academic_year = ?
                ''', (year,))

                student_count = cursor.fetchone()[0] or 0

                yoy_data[year] = {
                    'total_expected': revenue_data[0] or 0,
                    'total_collected': revenue_data[1] or 0,
                    'collection_rate': (revenue_data[1] / revenue_data[0] * 100) if revenue_data[0] else 0,
                    'student_count': student_count,
                    'revenue_per_student': (revenue_data[0] / student_count) if student_count else 0
                }

            conn.close()
            return yoy_data

        except Exception as e:
            print(f"Error in year-over-year analysis: {e}")
            return {}

    def department_comparison(self):
        """Compare financial performance by department/program"""
        import pandas as pd
        try:
            conn = get_connection()

            # Use fee_type as department proxy since major column may not exist
            query = '''
            SELECT
                COALESCE(ft.fee_name, 'General') as department,
                COUNT(DISTINCT s.student_id) as student_count,
                COALESCE(SUM(sf.amount), 0) as total_fees,
                COALESCE(SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END), 0) as collected_fees,
                COALESCE(AVG(sf.amount), 0) as avg_fee_per_student,
                COALESCE(SUM(ss.amount), 0) as total_scholarships
            FROM students s
            LEFT JOIN student_fees sf ON s.student_id = sf.student_id
            LEFT JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
            LEFT JOIN student_scholarships ss ON s.student_id = ss.student_id
            WHERE sf.amount IS NOT NULL
            GROUP BY ft.fee_name
            HAVING student_count > 0
            ORDER BY total_fees DESC
            '''

            df = pd.read_sql_query(query, conn)
            conn.close()

            if len(df) == 0:
                return None

            df['collection_rate'] = (df['collected_fees'] / df['total_fees'] * 100).fillna(0)
            df['scholarship_rate'] = (df['total_scholarships'] / df['total_fees'] * 100).fillna(0)

            return df

        except Exception as e:
            print(f"Error in department comparison: {e}")
            return None
