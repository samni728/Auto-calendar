import asyncio
import time
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

from .api.auth import router as auth_router
from .api.connections import router as connections_router
from .api.hotel import router as hotel_router
from .config import get_settings
from .db import SessionLocal, engine
from .models import ProviderConnection
from .seed import seed_database
from .services.providers import sync_connection


def initialize_database() -> None:
    last_error: Exception | None = None
    for _ in range(20):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            with SessionLocal() as db:
                seed_database(db)
            return
        except OperationalError as exc:
            last_error = exc
            time.sleep(1)
    raise RuntimeError("Database did not become ready") from last_error


async def periodic_calendar_sync() -> None:
    while True:
        await asyncio.sleep(max(1, get_settings().sync_interval_minutes) * 60)
        with SessionLocal() as db:
            connections = db.scalars(
                select(ProviderConnection).where(
                    ProviderConnection.status == "connected",
                    ProviderConnection.selected_calendar_id.is_not(None),
                )
            ).all()
            for connection in connections:
                try:
                    await sync_connection(connection, db)
                except Exception as exc:
                    db.rollback()
                    current = db.get(ProviderConnection, connection.id)
                    if current:
                        current.last_error = f"Background sync failed: {type(exc).__name__}"
                        db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    task = asyncio.create_task(periodic_calendar_sync())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(hotel_router)
app.include_router(connections_router)


@app.get("/healthz", tags=["operations"])
def healthz():
    return {"status": "ok"}
