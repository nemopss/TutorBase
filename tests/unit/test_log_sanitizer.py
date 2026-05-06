from api.log_sanitizer import REDACTED, redact_query_params


def test_redact_query_params_redacts_secret_like_values():
    query = (
        "token=invite-secret&refresh_token=refresh-secret&password=plain"
        "&hash=telegram-hash&email=tutor%40example.com"
    )

    redacted = redact_query_params(query)

    assert f"token={REDACTED}" in redacted
    assert f"refresh_token={REDACTED}" in redacted
    assert f"password={REDACTED}" in redacted
    assert f"hash={REDACTED}" in redacted
    assert "email=tutor%40example.com" in redacted
    assert "invite-secret" not in redacted
    assert "refresh-secret" not in redacted
    assert "plain" not in redacted
    assert "telegram-hash" not in redacted
