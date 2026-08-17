from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Room, TimelineEvent, User, Workspace, WorkspaceMembership
from .security import hash_password

ROOMS = [
    ("301", "大床房", "3F"),
    ("302", "大床房", "3F"),
    ("303", "双床房", "3F"),
    ("305", "家庭房", "3F"),
    ("401", "景观房", "4F"),
    ("402", "景观房", "4F"),
    ("403", "套房", "4F"),
    ("501", "行政房", "5F"),
]


def seed_database(db: Session) -> None:
    settings = get_settings()
    user = db.scalar(select(User).where(User.email == settings.initial_admin_email.lower()))
    if not user:
        user = User(
            email=settings.initial_admin_email.lower(),
            display_name="陈经理",
            password_hash=hash_password(settings.initial_admin_password),
            must_change_password=True,
        )
        db.add(user)
        db.flush()

    workspace = db.scalar(select(Workspace).limit(1))
    if not workspace:
        workspace = Workspace(name="广州栖岸酒店", timezone="Asia/Shanghai")
        db.add(workspace)
        db.flush()

    membership = db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace.id,
            WorkspaceMembership.user_id == user.id,
        )
    )
    if not membership:
        db.add(
            WorkspaceMembership(workspace_id=workspace.id, user_id=user.id, role="security_admin")
        )

    existing_rooms = db.scalars(select(Room).where(Room.workspace_id == workspace.id)).all()
    if not existing_rooms:
        for code, room_type, floor in ROOMS:
            db.add(Room(workspace_id=workspace.id, code=code, room_type=room_type, floor=floor))
        db.flush()
        existing_rooms = db.scalars(select(Room).where(Room.workspace_id == workspace.id)).all()

    if not db.scalar(
        select(TimelineEvent).where(TimelineEvent.workspace_id == workspace.id).limit(1)
    ):
        room_by_code = {room.code: room for room in existing_rooms}
        today = date.today()
        samples = [
            ("301", "林女士 · 已入住", "林女士", "reservation", "checked_in", 0, 3),
            ("302", "David · Agoda", "David", "reservation", "reserved", 2, 6),
            ("303", "退房清洁", "", "cleaning", "cleaning", 0, 1),
            ("305", "空调维护", "", "maintenance", "maintenance", 1, 4),
            ("401", "周先生 · 携程", "周先生", "reservation", "reserved", 3, 7),
        ]
        for code, title, guest, event_type, event_status, start, end in samples:
            db.add(
                TimelineEvent(
                    workspace_id=workspace.id,
                    room_id=room_by_code[code].id,
                    title=title,
                    guest_name=guest,
                    event_type=event_type,
                    status=event_status,
                    start_date=today + timedelta(days=start),
                    end_date=today + timedelta(days=end),
                )
            )
    db.commit()
