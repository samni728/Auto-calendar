from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import current_membership, current_user
from ..models import AuditLog, OAuthState, ProviderConnection, User, WorkspaceMembership
from ..schemas import (
    CalendarCreateRequest,
    CalendarSelectRequest,
    ConnectionResponse,
    ConnectionSettingsRequest,
    OAuthStartResponse,
    ProviderCalendar,
)
from ..security import (
    create_secret_token,
    decrypt_secret,
    encrypt_secret,
    pkce_challenge,
    token_hash,
)
from ..services.providers import (
    account_email,
    authorization_url,
    create_calendar,
    exchange_code,
    list_calendars,
    provider_configuration_issue,
    provider_configured,
    redirect_uri,
    reset_calendar_mapping,
    sync_connection,
    sync_connections,
)
from ..time_utils import as_utc

router = APIRouter(prefix="/api", tags=["connections"])
PROVIDERS = ("google", "microsoft")


def _validate_provider(provider: str) -> None:
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail="不支持该日历服务")


def _connection(db: Session, user_id: str, provider: str) -> ProviderConnection:
    connection = db.scalar(
        select(ProviderConnection).where(
            ProviderConnection.user_id == user_id,
            ProviderConnection.provider == provider,
        )
    )
    if not connection:
        raise HTTPException(status_code=404, detail="尚未连接该日历账号")
    return connection


def _response(provider: str, connection: ProviderConnection | None) -> ConnectionResponse:
    if not connection:
        return ConnectionResponse(
            provider=provider,
            configured=provider_configured(provider),
            configuration_issue=provider_configuration_issue(provider),
            redirect_uri=redirect_uri(provider),
            status="disconnected",
        )
    return ConnectionResponse(
        id=connection.id,
        provider=provider,
        configured=provider_configured(provider),
        configuration_issue=provider_configuration_issue(provider),
        redirect_uri=redirect_uri(provider),
        status=connection.status,
        account_email=connection.account_email,
        selected_calendar_id=connection.selected_calendar_id,
        selected_calendar_name=connection.selected_calendar_name,
        sync_mode=connection.sync_mode,
        sync_label=connection.sync_label,
        last_sync_at=connection.last_sync_at,
        last_error=connection.last_error,
    )


@router.get("/connections", response_model=list[ConnectionResponse])
def connections(user: User = Depends(current_user), db: Session = Depends(get_db)):
    existing = {
        item.provider: item
        for item in db.scalars(
            select(ProviderConnection).where(ProviderConnection.user_id == user.id)
        ).all()
    }
    return [_response(provider, existing.get(provider)) for provider in PROVIDERS]


@router.post("/oauth/{provider}/start", response_model=OAuthStartResponse)
def oauth_start(
    provider: str,
    user: User = Depends(current_user),
    membership: WorkspaceMembership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    _validate_provider(provider)
    configuration_issue = provider_configuration_issue(provider)
    if configuration_issue:
        raise HTTPException(status_code=409, detail=configuration_issue)
    state = create_secret_token()
    verifier = create_secret_token(64)
    db.add(
        OAuthState(
            state_hash=token_hash(state),
            user_id=user.id,
            workspace_id=membership.workspace_id,
            provider=provider,
            code_verifier_encrypted=encrypt_secret(verifier),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
    )
    db.commit()
    return OAuthStartResponse(
        authorization_url=authorization_url(provider, state, pkce_challenge(verifier))
    )


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    state: str = "",
    code: str = "",
    error: str = "",
    db: Session = Depends(get_db),
):
    _validate_provider(provider)
    if error:
        return RedirectResponse(
            url=f"{get_settings().public_base_url}/?view=connections&oauth=denied"
        )
    oauth_state = db.scalar(select(OAuthState).where(OAuthState.state_hash == token_hash(state)))
    now = datetime.now(UTC)
    if (
        not oauth_state
        or oauth_state.provider != provider
        or as_utc(oauth_state.expires_at) < now
        or not code
    ):
        raise HTTPException(status_code=400, detail="OAuth state 已失效，请重新连接")
    verifier = decrypt_secret(oauth_state.code_verifier_encrypted)
    payload = await exchange_code(provider, code, verifier)
    access_token = payload.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="日历服务未返回 access token")
    connection = db.scalar(
        select(ProviderConnection).where(
            ProviderConnection.user_id == oauth_state.user_id,
            ProviderConnection.provider == provider,
        )
    )
    if not connection:
        connection = ProviderConnection(
            user_id=oauth_state.user_id,
            workspace_id=oauth_state.workspace_id,
            provider=provider,
        )
        db.add(connection)
    connection.status = "connected"
    connection.access_token_encrypted = encrypt_secret(access_token)
    if payload.get("refresh_token"):
        connection.refresh_token_encrypted = encrypt_secret(payload["refresh_token"])
    connection.token_expires_at = now + timedelta(seconds=int(payload.get("expires_in", 3600)))
    connection.account_email = await account_email(provider, access_token)
    connection.last_error = None
    db.delete(oauth_state)
    db.add(
        AuditLog(
            user_id=connection.user_id, action="connect", object_type="calendar", object_id=provider
        )
    )
    db.commit()
    return RedirectResponse(
        url=f"{get_settings().public_base_url}/?view=connections&oauth=connected"
    )


