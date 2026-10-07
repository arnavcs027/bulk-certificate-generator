from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CERT_")

    database_url: str = "sqlite:///./certificates.db"
    storage_dir: Path = Path("storage/certificates")
    template_title: str = "Certificate of Completion"
    template_subtitle: str = "This certifies that"


settings = Settings()
settings.storage_dir.mkdir(parents=True, exist_ok=True)
