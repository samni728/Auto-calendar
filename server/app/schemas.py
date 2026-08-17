from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=200)


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    job_title: str
    role: str
    workspace_id: str
    workspace_name: str
    timezone: str
    must_change_password: bool
    onboarding_completed: bool


class ProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    job_title: str = Field(min_length=1, max_length=80)


class WorkspaceUpdate(BaseModel):
    workspace_name: str = Field(min_length=1, max_length=160)
    timezone: str = Field(min_length=1, max_length=80)


class RoomSetup(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    room_type: str = Field(default="标准房", min_length=1, max_length=80)
    floor: str = Field(default="", max_length=32)


class OnboardingRequest(ProfileUpdate, WorkspaceUpdate):
    rooms: list[RoomSetup] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def unique_room_codes(self):
        normalized = [room.code.strip().lower() for room in self.rooms]
        if len(normalized) != len(set(normalized)):
            raise ValueError("room codes must be unique")
        return self


class RoomCreate(RoomSetup):
    pass


class RoomUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=32)
    room_type: str | None = Field(default=None, min_length=1, max_length=80)
    floor: str | None = Field(default=None, max_length=32)


class RoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    room_type: str
    floor: str


class EventBase(BaseModel):
    room_id: str | None = None
    title: str = Field(min_length=1, max_length=240)
    guest_name: str = Field(default="", max_length=160)
    event_type: str = Field(pattern="^(reservation|maintenance|blocked|cleaning)$")
    status: str = Field(
        pattern="^(reserved|checked_in|checked_out|maintenance|blocked|cleaning|cancelled)$"
    )
    start_date: date
    end_date: date
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    room_id: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=240)
    guest_name: str | None = Field(default=None, max_length=160)
    event_type: str | None = Field(
        default=None, pattern="^(reservation|maintenance|blocked|cleaning)$"
    )
    status: str | None = Field(
        default=None,
        pattern="^(reserved|checked_in|checked_out|maintenance|blocked|cleaning|cancelled)$",
    )
    start_date: date | None = None
    end_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class EventResponse(EventBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    source_system: str
    sync_status: str
    provider_connection_id: str | None
    updated_at: datetime


class DashboardResponse(BaseModel):
    workspace_id: str
    workspace_name: str
    timezone: str
    rooms: list[RoomResponse]
    events: list[EventResponse]
    unassigned_count: int


class ProviderCalendar(BaseModel):
    id: str
    name: str
    primary: bool = False


class ConnectionResponse(BaseModel):
    id: str | None = None
    provider: str
    configured: bool
    status: str
    account_email: str | None = None
    selected_calendar_id: str | None = None
    selected_calendar_name: str | None = None
    last_sync_at: datetime | None = None
    last_error: str | None = None


class CalendarSelectRequest(BaseModel):
    calendar_id: str
    calendar_name: str


class OAuthStartResponse(BaseModel):
    authorization_url: str
