"""Miscellaneous utilities for the university system.

This module provides helper functions used internally by the email
manager and other components for debugging and code analysis.
"""

from __future__ import annotations

from typing import Any, Optional, List
import ast
import inspect
import re

__all__ = [
    'debug_function_definition', 'find_function_in_file', 'check_syntax_errors'
]


def debug_function_definition(func: Any, *args: Any, **kwargs: Any) -> None:
    """Debug a function definition by printing its signature and source.

    Args:
        func: The function object to debug
        *args: Additional arguments
        **kwargs: Additional keyword arguments
    """
    if not callable(func):
        print(f"Not a callable: {func}")
        return None

    try:
        # Get function name
        func_name = getattr(func, '__name__', str(func))

        # Get signature
        try:
            sig = inspect.signature(func)
            print(f"Function: {func_name}{sig}")
        except (ValueError, TypeError):
            print(f"Function: {func_name} (signature unavailable)")

        # Get docstring
        doc = inspect.getdoc(func)
        if doc:
            print(f"Docstring: {doc[:200]}..." if len(doc) > 200 else f"Docstring: {doc}")

        # Get source file
        try:
            source_file = inspect.getfile(func)
            print(f"Defined in: {source_file}")
        except (TypeError, OSError):
            pass

    except Exception as e:
        print(f"Error debugging function: {e}")

    return None


def find_function_in_file(file_path: str, function_name: str, *args: Any, **kwargs: Any) -> Optional[int]:
    """Find a function definition in a file and return its line number.

    Args:
        file_path: Path to the Python file
        function_name: Name of the function to find
        *args: Additional arguments
        **kwargs: Additional keyword arguments

    Returns:
        Line number where function is defined, or None if not found
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()

        # Parse the source code
        tree = ast.parse(source)

        # Find function definitions
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == function_name:
                    return node.lineno

        # Fallback: regex search if AST fails
        pattern = rf'^(\s*)def\s+{re.escape(function_name)}\s*\('
        for i, line in enumerate(source.split('\n'), 1):
            if re.match(pattern, line):
                return i

        return None

    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return None
    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}")
        return None
    except Exception as e:
        print(f"Error searching file: {e}")
        return None


def check_syntax_errors(source_code: str, *args: Any, **kwargs: Any) -> Optional[List[str]]:
    """Check Python source code for syntax errors.

    Args:
        source_code: Python source code as string or file path
        *args: Additional arguments
        **kwargs: Additional keyword arguments

    Returns:
        List of syntax error messages, or None if no errors
    """
    errors = []

    # Check if source_code is a file path
    try:
        if isinstance(source_code, str) and '\n' not in source_code and len(source_code) < 500:
            # Might be a file path
            try:
                with open(source_code, 'r', encoding='utf-8') as f:
                    source_code = f.read()
            except (FileNotFoundError, OSError):
                # Not a file path, treat as source code
                pass
    except Exception:
        pass

    # Check syntax using ast.parse
    try:
        ast.parse(source_code)
        return None  # No errors
    except SyntaxError as e:
        error_msg = f"Syntax error at line {e.lineno}: {e.msg}"
        if e.text:
            error_msg += f"\n  {e.text.strip()}"
            if e.offset:
                error_msg += f"\n  {' ' * (e.offset - 1)}^"
        errors.append(error_msg)
    except Exception as e:
        errors.append(f"Parse error: {str(e)}")

    return errors if errors else None