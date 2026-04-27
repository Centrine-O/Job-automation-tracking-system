from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # AI APIs
    gemini_api_key: str = ""
    groq_api_key: str = ""
    serpapi_key: str = ""
    openrouter_api_key: str = ""
    cohere_api_key: str = ""

    # Scoring thresholds
    skill_score_threshold: int = 65
    hire_score_threshold: int = 60

    # Application limits
    max_applications_per_day: int = 15

    # Dashboard
    dashboard_password: str = "changeme123"
    dashboard_secret_key: str = "replace-this-with-a-random-string"

    # Mode
    dry_run: bool = True


settings = Settings()
