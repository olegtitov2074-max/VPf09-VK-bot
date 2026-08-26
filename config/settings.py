"""Конфигурация приложения через .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Все настройки бота. Читаются из .env, значения по умолчанию заданы здесь."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # VK
    VK_TOKEN: str
    GROUP_ID: int

    # Gemini через ProxyAPI
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_BASE_URL: str = "https://api.proxyapi.ru/google"
    API_VERSION: str = "v1beta"

    # Настройки памяти
    DEFAULT_ROLE: str = "assistant"
    MAX_HISTORY: int = 100  # максимум сообщений, хранимых в диалоге
    MESSAGE_LIMIT: int = 4000  # лимит длины сообщения (лимит VK 4096)

    # Хранилище
    STORAGE_DIR: str = "data/users"

    # Логирование
    LOG_LEVEL: str = "INFO"


_settings: Settings | None = None


def get_settings() -> Settings:
    """Возвращает синглтон настроек."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings