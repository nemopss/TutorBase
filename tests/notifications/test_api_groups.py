from datetime import datetime, timezone

from api.app import create_app
from api.routes.groups import _group_response
from notifications.application.dto import LearnerGroupMemberRecord, LearnerGroupRecord


def test_group_routes_are_registered():
    app = create_app()
    paths = {route.path for route in app.routes}

    assert "/api/v1/groups" in paths
    assert "/api/v1/groups/{group_id}" in paths
    assert "/api/v1/groups/{group_id}/members" in paths
    assert "/api/v1/groups/{group_id}/members/{learner_id}" in paths


def test_group_response_maps_members_for_ui():
    created_at = datetime(2026, 4, 7, 7, 0, tzinfo=timezone.utc)
    group = LearnerGroupRecord(
        group_id=1,
        name="TOPIK",
        description="Speaking prep",
        color="#3366ff",
        status="active",
        member_count=1,
        members=(
            LearnerGroupMemberRecord(
                learner_id=10,
                display_name="Вика",
                status="active",
                joined_at=created_at,
            ),
        ),
        created_at=created_at,
        updated_at=created_at,
    )

    response = _group_response(group)

    assert response.id == 1
    assert response.name == "TOPIK"
    assert response.member_count == 1
    assert response.members[0].display_name == "Вика"
