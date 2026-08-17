from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from urllib.parse import quote, urlencode

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import ProviderConnection, TimelineEvent
from ..security import decrypt_secret, encrypt_secret
from ..time_utils import as_utc

GOOGLE_SCOPES = [
    "openid",
    "email",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
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
    if provider == "google":
        url = "https://openidconnect.googleapis.com/v1/userinfo"
    else:
        url = "https://graph.microsoft.com/v1.0/me?$select=mail,userPrincipalName"
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=headers)
    if response.is_error:
        return None
    payload = response.json()
    return payload.get("email") or payload.get("mail") or payload.get("userPrincipalName")


async def list_calendars(connection: ProviderConnection, db: Session) -> list[dict]:
    token = await valid_access_token(connection, db)
    headers = {"Authorization": f"Bearer {token}"}
    if connection.provider == "google":
        url = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
    else:
        url = "https://graph.microsoft.com/v1.0/me/calendars?$select=id,name,isDefaultCalendar"
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=headers)
    if response.is_error:
        raise HTTPException(status_code=502, detail="Unable to retrieve calendars")
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


def _date_value(value: dict | None, fallback: date) -> date:
    if not value:
        return fallback
    raw = value.get("date") or value.get("dateTime")
    if not raw:
        return fallback
    return date.fromisoformat(raw[:10])


def _upsert_external_event(
    db: Session, connection: ProviderConnection, payload: dict, provider: str
) -> None:
    external_id = payload.get("id")
    if not external_id:
        return
    event = db.scalar(
        select(TimelineEvent).where(
            TimelineEvent.provider_connection_id == connection.id,
            TimelineEvent.external_event_id == external_id,
        )
    )
    if not event:
        event = TimelineEvent(
            workspace_id=connection.workspace_id,
            provider_connection_id=connection.id,
            external_event_id=external_id,
            room_id=None,
            title="Imported event",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1),
            source_system=provider,
            sync_status="synced",
        )
        db.add(event)
    if provider == "google":
        cancelled = payload.get("status") == "cancelled"
        event.title = payload.get("summary") or "Google Calendar event"
        event.start_date = _date_value(payload.get("start"), event.start_date)
        event.end_date = _date_value(payload.get("end"), event.start_date + timedelta(days=1))
        event.external_version = payload.get("etag")
    else:
        cancelled = payload.get("isCancelled", False) or "@removed" in payload
        event.title = payload.get("subject") or "Microsoft Calendar event"
        event.start_date = _date_value(payload.get("start"), event.start_date)
        event.end_date = _date_value(payload.get("end"), event.start_date + timedelta(days=1))
        event.external_version = payload.get("changeKey")
    if event.end_date <= event.start_date:
        event.end_date = event.start_date + timedelta(days=1)
    event.status = "cancelled" if cancelled else "reserved"
    event.is_deleted = cancelled
    event.sync_status = "synced"


async def sync_connection(connection: ProviderConnection, db: Session) -> int:
    if not connection.selected_calendar_id:
        raise HTTPException(status_code=409, detail="Select a calendar before syncing")
    token = await valid_access_token(connection, db)
    headers = {"Authorization": f"Bearer {token}"}
    count = 0
    if connection.provider == "google":
        calendar_id = quote(connection.selected_calendar_id, safe="")
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
                    return await sync_connection(connection, db)
                if response.is_error:
                    raise HTTPException(status_code=502, detail="Google Calendar sync failed")
                payload = response.json()
                for item in payload.get("items", []):
                    _upsert_external_event(db, connection, item, "google")
                    count += 1
                next_page = payload.get("nextPageToken")
                if next_page:
                    params["pageToken"] = next_page
                else:
                    connection.sync_cursor = payload.get("nextSyncToken")
                    url = ""
    else:
        calendar_id = quote(connection.selected_calendar_id, safe="")
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
                    raise HTTPException(status_code=502, detail="Microsoft Calendar sync failed")
                payload = response.json()
                for item in payload.get("value", []):
                    _upsert_external_event(db, connection, item, "microsoft")
                    count += 1
                url = payload.get("@odata.nextLink", "")
                if payload.get("@odata.deltaLink"):
                    connection.sync_cursor = payload["@odata.deltaLink"]
    connection.last_sync_at = datetime.now(UTC)
    connection.status = "connected"
    connection.last_error = None
    db.commit()
    return count
