"""/api/meeting/... 주소들. 입력 받고 -> 서비스 부르고 -> 저장하고 -> 돌려준다.
프로토타입이라 모임은 하나뿐이고 로그인·ID가 없다. 참여자는 이름으로 구분하며, 처음 보는 이름이면 자동으로 추가된다."""
from typing import Annotated

from fastapi import APIRouter, Body

from app import examples as ex
from app import store
from app.errors import ApiError
from app.schemas import (AvailabilityReq, ConfirmReq, CreateMeetingReq, JoinReq,
                         PreferenceReq, RecommendReq, TextReq)
from app.services import preference_service, recommend_service, schedule_service

router = APIRouter(prefix="/api/meeting", tags=["meeting"])


# ---------- 4. 모임 ----------
@router.post("", status_code=201)
def create_meeting(req: Annotated[CreateMeetingReq, Body(openapi_examples=ex.CREATE_MEETING)]):
    """새 모임으로 초기화. 모든 값이 선택이라 {} 만 보내도 된다."""
    if req.time_range.start >= req.time_range.end:
        raise ApiError(400, "VALIDATION_ERROR", "시작 시간이 끝 시간보다 빨라야 해요.")
    if len(set(req.members)) > store.MAX_MEMBERS:
        raise ApiError(400, "MEETING_FULL", "인원이 가득 찼어요.")
    return store.create_meeting(req.title, req.candidate_dates, req.time_range.model_dump(),
                                req.slot_minutes, req.members)


@router.get("")
def get_meeting():
    return store.get_meeting()


@router.post("/members", status_code=201)
def join_meeting(req: Annotated[JoinReq, Body(openapi_examples=ex.JOIN)]):
    meeting = store.get_meeting()
    member = store.get_member(meeting, req.name)
    store.save()
    return member


# ---------- 5. 일정 ----------
@router.put("/availability")
def save_availability(req: Annotated[AvailabilityReq, Body(openapi_examples=ex.AVAILABILITY)]):
    meeting = store.get_meeting()
    availability = schedule_service.clean_availability(meeting, req.availability)
    member = store.get_member(meeting, req.name)
    member["availability"] = availability
    store.save()
    return member


@router.post("/availability/parse")
async def parse_availability(req: Annotated[TextReq, Body(openapi_examples=ex.PARSE_AVAILABILITY)]):
    return await schedule_service.parse_availability_text(store.get_meeting(), req.text)


@router.get("/schedule")
def get_schedule(min_hours: float = 2, top: int = 5):
    return schedule_service.best_slots(store.get_meeting(), min_hours=min_hours, top=top)


@router.post("/schedule/confirm")
def confirm_schedule(req: Annotated[ConfirmReq, Body(openapi_examples=ex.CONFIRM)]):
    meeting = store.get_meeting()
    if req.date not in meeting["candidate_dates"]:
        raise ApiError(400, "INVALID_DATE", "열려 있는 날짜만 고를 수 있어요.")
    meeting["confirmed"] = {"date": req.date, "start": req.start, "end": req.end}
    meeting["status"] = "scheduled"
    store.save()
    return meeting


# ---------- 6. 선호 ----------
@router.post("/preference")
async def save_preference(req: Annotated[PreferenceReq, Body(openapi_examples=ex.PREFERENCE)]):
    meeting = store.get_meeting()
    loc = req.start_location.model_dump() if req.start_location else None
    pref, found = await preference_service.build_preference(req.text, loc)
    member = store.get_member(meeting, req.name)
    member["preference"] = pref
    store.save()
    return {"name": req.name, "preference": pref, "location_found": found}


@router.get("/preferences/summary")
async def preference_summary():
    meeting = store.get_meeting()
    prefs = [m["preference"] for m in meeting["members"] if m["preference"]]
    if not prefs:
        raise ApiError(400, "NO_PREFERENCES", "먼저 원하는 조건을 적어 주세요.")
    merged = preference_service.merge_group(prefs)
    return {"responded": len(prefs), "total": len(meeting["members"]), **merged,
            "summary": await preference_service.group_summary(merged)}


# ---------- 7. 추천 ----------
@router.post("/recommend")
async def recommend(req: Annotated[RecommendReq, Body(openapi_examples=ex.RECOMMEND)]):
    meeting = store.get_meeting()
    people = [{"name": m["name"], "preference": m["preference"]} for m in meeting["members"]]
    result = await recommend_service.recommend(people, req.count, req.radius_m, req.extra_text)
    meeting["recommendations"] = result["recommendations"]
    meeting["status"] = "recommended"
    store.save()
    return result
