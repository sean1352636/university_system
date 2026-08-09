def required(prompt):
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("A value is required.")

def integer(prompt, minimum=None):
    while True:
        try:
            value = int(input(prompt))
            if minimum is None or value >= minimum:
                return value
        except ValueError:
            pass
        print("Enter a valid number.")
