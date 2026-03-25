from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from education_system.university_system.core.sql_safety import validate_table_name, validate_identifier
import datetime
import json
import qrcode
import io
import base64


class AnalyticsMixin:
    def view_grade_analytics(self):
        """View grade trends and analytics"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view grade analytics.")
            return
        
        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('view_analytics'):
            print("You don't have permission to view analytics.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect child for grade analytics:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            
            if selected_child[6] == 'minimal':
                print("You have minimal access and cannot view analytics for this child.")
                return
            
            student_id = selected_child[0]
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                # Get grade analytics
                cursor.execute('''
                SELECT m.module_name, ga.assessment_date, ga.grade_value, ga.class_average, 
                       ga.percentile_rank, ga.trend_direction
                FROM grade_analytics ga
                JOIN modules m ON ga.module_code = m.module_code
                WHERE ga.student_id = ?
                ORDER BY m.module_name, ga.assessment_date DESC
                ''', (student_id,))
                
                analytics = cursor.fetchall()
                
                print(f"\nGrade Analytics for {selected_child[1]} {selected_child[3]}:")
                
                if not analytics:
                    print("No grade analytics available yet.")
                    return
                
                # Group by module
                modules = {}
                for analytic in analytics:
                    module_name = analytic[0]
                    if module_name not in modules:
                        modules[module_name] = []
                    modules[module_name].append(analytic[1:])
                
                for module_name, grades in modules.items():
                    print(f"\n{module_name}:")
                    
                    # Calculate module statistics
                    recent_grades = [float(g[1]) for g in grades[:5]]  # Last 5 grades
                    class_averages = [float(g[2]) for g in grades[:5] if g[2]]
                    
                    if recent_grades:
                        student_avg = sum(recent_grades) / len(recent_grades)
                        if class_averages:
                            class_avg = sum(class_averages) / len(class_averages)
                            performance = "Above" if student_avg > class_avg else "Below" if student_avg < class_avg else "At"
                            print(f"  Recent average: {student_avg:.1f} ({performance} class average of {class_avg:.1f})")
                    
                    # Show recent assessments
                    print("  Recent assessments:")
                    for grade in grades[:3]:
                        date, grade_value, class_average, percentile, trend = grade
                        trend_arrow = "↗️" if trend == "improving" else "↘️" if trend == "declining" else "➡️"
                        print(f"    {date}: {grade_value}% (class avg: {class_average}%) {trend_arrow}")
                        if percentile:
                            print(f"              Percentile rank: {percentile}")
                
                # Overall performance summary
                all_grades = [float(a[2]) for a in analytics]
                if all_grades:
                    overall_avg = sum(all_grades) / len(all_grades)
                    print(f"\nOverall Performance:")
                    print(f"Average across all subjects: {overall_avg:.1f}%")
                    
                    # Performance trend
                    recent_avg = sum(all_grades[:10]) / min(10, len(all_grades))
                    older_avg = sum(all_grades[-10:]) / min(10, len(all_grades))
                    
                    if len(all_grades) > 10:
                        if recent_avg > older_avg + 2:
                            print("Trend: Improving ↗️")
                        elif recent_avg < older_avg - 2:
                            print("Trend: Declining ↘️")
                        else:
                            print("Trend: Stable ➡️")
                
            except sqlite3.Error as e:
                print(f"Database error viewing analytics: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")

    def generate_qr_code(self):
        """Generate QR code for student pickup/identification"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to generate QR codes.")
            return
        
        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect child for QR code generation:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            student_id = selected_child[0]
            
            # Generate QR code data
            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            qr_data = {
                'student_id': student_id,
                'parent_id': parent_id,
                'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'type': 'pickup_authorization'
            }
            
            qr_string = json.dumps(qr_data)
            
            try:
                # Generate QR code
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(qr_string)
                qr.make(fit=True)
                
                # In a real implementation, you would save this as an image file
                print(f"\nQR Code generated for {selected_child[1]} {selected_child[3]}")
                print("QR Code data:", qr_string)
                print("This QR code can be used for secure student pickup.")
                print("Note: In a real implementation, this would generate an actual image file.")
                
            except Exception as e:
                print(f"Error generating QR code: {e}")
                print("QR code generation requires the qrcode library.")
            
        except (ValueError, IndexError):
            print("Invalid choice.")

    def export_child_data(self):
        """Export all data for a child (for data portability)"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to export data.")
            return
        
        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect child to export data for:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            student_id = selected_child[0]
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                export_data = {
                    'student_info': {
                        'student_id': student_id,
                        'name': f"{selected_child[1]} {selected_child[3]}",
                        'course': selected_child[4]
                    },
                    'export_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'data': {}
                }
                
                # Export various data types
                tables_to_export = [
                    ('grades', 'student_grades', 'student_id'),
                    ('attendance', 'attendance', 'student_id'),
                    ('assignments', 'homework_assignments', 'student_id'),
                    ('behavior', 'student_behavior', 'student_id'),
                    ('medical', 'student_medical_info', 'student_id'),
                    ('fees', 'student_fees', 'student_id'),
                    ('meal_transactions', 'transactions', 'student_id'),  # source_type='meal'
                    ('library', 'library_accounts', 'student_id'),
                    ('activities', 'student_activities', 'student_id')
                ]
                
                for data_type, table_name, id_column in tables_to_export:
                    try:
                        safe_table = validate_table_name(table_name, conn=conn)
                        safe_id_col = validate_identifier(id_column, "column")
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
                        if cursor.fetchone():
                            if data_type == 'meal_transactions':
                                cursor.execute("SELECT * FROM [" + safe_table + "] WHERE source_type = 'meal' AND [" + safe_id_col + "] = ?", (student_id,))
                            else:
                                cursor.execute("SELECT * FROM [" + safe_table + "] WHERE [" + safe_id_col + "] = ?", (student_id,))
                            rows = cursor.fetchall()

                            # Get column names
                            cursor.execute("PRAGMA table_info([" + safe_table + "])")
                            columns = [col[1] for col in cursor.fetchall()]
                            
                            # Convert to list of dictionaries
                            export_data['data'][data_type] = [
                                dict(zip(columns, row)) for row in rows
                            ]
                    except sqlite3.Error:
                        export_data['data'][data_type] = []
                
                # Generate export file content
                import json
                export_json = json.dumps(export_data, indent=2, default=str)
                
                print(f"\nData export completed for {selected_child[1]} {selected_child[3]}")
                print("Export file content (save as JSON file):")
                print("=" * 60)
                print(export_json)
                print("=" * 60)
                
                # Log the activity
                self.log_activity("data_export", f"Data exported for student {student_id}")
                
            except sqlite3.Error as e:
                print(f"Database error exporting data: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")
