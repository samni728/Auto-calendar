from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import User, Workspace, WorkspaceMembership
from .security import hash_password


def seed_database(db: Session) -> None:
    settings = get_settings()
    user = db.scalar(select(User).where(User.email == settings.initial_admin_email.lower()))
    if not user:
        user = User(
            email=settings.initial_admin_email.lower(),
            display_name="管理员",
            job_title="",
            password_hash=hash_password(settings.initial_admin_password),
            must_change_password=True,
            onboarding_completed=False,
        )
        db.add(user)
        db.flush()

    workspace = db.scalar(select(Workspace).limit(1))
    if not workspace:
        workspace = Workspace(name="未命名酒店", timezone="Asia/Shanghai")
        db.add(workspace)
        db.flush()

    membership = db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace.id,
            WorkspaceMembership.user_id == user.id,
        )
    )
    if not membership:
        db.add(WorkspaceMembership(workspace_id=workspace.id, user_id=user.id, role="workspace_admin"))
    db.commit()
