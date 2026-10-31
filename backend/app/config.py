from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/nalam"
    SUPABASE_DATABASE_URL: str = ""

    # Bolna AI
    BOLNA_API_KEY: str = ""
    BOLNA_AGENT_ID_TAMIL: str = ""
    BOLNA_WEBHOOK_SECRET: str = ""

    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_FROM: str = "whatsapp:+14155238886"

    # App
    APP_ENV: str = "development"
    APP_BASE_URL: str = ""
    BACKEND_PUBLIC_URL: str = ""
    FRONTEND_ORIGIN: str = ""
    CORS_ORIGINS: str = "http://localhost:3000"
    DEMO_FAMILY_WHATSAPP: str = ""
    DEMO_MODE: bool = False
    DEMO_RETRY_DELAY_SECONDS: int = 1800
    DEFAULT_TIMEZONE: str = "Asia/Kolkata"
    LOG_LEVEL: str = "INFO"

    @property
    def effective_database_url(self) -> str:
        """Return SUPABASE_DATABASE_URL if set, else DATABASE_URL."""
        return self.SUPABASE_DATABASE_URL if self.SUPABASE_DATABASE_URL else self.DATABASE_URL


settings = Settings()
