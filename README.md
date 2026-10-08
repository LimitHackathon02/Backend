# Backend

Python 3.11 이상, FastAPI 기반 백엔드입니다.

## 실행

Windows (PowerShell):

```powershell
.\scripts\start.ps1
```

macOS / Linux / Git Bash:

```sh
sh scripts/start.sh
```

스크립트가 `.venv` 생성, 패키지 설치, `.env` 생성(없을 때 `.env.example` 복사)까지 한 뒤 서버를 켭니다.
실행 후 http://127.0.0.1:8000/docs 에서 API를 확인합니다.

PowerShell에서 "스크립트를 실행할 수 없습니다" 오류가 나면 한 번만 실행하세요.

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

직접 실행할 때:

```powershell
.venv\Scripts\python -m uvicorn app.main:app --reload
```

## 환경변수 (.env)

| 변수 | 설명 | 기본값 |
|---|---|---|
| `APP_ENV` | `development`일 때만 `/docs` 노출 | `development` |
| `HOST`, `PORT` | 서버 주소 (스크립트는 `PORT`만 사용) | `127.0.0.1`, `8000` |
| `CORS_ORIGINS` | 허용할 프론트엔드 주소, 쉼표 구분 | `http://localhost:3000,http://localhost:5173` |
| `TEAM_API_KEY` | 설정 시 모든 요청에 `X-Team-Key` 헤더 필요 | 비어 있음 |
| `MOCK_MODE` | `true`면 외부 API 호출 없이 동작 | `true` |
| `CLOVA_API_KEY` | CLOVA Studio API 키 | |
| `CLOVA_BASE_URL`, `CLOVA_TEXT_MODEL`, `CLOVA_VISION_MODEL`, `CLOVA_TIMEOUT_SECONDS` | HyperCLOVA X 호출 설정 | |
| `NAVER_SEARCH_CLIENT_ID`, `NAVER_SEARCH_CLIENT_SECRET`, `NAVER_SEARCH_BASE_URL` | 네이버 지역 검색 (NAVER API HUB) | |
| `NCP_MAPS_CLIENT_ID`, `NCP_MAPS_CLIENT_SECRET`, `NCP_MAPS_BASE_URL` | NCP Maps | |
| `DATABASE_PATH` | SQLite 파일 경로 | `data/app.sqlite3` |

`.env`를 수정하면 서버를 재시작해야 반영됩니다. 설정 상태는 `GET /health`로 확인합니다(키 값은 반환하지 않고 설정 여부만 표시).

## 테스트

```powershell
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest -q
```
