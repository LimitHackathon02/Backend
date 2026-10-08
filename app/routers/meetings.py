"""/api/meetings/... 주소들. 입력 받고 -> 서비스 부르고 -> 저장하고 -> 돌려준다."""
from fastapi import APIRouter

from app import store
from app.errors import ApiError
from app.schemas import (AvailabilityReq, ConfirmReq, CreateMeetingReq, JoinReq,
                         PreferenceReq, RecommendReq, TextReq)
from app.services import preference_service, recommend_service, schedule_service

router = APIRouter(prefix="/api/meetings", tags=["meetings"])
MAX_MEMBERS = 10


# ---------- 4. 모임 ----------
@router.post("", status_code=201)
def create_meeting(req: CreateMeetingReq):
    if req.time_range.start >= req.time_range.end:
        raise ApiError(400, "VALIDATION_ERROR", "시작 시간이 끝 시간보다 빨라야 해요.")
    meeting = store.create_meeting(req.title, req.candidate_dates, req.time_range.model_dump(),
                                   req.slot_minutes, req.host_name)
    return {"meeting_id": meeting["id"], "host_member_id": meeting["members"][0]["id"],
            "share_path": f"/join.html?m={meeting['id']}", "meeting": meeting}


@router.get("/{meeting_id}")
def get_meeting(meeting_id: str):
    return store.get_meeting(meeting_id)


@router.post("/{meeting_id}/members", status_code=201)
def join_meeting(meeting_id: str, req: JoinReq):
    meeting = store.get_meeting(meeting_id)
    if len(meeting["members"]) >= MAX_MEMBERS:
        raise ApiError(400, "MEETING_FULL", "인원이 가득 찼어요.")
    if any(m["name"] == req.name for m in meeting["members"]):
        raise ApiError(409, "NAME_TAKEN", "같은 이름이 이미 있어요. 다른 이름을 써 주세요.")
    member = store.new_member(req.name)
    meeting["members"].append(member)
    store.save()
    return member


# ---------- 5. 일정 ----------
@router.put("/{meeting_id}/members/{member_id}/availability")
def save_availability(meeting_id: str, member_id: str, req: AvailabilityReq):
    meeting = store.get_meeting(meeting_id)
    member = store.get_member(meeting, member_id)
    member["availability"] = schedule_service.clean_availability(meeting, req.availability)
    store.save()
    return member


@router.post("/{meeting_id}/members/{member_id}/availability/parse")
async def parse_availability(meeting_id: str, member_id: str, req: TextReq):
    meeting = store.get_meeting(meeting_id)
    store.get_member(meeting, member_id)
    return await schedule_service.parse_availability_text(meeting, req.text)


@router.get("/{meeting_id}/schedule")
def get_schedule(meeting_id: str, min_hours: float = 2, top: int = 5):
    meeting = store.get_meeting(meeting_id)
    return schedule_service.best_slots(meeting, min_hours=min_hours, top=top)


@router.post("/{meeting_id}/schedule/confirm")
def confirm_schedule(meeting_id: str, req: ConfirmReq):
    meeting = store.get_meeting(meeting_id)
    member = store.get_member(meeting, req.member_id)
    if not member["is_host"]:
        raise ApiError(403, "NOT_HOST", "방장만 확정할 수 있어요.")
    if req.date not in meeting["candidate_dates"]:
        raise ApiError(400, "INVALID_DATE", "열려 있는 날짜만 고를 수 있어요.")
    meeting["confirmed"] = {"date": req.date, "start": req.start, "end": req.end}
    meeting["status"] = "scheduled"
    store.save()
    return meeting


# ---------- 6. 선호 ----------
@router.post("/{meeting_id}/members/{member_id}/preference")
async def save_preference(meeting_id: str, member_id: str, req: PreferenceReq):
    meeting = store.get_meeting(meeting_id)
    member = store.get_member(meeting, member_id)
    loc = req.start_location.model_dump() if req.start_location else None
    pref, found = await preference_service.build_preference(req.text, loc)
    member["preference"] = pref
    store.save()
    return {"member_id": member_id, "preference": pref, "location_found": found}


@router.get("/{meeting_id}/preferences/summary")
async def preference_summary(meeting_id: str):
    meeting = store.get_meeting(meeting_id)
    prefs = [m["preference"] for m in meeting["members"] if m["preference"]]
    if not prefs:
        raise ApiError(400, "NO_PREFERENCES", "먼저 원하는 조건을 적어 주세요.")
    merged = preference_service.merge_group(prefs)
    return {"responded": len(prefs), "total": len(meeting["members"]), **merged,
            "summary": await preference_service.group_summary(merged)}


# ---------- 7. 추천 ----------
@router.post("/{meeting_id}/recommend")
async def recommend(meeting_id: str, req: RecommendReq):
    meeting = store.get_meeting(meeting_id)
    people = [{"name": m["name"], "preference": m["preference"]} for m in meeting["members"]]
    result = await recommend_service.recommend(people, req.count, req.radius_m, req.extra_text)
    meeting["recommendations"] = result["recommendations"]
    meeting["status"] = "recommended"
    store.save()
    return result