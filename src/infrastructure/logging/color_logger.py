"""Colored logging setup for TutorBase.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.7
"""
import logging
from typing import Optional

# Color mapping according to requirements
LOG_COLORS = {
    "DEBUG": "cyan",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "bold_red",
}

DEFAULT_FORMAT = "%(asctime)s | %(log_color)s%(levelname)-8s%(reset)s | %(name)s | %(message)s"
NO_COLOR_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_color_logging(
    level: int = logging.INFO,
    format_string: Optional[str] = None,
    disable_colors: bool = False,
) -> None:
    """Configure colored logging for the application.
    
    Args:
        level: Logging level (default: INFO)
        format_string: Custom format string (optional)
        disable_colors: If True, use standard logging without colors
        
    Requirements:
        3.1: DEBUG messages in cyan
        3.2: INFO messages in green
        3.3: WARNING messages in yellow
        3.4: ERROR messages in red
        3.5: CRITICAL messages in bold_red
        3.6: Include timestamp, logger name, and log level
        3.7: Configurable to disable colors for production/file output
    """
    root_logger = logging.getLogger()
    root_logger.handlers = []
    
    if disable_colors:
        # Standard logging without colors
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            format_string or NO_COLOR_FORMAT
        ))
    else:
        try:
            import colorlog
            
            handler = colorlog.StreamHandler()
            handler.setFormatter(colorlog.ColoredFormatter(
                format_string or DEFAULT_FORMAT,
                log_colors=LOG_COLORS,
                secondary_log_colors={},
                style="%",
            ))
        except ImportError:
            # Fallback to standard logging if colorlog not installed
            logging.warning("colorlog not installed, using standard logging")
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                format_string or NO_COLOR_FORMAT
            ))
    
    root_logger.addHandler(handler)
    root_logger.setLevel(level)


def get_color_formatter() -> Optional["colorlog.ColoredFormatter"]:
    """Get a ColoredFormatter instance for testing purposes.
    
    Returns:
        ColoredFormatter with configured colors, or None if colorlog not available.
    """
    try:
        import colorlog
        
        return colorlog.ColoredFormatter(
            DEFAULT_FORMAT,
            log_colors=LOG_COLORS,
            secondary_log_colors={},
            style="%",
        )
    except ImportError:
        return None
