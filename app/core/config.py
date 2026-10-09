from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    database_url: str  # Railway PostgreSQL
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
