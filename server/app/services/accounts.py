from ..models import User, WorkspaceMembership
from ..schemas import UserResponse


def user_response(user: User, membership: WorkspaceMembership) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        job_title=user.job_title,
        role=membership.role,
        workspace_id=membership.workspace_id,
        workspace_name=membership.workspace.name,
        timezone=membership.workspace.timezone,
        must_change_password=user.must_change_password,
        onboarding_completed=user.onboarding_completed,
    )
