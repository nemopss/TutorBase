"""
Property-based tests for color logger.

Feature: clean-architecture-phase1, Property 3: Log Color Configuration
Feature: clean-architecture-phase1, Property 4: Log Format Completeness
Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
"""
from hypothesis import given, settings, strategies as st

from src.infrastructure.logging import LOG_COLORS, DEFAULT_FORMAT, get_color_formatter


# Expected color mapping per requirements
EXPECTED_COLORS = {
    "DEBUG": "cyan",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "bold_red",
}


@given(level=st.sampled_from(list(EXPECTED_COLORS.keys())))
@settings(max_examples=100)
def test_log_color_configuration(level: str) -> None:
    """
    Property 3: Log Color Configuration
    
    For any log level (DEBUG, INFO, WARNING, ERROR, CRITICAL), the Color_Logger
    formatter SHALL have the correct color mapping configured.
    
    Feature: clean-architecture-phase1, Property 3: Log Color Configuration
    Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5
    """
    expected_color = EXPECTED_COLORS[level]
    actual_color = LOG_COLORS.get(level)
    
    assert actual_color == expected_color, (
        f"Color for {level} should be '{expected_color}', got '{actual_color}'"
    )


@given(placeholder=st.sampled_from(["%(asctime)s", "%(name)s", "%(levelname)"]))
@settings(max_examples=100)
def test_log_format_completeness(placeholder: str) -> None:
    """
    Property 4: Log Format Completeness
    
    For any log message produced by Color_Logger, the output format SHALL
    include timestamp, logger name, and log level placeholders.
    
    Feature: clean-architecture-phase1, Property 4: Log Format Completeness
    Validates: Requirements 3.6
    """
    assert placeholder in DEFAULT_FORMAT, (
        f"DEFAULT_FORMAT should contain '{placeholder}'"
    )


def test_formatter_has_correct_colors() -> None:
    """Verify ColoredFormatter is configured with correct colors."""
    formatter = get_color_formatter()
    
    if formatter is None:
        # colorlog not installed, skip
        return
    
    for level, expected_color in EXPECTED_COLORS.items():
        actual_color = formatter.log_colors.get(level)
        assert actual_color == expected_color, (
            f"Formatter color for {level} should be '{expected_color}', got '{actual_color}'"
        )


def test_all_log_levels_have_colors() -> None:
    """Verify all standard log levels have color mappings."""
    required_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    configured_levels = set(LOG_COLORS.keys())
    
    missing = required_levels - configured_levels
    assert not missing, f"Missing color configuration for levels: {missing}"
