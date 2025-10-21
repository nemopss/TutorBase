"""Tests for database validators including LIKE escape functionality."""

import pytest
from database.validators import (
    escape_like_pattern,
    ensure_positive_int,
    ensure_non_empty,
    ensure_valid_timezone,
    ensure_in_list,
    ensure_positive_int_or_none,
)


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


class TestEnsurePositiveInt:
    """Tests for ensure_positive_int validator."""
    
    def test_valid_positive_int(self):
        assert ensure_positive_int(1, "test") == 1
        assert ensure_positive_int(100, "test") == 100
    
    def test_zero_raises_error(self):
        with pytest.raises(ValueError, match="must be a positive integer"):
            ensure_positive_int(0, "test")
    
    def test_negative_raises_error(self):
        with pytest.raises(ValueError, match="must be a positive integer"):
            ensure_positive_int(-1, "test")
    
    def test_none_raises_error(self):
        with pytest.raises(ValueError, match="must be a positive integer"):
            ensure_positive_int(None, "test")


class TestEnsureNonEmpty:
    """Tests for ensure_non_empty validator."""
    
    def test_valid_string(self):
        assert ensure_non_empty("hello", "test") == "hello"
        assert ensure_non_empty("  hello  ", "test") == "hello"
    
    def test_empty_string_raises_error(self):
        with pytest.raises(ValueError, match="must be a non-empty string"):
            ensure_non_empty("", "test")
    
    def test_whitespace_only_raises_error(self):
        with pytest.raises(ValueError, match="must be a non-empty string"):
            ensure_non_empty("   ", "test")
    
    def test_max_length(self):
        assert ensure_non_empty("hello", "test", max_len=10) == "hello"
        
        with pytest.raises(ValueError, match="must not exceed 5 characters"):
            ensure_non_empty("hello world", "test", max_len=5)


class TestEnsureValidTimezone:
    """Tests for ensure_valid_timezone validator."""
    
    def test_valid_timezone(self):
        assert ensure_valid_timezone("Europe/Moscow", "test") == "Europe/Moscow"
        assert ensure_valid_timezone("America/New_York", "test") == "America/New_York"
        assert ensure_valid_timezone("UTC", "test") == "UTC"
    
    def test_invalid_timezone_raises_error(self):
        with pytest.raises(ValueError, match="must be a valid timezone"):
            ensure_valid_timezone("Invalid/Timezone", "test")
    
    def test_empty_string_raises_error(self):
        with pytest.raises(ValueError, match="must be a non-empty string"):
            ensure_valid_timezone("", "test")


class TestEnsureInList:
    """Tests for ensure_in_list validator."""
    
    def test_valid_value(self):
        allowed = ["admin", "teacher", "viewer"]
        assert ensure_in_list("admin", "role", allowed) == "admin"
        assert ensure_in_list("teacher", "role", allowed) == "teacher"
    
    def test_invalid_value_raises_error(self):
        allowed = ["admin", "teacher", "viewer"]
        with pytest.raises(ValueError, match="must be one of"):
            ensure_in_list("invalid", "role", allowed)
    
    def test_empty_string_raises_error(self):
        allowed = ["admin", "teacher"]
        with pytest.raises(ValueError, match="must be one of"):
            ensure_in_list("", "role", allowed)


class TestEnsurePositiveIntOrNone:
    """Tests for ensure_positive_int_or_none validator."""
    
    def test_valid_positive_int(self):
        assert ensure_positive_int_or_none(1, "test") == 1
        assert ensure_positive_int_or_none(100, "test") == 100
    
    def test_none_is_allowed(self):
        assert ensure_positive_int_or_none(None, "test") is None
    
    def test_zero_raises_error(self):
        with pytest.raises(ValueError, match="must be a positive integer"):
            ensure_positive_int_or_none(0, "test")
    
    def test_negative_raises_error(self):
        with pytest.raises(ValueError, match="must be a positive integer"):
            ensure_positive_int_or_none(-1, "test")
