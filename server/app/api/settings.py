from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_membership, current_user
from ..models import AuditLog, Room, TimelineEvent, User, WorkspaceMembership
from ..schemas import (
    OnboardingRequest,
    ProfileUpdate,
    RoomCreate,
    RoomResponse,
    RoomUpdate,
    UserResponse,
    WorkspaceUpdate,
)
from ..services.accounts import user_response

router = APIRouter(prefix="/api", tags=["settings"])


def _clean(value: str, field: str | None = None) -> str:
    cleaned = value.strip()
    if field and not cleaned:
        raise HTTPException(status_code=422, detail=f"{field}不能为空")
    return cleaned


def _validate_timezone(value: str) -> str:
    timezone = _clean(value)
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=422, detail="无效的时区") from exc
    return timezone


def _room_for_workspace(db: Session, workspace_id: str, room_id: str) -> Room:
    room = db.scalar(
        select(Room).where(Room.id == room_id, Room.workspace_id == workspace_id, Room.is_active)
    )
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    return room


def _require_workspace_admin(membership: WorkspaceMembership) -> None:
    if membership.role not in {"workspace_admin", "security_admin"}:
        raise HTTPException(status_code=403, detail="只有工作区管理员可以修改酒店配置")


@router.patch("/settings/profile", response_model=UserResponse)
def update_profile(
    payload: ProfileUpdate,
    user: User = Depends(current_user),
    membership: WorkspaceMembership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    user.display_name = _clean(payload.display_name, "姓名")
    user.job_title = _clean(payload.job_title, "展示身份")
    db.add(
        AuditLog(user_id=user.id, action="update_profile", object_type="user", object_id=user.id)
    )
    db.commit()
    return user_response(user, membership)


@router.patch("/settings/workspace", response_model=UserResponse)
def update_workspace(
    payload: WorkspaceUpdate,
    user: User = Depends(current_user),
    membership: WorkspaceMembership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    _require_workspace_admin(membership)
    membership.workspace.name = _clean(payload.workspace_name, "酒店名称")
    membership.workspace.timezone = _validate_timezone(payload.timezone)
    db.add(
        AuditLog(
            user_id=user.id,
            action="update_workspace",
            object_type="workspace",
            object_id=membership.workspace_id,
        )
    )
    db.commit()
    return user_response(user, membership)


@router.post("/settings/onboarding", response_model=UserResponse)
def complete_onboarding(
    payload: OnboardingRequest,
    user: User = Depends(current_user),
    membership: WorkspaceMembership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    _require_workspace_admin(membership)
    user.display_name = _clean(payload.display_name, "姓名")
    user.job_title = _clean(payload.job_title, "展示身份")
    user.onboarding_completed = True
    membership.role = "workspace_admin"
    membership.workspace.name = _clean(payload.workspace_name, "酒店名称")
    membership.workspace.timezone = _validate_timezone(payload.timezone)

    existing_rooms = {
        room.code.casefold(): room
        for room in db.scalars(select(Room).where(Room.workspace_id == membership.workspace_id)).all()
    }
    requested_codes: set[str] = set()
    for room_data in payload.rooms:
        code = _clean(room_data.code, "房号")
        normalized = code.casefold()
        requested_codes.add(normalized)
        room = existing_rooms.get(normalized)
        if room:
            room.code = code
            room.room_type = _clean(room_data.room_type, "房型")
            room.floor = _clean(room_data.floor)
            room.is_active = True
        else:
            db.add(
                Room(
                    workspace_id=membership.workspace_id,
                    code=code,
                    room_type=_clean(room_data.room_type, "房型"),
                    floor=_clean(room_data.floor),
                )
            )

    for normalized, room in existing_rooms.items():
        if room.is_active and normalized not in requested_codes:
            db.execute(
                update(TimelineEvent)
                .where(TimelineEvent.room_id == room.id)
                .values(room_id=None)
            )
            room.is_active = False

    db.add(
        AuditLog(
            user_id=user.id,
            action="complete_onboarding",
            object_type="workspace",
            object_id=membership.workspace_id,
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="房间编号已存在") from exc
    return user_response(user, membership)


@router.post("/rooms", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
def create_room(
    payload: RoomCreate,
    user: User = Depends(current_user),
    membership: WorkspaceMembership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    _require_workspace_admin(membership)
    code = _clean(payload.code, "房号")
    room = db.scalar(
        select(Room).where(
            Room.workspace_id == membership.workspace_id,
            func.lower(Room.code) == code.casefold(),
        )
    )
    if room and room.is_active:
        raise HTTPException(status_code=409, detail="房间编号已存在")
    if room:
        room.room_type = _clean(payload.room_type, "房型")
        room.floor = _clean(payload.floor)
        room.is_active = True
    else:
        room = Room(
            workspace_id=membership.workspace_id,
            code=code,
            room_type=_clean(payload.room_type, "房型"),
            floor=_clean(payload.floor),
        )
        db.add(room)
    db.flush()
    db.add(AuditLog(user_id=user.id, action="create", object_type="room", object_id=room.id))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="房间编号已存在") from exc
    db.refresh(room)
    return room


@router.patch("/rooms/{room_id}", response_model=RoomResponse)
def update_room(
    room_id: str,
    payload: RoomUpdate,
    user: User = Depends(current_user),
    membership: WorkspaceMembership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    _require_workspace_admin(membership)
    room = _room_for_workspace(db, membership.workspace_id, room_id)
    values = payload.model_dump(exclude_unset=True)
    if any(value is None for value in values.values()):
        raise HTTPException(status_code=422, detail="房间字段不能为 null")
    if "code" in values:
        values["code"] = _clean(values["code"], "房号")
        duplicate = db.scalar(
            select(Room.id).where(
                Room.workspace_id == membership.workspace_id,
                Room.id != room.id,
                Room.is_active,
                func.lower(Room.code) == values["code"].casefold(),
            )
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="房间编号已存在")
    if "room_type" in values:
        values["room_type"] = _clean(values["room_type"], "房型")
    for key, value in values.items():
        setattr(room, key, _clean(value))
    db.add(AuditLog(user_id=user.id, action="update", object_type="room", object_id=room.id))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="房间编号已存在") from exc
    db.refresh(room)
    return room


@router.delete("/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room(
    room_id: str,
    user: User = Depends(current_user),
    membership: WorkspaceMembership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    _require_workspace_admin(membership)
    room = _room_for_workspace(db, membership.workspace_id, room_id)
    db.execute(update(TimelineEvent).where(TimelineEvent.room_id == room.id).values(room_id=None))
    room.is_active = False
    db.add(AuditLog(user_id=user.id, action="delete", object_type="room", object_id=room.id))
    db.commit()
