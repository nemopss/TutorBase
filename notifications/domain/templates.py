from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping


_VARIABLE_PATTERN = re.compile(r"\{([a-z_][a-z0-9_]*)\}")


@dataclass(frozen=True)
class TemplateVariable:
    key: str
    label: str


@dataclass(frozen=True)
class TemplateValidationResult:
    valid: bool
    variables: tuple[str, ...]
    unknown_variables: tuple[str, ...] = ()


class TemplateRenderError(ValueError):
    pass


ALLOWED_TEMPLATE_VARIABLES: tuple[TemplateVariable, ...] = (
    TemplateVariable("student_name", "Имя ученика"),
    TemplateVariable("lesson_date", "Дата урока"),
    TemplateVariable("lesson_time", "Время урока"),
    TemplateVariable("lesson_datetime", "Дата и время урока"),
    TemplateVariable("package_title", "Название пакета"),
    TemplateVariable("package_end", "Дата окончания пакета"),
    TemplateVariable("teacher_name", "Имя преподавателя"),
    TemplateVariable("homework_due_at", "Дедлайн домашки"),
    TemplateVariable("custom_note", "Дополнительная заметка"),
)

ALLOWED_TEMPLATE_VARIABLE_KEYS = frozenset(variable.key for variable in ALLOWED_TEMPLATE_VARIABLES)


def extract_template_variables(body: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(_VARIABLE_PATTERN.findall(body)))


def validate_template_body(body: str) -> TemplateValidationResult:
    variables = extract_template_variables(body)
    unknown = tuple(variable for variable in variables if variable not in ALLOWED_TEMPLATE_VARIABLE_KEYS)
    return TemplateValidationResult(
        valid=not unknown,
        variables=variables,
        unknown_variables=unknown,
    )


def render_template_body(body: str, values: Mapping[str, object]) -> str:
    validation = validate_template_body(body)
    if validation.unknown_variables:
        raise TemplateRenderError(
            f"Unknown template variables: {', '.join(validation.unknown_variables)}"
        )

    missing = tuple(variable for variable in validation.variables if variable not in values)
    if missing:
        raise TemplateRenderError(f"Missing template variables: {', '.join(missing)}")

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = values[key]
        return "" if value is None else str(value)

    return _VARIABLE_PATTERN.sub(replace, body)
