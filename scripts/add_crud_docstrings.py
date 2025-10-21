#!/usr/bin/env python3
"""Script to add docstrings to remaining CRUD functions.

This script analyzes function signatures and adds appropriate Google Style
docstrings to undocumented functions in database/crud.py.
"""

import re
import ast
from pathlib import Path


def has_docstring(func_node):
    """Check if function has a docstring."""
    if (func_node.body and 
        isinstance(func_node.body[0], ast.Expr) and
        isinstance(func_node.body[0].value, ast.Constant) and
        isinstance(func_node.body[0].value.value, str)):
        return True
    return False


def generate_docstring(func_name, args, returns):
    """Generate appropriate docstring based on function name and signature."""
    
    # Common patterns
    if func_name.startswith('list_'):
        entity = func_name.replace('list_', '').replace('_', ' ')
        return f'''"""List all {entity}.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        
    Returns:
        List of {entity.title()} objects
    """'''
    
    elif func_name.startswith('fetch_'):
        entity = func_name.replace('fetch_', '').replace('_', ' ')
        return f'''"""Fetch {entity}.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        
    Returns:
        Requested {entity}
    """'''
    
    elif func_name.startswith('get_'):
        entity = func_name.replace('get_', '').replace('_', ' ')
        has_id = any('_id' in arg for arg in args)
        if has_id:
            return f'''"""Get {entity} by ID.
    
    Args:
        session: Async database session
        {args[1]}: ID to fetch
        
    Returns:
        {entity.title().replace(' ', '')} object or None
    """'''
        else:
            return f'''"""Get {entity}.
    
    Args:
        session: Async database session
        
    Returns:
        {entity.title().replace(' ', '')} object or None
    """'''
    
    elif func_name.startswith('create_') or func_name.startswith('add_'):
        entity = func_name.replace('create_', '').replace('add_', '').replace('_', ' ')
        return f'''"""Create new {entity}.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context
        
    Returns:
        Created {entity.title().replace(' ', '')} object
    """'''
    
    elif func_name.startswith('update_'):
        entity = func_name.replace('update_', '').replace('_', ' ')
        return f'''"""Update {entity}.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context
        
    Returns:
        Updated {entity.title().replace(' ', '')} object
    """'''
    
    elif func_name.startswith('delete_'):
        entity = func_name.replace('delete_', '').replace('_', ' ')
        return f'''"""Delete {entity}.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context
    """'''
    
    elif func_name.startswith('upsert_'):
        entity = func_name.replace('upsert_', '').replace('_', ' ')
        return f'''"""Create or update {entity}.
    
    Args:
        session: Async database session
        
    Returns:
        {entity.title().replace(' ', '')} object
    """'''
    
    else:
        # Generic docstring
        return f'''"""Perform {func_name.replace('_', ' ')} operation.
    
    Args:
        session: Async database session
    """'''


def main():
    """Main function."""
    crud_file = Path("database/crud.py")
    
    if not crud_file.exists():
        print(f"❌ File not found: {crud_file}")
        return 1
    
    content = crud_file.read_text()
    tree = ast.parse(content)
    
    functions_without_docstrings = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            if not has_docstring(node):
                args = [arg.arg for arg in node.args.args]
                returns = ast.unparse(node.returns) if node.returns else None
                functions_without_docstrings.append((node.name, args, returns, node.lineno))
    
    print(f"\n📊 Found {len(functions_without_docstrings)} functions without docstrings:\n")
    for name, args, returns, lineno in functions_without_docstrings:
        print(f"  Line {lineno}: {name}({', '.join(args)})")
    
    print(f"\n✅ Analysis complete!")
    print(f"\nTo add docstrings, manually update each function using the templates in templates.md")
    
    return 0


if __name__ == "__main__":
    exit(main())
