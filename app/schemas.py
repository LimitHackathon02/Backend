"""요청 JSON의 모양. 여기서 틀리면 FastAPI가 자동으로 400 VALIDATION_ERROR 를 돌려준다."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


def _check_date(v: str) -> str:
    datetime.strptime(v, "%Y-%m-%d")  # 형식이 틀리면 ValueError
    return v


def _check_time(v: str) -> str:
    datetime.strptime(v, "%H:%M")
    return v


class TimeRange(BaseModel):
    start: str = "10:00"
    end: str = "23:00"

    _v_start = field_validator("start")(_check_time)
    _v_end = field_validator("end")(_check_time)


class CreateMeetingReq(BaseModel):
    title: str = Field(min_length=1, max_length=40)
    host_name: str = Field(min_length=1, max_length=20)
    candidate_dates: list[str] = Field(min_length=1, max_length=14)
    time_range: TimeRange = TimeRange()
    slot_minutes: Literal[30, 60] = 60

    @field_validator("candidate_dates")
    @classmethod
    def check_dates(cls, v):
        return [_check_date(d) for d in v]


class JoinReq(BaseModel):
    name: str = Field(min_length=1, max_length=20)


class AvailabilityReq(BaseModel):
    availability: dict[str, list[str]]


class TextReq(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class Location(BaseModel):
    text: str
    lat: float
    lng: float


class PreferenceReq(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    start_location: Optional[Location] = None


class ConfirmReq(BaseModel):
    member_id: str
    date: str
    start: str
    end: str


class RecommendReq(BaseModel):
    count: int = Field(default=5, ge=1, le=10)
    radius_m: int = Field(default=1000, ge=300, le=3000)
    extra_text: str = Field(default="", max_length=200)


class QuickPerson(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    text: str = Field(min_length=1, max_length=500)


class QuickReq(BaseModel):
    people: list[QuickPerson] = Field(min_length=1, max_length=10)
    count: int = Field(default=5, ge=1, le=10)
    radius_m: int = Field(default=1000, ge=300, le=3000)
    extra_text: str = Field(default="", max_length=200)