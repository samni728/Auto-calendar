from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from urllib.parse import quote, urlencode

import httpx
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import EventMirror, ProviderConnection, Room, TimelineEvent
from ..security import decrypt_secret, encrypt_secret
from ..time_utils import as_utc

GOOGLE_SCOPES = [
    "openid",
    "email",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/calendar.calendars",
    "https://www.googleapis.com/auth/calendar.events",
]
MICROSOFT_SCOPES = [
    "openid",
    "email",
    "profile",
    "offline_access",
    "User.Read",
    "Calendars.ReadWrite",
]
READ_MODES = {"two_way", "read_only"}
WRITE_MODES = {"two_way", "write_only"}


def provider_configuration_issue(provider: str) -> str | None:
    settings = get_settings()
    if provider == "google":
        client_id = settings.google_client_id.strip()
        client_secret = settings.google_client_secret.strip()
    elif provider == "microsoft":
        client_id = settings.microsoft_client_id.strip()
        client_secret = settings.microsoft_client_secret.strip()
    else:
        return "不支持该日历服务"
    if client_id.startswith(("http://", "https://")):
        return "Client ID 误填成了回调地址；请填写供应商生成的 Client ID"
    if not client_id and not client_secret:
        return "尚未填写 Client ID 和 Client Secret"
    if not client_id:
        return "尚未填写 Client ID"
    if not client_secret:
        return "尚未填写 Client Secret"
    return None


def provider_configured(provider: str) -> bool:
    return provider_configuration_issue(provider) is None


def redirect_uri(provider: str) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}/api/oauth/{provider}/callback"


def authorization_url(provider: str, state: str, challenge: str) -> str:
    settings = get_settings()
    if provider == "google":
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri(provider),
            "response_type": "code",
            "scope": " ".join(GOOGLE_SCOPES),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    if provider == "microsoft":
        params = {
            "client_id": settings.microsoft_client_id,
            "redirect_uri": redirect_uri(provider),
            "response_type": "code",
            "response_mode": "query",
            "scope": " ".join(MICROSOFT_SCOPES),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        tenant = quote(settings.microsoft_tenant, safe="")
        return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize?" + urlencode(
            params
        )
    raise HTTPException(status_code=404, detail="Unsupported provider")


async def exchange_code(provider: str, code: str, verifier: str) -> dict:
    settings = get_settings()
    if provider == "google":
        url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "code": code,
            "code_verifier": verifier,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri(provider),
        }
    elif provider == "microsoft":
        tenant = quote(settings.microsoft_tenant, safe="")
        url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
        data = {
            "client_id": settings.microsoft_client_id,
            "client_secret": settings.microsoft_client_secret,
            "code": code,
            "code_verifier": verifier,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri(provider),
            "scope": " ".join(MICROSOFT_SCOPES),
        }
    else:
        raise HTTPException(status_code=404, detail="Unsupported provider")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, data=data)
    if response.is_error:
        raise HTTPException(status_code=400, detail="Provider rejected the authorization code")
    return response.json()


async def refresh_access_token(connection: ProviderConnection, db: Session) -> str:
    settings = get_settings()
    refresh_token = decrypt_secret(connection.refresh_token_encrypted)
    if not refresh_token:
        raise HTTPException(status_code=409, detail="Connection requires reauthorization")
    if connection.provider == "google":
        url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    else:
        tenant = quote(settings.microsoft_tenant, safe="")
        url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
        data = {
            "client_id": settings.microsoft_client_id,
            "client_secret": settings.microsoft_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "scope": " ".join(MICROSOFT_SCOPES),
        }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, data=data)
    if response.is_error:
        connection.status = "reauthorization_required"
        connection.last_error = "Token refresh failed; reconnect this account"
        db.commit()
        raise HTTPException(status_code=409, detail=connection.last_error)
    payload = response.json()
    connection.access_token_encrypted = encrypt_secret(payload["access_token"])
    if payload.get("refresh_token"):
        connection.refresh_token_encrypted = encrypt_secret(payload["refresh_token"])
    connection.token_expires_at = datetime.now(UTC) + timedelta(
        seconds=int(payload.get("expires_in", 3600))
    )
    connection.status = "connected"
    connection.last_error = None
    db.commit()
    return payload["access_token"]


