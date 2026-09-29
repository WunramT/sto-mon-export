"""Laufzeitkonfiguration des Backends (Umgebungsvariablen bzw. sens.env)."""

from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Export konfigurierbare Stücklisten"
    app_version: str = "0.1.0"
    # "production": Passwort Pflicht; "development": ohne MASTER_PASSWORD_ADMIN ist die Anmeldung abgeschaltet
    mode: str = "production"
    root_path: str = ""

    # Sicherheit: ein gemeinsames Passwort für alle (Prototyp – jede:r hat alle Rechte)
    secret_key: str
    master_password_admin: str = ""
    access_token_expire_minutes: int = 12 * 60

    # Datenbank (eigene Datenbank im gemeinsamen Postgres-Container)
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "konfig_stueckliste_export"
    database_user: str = "postgres"
    database_password: str = ""

    # Vom Host gemountete Verzeichnisse
    exports_dir: Path = Path("/data/exports")
    out_dir: Path = Path("/data/out")
    # Ist die Datenbank leer und liegen keine Exporte vor: synthetische Beispieldaten laden (Demo/Test)
    demo_fixtures: bool = False

    cors_origins: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

    @field_validator("demo_fixtures", mode="before")
    @classmethod
    def _bool(cls, v):
        if isinstance(v, str):
            return v.strip().upper() in ("T", "TRUE", "1", "YES", "JA", "ON")
        return bool(v)

    @field_validator("mode")
    @classmethod
    def _mode(cls, v: str) -> str:
        if v not in ("development", "production"):
            raise ValueError("MODE muss development oder production sein")
        return v

    @field_validator("secret_key")
    @classmethod
    def _secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY muss mindestens 32 Zeichen lang sein")
        return v

    @property
    def auth_aktiv(self) -> bool:
        return self.mode == "production" or bool(self.master_password_admin)

    @property
    def database_url(self) -> str:
        from urllib.parse import quote_plus

        return (f"postgresql+psycopg://{quote_plus(self.database_user)}:{quote_plus(self.database_password)}"
                f"@{self.database_host}:{self.database_port}/{self.database_name}?connect_timeout=10")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def pruefe(self) -> None:
        if self.mode == "production" and not self.master_password_admin:
            raise ValueError("MODE=production verlangt MASTER_PASSWORD_ADMIN")
        if self.mode == "production" and not self.database_password:
            import logging

            logging.getLogger("app").error("DATABASE_PASSWORD ist leer – die Verbindung zur Datenbank "
                                           "wird scheitern (sens.env)")


settings = Settings()  # type: ignore[call-arg]
