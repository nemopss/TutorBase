"""Tests for database utility functions.

Note: Input validation tests have been moved to test_schemas.py as validation
is now handled by Pydantic schemas at the API boundary. This file only tests
database-specific utilities like SQL LIKE pattern escaping.
"""

import pytest
from database.validators import escape_like_pattern


class TestEscapeLikePattern:
    """Tests for escape_like_pattern function to prevent LIKE injection."""
    
    def test_escape_percent(self):
        """Test that % is properly escaped."""
        assert escape_like_pattern("50% off") == "50\\% off"
        assert escape_like_pattern("100%") == "100\\%"
        assert escape_like_pattern("%") == "\\%"
    
    def test_escape_underscore(self):
        """Test that _ is properly escaped."""
        assert escape_like_pattern("user_name") == "user\\_name"
        assert escape_like_pattern("test_123_abc") == "test\\_123\\_abc"
        assert escape_like_pattern("_") == "\\_"
    
    def test_escape_backslash(self):
        """Test that \\ is properly escaped."""
        assert escape_like_pattern("path\\to\\file") == "path\\\\to\\\\file"
        assert escape_like_pattern("\\") == "\\\\"
    
    def test_escape_combined(self):
        """Test escaping multiple special characters together."""
        assert escape_like_pattern("50%_off\\sale") == "50\\%\\_off\\\\sale"
        assert escape_like_pattern("%_\\") == "\\%\\_\\\\"
    
    def test_normal_text(self):
        """Test that normal text is not modified."""
        assert escape_like_pattern("normal text") == "normal text"
        assert escape_like_pattern("hello world") == "hello world"
        assert escape_like_pattern("123 abc") == "123 abc"
    
    def test_empty_string(self):
        """Test that empty string is handled correctly."""
        assert escape_like_pattern("") == ""
    
    def test_unicode(self):
        """Test that Unicode characters are preserved."""
        assert escape_like_pattern("Привет мир") == "Привет мир"
        assert escape_like_pattern("50% скидка") == "50\\% скидка"
    
    def test_sql_injection_attempts(self):
        """Test that common SQL injection patterns are escaped."""
        # These should be escaped and won't work as wildcards
        assert escape_like_pattern("%%") == "\\%\\%"
        assert escape_like_pattern("___") == "\\_\\_\\_"
        assert escape_like_pattern("%admin%") == "\\%admin\\%"
        assert escape_like_pattern("a%b_c\\d") == "a\\%b\\_c\\\\d"
