import asyncio
import html
import logging
import math
import re
from urllib.parse import quote

import httpx
from fastapi import HTTPException

from .settings import Settings

log = logging.getLogger("uvicorn.error")

TAGS = re.compile(r"<[^>]*>")
PER_KEYWORD = 5
MAX_PLACES = 10

# 모의 실행에서 외부 호출 없이 화면을 연결해 보기 위한 고정 예시입니다. 실제 장소가 아닙니다.
MOCK_PLACES = [
    {"name": "[MOCK] 예시 카페 1", "category": "음식점>카페", "address": "[MOCK] 예시 지번 주소", "road_address": "[MOCK] 예시 도로명 주소", "lat": 37.5665, "lng": 126.9780},
    {"name": "[MOCK] 예시 카페 2", "category": "음식점>카페", "address": "[MOCK] 예시 지번 주소", "road_address": "[MOCK] 예시 도로명 주소", "lat": 37.5700, "lng": 126.9830},
]
# 모의 실행용 출발지 좌표(서울 중심부의 임의 지점)
MOCK_ORIGIN_COORDS = [(37.5400, 126.9700), (37.5800, 127.0100), (37.5600, 126.9400)]


def clean(text):
    # 네이버 응답의 title에는 <b>검색어</b> 태그와 HTML 엔티티가 섞여 옵니다.
    return html.unescape(TAGS.sub("", text or "")).strip()


def map_link(name, address):
    # 장소명과 주소로 만든 네이버 지도 검색 링크입니다. 정확히 한 곳을 가리킨다고 보장하지 않습니다.
    return "https://map.naver.com/p/search/" + quote(f"{name} {address}".strip())


def normalize_searches(searches, limit=4, max_len=40):
    """AI가 세운 검색 계획을 정리합니다. 형식이 조금 달라도 실패시키지 않고, 쓸 수 있는 검색이 하나도 없을 때만 502입니다.

    각 항목: query(네이버 지역 검색어), label(결과 묶음 제목), reason(AI의 설명)."""
    cleaned = []
    for item in searches if isinstance(searches, list) else []:
        if isinstance(item, str):
            item = {"query": item}
        if not isinstance(item, dict) or not isinstance(item.get("query"), str):
            continue
        query = " ".join(item["query"].split())[:max_len].strip()
        if not query or any(query == other["query"] for other in cleaned):
            continue
        label = item.get("label")
        label = " ".join(label.split())[:30] if isinstance(label, str) else ""
        reason = item.get("reason")
        reason = " ".join(reason.split())[:150] if isinstance(reason, str) else ""
        cleaned.append({"label": label or query, "reason": reason, "query": query})
    if not cleaned:
        raise HTTPException(502, "AI가 사용할 수 있는 검색어를 만들지 못했습니다. 입력을 조금 바꿔 다시 시도하세요.")
    return cleaned[:limit]


def candidate_list(groups, limit=20):
    """검색 묶음에서 중복을 뺀 후보 목록. 번호(id)는 AI가 장소를 고를 때만 쓰는 임시 번호입니다."""
    candidates, seen = [], set()
    for group in groups:
        for place in group["places"]:
            key = (place["name"], place["road_address"] or place["address"])
            if key not in seen and len(candidates) < limit:
                seen.add(key)
                candidates.append({**place, "id": len(candidates), "search": group["label"]})
    return candidates


def short_list(values, limit=4, max_len=80):
    return [" ".join(v.split())[:max_len] for v in values if isinstance(v, str) and v.strip()][:limit] if isinstance(values, list) else []


