from .. import *  # shared compatibility dependencies

class PatientSummaryMixin:
        def _refresh_patient_info(self):
            if self.patient:
                info = f"Patient #: {self.patient['patient_number']} | Last Visit: {self.patient.get('last_visit', 'Never')}"
            else:
                info = _t("dentist.messages.not_registered")
            self.patient_info_label.config(text=info)

        def _refresh_profile(self):
            self.profile_text.delete("1.0", tk.END)
            if self.patient:
                profile = f"""Patient Number: {self.patient['patient_number']}
    Name: {self.patient['user_name']}
    Email: {self.patient.get('user_email', 'N/A')}
    Phone: {self.patient.get('user_phone', 'N/A')}
    Date of Birth: {self.patient.get('date_of_birth', 'N/A')}
    Allergies: {self.patient.get('allergies', 'None recorded')}
    Last Visit: {self.patient.get('last_visit', 'Never')}"""
                self.profile_text.insert("1.0", profile)
            else:
                self.profile_text.insert("1.0", _t("dentist.messages.not_registered"))
