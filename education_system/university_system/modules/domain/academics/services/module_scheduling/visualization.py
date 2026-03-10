from education_system.university_system.modules.shared.constants import paths
from .constants import DAYS_OF_WEEK, TIME_SLOTS
from datetime import datetime
import os
import matplotlib.pyplot as plt
import numpy as np


class VisualizationMixin:
    def generate_visual_timetable(self, entity_type, entity_id, output_path=None):
        """Generate a visual timetable using matplotlib"""
        # Get schedule data
        if entity_type == 'student':
            schedule_data = self._get_student_schedule_data(entity_id)
            title = f"Student {entity_id} Timetable"
        elif entity_type == 'instructor':
            schedule_data = self._get_instructor_schedule_data(entity_id)
            title = f"Instructor {entity_id} Timetable"
        else:
            print("Invalid entity type")
            return None

        if not schedule_data:
            print("No schedule data found")
            return None

        # Create figure
        fig, ax = plt.subplots(figsize=(12, 8))

        # Set up the grid
        days = DAYS_OF_WEEK
        times = TIME_SLOTS

        # Create a matrix for the schedule
        schedule_matrix = np.zeros((len(times), len(days)))
        schedule_text = {}

        # Color map for different session types
        colors = {
            'Lecture': '#FF6B6B',
            'Lab': '#4ECDC4',
            'Tutorial': '#45B7D1',
            'Seminar': '#96CEB4',
            'Workshop': '#FFEAA7'
        }

        # Fill the matrix
        for schedule in schedule_data:
            day_idx = days.index(schedule['day'])

            # Find the closest time slot
            start_time = schedule['start_time']
            closest_time_idx = 0
            min_diff = float('inf')

            for i, time_slot in enumerate(times):
                time_diff = abs(int(start_time[:2]) - int(time_slot[:2]))
                if time_diff < min_diff:
                    min_diff = time_diff
                    closest_time_idx = i

            schedule_matrix[closest_time_idx, day_idx] = 1
            schedule_text[(closest_time_idx, day_idx)] = {
                'module': schedule['module_code'],
                'type': schedule['session_type'],
                'room': schedule['room'],
                'time': f"{schedule['start_time']}-{schedule['end_time']}"
            }

        # Create the heatmap
        im = ax.imshow(schedule_matrix, cmap='Blues', aspect='auto', alpha=0.3)

        # Set ticks and labels
        ax.set_xticks(range(len(days)))
        ax.set_yticks(range(len(times)))
        ax.set_xticklabels(days)
        ax.set_yticklabels(times)

        # Add text annotations
        for (time_idx, day_idx), info in schedule_text.items():
            session_type = info['type']
            color = colors.get(session_type, '#95A5A6')

            # Create a colored rectangle
            rect = plt.Rectangle((day_idx-0.4, time_idx-0.4), 0.8, 0.8,
                               facecolor=color, alpha=0.7, edgecolor='black')
            ax.add_patch(rect)

            # Add text
            ax.text(day_idx, time_idx-0.2, info['module'],
                   ha='center', va='center', fontweight='bold', fontsize=10)
            ax.text(day_idx, time_idx, info['type'],
                   ha='center', va='center', fontsize=8)
            ax.text(day_idx, time_idx+0.2, info['room'],
                   ha='center', va='center', fontsize=7)

        # Customize the plot
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Days of Week', fontsize=12)
        ax.set_ylabel('Time Slots', fontsize=12)

        # Add grid
        ax.set_xticks(np.arange(-0.5, len(days), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, len(times), 1), minor=True)
        ax.grid(which='minor', color='gray', linestyle='-', linewidth=0.5)

        # Add legend
        legend_elements = [plt.Rectangle((0,0),1,1, facecolor=color, alpha=0.7, label=session_type)
                          for session_type, color in colors.items()]
        ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1.05, 1))

        plt.tight_layout()

        # Save the plot
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = paths.ANALYTICS_DIR / f"{entity_type}_{entity_id}_visual_timetable_{timestamp}.png"

        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

        print(f"Visual timetable saved: {output_path}")
        return output_path

    def generate_utilization_charts(self):
        """Generate utilization charts and graphs"""
        # Room utilization chart
        room_data = self.generate_room_utilization_report(output_format='data')

        if room_data:
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))

            # Room utilization bar chart
            rooms = [r['Room'] for r in room_data[:10]]  # Top 10 rooms
            utilization = [r['Utilization Rate (%)'] for r in room_data[:10]]

            ax1.bar(rooms, utilization, color='skyblue')
            ax1.set_title('Room Utilization Rates (Top 10)')
            ax1.set_xlabel('Rooms')
            ax1.set_ylabel('Utilization Rate (%)')
            ax1.tick_params(axis='x', rotation=45)

            # Room type distribution pie chart
            type_counts = {}
            for room in room_data:
                room_type = room['Type']
                type_counts[room_type] = type_counts.get(room_type, 0) + 1

            ax2.pie(type_counts.values(), labels=type_counts.keys(), autopct='%1.1f%%')
            ax2.set_title('Room Type Distribution')

            # Capacity vs Utilization scatter plot
            capacities = [r['Capacity'] for r in room_data]
            utilizations = [r['Utilization Rate (%)'] for r in room_data]

            ax3.scatter(capacities, utilizations, alpha=0.6)
            ax3.set_title('Room Capacity vs Utilization')
            ax3.set_xlabel('Room Capacity')
            ax3.set_ylabel('Utilization Rate (%)')

            # Session duration histogram
            durations = [r['Avg Duration (min)'] for r in room_data if r['Avg Duration (min)'] > 0]

            ax4.hist(durations, bins=10, color='lightgreen', alpha=0.7)
            ax4.set_title('Average Session Duration Distribution')
            ax4.set_xlabel('Duration (minutes)')
            ax4.set_ylabel('Number of Rooms')

            plt.tight_layout()

            # Save the charts
            from education_system.university_system.modules.shared.constants import paths
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            chart_path = os.path.join(str(paths.ANALYTICS_DIR), f"utilization_charts_{timestamp}.png")

            # Ensure directory exists (already created via paths._ensure)
            os.makedirs(str(paths.ANALYTICS_DIR), exist_ok=True)

            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            plt.close()

            print(f"Utilization charts saved: {chart_path}")
            return chart_path
