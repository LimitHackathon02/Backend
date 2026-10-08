from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.settings import get_settings

settings = get_settings()
Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)


def require_team_key(x_team_key: str | None = Header(default=None)):
    if settings.team_key and x_team_key != settings.team_key:
        raise HTTPException(status_code=401, detail="X-Team-Key가 올바르지 않습니다.")


app = FastAPI(
    title="Backend",
    docs_url="/docs" if settings.is_dev else None,
    redoc_url=None,
    dependencies=[Depends(require_team_key)],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "Backend is running"}


@app.get("/health")
def health():
    # 키 값은 노출하지 않고 설정 여부만 반환
    return {
        "status": "ok",
        "env": settings.app_env,
        "mock": settings.mock,
        "clova_api_key_configured": bool(settings.clova_api_key),
        "naver_search_configured": bool(settings.naver_client_id and settings.naver_client_secret),
        "maps_configured": bool(settings.maps_client_id and settings.maps_client_secret),
    }
