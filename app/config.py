#.env 읽기
"""환경변수(.env)를 읽어서 settings 하나로 모아두는 파일."""
import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    MOCK_MODE: bool = os.getenv("MOCK_MODE", "1") == "1"
    CLOVA_API_KEY: str = os.getenv("CLOVA_API_KEY", "")
    CLOVA_BASE_URL: str = os.getenv("CLOVA_BASE_URL", "https://clovastudio.stream.ntruss.com")
    HCX_MODEL: str = os.getenv("HCX_MODEL", "HCX-007")
    HCX_LIGHT_MODEL: str = os.getenv("HCX_LIGHT_MODEL", "HCX-DASH-002")
    NAVER_CLIENT_ID: str = os.getenv("NAVER_CLIENT_ID", "")
    NAVER_CLIENT_SECRET: str = os.getenv("NAVER_CLIENT_SECRET", "")
    NCP_MAPS_KEY_ID: str = os.getenv("NCP_MAPS_KEY_ID", "")
    NCP_MAPS_KEY: str = os.getenv("NCP_MAPS_KEY", "")
    NCP_MAPS_BASE: str = os.getenv("NCP_MAPS_BASE", "https://maps.apigw.ntruss.com")
    DATA_PATH: str = os.getenv("DATA_PATH", "data/meetings.json")
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "*").split(",")


settings = Settings()