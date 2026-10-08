"""/docs 의 Try it out 에 미리 채워지는 테스트·발표용 예시.
위에서부터 순서대로 실행하면 모임 생성 -> 일정 -> 선호 -> 추천까지 한 흐름이 된다.
날짜는 서버 시작일 기준(오늘·내일·모레)이라 모임 생성 예시와 일정 예시가 항상 맞는다."""
from datetime import date, timedelta

D0, D1, D2 = [(date.today() + timedelta(days=i)).isoformat() for i in range(3)]


def _ex(summary: str, value) -> dict:
    return {"summary": summary, "value": value}


CREATE_MEETING = {
    "demo": _ex("발표용: 동아리 뒤풀이 (3명, 3일)", {
        "title": "동아리 뒤풀이",
        "members": ["보경", "지민", "수아"],
        "candidate_dates": [D0, D1, D2],
        "time_range": {"start": "10:00", "end": "23:00"},
        "slot_minutes": 60,
    }),
    "empty": _ex("기본값으로 초기화 (오늘부터 7일, 참여자 없음)", {}),
}

JOIN = {
    "minho": _ex("민호 참여", {"name": "민호"}),
}

AVAILABILITY = {
    "bokyung": _ex("보경: 오늘 저녁 + 내일 오후", {
        "name": "보경",
        "availability": {D0: ["18:00", "19:00", "20:00", "21:00"], D1: ["14:00", "15:00", "16:00"]},
    }),
    "jimin": _ex("지민: 오늘 저녁 늦게", {
        "name": "지민",
        "availability": {D0: ["19:00", "20:00", "21:00", "22:00"]},
    }),
    "sua": _ex("수아: 오늘 저녁 + 모레 하루 종일", {
        "name": "수아",
        "availability": {D0: ["18:00", "19:00", "20:00"],
                         D2: ["12:00", "13:00", "14:00", "15:00", "16:00", "17:00"]},
    }),
}

PARSE_AVAILABILITY = {
    "evening": _ex("저녁", {"text": "평일 저녁 7시 이후면 다 괜찮아"}),
    "weekend": _ex("주말 오후", {"text": "토요일 오후는 되는데 일요일은 안 돼"}),
}

CONFIRM = {
    "tonight": _ex("오늘 19시~21시로 확정", {"date": D0, "start": "19:00", "end": "21:00"}),
}

PREFERENCE = {
    "bokyung": _ex("보경: 강남역, 조용한 카페", {
        "name": "보경",
        "text": "강남역 근처에서 조용히 얘기할 수 있는 카페가 좋아. 너무 비싸지 않았으면.",
    }),
    "jimin": _ex("지민: 파스타, 역삼역 출발", {
        "name": "지민",
        "text": "역삼역에서 출발해. 파스타나 양식 먹고 싶어.",
    }),
    "sua": _ex("수아: 고기, 단체석 (출발 좌표 포함)", {
        "name": "수아",
        "text": "고기 먹자! 3명 앉을 수 있는 넓은 자리면 좋겠어.",
        "start_location": {"text": "신논현역", "lat": 37.5045, "lng": 127.0250},
    }),
}

RECOMMEND = {
    "default": _ex("3곳 추천, 반경 1km", {"count": 3, "radius_m": 1000, "extra_text": ""}),
    "extra": _ex("추가 조건 포함", {"count": 5, "radius_m": 1500, "extra_text": "주차 가능하고 늦게까지 하는 곳"}),
}

QUICK = {
    "two": _ex("모임 없이 바로 추천 (2명)", {
        "people": [
            {"name": "지민", "text": "강남역 근처 조용한 카페"},
            {"name": "수아", "text": "파스타 먹고 싶어, 강남역에서 출발"},
        ],
        "count": 3,
        "radius_m": 1000,
        "extra_text": "",
    }),
}
