"""
Property-based tests for Clean Architecture directory structure.

Feature: clean-architecture-phase1, Property 2: Directory Structure Completeness
Validates: Requirements 2.5
"""
import os
from pathlib import Path

from hypothesis import given, strategies as st, settings


# Define all expected directories in src/ structure
EXPECTED_DIRECTORIES = [
    "src",
    "src/domain",
    "src/domain/entities",
    "src/domain/interfaces",
    "src/application",
    "src/application/services",
    "src/application/dto",
    "src/infrastructure",
    "src/infrastructure/repositories",
    "src/infrastructure/persistence",
    "src/infrastructure/logging",
    "src/infrastructure/cache",
    "src/presentation",
    "src/presentation/api",
    "src/presentation/handlers",
]


def get_project_root() -> Path:
    """Get the project root directory."""
    # Navigate from tests/unit/ to project root
    return Path(__file__).parent.parent.parent


@given(directory=st.sampled_from(EXPECTED_DIRECTORIES))
@settings(max_examples=100)
def test_directory_contains_init_py(directory: str) -> None:
    """
    Property 2: Directory Structure Completeness
    
    For any directory in the src/ structure, that directory SHALL contain
    an __init__.py file for proper Python packaging.
    
    Feature: clean-architecture-phase1, Property 2: Directory Structure Completeness
    Validates: Requirements 2.5
    """
    project_root = get_project_root()
    dir_path = project_root / directory
    init_file = dir_path / "__init__.py"
    
    assert dir_path.exists(), f"Directory {directory} does not exist"
    assert dir_path.is_dir(), f"{directory} is not a directory"
    assert init_file.exists(), f"__init__.py missing in {directory}"
    assert init_file.is_file(), f"__init__.py in {directory} is not a file"


def test_all_src_subdirectories_have_init() -> None:
    """
    Verify that ALL subdirectories under src/ have __init__.py files.
    This is a comprehensive check beyond the property test.
    """
    project_root = get_project_root()
    src_path = project_root / "src"
    
    missing_init = []
    
    for root, dirs, files in os.walk(src_path):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        
        if "__init__.py" not in files:
            rel_path = os.path.relpath(root, project_root)
            missing_init.append(rel_path)
    
    assert not missing_init, f"Missing __init__.py in directories: {missing_init}"


def test_expected_directories_exist() -> None:
    """Verify all expected directories exist."""
    project_root = get_project_root()
    
    missing_dirs = []
    for directory in EXPECTED_DIRECTORIES:
        dir_path = project_root / directory
        if not dir_path.exists():
            missing_dirs.append(directory)
    
    assert not missing_dirs, f"Missing directories: {missing_dirs}"