async def valid_access_token(connection: ProviderConnection, db: Session) -> str:
    now = datetime.now(UTC)
    if (
        connection.access_token_encrypted
        and connection.token_expires_at
        and as_utc(connection.token_expires_at) > now + timedelta(minutes=2)
    ):
        return decrypt_secret(connection.access_token_encrypted)
    return await refresh_access_token(connection, db)


async def account_email(provider: str, access_token: str) -> str | None:
    headers = {"Authorization": f"Bearer {access_token}"}
    url = (
        "https://openidconnect.googleapis.com/v1/userinfo"
        if provider == "google"
        else "https://graph.microsoft.com/v1.0/me?$select=mail,userPrincipalName"
    )
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=headers)
    if response.is_error:
        return None
    payload = response.json()
    return payload.get("email") or payload.get("mail") or payload.get("userPrincipalName")


def _provider_error(response: httpx.Response, action: str) -> HTTPException:
    try:
        payload = response.json()
        error = payload.get("error", payload)
        detail = error.get("message") or error.get("error_description") or response.text
    except (ValueError, AttributeError):
        detail = response.text
    return HTTPException(status_code=502, detail=f"{action}失败：{str(detail)[:300]}")


async def list_calendars(connection: ProviderConnection, db: Session) -> list[dict]:
    token = await valid_access_token(connection, db)
    headers = {"Authorization": f"Bearer {token}"}
    url = (
        "https://www.googleapis.com/calendar/v3/users/me/calendarList"
        if connection.provider == "google"
        else "https://graph.microsoft.com/v1.0/me/calendars?$select=id,name,isDefaultCalendar"
    )
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=headers)
    if response.is_error:
        raise _provider_error(response, "读取日历列表")
    payload = response.json()
    if connection.provider == "google":
        return [
            {
                "id": item["id"],
                "name": item.get("summary", item["id"]),
                "primary": item.get("primary", False),
            }
            for item in payload.get("items", [])
        ]
    return [
        {
            "id": item["id"],
            "name": item.get("name", item["id"]),
            "primary": item.get("isDefaultCalendar", False),
        }
        for item in payload.get("value", [])
    ]


async def create_calendar(
    connection: ProviderConnection, db: Session, name: str, timezone: str
) -> dict:
    token = await valid_access_token(connection, db)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if connection.provider == "google":
        url = "https://www.googleapis.com/calendar/v3/calendars"
        body = {
            "summary": name,
            "description": "Auto Calendar 专用日历；由应用维护酒店订房事件。",
            "timeZone": timezone,
        }
    else:
        url = "https://graph.microsoft.com/v1.0/me/calendars"
        body = {"name": name}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, headers=headers, json=body)
    if response.is_error:
        error = _provider_error(response, "创建专用日历")
        if connection.provider == "google":
            error.detail = f"{error.detail}；Google 旧授权需点击“重新授权”取得创建权限"
        raise error
    payload = response.json()
    return {
        "id": payload["id"],
        "name": payload.get("summary") or payload.get("name") or name,
        "primary": False,
    }


def reset_calendar_mapping(db: Session, connection: ProviderConnection) -> None:
    connection.sync_cursor = None
    db.execute(delete(EventMirror).where(EventMirror.provider_connection_id == connection.id))


