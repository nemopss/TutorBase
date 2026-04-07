import pytest

from notifications.domain.templates import (
    ALLOWED_TEMPLATE_VARIABLES,
    TemplateRenderError,
    extract_template_variables,
    render_template_body,
    validate_template_body,
)


def test_allowed_variables_have_teacher_friendly_labels():
    labels_by_key = {variable.key: variable.label for variable in ALLOWED_TEMPLATE_VARIABLES}

    assert labels_by_key["student_name"] == "Имя ученика"
    assert labels_by_key["lesson_time"] == "Время урока"


def test_extract_template_variables_preserves_first_seen_order_and_dedupes():
    body = "Привет, {student_name}! Урок {lesson_time}. До встречи, {student_name}."

    assert extract_template_variables(body) == ("student_name", "lesson_time")


def test_validate_template_body_reports_unknown_variables():
    result = validate_template_body("Привет, {student_name}. Урок {unknown_value}.")

    assert result.valid is False
    assert result.variables == ("student_name", "unknown_value")
    assert result.unknown_variables == ("unknown_value",)


def test_render_template_body_replaces_known_variables():
    rendered = render_template_body(
        "Привет, {student_name}! Урок в {lesson_time}.",
        {"student_name": "Вика", "lesson_time": "20:00"},
    )

    assert rendered == "Привет, Вика! Урок в 20:00."


def test_render_template_body_rejects_unknown_variables():
    with pytest.raises(TemplateRenderError, match="Unknown template variables"):
        render_template_body("Привет, {nickname}.", {"nickname": "vika"})


def test_render_template_body_rejects_missing_values():
    with pytest.raises(TemplateRenderError, match="Missing template variables"):
        render_template_body("Привет, {student_name}.", {})
