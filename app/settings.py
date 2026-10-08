import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _list(name: str, default: str = "") -> tuple[str, ...]:
    return tuple(x.strip() for x in os.getenv(name, default).split(",") if x.strip())


@dataclass(frozen=True)
class Settings:
    app_env: str
    host: str
    port: int
    cors_origins: tuple[str, ...]
    team_key: str

    mock: bool
    clova_api_key: str
    clova_base_url: str
    clova_text_model: str
    clova_vision_model: str
    clova_timeout: float

    naver_client_id: str
    naver_client_secret: str
    naver_base_url: str

    maps_client_id: str
    maps_client_secret: str
    maps_base_url: str

    database_path: str

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            host=os.getenv("HOST", "127.0.0.1"),
            port=int(os.getenv("PORT", "8000")),
            cors_origins=_list("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"),
            team_key=os.getenv("TEAM_API_KEY", ""),
            mock=_bool("MOCK_MODE", True),
            clova_api_key=os.getenv("CLOVA_API_KEY", ""),
            clova_base_url=os.getenv("CLOVA_BASE_URL", "https://clovastudio.stream.ntruss.com").rstrip("/"),
            clova_text_model=os.getenv("CLOVA_TEXT_MODEL", "HCX-DASH-002"),
            clova_vision_model=os.getenv("CLOVA_VISION_MODEL", "HCX-005"),
            clova_timeout=float(os.getenv("CLOVA_TIMEOUT_SECONDS", "60")),
            naver_client_id=os.getenv("NAVER_SEARCH_CLIENT_ID", ""),
            naver_client_secret=os.getenv("NAVER_SEARCH_CLIENT_SECRET", ""),
            naver_base_url=os.getenv("NAVER_SEARCH_BASE_URL", "https://naverapihub.apigw.ntruss.com").rstrip("/"),
            maps_client_id=os.getenv("NCP_MAPS_CLIENT_ID", ""),
            maps_client_secret=os.getenv("NCP_MAPS_CLIENT_SECRET", ""),
            maps_base_url=os.getenv("NCP_MAPS_BASE_URL", "https://maps.apigw.ntruss.com").rstrip("/"),
            database_path=os.getenv("DATABASE_PATH", "data/app.sqlite3"),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