def event_fingerprint(event: TimelineEvent) -> str:
    values = {
        "title": event.title,
        "guest_name": event.guest_name,
        "event_type": event.event_type,
        "status": event.status,
        "start_date": event.start_date.isoformat(),
        "end_date": event.end_date.isoformat(),
        "room_id": event.room_id,
        "notes": event.notes,
        "is_deleted": event.is_deleted,
    }
    encoded = json.dumps(values, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _date_value(value: dict | None, fallback: date) -> date:
    if not value:
        return fallback
    raw = value.get("date") or value.get("dateTime")
    return date.fromisoformat(raw[:10]) if raw else fallback


def _external_version(provider: str, payload: dict) -> str | None:
    return payload.get("etag") if provider == "google" else payload.get("changeKey")


def _external_deleted(provider: str, payload: dict) -> bool:
    if provider == "google":
        return payload.get("status") == "cancelled"
    return payload.get("isCancelled", False) or "@removed" in payload


def _mirror_for_payload(
    db: Session, connection: ProviderConnection, payload: dict
) -> EventMirror | None:
    external_id = payload.get("id")
    if not external_id:
        return None
    mirror = db.scalar(
        select(EventMirror).where(
            EventMirror.provider_connection_id == connection.id,
            EventMirror.external_event_id == external_id,
        )
    )
    if mirror or connection.provider != "google":
        return mirror
    internal_id = (
        payload.get("extendedProperties", {}).get("private", {}).get("autoCalendarEventId")
    )
    event = db.get(TimelineEvent, internal_id) if internal_id else None
    if event and event.workspace_id == connection.workspace_id:
        mirror = EventMirror(
            event_id=event.id,
            provider_connection_id=connection.id,
            external_event_id=external_id,
        )
        db.add(mirror)
        db.flush()
    return mirror


def _apply_external_event(db: Session, connection: ProviderConnection, payload: dict) -> None:
    external_id = payload.get("id")
    if not external_id:
        return
    mirror = _mirror_for_payload(db, connection, payload)
    event = db.get(TimelineEvent, mirror.event_id) if mirror else None
    created_event = event is None
    deleted = _external_deleted(connection.provider, payload)
    version = _external_version(connection.provider, payload)
    if mirror and mirror.external_version == version:
        return
    if not event and deleted:
        return
    if not event:
        event = TimelineEvent(
            workspace_id=connection.workspace_id,
            room_id=None,
            title="Imported event",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1),
            source_system=connection.provider,
            sync_status="pending",
        )
        db.add(event)
        db.flush()
        mirror = EventMirror(
            event_id=event.id,
            provider_connection_id=connection.id,
            external_event_id=external_id,
        )
        db.add(mirror)
    assert mirror is not None
    mirror.external_version = version
    if not created_event and event.sync_status in {"pending", "local_override"} and not deleted:
        return
    if deleted:
        event.is_deleted = True
        event.status = "cancelled"
        mirror.is_deleted = True
    else:
        event.title = (
            payload.get("summary")
            if connection.provider == "google"
            else payload.get("subject")
        ) or event.title
        event.start_date = _date_value(payload.get("start"), event.start_date)
        event.end_date = _date_value(payload.get("end"), event.start_date + timedelta(days=1))
        if event.end_date <= event.start_date:
            event.end_date = event.start_date + timedelta(days=1)
        event.is_deleted = False
        mirror.is_deleted = False
    mirror.last_synced_hash = event_fingerprint(event)
    event.sync_status = "pending"


def _room_label(db: Session, event: TimelineEvent) -> str:
    room = db.get(Room, event.room_id) if event.room_id else None
    return room.code if room else "待分配"


def _event_body(db: Session, connection: ProviderConnection, event: TimelineEvent) -> dict:
    details = (
        f"Auto Calendar 酒店事件\n房间：{_room_label(db, event)}\n类型：{event.event_type}"
        f"\n状态：{event.status}\n备注：{event.notes or '-'}\nAutoCalendar-ID: {event.id}"
    )
    if connection.provider == "google":
        return {
            "summary": event.title,
            "description": details,
            "start": {"date": event.start_date.isoformat()},
            "end": {"date": event.end_date.isoformat()},
            "extendedProperties": {
                "private": {
                    "autoCalendarEventId": event.id,
                    "autoCalendarWorkspaceId": event.workspace_id,
                    "autoCalendarTag": connection.sync_label,
                    "eventType": event.event_type,
                    "status": event.status,
                }
            },
        }
    return {
        "subject": event.title,
        "body": {"contentType": "text", "content": details},
        "start": {"dateTime": f"{event.start_date.isoformat()}T00:00:00", "timeZone": "UTC"},
        "end": {"dateTime": f"{event.end_date.isoformat()}T00:00:00", "timeZone": "UTC"},
        "isAllDay": True,
        "categories": [connection.sync_label],
    }


def _event_url(connection: ProviderConnection, external_id: str | None = None) -> str:
    calendar_id = quote(connection.selected_calendar_id or "", safe="")
    if connection.provider == "google":
        base = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
    else:
        base = f"https://graph.microsoft.com/v1.0/me/calendars/{calendar_id}/events"
    return f"{base}/{quote(external_id, safe='')}" if external_id else base


