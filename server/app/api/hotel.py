from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_membership, current_user
from ..models import AuditLog, Room, TimelineEvent, User, WorkspaceMembership
from ..schemas import DashboardResponse, EventCreate, EventResponse, EventUpdate
from ..services.providers import push_event_to_workspace

router = APIRouter(prefix="/api", tags=["hotel"])


def _room_or_none(db: Session, workspace_id: str, room_id: str | None) -> Room | None:
    if room_id is None:
        return None
    room = db.scalar(
        select(Room).where(Room.id == room_id, Room.workspace_id == workspace_id, Room.is_active)
    )
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    return room


def _ensure_no_conflict(
    db: Session,
    workspace_id: str,
    room_id: str | None,
    start_date: date,
    end_date: date,
    exclude_id: str | None = None,
) -> None:
    if not room_id:
        return
    conditions = [
        TimelineEvent.workspace_id == workspace_id,
        TimelineEvent.room_id == room_id,
        TimelineEvent.is_deleted.is_(False),
        TimelineEvent.status != "cancelled",
        TimelineEvent.start_date < end_date,
        TimelineEvent.end_date > start_date,
    ]
    if exclude_id:
        conditions.append(TimelineEvent.id != exclude_id)
    if db.scalar(select(TimelineEvent.id).where(*conditions).limit(1)):
        raise HTTPException(status_code=409, detail="该房间在所选日期已有安排")


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    start: date = Query(default_factory=date.today),
    days: int = Query(default=14, ge=7, le=93),
    membership: WorkspaceMembership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    end = start + timedelta(days=days)
    rooms = db.scalars(
        select(Room)
        .where(Room.workspace_id == membership.workspace_id, Room.is_active)
        .order_by(Room.code)
    ).all()
    events = db.scalars(
        select(TimelineEvent)
        .where(
            TimelineEvent.workspace_id == membership.workspace_id,
            TimelineEvent.is_deleted.is_(False),
            TimelineEvent.start_date < end,
            TimelineEvent.end_date > start,
        )
        .order_by(TimelineEvent.start_date, TimelineEvent.created_at)
    ).all()
    unassigned_count = (
        db.scalar(
            select(func.count(TimelineEvent.id)).where(
                TimelineEvent.workspace_id == membership.workspace_id,
                TimelineEvent.room_id.is_(None),
                TimelineEvent.is_deleted.is_(False),
                TimelineEvent.status != "cancelled",
            )
        )
        or 0
    )
    return DashboardResponse(
        workspace_id=membership.workspace_id,
        workspace_name=membership.workspace.name,
        timezone=membership.workspace.timezone,
        rooms=rooms,
        events=events,
        unassigned_count=unassigned_count,
    )


@router.post("/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreate,
    user: User = Depends(current_user),
    membership: WorkspaceMembership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    _room_or_none(db, membership.workspace_id, payload.room_id)
    _ensure_no_conflict(
        db, membership.workspace_id, payload.room_id, payload.start_date, payload.end_date
    )
    event = TimelineEvent(
        workspace_id=membership.workspace_id,
        sync_status="pending",
        **payload.model_dump(),
    )
    db.add(event)
    db.flush()
    db.add(
        AuditLog(user_id=user.id, action="create", object_type="timeline_event", object_id=event.id)
    )
    db.commit()
    db.refresh(event)
    try:
        await push_event_to_workspace(event, db)
    except Exception:
        db.rollback()
        event = db.get(TimelineEvent, event.id)
        if event:
            event.sync_status = "sync_error"
            db.commit()
    return event


@router.patch("/events/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: str,
    payload: EventUpdate,
    user: User = Depends(current_user),
    membership: WorkspaceMembership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    event = db.scalar(
        select(TimelineEvent).where(
            TimelineEvent.id == event_id,
            TimelineEvent.workspace_id == membership.workspace_id,
            TimelineEvent.is_deleted.is_(False),
        )
    )
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    values = payload.model_dump(exclude_unset=True)
    room_id = values.get("room_id", event.room_id)
    start_date = values.get("start_date", event.start_date)
    end_date = values.get("end_date", event.end_date)
    if end_date <= start_date:
        raise HTTPException(status_code=422, detail="结束日期必须晚于开始日期")
    _room_or_none(db, membership.workspace_id, room_id)
    _ensure_no_conflict(db, membership.workspace_id, room_id, start_date, end_date, event.id)
    for key, value in values.items():
        setattr(event, key, value)
    event.sync_status = "local_override" if event.source_system != "local" else "pending"
    db.add(
        AuditLog(user_id=user.id, action="update", object_type="timeline_event", object_id=event.id)
    )
    db.commit()
    db.refresh(event)
    try:
        await push_event_to_workspace(event, db)
    except Exception:
        db.rollback()
        event = db.get(TimelineEvent, event.id)
        if event:
            event.sync_status = "sync_error"
            db.commit()
    return event


@router.delete("/events/{event_id}", status_code=204)
async def delete_event(
    event_id: str,
    user: User = Depends(current_user),
    membership: WorkspaceMembership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    event = db.scalar(
        select(TimelineEvent).where(
            TimelineEvent.id == event_id,
            TimelineEvent.workspace_id == membership.workspace_id,
            TimelineEvent.is_deleted.is_(False),
        )
    )
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    event.is_deleted = True
    event.status = "cancelled"
    event.sync_status = "pending"
    db.add(
        AuditLog(user_id=user.id, action="delete", object_type="timeline_event", object_id=event.id)
    )
    db.commit()
    try:
        await push_event_to_workspace(event, db)
    except Exception:
        db.rollback()
        event = db.get(TimelineEvent, event.id)
        if event:
            event.sync_status = "sync_error"
            db.commit()