def normalize_picks(picks, candidates, limit=5):
    """AI가 고른 번호로 후보를 찾아 추천 목록을 만듭니다. 이름과 주소는 항상 후보의 값을 쓰고 AI가 쓴 값은 쓰지 않습니다.

    없는 번호, 중복 번호는 버립니다."""
    by_id = {c["id"]: c for c in candidates}
    result, used = [], set()
    for item in picks if isinstance(picks, list) else []:
        if not isinstance(item, dict) or type(item.get("id")) is not int or item["id"] not in by_id or item["id"] in used:
            continue
        used.add(item["id"])
        reason = item.get("reason")
        candidate = by_id[item["id"]]
        result.append({"rank": len(result) + 1, **{k: v for k, v in candidate.items() if k != "id"},
                       "reason": " ".join(reason.split())[:200] if isinstance(reason, str) else "",
                       "fits": short_list(item.get("fits")), "unknown": short_list(item.get("unknown"))})
    return result[:limit]


def to_lnglat(mapx, mapy):
    """네이버 지역 검색의 mapx/mapy를 (위도, 경도)로 바꿉니다.

    문서에는 WGS84라고만 있고 단위가 없어서, 도(degree) 그대로이거나 10^7배 정수인 경우만 받아들입니다.
    한국 범위를 벗어나거나 다른 좌표계 값이면 None(좌표 없음)입니다."""
    try:
        x, y = float(mapx), float(mapy)
    except (TypeError, ValueError):
        return None
    for scale in (1, 1e7):
        lng, lat = x / scale, y / scale
        if 124 <= lng <= 132 and 33 <= lat <= 39.5:
            return lat, lng
    return None


def straight_km(a, b):
    """두 지점(lat, lng) 사이의 직선거리(km). 실제 이동 거리가 아닙니다."""
    (lat1, lng1), (lat2, lng2) = a, b
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 6371.0 * 2 * math.asin(min(1.0, math.sqrt(h)))


def as_place(name, category, address, road_address, lat=None, lng=None):
    return {"name": name, "category": category, "address": address, "road_address": road_address,
            "lat": lat, "lng": lng, "map_link": map_link(name, road_address or address)}


def normalize_origins(origins, limit=3):
    """AI가 입력에서 뽑은 출발지 이름을 정리합니다."""
    result = []
    for name in origins if isinstance(origins, list) else []:
        if isinstance(name, str):
            name = " ".join(name.split())[:40].strip()
            if name and name not in result:
                result.append(name)
    return result[:limit]


def travel_entries(origins, place):
    """각 출발지에서 장소까지의 직선거리. 좌표가 없으면 빈 목록입니다."""
    if not origins or place.get("lat") is None or place.get("lng") is None:
        return []
    return [{"origin": o["name"], "straight_km": round(straight_km((o["lat"], o["lng"]), (place["lat"], place["lng"])), 1)} for o in origins]


def travel_gap(travel):
    """출발지가 둘 이상일 때 가장 먼 사람과 가까운 사람의 차이. 자동차 시간이 모두 있으면 그것으로, 아니면 직선거리로 계산합니다."""
    if len(travel) < 2:
        return None
    if all(t.get("driving_min") is not None for t in travel):
        values, basis, unit = [t["driving_min"] for t in travel], "driving_min", "분"
    else:
        values, basis, unit = [t["straight_km"] for t in travel], "straight_km", "km"
    return {"basis": basis, "unit": unit, "value": round(max(values) - min(values), 1)}


