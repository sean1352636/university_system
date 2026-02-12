from university_system.core.i18n import get_text


def debug_function_definition():
    """Debug the function definition issue"""

    print(get_text("email.misc.debugging_function_definition"))
    print("="*60)
    
    # Check 1: Look for syntax errors before the function
    print(get_text("email.misc.checking_syntax_errors"))
    
    # Check 2: Verify the function is actually being defined
    try:
        # This will tell us if the function exists in the current namespace
        from university_system.infrastructure.email import email_manager

        
        if hasattr(email_manager, 'display_chat_rooms_menu'):
            print(get_text("email.misc.function_exists"))
        else:
            print(get_text("email.misc.function_not_found"))
            
            # List all functions that start with 'display'
            display_functions = [name for name in dir(email_manager) if name.startswith('display')]
            print(get_text("email.misc.available_display_functions", functions=display_functions))
            
    except ImportError as e:
        print(get_text("email.misc.import_error", error=e))
    except Exception as e:
        print(get_text("email.misc.check_function_error", error=e))
    
    # Check 3: Look for common issues
    print(get_text("email.misc.common_issues_header"))
    print(get_text("email.misc.issue_syntax_error"))
    print(get_text("email.misc.issue_indentation"))
    print(get_text("email.misc.issue_decorator_import"))
    print(get_text("email.misc.issue_circular_import"))
    print(get_text("email.misc.issue_function_order"))
    
    # Check 4: Verify handle_exception decorator
    try:
        from university_system.infrastructure.email.email_manager import handle_exception
        print(get_text("email.misc.decorator_imported"))
    except ImportError:
        print(get_text("email.misc.decorator_not_found"))
    
    return True



def find_function_in_file(filename="email_manager.py"):
    """Search for the function definition in the file"""
    print(get_text("email.misc.searching_function", filename=filename))
    
    try:
        with open(filename, 'r') as f:
            lines = f.readlines()
        
        function_found = False
        function_line = None
        
        for i, line in enumerate(lines, 1):
            if 'def display_chat_rooms_menu' in line:
                function_found = True
                function_line = i
                print(f"✅ Found function definition at line {i}")
                
                # Check the lines around it for syntax issues
                start = max(0, i-5)
                end = min(len(lines), i+5)
                
                print("Context around function definition:")
                for j in range(start, end):
                    marker = " >>> " if j == i-1 else "     "
                    print(f"{marker}{j+1:4d}: {lines[j].rstrip()}")
                break
        
        if not function_found:
            print("❌ Function definition not found in file")
            
            # Search for similar function names
            similar_functions = []
            for i, line in enumerate(lines, 1):
                if 'def display_' in line and 'chat' in line.lower():
                    similar_functions.append((i, line.strip()))
            
            if similar_functions:
                print("Similar functions found:")
                for line_num, func_line in similar_functions:
                    print(f"  Line {line_num}: {func_line}")
        
        return function_found, function_line
        
    except FileNotFoundError:
        print(f"❌ File {filename} not found")
        return False, None
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False, None



def check_syntax_errors(filename="email_manager.py"):
    """Check for syntax errors in the file"""
    print(f"\n4. Checking for syntax errors in {filename}...")
    
    try:
        with open(filename, 'r') as f:
            content = f.read()
        
        # Try to compile the file
        compile(content, filename, 'exec')
        print("✅ No syntax errors found")
        return True
        
    except SyntaxError as e:
        print(f"❌ Syntax error found:")
        print(f"   Line {e.lineno}: {e.text}")
        print(f"   Error: {e.msg}")
        return False
    except Exception as e:
        print(f"❌ Error checking syntax: {e}")
        return False
