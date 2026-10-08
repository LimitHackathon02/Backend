"""모임 없이 쓰는 빠른 추천, 토큰 사용량, 헬스체크."""
from typing import Annotated

from fastapi import APIRouter, Body

from app import examples as ex
from app.clients.hcx_client import USAGE
from app.config import settings
from app.schemas import QuickReq
from app.services import preference_service, recommend_service

router = APIRouter(tags=["misc"])


@router.get("/health")
def health():
    return {"ok": True, "mock": settings.MOCK_MODE}


@router.get("/api/usage")
def usage():
    return USAGE


@router.post("/api/recommend/quick")
async def quick_recommend(req: Annotated[QuickReq, Body(openapi_examples=ex.QUICK)]):
    people = []
    for p in req.people:
        pref, _ = await preference_service.build_preference(p.text)
        people.append({"name": p.name, "preference": pref})
    return await recommend_service.recommend(people, req.count, req.radius_m, req.extra_text)
