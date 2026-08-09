"""Students tab mixin for LayoutManager."""


class StudentsMixin:
    """Students tab (delegates to main GUI)."""

    def create_students_tab(self):
        """Create students tab"""
        try:
            if hasattr(self.gui, 'create_students_tab'):
                self.gui.create_students_tab()
            else:
                self._create_placeholder_tab('students', '\U0001f464 Students')
        except Exception as e:
            print(f"Error creating students tab: {e}")
            self._create_placeholder_tab('students', '\U0001f464 Students')
