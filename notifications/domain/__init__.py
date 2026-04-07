"""Pure domain logic for the notification bounded context."""

from notifications.domain.enums import (
    CapMode,
    CategoryKey,
    EventType,
    InstanceStatus,
    PreferenceScope,
    Priority,
    QuietHoursMode,
    RuleStatus,
    TriggerType,
)
from notifications.domain.templates import (
    ALLOWED_TEMPLATE_VARIABLES,
    TemplateRenderError,
    extract_template_variables,
    render_template_body,
    validate_template_body,
)

__all__ = [
    "CapMode",
    "CategoryKey",
    "EventType",
    "InstanceStatus",
    "PreferenceScope",
    "Priority",
    "QuietHoursMode",
    "RuleStatus",
    "TriggerType",
    "ALLOWED_TEMPLATE_VARIABLES",
    "TemplateRenderError",
    "extract_template_variables",
    "render_template_body",
    "validate_template_body",
]
