"""API package exports.

Keep imports lazy so utility modules can safely import submodules like
`api.prometheus_metrics` without triggering full application construction and
route imports during module initialization.
"""

__all__ = ["create_app"]


def create_app():
    from .app import create_app as _create_app

    return _create_app()
