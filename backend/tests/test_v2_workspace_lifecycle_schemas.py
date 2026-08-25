import uuid

import pytest

from pydantic import ValidationError

from app.schemas.v2_workspace_lifecycle import (
    MemberExitResolution,
    ResponsibilityDirective,
)


def test_resolution_contract_is_strict_and_requires_reassignment_target() -> None:
    target = uuid.uuid4()
    assert ResponsibilityDirective(
        action="REASSIGN", target_user_id=target
    ).target_user_id == target
    with pytest.raises(ValidationError):
        ResponsibilityDirective(action="REASSIGN")
    with pytest.raises(ValidationError):
        ResponsibilityDirective(action="DELETE", target_user_id=target)
    with pytest.raises(ValidationError):
        ResponsibilityDirective.model_validate({"action": "DELETE", "owner_user_id": target})


def test_delete_all_cannot_be_combined_with_domain_directives() -> None:
    with pytest.raises(ValidationError):
        MemberExitResolution(
            delete_all=True,
            tasks=ResponsibilityDirective(action="DELETE"),
        )
