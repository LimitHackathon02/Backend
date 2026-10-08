import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Settings:
    mock: bool = True
    api_key: str = ""
    base_url: str = "https://clovastudio.stream.ntruss.com"
    text_model: str = "HCX-DASH-002"
    vision_model: str = "HCX-005"
    timeout: float = 60
    database: str = "data/hackathon.sqlite3"
    tasks_path: str = "tasks.json"
    cache_ttl: int = 3600
    max_calls: int = 300
    token_threshold: int = 200000
    team_key: str = ""
    cors_origins: tuple[str, ...] = ("http://localhost:3000", "http://localhost:5173")
    naver_client_id: str = ""
    naver_client_secret: str = ""
    naver_base_url: str = "https://naverapihub.apigw.ntruss.com"
    # NCP Maps Application(지도 표시, Geocoding, Directions) 인증 정보. 없어도 동작하며 이동 시간은 직선거리로 대체됩니다.
    maps_client_id: str = ""
    maps_client_secret: str = ""
    maps_base_url: str = "https://maps.apigw.ntruss.com"

    @classmethod
    def from_env(cls):
        load_dotenv()
        return cls(
            mock=os.getenv("MOCK_MODE", "true").lower() == "true",
            api_key=os.getenv("CLOVA_API_KEY", ""),
            base_url=os.getenv("CLOVA_BASE_URL", cls.base_url).rstrip("/"),
            text_model=os.getenv("CLOVA_TEXT_MODEL", cls.text_model),
            vision_model=os.getenv("CLOVA_VISION_MODEL", cls.vision_model),
            timeout=float(os.getenv("CLOVA_TIMEOUT_SECONDS", "60")),
            database=os.getenv("DATABASE_PATH", cls.database),
            tasks_path=os.getenv("TASKS_PATH", cls.tasks_path),
            cache_ttl=int(os.getenv("CACHE_TTL_SECONDS", "3600")),
            max_calls=int(os.getenv("MAX_LIVE_CALLS", "300")),
            token_threshold=int(os.getenv("TOKEN_STOP_THRESHOLD", "200000")),
            team_key=os.getenv("TEAM_API_KEY", ""),
            cors_origins=tuple(x.strip() for x in os.getenv("CORS_ORIGINS", ",".join(cls.cors_origins)).split(",") if x.strip()),
            naver_client_id=os.getenv("NAVER_SEARCH_CLIENT_ID", ""),
            naver_client_secret=os.getenv("NAVER_SEARCH_CLIENT_SECRET", ""),
            naver_base_url=os.getenv("NAVER_SEARCH_BASE_URL", cls.naver_base_url).rstrip("/"),
            maps_client_id=os.getenv("NCP_MAPS_CLIENT_ID", ""),
            maps_client_secret=os.getenv("NCP_MAPS_CLIENT_SECRET", ""),
            maps_base_url=os.getenv("NCP_MAPS_BASE_URL", cls.maps_base_url).rstrip("/"),
        )