@router.get("/connections/{provider}/calendars", response_model=list[ProviderCalendar])
async def calendars(
    provider: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    _validate_provider(provider)
    return await list_calendars(_connection(db, user.id, provider), db)


@router.put("/connections/{provider}/calendar", response_model=ConnectionResponse)
def select_calendar(
    provider: str,
    payload: CalendarSelectRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    _validate_provider(provider)
    connection = _connection(db, user.id, provider)
    if connection.selected_calendar_id != payload.calendar_id:
        reset_calendar_mapping(db, connection)
    connection.selected_calendar_id = payload.calendar_id
    connection.selected_calendar_name = payload.calendar_name
    connection.sync_cursor = None
    db.add(
        AuditLog(
            user_id=user.id, action="select_calendar", object_type="calendar", object_id=provider
        )
    )
    db.commit()
    return _response(provider, connection)


@router.post("/connections/{provider}/calendars", response_model=ProviderCalendar)
async def add_calendar(
    provider: str,
    payload: CalendarCreateRequest,
    user: User = Depends(current_user),
    membership: WorkspaceMembership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    _validate_provider(provider)
    connection = _connection(db, user.id, provider)
    created = await create_calendar(
        connection, db, payload.calendar_name.strip(), membership.workspace.timezone
    )
    reset_calendar_mapping(db, connection)
    connection.selected_calendar_id = created["id"]
    connection.selected_calendar_name = created["name"]
    connection.sync_label = payload.calendar_name.strip()
    db.add(
        AuditLog(
            user_id=user.id,
            action="create_sync_calendar",
            object_type="calendar",
            object_id=provider,
            detail=created["name"],
        )
    )
    db.commit()
    return created


@router.put("/connections/{provider}/settings", response_model=ConnectionResponse)
def update_connection_settings(
    provider: str,
    payload: ConnectionSettingsRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    _validate_provider(provider)
    connection = _connection(db, user.id, provider)
    if connection.selected_calendar_id != payload.calendar_id:
        reset_calendar_mapping(db, connection)
    connection.selected_calendar_id = payload.calendar_id
    connection.selected_calendar_name = payload.calendar_name
    connection.sync_mode = payload.sync_mode
    connection.sync_label = payload.sync_label.strip()
    db.add(
        AuditLog(
            user_id=user.id,
            action="update_sync_settings",
            object_type="calendar",
            object_id=provider,
            detail=f"mode={payload.sync_mode}",
        )
    )
    db.commit()
    return _response(provider, connection)


@router.post("/connections/{provider}/sync")
async def sync(provider: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _validate_provider(provider)
    count = await sync_connection(_connection(db, user.id, provider), db)
    db.add(
        AuditLog(
            user_id=user.id,
            action="sync",
            object_type="calendar",
            object_id=provider,
            detail=f"{count} events",
        )
    )
    db.commit()
    return {"synced": count}


@router.post("/connections/sync-all")
async def sync_all(
    user: User = Depends(current_user),
    membership: WorkspaceMembership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    connections = db.scalars(
        select(ProviderConnection).where(
            ProviderConnection.user_id == user.id,
            ProviderConnection.workspace_id == membership.workspace_id,
            ProviderConnection.status == "connected",
            ProviderConnection.selected_calendar_id.is_not(None),
            ProviderConnection.sync_mode != "disabled",
        )
    ).all()
    results, errors = await sync_connections(connections, db)
    return {"synced": results, "errors": errors}


@router.delete("/connections/{provider}", status_code=204)
def disconnect(provider: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _validate_provider(provider)
    connection = _connection(db, user.id, provider)
    db.delete(connection)
    db.add(
        AuditLog(user_id=user.id, action="disconnect", object_type="calendar", object_id=provider)
    )
    db.commit()
