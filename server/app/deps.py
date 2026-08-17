from datetime import UTC, datetime

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import User, UserSession, WorkspaceMembership
from .security import token_hash


def current_user(
    session_token: str | None = Cookie(default=None, alias=get_settings().session_cookie_name),
    db: Session = Depends(get_db),
) -> User:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    session = db.scalar(
        select(UserSession).where(UserSession.token_hash == token_hash(session_token))
    )
    now = datetime.now(UTC)
    if not session or session.expires_at < now:
        if session:
            db.delete(session)
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account disabled")
    session.last_seen_at = now
    db.commit()
    return user


def current_membership(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> WorkspaceMembership:
    membership = db.scalar(
        select(WorkspaceMembership).where(WorkspaceMembership.user_id == user.id)
    )
    if not membership:
        raise HTTPException(status_code=403, detail="No workspace membership")
    return membership
