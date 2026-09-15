from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    pubmed_api_key: str = ""
    ai_provider: str = "mock"
    ai_api_key: str = ""
    database_url: str = "sqlite:///data/pubmed_demo.db"
    use_mock_on_error: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()

