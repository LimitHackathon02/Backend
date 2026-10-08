"""DB 대신 쓰는 저장소: 프로토타입이라 모임은 서버에 '하나만' 둔다.
메모리에 두고, 바뀔 때마다 JSON 파일로 저장. 서버를 껐다 켜도 data/meetings.json 에서 다시 불러온다.
모임을 만들지 않고 API를 불러도 기본 모임이 자동으로 생긴다."""
import json
import os
import threading
from datetime import datetime

from app.config import settings
from app.errors import ApiError
from app.schemas import default_dates

MAX_MEMBERS = 10

_lock = threading.Lock()
_meeting: dict | None = None


def _load() -> None:
    global _meeting
    if not os.path.exists(settings.DATA_PATH):
        return
    with open(settings.DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    if "members" in data:
        _meeting = data
    elif data:  # 예전 형식({모임ID: 모임}) -> 가장 최근 모임 하나만 사용
        _meeting = max(data.values(), key=lambda m: m.get("created_at", ""))


def save() -> None:
    with _lock:
        folder = os.path.dirname(settings.DATA_PATH)
        if folder:
            os.makedirs(folder, exist_ok=True)
        tmp = settings.DATA_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_meeting, f, ensure_ascii=False, indent=2)
        os.replace(tmp, settings.DATA_PATH)


def new_member(name: str) -> dict:
    return {"name": name, "availability": {}, "preference": None}


def create_meeting(title="우리 모임", candidate_dates=None, time_range=None,
                   slot_minutes=60, members=()) -> dict:
    """새 모임으로 교체(기존 모임은 사라짐)."""
    global _meeting
    _meeting = {
        "title": title,
        "candidate_dates": sorted(set(candidate_dates or default_dates())),
        "time_range": time_range or {"start": "10:00", "end": "23:00"},
        "slot_minutes": slot_minutes,
        "status": "collecting",
        "confirmed": None,
        "members": [new_member(n) for n in dict.fromkeys(members)],
        "recommendations": [],
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    save()
    return _meeting


def get_meeting() -> dict:
    return _meeting if _meeting is not None else create_meeting()


def get_member(meeting: dict, name: str) -> dict:
    """이름으로 참여자를 찾고, 없으면 새로 추가한다."""
    for m in meeting["members"]:
        if m["name"] == name:
            return m
    if len(meeting["members"]) >= MAX_MEMBERS:
        raise ApiError(400, "MEETING_FULL", "인원이 가득 찼어요.")
    member = new_member(name)
    meeting["members"].append(member)
    return member


_load()
