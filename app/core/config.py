from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_prompts_dir() -> Path:
    """FastAPI ルートからの prompts/completed 相対パス."""
    return Path(__file__).resolve().parent.parent.parent / "prompts" / "completed"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    dry_run: bool = Field(default=False, validation_alias="DRY_RUN")
    content_source_api_key: str = Field(default="", validation_alias="CONTENT_SOURCE_API_KEY")
    analysis_api_key: str = Field(default="", validation_alias="ANALYSIS_API_KEY")
    database_url: str = Field(
        default="postgresql://localhost:5432/preness_analysis",
        validation_alias="DATABASE_URL",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="REDIS_URL",
    )
    openai_api_key: Optional[str] = Field(default=None, validation_alias="OPENAI_API_KEY")
    generation_openai_api_key: Optional[str] = Field(
        default=None, validation_alias="GENERATION_OPENAI_API_KEY"
    )
    analysis_openai_api_key: Optional[str] = Field(default=None, validation_alias="ANALYSIS_OPENAI_API_KEY")
    generation_prompts_dir: Path = Field(
        default_factory=_default_prompts_dir,
        validation_alias="GENERATION_PROMPTS_DIR",
        description="プロンプト .txt が入ったディレクトリ (prompts/completed)",
    )
    # Azure Speech (Optional)
    azure_speech_key: Optional[str] = Field(default=None, validation_alias="AZURE_SPEECH_KEY")
    azure_speech_region: Optional[str] = Field(default=None, validation_alias="AZURE_SPEECH_REGION")
    # AWS S3 (Optional)
    aws_access_key_id: Optional[str] = Field(default=None, validation_alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(default=None, validation_alias="AWS_SECRET_ACCESS_KEY")
    s3_bucket: Optional[str] = Field(default=None, validation_alias="S3_BUCKET")
    s3_region: Optional[str] = Field(default=None, validation_alias="S3_REGION")
    s3_mock_audio_prefix: str = Field(
        default="mocks/audio",
        validation_alias="S3_MOCK_AUDIO_PREFIX",
    )
    rails_api_base_url: Optional[str] = Field(
        default=None, validation_alias="RAILS_API_BASE_URL"
    )

    @model_validator(mode="after")
    def _api_keys_required_unless_dry_run(self) -> "Settings":
        if not self.dry_run:
            if not (self.content_source_api_key or "").strip():
                raise ValueError("CONTENT_SOURCE_API_KEY is required when DRY_RUN is not true")
            if not (self.analysis_api_key or "").strip():
                raise ValueError("ANALYSIS_API_KEY is required when DRY_RUN is not true")
        return self


@lru_cache()
def get_settings() -> Settings:
    return Settings()

