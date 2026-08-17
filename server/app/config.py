from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Auto Calendar"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://autocalendar:autocalendar@postgres:5432/autocalendar"
    public_base_url: str = "http://localhost:8080"
    cors_origins: str = "http://localhost:3000,http://localhost:8080"

    session_cookie_name: str = "ac_session"
    session_cookie_secure: bool = False
    session_days: int = 14
    sync_interval_minutes: int = 15
    app_encryption_key: str
    initial_admin_email: str = "admin@autocalendar.app"
    initial_admin_password: str

    google_client_id: str = ""
    google_client_secret: str = ""
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_tenant: str = "consumers"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