async def _push_event(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    db: Session,
    connection: ProviderConnection,
    event: TimelineEvent,
) -> bool:
    mirror = db.scalar(
        select(EventMirror).where(
            EventMirror.event_id == event.id,
            EventMirror.provider_connection_id == connection.id,
        )
    )
    fingerprint = event_fingerprint(event)
    if event.is_deleted:
        if not mirror:
            return False
        if not mirror.is_deleted:
            response = await client.delete(_event_url(connection, mirror.external_event_id), headers=headers)
            if response.is_error and response.status_code != 404:
                raise _provider_error(response, f"删除 {connection.provider} 事件")
        mirror.is_deleted = True
        mirror.last_synced_hash = fingerprint
        return True
    if mirror and not mirror.is_deleted and mirror.last_synced_hash == fingerprint:
        return False
    body = _event_body(db, connection, event)
    if mirror and not mirror.is_deleted:
        response = await client.patch(
            _event_url(connection, mirror.external_event_id), headers=headers, json=body
        )
        if response.status_code == 404:
            mirror.is_deleted = True
            return await _push_event(client, headers, db, connection, event)
    else:
        response = await client.post(_event_url(connection), headers=headers, json=body)
    if response.is_error:
        raise _provider_error(response, f"写入 {connection.provider} 事件")
    payload = response.json()
    if not mirror:
        mirror = EventMirror(
            event_id=event.id,
            provider_connection_id=connection.id,
            external_event_id=payload["id"],
        )
        db.add(mirror)
    else:
        mirror.external_event_id = payload["id"]
    mirror.external_version = _external_version(connection.provider, payload)
    mirror.last_synced_hash = fingerprint
    mirror.is_deleted = False
    return True


def _refresh_event_status(db: Session, event: TimelineEvent) -> None:
    connections = db.scalars(
        select(ProviderConnection).where(
            ProviderConnection.workspace_id == event.workspace_id,
            ProviderConnection.status == "connected",
            ProviderConnection.selected_calendar_id.is_not(None),
            ProviderConnection.sync_mode.in_(WRITE_MODES),
        )
    ).all()
    fingerprint = event_fingerprint(event)
    for connection in connections:
        mirror = db.scalar(
            select(EventMirror).where(
                EventMirror.event_id == event.id,
                EventMirror.provider_connection_id == connection.id,
            )
        )
        if not mirror or mirror.last_synced_hash != fingerprint:
            event.sync_status = "pending"
            return
    event.sync_status = "synced"


async def push_workspace_events(connection: ProviderConnection, db: Session) -> int:
    if connection.sync_mode not in WRITE_MODES:
        return 0
    token = await valid_access_token(connection, db)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    events = db.scalars(
        select(TimelineEvent).where(TimelineEvent.workspace_id == connection.workspace_id)
    ).all()
    count = 0
    async with httpx.AsyncClient(timeout=60) as client:
        for event in events:
            if await _push_event(client, headers, db, connection, event):
                count += 1
    for event in events:
        _refresh_event_status(db, event)
    db.flush()
    return count


async def push_event_to_workspace(event: TimelineEvent, db: Session) -> int:
    connection_ids = db.scalars(
        select(ProviderConnection).where(
            ProviderConnection.workspace_id == event.workspace_id,
            ProviderConnection.status == "connected",
            ProviderConnection.selected_calendar_id.is_not(None),
            ProviderConnection.sync_mode.in_(WRITE_MODES),
        )
    ).with_only_columns(ProviderConnection.id).all()
    count = 0
    errors: list[str] = []
    event_id = event.id
    for connection_id in connection_ids:
        connection: ProviderConnection | None = None
        try:
            connection = db.get(ProviderConnection, connection_id)
            current_event = db.get(TimelineEvent, event_id)
            if not connection or not current_event:
                continue
            token = await valid_access_token(connection, db)
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            async with httpx.AsyncClient(timeout=60) as client:
                if await _push_event(client, headers, db, connection, current_event):
                    count += 1
            db.commit()
        except Exception as exc:
            db.rollback()
            provider = connection.provider if connection else str(connection_id)
            detail = exc.detail if isinstance(exc, HTTPException) else type(exc).__name__
            errors.append(f"{provider}: {detail}")
    current_event = db.get(TimelineEvent, event_id)
    if current_event:
        _refresh_event_status(db, current_event)
        if errors:
            current_event.sync_status = "sync_error"
    db.commit()
    if errors:
        raise HTTPException(status_code=502, detail="；".join(errors))
    return count


