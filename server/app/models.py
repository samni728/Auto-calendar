from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def uuid_str() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    user: Mapped[User] = relationship()


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(160))
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Shanghai")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class WorkspaceMembership(Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(32), default="workspace_admin")
    workspace: Mapped[Workspace] = relationship()


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (UniqueConstraint("workspace_id", "code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(32))
    room_type: Mapped[str] = mapped_column(String(80))
    floor: Mapped[str] = mapped_column(String(32), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ProviderConnection(Base):
    __tablename__ = "provider_connections"
    __table_args__ = (UniqueConstraint("user_id", "provider"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="disconnected")
    account_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    selected_calendar_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_calendar_name: Mapped[str | None] = mapped_column(String(240), nullable=True)
    sync_cursor: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class OAuthState(Base):
    __tablename__ = "oauth_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    state_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(32))
    code_verifier_encrypted: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class TimelineEvent(Base):
    __tablename__ = "timeline_events"
    __table_args__ = (
        UniqueConstraint("provider_connection_id", "external_event_id", name="uq_provider_event"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    room_id: Mapped[str | None] = mapped_column(
        ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(240))
    guest_name: Mapped[str] = mapped_column(String(160), default="")
    event_type: Mapped[str] = mapped_column(String(32), default="reservation")
    status: Mapped[str] = mapped_column(String(32), default="reserved")
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    source_system: Mapped[str] = mapped_column(String(32), default="local")
    sync_status: Mapped[str] = mapped_column(String(32), default="local")
    provider_connection_id: Mapped[str | None] = mapped_column(
        ForeignKey("provider_connections.id", ondelete="SET NULL"), nullable=True
    )
    external_event_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    object_type: Mapped[str] = mapped_column(String(80))
    object_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
