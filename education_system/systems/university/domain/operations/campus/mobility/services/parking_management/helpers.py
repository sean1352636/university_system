import os
from education_system.systems.university.infrastructure.i18n import get_text

_t = get_text


def get_file_path(file_format, default_filename):
    """Helper function to get file path from user with error handling"""
    while True:
        location_choice = input(f"Where would you like to save the {file_format} file?\n1. Current directory\n2. Custom path\nEnter your choice (1-2): ")

        if location_choice == '1':
            # Use current directory
            return os.path.join(os.getcwd(), default_filename)
        elif location_choice == '2':
            # Custom directory
            while True:
                custom_path = input("Enter the full path (including filename): ")
                directory = os.path.dirname(custom_path)

                # Check if directory exists or can be created
                if not directory:  # If no directory specified, use current directory
                    return custom_path

                if not os.path.exists(directory):
                    try_create = input(f"Directory {directory} does not exist. Create it? (y/n): ")
                    if try_create.lower() == 'y':
                        try:
                            os.makedirs(directory, exist_ok=True)
                            return custom_path
                        except OSError as e:
                            print(_t("parking.error.creating_directory") + f": {e}")
                            continue
                    else:
                        continue
                return custom_path
        else:
            print(_t("parking.error.invalid_choice_1_or_2"))
