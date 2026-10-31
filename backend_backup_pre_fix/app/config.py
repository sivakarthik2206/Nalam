from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/nalam"

    # Bolna AI
    BOLNA_API_KEY: str = ""
    BOLNA_AGENT_ID_HINDI: str = ""
    BOLNA_AGENT_ID_TAMIL: str = ""
    BOLNA_AGENT_ID_ENGLISH: str = ""

    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_FROM: str = "whatsapp:+14155238886"

    # Sarvam AI
    SARVAM_API_KEY: str = ""

    # App
    APP_BASE_URL: str = ""


settings = Settings()