class PlaceSearch:
    """네이버 검색 API(지역 검색)로 실제 등록된 장소만 조회합니다. AI가 장소를 만들어 내지 않습니다."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def ensure_ready(self):
        # AI 토큰을 쓰기 전에 검색 키부터 확인합니다.
        if not self.settings.mock and not (self.settings.naver_client_id and self.settings.naver_client_secret):
            raise HTTPException(503, "NAVER_SEARCH_CLIENT_ID와 NAVER_SEARCH_CLIENT_SECRET(NAVER API HUB의 Client ID/Secret)을 .env에 설정하세요.")

    def legacy(self):
        # 개발자센터(openapi.naver.com) 키는 신규 발급이 종료됐습니다. 이미 가진 키를 쓰는 경우만 이 방식입니다.
        return "openapi.naver.com" in self.settings.naver_base_url

    def auth_headers(self):
        if self.legacy():
            return {"X-Naver-Client-Id": self.settings.naver_client_id,
                    "X-Naver-Client-Secret": self.settings.naver_client_secret}
        return {"X-NCP-APIGW-API-KEY-ID": self.settings.naver_client_id,
                "X-NCP-APIGW-API-KEY": self.settings.naver_client_secret}

    async def locate_origins(self, names, maps=None):
        """출발지 이름을 네이버 지역 검색으로 찾아 좌표를 얻습니다. 못 찾은 출발지는 건너뛰고 요청은 실패시키지 않습니다."""
        names = normalize_origins(names)
        if not names:
            return []
        if self.settings.mock:
            return [{"name": n, "address": "[MOCK] 예시 주소", "lat": MOCK_ORIGIN_COORDS[i][0], "lng": MOCK_ORIGIN_COORDS[i][1]}
                    for i, n in enumerate(names)]
        headers = self.auth_headers()
        async with httpx.AsyncClient(timeout=self.settings.timeout) as client:
            async def one(name):
                try:
                    items = await self.fetch(client, headers, name, display=1, sort="random")
                except HTTPException:
                    return None
                if not items:
                    return None
                item = items[0]
                address = clean(item.get("roadAddress")) or clean(item.get("address"))
                coords = to_lnglat(item.get("mapx"), item.get("mapy"))
                if coords is None and maps is not None and maps.configured and address:
                    lnglat = await maps.geocode(address)
                    coords = (lnglat[1], lnglat[0]) if lnglat else None
                if coords is None:
                    return None
                return {"name": name, "address": address, "lat": coords[0], "lng": coords[1]}
            found = await asyncio.gather(*(one(n) for n in names))
        return [f for f in found if f]

    async def search(self, keywords):
        if self.settings.mock:
            return [as_place(p["name"], p["category"], p["address"], p["road_address"], p["lat"], p["lng"]) for p in MOCK_PLACES]
        self.ensure_ready()
        headers = self.auth_headers()
        # 타임아웃/5xx 자동 재시도는 하지 않습니다.
        async with httpx.AsyncClient(timeout=self.settings.timeout) as client:
            batches = await asyncio.gather(*(self.fetch(client, headers, k) for k in keywords))
        seen, places = set(), []
        for item in (item for batch in batches for item in batch):
            coords = to_lnglat(item.get("mapx"), item.get("mapy")) or (None, None)
            place = as_place(clean(item.get("title")), clean(item.get("category")),
                             clean(item.get("address")), clean(item.get("roadAddress")), coords[0], coords[1])
            key = (place["name"], place["road_address"] or place["address"])
            if not place["name"] or key in seen:
                continue
            seen.add(key)
            places.append(place)
        return places[:MAX_PLACES]

    async def fetch(self, client, headers, keyword, display=PER_KEYWORD, sort="comment"):
        try:
            path = "/v1/search/local.json" if self.legacy() else "/search/v1/local"
            response = await client.get(f"{self.settings.naver_base_url}{path}", headers=headers,
                                        params={"query": keyword, "display": display, "sort": sort})
        except httpx.TimeoutException:
            raise HTTPException(504, "네이버 검색 응답 시간 초과. 잠시 후 다시 시도하세요.") from None
        except httpx.RequestError:
            raise HTTPException(502, "네이버 검색 연결 실패. 네트워크와 API 주소를 확인하세요.") from None
        if response.status_code != 200:
            hint = {401: "검색 API 키 확인", 403: "검색 API 사용 권한 확인", 429: "호출 제한: 잠시 후 재시도"}.get(response.status_code, "공급자 오류")
            raise HTTPException(502, f"네이버 검색 HTTP {response.status_code}: {hint}")
        try:
            items = response.json()["items"]
            if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
                raise ValueError()
            return items
        except (KeyError, TypeError, ValueError):
            raise HTTPException(502, "네이버 검색 응답 형식이 예상과 다릅니다.") from None
