class Alumni:
    def __init__(self, alumni_id, student_id, email_address, title, first_name, middle_name,
                 last_name, gender, dob, graduation_year, degree_earned, current_employer,
                 job_title, industry, address, city, country, phone, linkedin_url,
                 date_registered, is_donor=False, is_mentor=False, is_board_member=False):

        self.alumni_id = alumni_id
        self.student_id = student_id
        self.email_address = email_address
        self.title = title
        self.first_name = first_name
        self.middle_name = middle_name
        self.last_name = last_name
        self.gender = gender
        self.dob = dob
        self.graduation_year = graduation_year
        self.degree_earned = degree_earned
        self.current_employer = current_employer
        self.job_title = job_title
        self.industry = industry
        self.address = address
        self.city = city
        self.country = country
        self.phone = phone
        self.linkedin_url = linkedin_url
        self.date_registered = date_registered
        self.is_donor = is_donor
        self.is_mentor = is_mentor
        self.is_board_member = is_board_member
