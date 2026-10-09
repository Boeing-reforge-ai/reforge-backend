from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    database_url: str  # Railway PostgreSQL
    cors_origins: list[str] = ["http://localhost:5173"]
    station_key: str = ""  # 스캔 스테이션 인증 (X-Station-Key), 비어 있으면 등록 거부
    upload_dir: str = "uploads"
    analysis_step_sec: float = 0.5  # 판정 단계별 대기 (시연용 진행률 애니메이션)

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
