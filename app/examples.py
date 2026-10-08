"""발표 시연용 데이터와 /docs 의 Try it out 에 미리 채워지는 예시.

시연 흐름 (2명: 보경 = 미리 입력된 사람, 지민 = 발표 중 직접 입력하는 사람)
  0) 발표 전  POST /api/meeting/demo              -> DEMO 데이터로 세팅 (보경 전체 + 지민 일정)
  1) 시연     GET  /api/meeting/schedule          -> 둘 다 되는 시간 확인 (입력 없음)
  2) 시연     POST /api/meeting/schedule/confirm  -> 확정 (예시 그대로)
  3) 시연     POST /api/meeting/preference        -> ★ 지민의 선호/비선호 + 출발지를 직접 입력
  4) 시연     POST /api/meeting/recommend         -> 추천 + 각 출발지에서 거리·자동차 시간
날짜는 서버 시작일 기준(오늘·내일·모레)이라 발표 당일 서버를 켜면 날짜가 맞는다."""
from datetime import date, timedelta

D0, D1, D2 = [(date.today() + timedelta(days=i)).isoformat() for i in range(3)]

HOST = "보경"    # 미리 입력된 사람
GUEST = "지민"   # 발표 중 직접 입력하는 사람

# POST /api/meeting/demo 가 넣는 데이터. 시연 내용을 바꾸려면 여기만 고치면 된다.
DEMO = {
    "title": "동아리 뒤풀이",
    "candidate_dates": [D0, D1, D2],
    "time_range": {"start": "10:00", "end": "23:00"},
    "slot_minutes": 60,
    "availability": {
        HOST: {D0: ["18:00", "19:00", "20:00"], D1: ["14:00", "15:00", "16:00"]},
        GUEST: {D0: ["19:00", "20:00", "21:00"], D2: ["12:00", "13:00"]},
    },
    # 보경의 선호는 AI 분석이 끝난 상태로 저장해서 시연 시간을 아낀다.
    "preference": {
        HOST: {
            "raw_text": "강남역에서 출발해. 조용히 얘기할 수 있는 카페가 좋고, 술집은 별로야.",
            "likes": ["카페"],
            "dislikes": ["술집"],
            "mood": ["조용한", "대화하기 좋은"],
            "budget_max": None,
            "indoor": "any",
            "start_location": {"text": "강남역", "lat": 37.4979, "lng": 127.0276},
        },
    },
}


def _ex(summary: str, value) -> dict:
    return {"summary": summary, "value": value}


# ★ 시연 중 직접 입력하는 부분. 첫 번째 예시는 입력이 막힐 때 쓰는 비상용.
PREFERENCE = {
    "live": _ex(f"{GUEST}: 사당역 출발, 고기 좋음 / 회 싫음", {
        "name": GUEST,
        "text": "사당역에서 출발할게. 고기 먹고 싶고 회는 별로야.",
    }),
    "template": _ex(f"{GUEST}: 빈 칸 (직접 입력용)", {
        "name": GUEST,
        "text": "",
    }),
}

CONFIRM = {
    "tonight": _ex("오늘 19시~21시로 확정 (둘 다 되는 시간)", {"date": D0, "start": "19:00", "end": "21:00"}),
}

RECOMMEND = {
    "default": _ex("3곳 추천, 반경 1km", {"count": 3, "radius_m": 1000, "extra_text": ""}),
}

# ---- 아래는 시연 흐름 밖에서 따로 테스트할 때 쓰는 예시 ----
CREATE_MEETING = {
    "two": _ex(f"빈 모임 ({HOST}, {GUEST})", {
        "title": DEMO["title"],
        "members": [HOST, GUEST],
        "candidate_dates": DEMO["candidate_dates"],
        "time_range": DEMO["time_range"],
        "slot_minutes": DEMO["slot_minutes"],
    }),
    "empty": _ex("기본값으로 초기화 (오늘부터 7일, 참여자 없음)", {}),
}

JOIN = {
    "guest": _ex(f"{GUEST} 참여", {"name": GUEST}),
}

AVAILABILITY = {
    name: _ex(f"{name}: 시연용 일정", {"name": name, "availability": avail})
    for name, avail in DEMO["availability"].items()
}

PARSE_AVAILABILITY = {
    "evening": _ex("저녁", {"text": "평일 저녁 7시 이후면 다 괜찮아"}),
}

QUICK = {
    "two": _ex("모임 없이 바로 추천 (2명)", {
        "people": [
            {"name": HOST, "text": "강남역에서 출발, 조용한 카페"},
            {"name": GUEST, "text": "사당역에서 출발, 고기 먹고 싶어"},
        ],
        "count": 3,
        "radius_m": 1000,
        "extra_text": "",
    }),
}