async def _pull_connection(connection: ProviderConnection, db: Session) -> int:
    if connection.sync_mode not in READ_MODES:
        return 0
    token = await valid_access_token(connection, db)
    headers = {"Authorization": f"Bearer {token}"}
    count = 0
    if connection.provider == "google":
        calendar_id = quote(connection.selected_calendar_id or "", safe="")
        url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
        params: dict[str, str] = {"singleEvents": "true", "maxResults": "2500"}
        if connection.sync_cursor:
            params["syncToken"] = connection.sync_cursor
        else:
            params["timeMin"] = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        async with httpx.AsyncClient(timeout=60) as client:
            while url:
                response = await client.get(url, headers=headers, params=params)
                if response.status_code == 410:
                    connection.sync_cursor = None
                    db.commit()
                    return await _pull_connection(connection, db)
                if response.is_error:
                    raise _provider_error(response, "读取 Google Calendar")
                payload = response.json()
                for item in payload.get("items", []):
                    _apply_external_event(db, connection, item)
                    count += 1
                next_page = payload.get("nextPageToken")
                if next_page:
                    params["pageToken"] = next_page
                else:
                    connection.sync_cursor = payload.get("nextSyncToken")
                    url = ""
    else:
        calendar_id = quote(connection.selected_calendar_id or "", safe="")
        if connection.sync_cursor:
            url = connection.sync_cursor
        else:
            start = datetime.now(UTC) - timedelta(days=30)
            end = datetime.now(UTC) + timedelta(days=365)
            url = (
                f"https://graph.microsoft.com/v1.0/me/calendars/{calendar_id}/calendarView/delta?"
                + urlencode({"startDateTime": start.isoformat(), "endDateTime": end.isoformat()})
            )
        async with httpx.AsyncClient(timeout=60) as client:
            while url:
                response = await client.get(url, headers=headers)
                if response.is_error:
                    raise _provider_error(response, "读取 Microsoft Calendar")
                payload = response.json()
                for item in payload.get("value", []):
                    _apply_external_event(db, connection, item)
                    count += 1
                url = payload.get("@odata.nextLink", "")
                if payload.get("@odata.deltaLink"):
                    connection.sync_cursor = payload["@odata.deltaLink"]
    db.flush()
    return count


async def sync_connection(connection: ProviderConnection, db: Session) -> int:
    if not connection.selected_calendar_id:
        raise HTTPException(status_code=409, detail="请先选择或创建一个专用日历")
    if connection.sync_mode == "disabled":
        return 0
    try:
        pulled = await _pull_connection(connection, db)
        pushed = await push_workspace_events(connection, db)
        connection.last_sync_at = datetime.now(UTC)
        connection.status = "connected"
        connection.last_error = None
        db.commit()
        return pulled + pushed
    except Exception as exc:
        db.rollback()
        current = db.get(ProviderConnection, connection.id)
        if current:
            detail = exc.detail if isinstance(exc, HTTPException) else type(exc).__name__
            current.last_error = str(detail)[:500]
            db.commit()
        raise


async def sync_connections(
    connections: list[ProviderConnection], db: Session
) -> tuple[dict[str, int], dict[str, str]]:
    """Converge several providers in one cycle: pull every source, then push every target."""
    results: dict[str, int] = {}
    errors: dict[str, str] = {}
    ready_to_push: list[str] = []

    for connection in connections:
        if connection.sync_mode == "disabled":
            continue
        try:
            results[connection.provider] = await _pull_connection(connection, db)
            ready_to_push.append(connection.id)
            db.commit()
        except Exception as exc:
            db.rollback()
            current = db.get(ProviderConnection, connection.id)
            detail = exc.detail if isinstance(exc, HTTPException) else type(exc).__name__
            errors[connection.provider] = str(detail)
            if current:
                current.last_error = str(detail)[:500]
                db.commit()

    for connection_id in ready_to_push:
        connection = db.get(ProviderConnection, connection_id)
        if not connection:
            continue
        try:
            results[connection.provider] = results.get(connection.provider, 0) + (
                await push_workspace_events(connection, db)
            )
            connection.last_sync_at = datetime.now(UTC)
            connection.status = "connected"
            connection.last_error = None
            db.commit()
        except Exception as exc:
            db.rollback()
            current = db.get(ProviderConnection, connection_id)
            detail = exc.detail if isinstance(exc, HTTPException) else type(exc).__name__
            errors[connection.provider] = str(detail)
            if current:
                current.last_error = str(detail)[:500]
                db.commit()

    return results, errors
