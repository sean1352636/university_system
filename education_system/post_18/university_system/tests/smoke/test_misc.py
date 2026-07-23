"""
Comprehensive test suite for misc.py

Tests all functions and functionality including:
- debug_function_definition function
- find_function_in_file function
- check_syntax_errors function
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock

# Import the module under test
from education_system.post_18.university_system.modules.shared.utils import misc
from education_system.post_18.university_system.modules.shared.utils.misc import (
    debug_function_definition,
    find_function_in_file,
    check_syntax_errors,
)


class TestDebugFunctionDefinition:
    """Test debug_function_definition function"""

    @patch('builtins.print')
    def test_debug_function_definition_with_function(self, mock_print):
        """Test debug_function_definition with a real function"""
        def test_func(a, b, c=None):
            """Test docstring"""
            return a + b

        result = debug_function_definition(test_func)
        assert result is None
        assert mock_print.called

    @patch('builtins.print')
    def test_debug_function_definition_with_lambda(self, mock_print):
        """Test debug_function_definition with a lambda"""
        test_lambda = lambda x: x * 2

        result = debug_function_definition(test_lambda)
        assert result is None

    @patch('builtins.print')
    def test_debug_function_definition_with_builtin(self, mock_print):
        """Test debug_function_definition with a builtin function"""
        result = debug_function_definition(len)
        assert result is None
        assert mock_print.called

    @patch('builtins.print')
    def test_debug_function_definition_with_non_callable(self, mock_print):
        """Test debug_function_definition with non-callable"""
        result = debug_function_definition("not a function")
        assert result is None
        mock_print.assert_called_with("Not a callable: not a function")

    @patch('builtins.print')
    def test_debug_function_definition_with_method(self, mock_print):
        """Test debug_function_definition with a method"""
        class TestClass:
            def test_method(self, x):
                """Method docstring"""
                return x

        obj = TestClass()
        result = debug_function_definition(obj.test_method)
        assert result is None

    @patch('builtins.print')
    def test_debug_function_definition_with_class(self, mock_print):
        """Test debug_function_definition with a class"""
        class TestClass:
            """Class docstring"""
            pass

        result = debug_function_definition(TestClass)
        assert result is None

    @patch('builtins.print')
    def test_debug_function_definition_with_long_docstring(self, mock_print):
        """Test debug_function_definition with long docstring"""
        def test_func():
            """This is a very long docstring that exceeds 200 characters.
            It should be truncated when displayed by the debug_function_definition function.
            The function will add ellipsis at the end to indicate that the docstring was truncated.
            This is the complete docstring."""
            pass

        result = debug_function_definition(test_func)
        assert result is None

    @patch('builtins.print')
    def test_debug_function_definition_with_no_docstring(self, mock_print):
        """Test debug_function_definition with function without docstring"""
        def test_func():
            pass

        result = debug_function_definition(test_func)
        assert result is None

    @patch('builtins.print')
    def test_debug_function_definition_with_args_kwargs(self, mock_print):
        """Test debug_function_definition with extra args and kwargs"""
        def test_func():
            pass

        result = debug_function_definition(test_func, 'arg1', 'arg2', key='value')
        assert result is None


class TestFindFunctionInFile:
    """Test find_function_in_file function"""

    @pytest.fixture
    def temp_python_file(self):
        """Create a temporary Python file for testing"""
        content = '''
def first_function(a, b):
    """First function"""
    return a + b

class TestClass:
    def method_one(self):
        pass

def second_function(x):
    """Second function"""
    return x * 2

async def async_function():
    """Async function"""
    pass
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(content)
            temp_file = f.name

        yield temp_file

        # Cleanup
        try:
            os.remove(temp_file)
        except (OSError, IOError):
            pass

    def test_find_function_in_file_basic(self, temp_python_file):
        """Test finding a function in a file"""
        line_number = find_function_in_file(temp_python_file, 'first_function')
        assert line_number is not None
        assert isinstance(line_number, int)

    def test_find_function_in_file_async(self, temp_python_file):
        """Test finding an async function"""
        line_number = find_function_in_file(temp_python_file, 'async_function')
        assert line_number is not None

    def test_find_function_in_file_method(self, temp_python_file):
        """Test finding a class method"""
        line_number = find_function_in_file(temp_python_file, 'method_one')
        assert line_number is not None

    def test_find_function_in_file_not_found(self, temp_python_file):
        """Test finding a non-existent function"""
        line_number = find_function_in_file(temp_python_file, 'nonexistent_function')
        assert line_number is None

    def test_find_function_in_file_nonexistent_file(self):
        """Test with non-existent file"""
        line_number = find_function_in_file('/nonexistent/file.py', 'some_function')
        assert line_number is None

    @patch('builtins.print')
    def test_find_function_in_file_syntax_error(self, mock_print):
        """Test with file containing syntax errors"""
        content = '''
def broken_function(
    # Missing closing parenthesis and colon
    return 42
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(content)
            temp_file = f.name

        try:
            line_number = find_function_in_file(temp_file, 'broken_function')
            # Should handle syntax error gracefully
        finally:
            os.remove(temp_file)

    def test_find_function_in_file_with_args_kwargs(self, temp_python_file):
        """Test find_function_in_file with extra args and kwargs"""
        line_number = find_function_in_file(
            temp_python_file,
            'first_function',
            'arg1',
            key='value'
        )
        assert line_number is not None

    def test_find_function_in_file_special_chars_in_name(self):
        """Test finding function with special characters requiring escaping"""
        content = '''
def _private_function():
    pass

def function_with_underscores():
    pass
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(content)
            temp_file = f.name

        try:
            line_number = find_function_in_file(temp_file, '_private_function')
            assert line_number is not None

            line_number = find_function_in_file(temp_file, 'function_with_underscores')
            assert line_number is not None
        finally:
            os.remove(temp_file)


class TestCheckSyntaxErrors:
    """Test check_syntax_errors function"""

    def test_check_syntax_errors_valid_code(self):
        """Test with valid Python code"""
        valid_code = '''
def hello():
    return "Hello, World!"

class MyClass:
    pass
'''
        result = check_syntax_errors(valid_code)
        assert result is None

    def test_check_syntax_errors_invalid_code(self):
        """Test with invalid Python code"""
        invalid_code = '''
def broken_function(
    return 42
'''
        result = check_syntax_errors(invalid_code)
        assert result is not None
        assert isinstance(result, list)
        assert len(result) > 0

    def test_check_syntax_errors_missing_colon(self):
        """Test with missing colon"""
        invalid_code = '''
def test()
    pass
'''
        result = check_syntax_errors(invalid_code)
        assert result is not None
        assert isinstance(result, list)

    def test_check_syntax_errors_indentation_error(self):
        """Test with indentation error"""
        invalid_code = '''
def test():
pass
'''
        result = check_syntax_errors(invalid_code)
        assert result is not None

    def test_check_syntax_errors_empty_string(self):
        """Test with empty string"""
        result = check_syntax_errors('')
        assert result is None

    def test_check_syntax_errors_single_line(self):
        """Test with single line of code"""
        result = check_syntax_errors('x = 42')
        assert result is None

    def test_check_syntax_errors_from_file(self):
        """Test reading code from file"""
        content = '''
def valid_function():
    return True
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(content)
            temp_file = f.name

        try:
            result = check_syntax_errors(temp_file)
            assert result is None
        finally:
            os.remove(temp_file)

    def test_check_syntax_errors_invalid_file(self):
        """Test with invalid file content"""
        content = '''
def broken():
    return
        x = 1
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(content)
            temp_file = f.name

        try:
            result = check_syntax_errors(temp_file)
            # Should check syntax of file content
        finally:
            os.remove(temp_file)

    def test_check_syntax_errors_multiline_code(self):
        """Test with multiline valid code"""
        code = '''
class TestClass:
    def __init__(self):
        self.value = 0

    def increment(self):
        self.value += 1
        return self.value
'''
        result = check_syntax_errors(code)
        assert result is None

    def test_check_syntax_errors_with_args_kwargs(self):
        """Test check_syntax_errors with extra args and kwargs"""
        result = check_syntax_errors('x = 1', 'arg1', key='value')
        assert result is None

    def test_check_syntax_errors_unclosed_string(self):
        """Test with unclosed string"""
        invalid_code = '''
x = "unclosed string
y = 42
'''
        result = check_syntax_errors(invalid_code)
        assert result is not None

    def test_check_syntax_errors_missing_parenthesis(self):
        """Test with missing parenthesis"""
        invalid_code = '''
result = (1 + 2 + 3
'''
        result = check_syntax_errors(invalid_code)
        assert result is not None


class TestModuleExports:
    """Test module exports"""

    def test_module_has_all(self):
        """Test that module defines __all__"""
        assert hasattr(misc, '__all__')

    def test_all_contains_expected_functions(self):
        """Test that __all__ contains expected function names"""
        expected = [
            'debug_function_definition',
            'find_function_in_file',
            'check_syntax_errors'
        ]
        for name in expected:
            assert name in misc.__all__

    def test_exported_functions_are_callable(self):
        """Test that all exported functions are callable"""
        for name in misc.__all__:
            func = getattr(misc, name)
            assert callable(func)


class TestEdgeCases:
    """Test edge cases and error handling"""

    @patch('builtins.print')
    def test_debug_function_definition_with_none(self, mock_print):
        """Test debug_function_definition with None"""
        result = debug_function_definition(None)
        assert result is None

    @patch('builtins.print')
    def test_debug_function_definition_with_integer(self, mock_print):
        """Test debug_function_definition with integer"""
        result = debug_function_definition(42)
        assert result is None

    def test_find_function_in_file_empty_string(self):
        """Test find_function_in_file with empty filename"""
        result = find_function_in_file('', 'some_function')
        assert result is None

    def test_check_syntax_errors_unicode_code(self):
        """Test check_syntax_errors with unicode characters"""
        code = '''
def greet(name):
    return f"Hello, {name}! 你好"
'''
        result = check_syntax_errors(code)
        assert result is None

    def test_check_syntax_errors_complex_syntax(self):
        """Test with complex valid Python syntax"""
        code = '''
from typing import List, Dict, Optional

def process(data: List[Dict[str, int]]) -> Optional[int]:
    return sum(d.get('value', 0) for d in data)

async def async_process():
    async with some_context() as ctx:
        await ctx.do_something()
'''
        # Note: This might fail due to undefined names, but syntax should be valid
        result = check_syntax_errors(code)
        assert result is None


class TestIntegration:
    """Integration tests for misc utilities"""

    @patch('builtins.print')
    def test_debug_and_find_workflow(self, mock_print):
        """Test debugging a function and finding it in a file"""
        # Create a test function
        def test_function(x, y):
            """Test function for integration test"""
            return x + y

        # Debug it
        debug_function_definition(test_function)

        # Create a file with the function
        content = '''
def test_function(x, y):
    """Test function for integration test"""
    return x + y
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(content)
            temp_file = f.name

        try:
            # Find it in the file
            line_number = find_function_in_file(temp_file, 'test_function')
            assert line_number is not None

            # Check syntax
            result = check_syntax_errors(temp_file)
            assert result is None
        finally:
            os.remove(temp_file)

    def test_check_and_find_workflow(self):
        """Test checking syntax and finding functions"""
        content = '''
def valid_func():
    return True

def another_func(a, b):
    return a + b
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(content)
            temp_file = f.name

        try:
            # Check syntax
            errors = check_syntax_errors(temp_file)
            assert errors is None

            # Find functions
            line1 = find_function_in_file(temp_file, 'valid_func')
            line2 = find_function_in_file(temp_file, 'another_func')

            assert line1 is not None
            assert line2 is not None
            assert line1 < line2
        finally:
            os.remove(temp_file)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
