"""DB 대신 쓰는 저장소: 메모리(dict)에 두고, 바뀔 때마다 JSON 파일로 저장.
서버를 껐다 켜도 data/meetings.json 에서 다시 불러온다."""
import json
import os
import secrets
import string
import threading
from datetime import datetime

from app.config import settings
from app.errors import ApiError

_lock = threading.Lock()
_meetings: dict = {}


def _load() -> None:
    if os.path.exists(settings.DATA_PATH):
        with open(settings.DATA_PATH, encoding="utf-8") as f:
            _meetings.update(json.load(f))


def save() -> None:
    with _lock:
        folder = os.path.dirname(settings.DATA_PATH)
        if folder:
            os.makedirs(folder, exist_ok=True)
        tmp = settings.DATA_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_meetings, f, ensure_ascii=False, indent=2)
        os.replace(tmp, settings.DATA_PATH)


def new_id(length: int, upper: bool = False) -> str:
    chars = (string.ascii_uppercase if upper else string.ascii_lowercase) + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


def new_member(name: str, is_host: bool = False) -> dict:
    return {"id": new_id(8), "name": name, "is_host": is_host,
            "availability": {}, "preference": None}


def create_meeting(title, candidate_dates, time_range, slot_minutes, host_name) -> dict:
    meeting_id = new_id(6, upper=True)
    while meeting_id in _meetings:
        meeting_id = new_id(6, upper=True)
    meeting = {
        "id": meeting_id,
        "title": title,
        "candidate_dates": sorted(set(candidate_dates)),
        "time_range": time_range,
        "slot_minutes": slot_minutes,
        "status": "collecting",
        "confirmed": None,
        "members": [new_member(host_name, is_host=True)],
        "recommendations": [],
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    _meetings[meeting_id] = meeting
    save()
    return meeting


def get_meeting(meeting_id: str) -> dict:
    meeting = _meetings.get(meeting_id.upper())
    if not meeting:
        raise ApiError(404, "MEETING_NOT_FOUND", "모임을 찾을 수 없어요. 링크를 다시 확인해 주세요.")
    return meeting


def get_member(meeting: dict, member_id: str) -> dict:
    for m in meeting["members"]:
        if m["id"] == member_id:
            return m
    raise ApiError(404, "MEMBER_NOT_FOUND", "참여자를 찾을 수 없어요. 다시 입장해 주세요.")


_load()