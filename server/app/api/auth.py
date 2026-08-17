from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import current_membership, current_user
from ..models import AuditLog, User, UserSession, WorkspaceMembership
from ..schemas import LoginRequest, PasswordChangeRequest, UserResponse
from ..security import (
    create_secret_token,
    hash_password,
    session_expiry,
    token_hash,
    verify_password,
)
from ..services.accounts import user_response

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=UserResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not user.is_active or not verify_password(user.password_hash, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码不正确")
    membership = db.scalar(
        select(WorkspaceMembership).where(WorkspaceMembership.user_id == user.id)
    )
    if not membership:
        raise HTTPException(status_code=403, detail="账号尚未分配酒店工作区")
    raw_token = create_secret_token()
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=token_hash(raw_token),
            expires_at=session_expiry(),
        )
    )
    db.add(AuditLog(user_id=user.id, action="login", object_type="session"))
    db.commit()
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.session_days * 86400,
        path="/",
    )
    return user_response(user, membership)


@router.get("/me", response_model=UserResponse)
def me(
    user: User = Depends(current_user),
    membership: WorkspaceMembership = Depends(current_membership),
):
    return user_response(user, membership)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias=get_settings().session_cookie_name),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    if session_token:
        active_session = db.scalar(
            select(UserSession).where(UserSession.token_hash == token_hash(session_token))
        )
        if active_session:
            db.delete(active_session)
    response.delete_cookie(settings.session_cookie_name, path="/")
    db.add(AuditLog(user_id=user.id, action="logout", object_type="session"))
    db.commit()


@router.post("/change-password", response_model=UserResponse)
def change_password(
    payload: PasswordChangeRequest,
    user: User = Depends(current_user),
    membership: WorkspaceMembership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    if not verify_password(user.password_hash, payload.current_password):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    db.add(
        AuditLog(user_id=user.id, action="change_password", object_type="user", object_id=user.id)
    )
    db.commit()
    return user_response(user, membership)
