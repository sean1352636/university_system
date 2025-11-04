def debug_function_definition():
    """Debug the function definition issue"""
    
    print("Debugging display_chat_rooms_menu function definition...")
    print("="*60)
    
    # Check 1: Look for syntax errors before the function
    print("1. Checking for syntax errors that might prevent function definition...")
    
    # Check 2: Verify the function is actually being defined
    try:
        # This will tell us if the function exists in the current namespace
        from university_system.infrastructure.email import email_manager

        
        if hasattr(email_manager, 'display_chat_rooms_menu'):
            print("✅ display_chat_rooms_menu exists in email_manager module")
        else:
            print("❌ display_chat_rooms_menu NOT found in email_manager module")
            
            # List all functions that start with 'display'
            display_functions = [name for name in dir(email_manager) if name.startswith('display')]
            print(f"Available display functions: {display_functions}")
            
    except ImportError as e:
        print(f"❌ Could not import email_manager: {e}")
    except Exception as e:
        print(f"❌ Error checking function: {e}")
    
    # Check 3: Look for common issues
    print("\n2. Common issues that cause NameError:")
    print("   - Syntax error before the function definition")
    print("   - Incorrect indentation (function inside class/other function)")
    print("   - Missing @handle_exception decorator import")
    print("   - Circular import issues")
    print("   - Function defined after it's called")
    
    # Check 4: Verify handle_exception decorator
    try:
        from university_system.infrastructure.email.email_manager import handle_exception
        print("✅ handle_exception decorator imported successfully")
    except ImportError:
        print("❌ handle_exception decorator not found - this could be the issue!")
    
    return True



def find_function_in_file(filename="email_manager.py"):
    """Search for the function definition in the file"""
    print(f"\n3. Searching for function definition in {filename}...")
    
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
