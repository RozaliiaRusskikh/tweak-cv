from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: SecretStr
    public_url: str = ""
    slack_bot_token: SecretStr
    slack_signing_secret: SecretStr
    slack_channel_id: str
    langfuse_public_key: SecretStr
    langfuse_secret_key: SecretStr
    langfuse_host: str = "https://cloud.langfuse.com"
    database_url: str = "sqlite:///./data/tailorcv.db"
    output_dir: Path = Path("output/resumes")
    gemini_api_key_eval: SecretStr | None = None


settings = Settings()
