"""서버 시작점. 실행: uvicorn app.main:app --reload"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import meetings, misc

app = FastAPI(title="Backend/new", version="1.0")

# 프론트(다른 포트/도메인)에서 호출할 수 있게 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 입력 형식 오류(422)를 명세서의 400 VALIDATION_ERROR 모양으로 바꿈
@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(x) for x in first.get("loc", []) if x != "body")
    return JSONResponse(status_code=400, content={"detail": {
        "code": "VALIDATION_ERROR",
        "message": f"입력값을 다시 확인해 주세요 ({where}: {first.get('msg', '')})",
    }})


app.include_router(meetings.router)
app.include_router(misc.router)