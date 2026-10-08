import asyncio
import logging

import httpx

from .settings import Settings

log = logging.getLogger("uvicorn.error")
TIMEOUT = 10  # 이동 시간은 부가 정보라 오래 기다리지 않습니다.


class MapsClient:
    """NCP Maps의 Geocoding과 Directions 5(자동차)를 부르는 부가 기능입니다.

    실패하거나 키가 없으면 None을 돌려줄 뿐 요청 전체를 실패시키지 않습니다. 응답 본문과 키는 로그에 남기지 않습니다."""

    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self):
        return bool(self.settings.maps_client_id and self.settings.maps_client_secret)

    def headers(self):
        return {"x-ncp-apigw-api-key-id": self.settings.maps_client_id, "x-ncp-apigw-api-key": self.settings.maps_client_secret,
                "Accept": "application/json"}

    async def get(self, path, params):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.get(f"{self.settings.maps_base_url}{path}", headers=self.headers(), params=params)
        except httpx.HTTPError:
            log.warning("NCP Maps 연결 실패: %s", path)
            return None
        if response.status_code != 200:
            # 도로 근처가 아닌 지점 등 정상적인 400도 있으므로 상태 코드만 남깁니다.
            log.warning("NCP Maps %s HTTP %s", path, response.status_code)
            return None
        try:
            return response.json()
        except ValueError:
            return None

    async def geocode(self, address):
        """주소 → (경도, 위도). 결과가 없거나 실패하면 None."""
        if not self.configured or not address:
            return None
        data = await self.get("/map-geocode/v2/geocode", {"query": address})
        try:
            first = data["addresses"][0]
            return float(first["x"]), float(first["y"])
        except (TypeError, KeyError, IndexError, ValueError):
            return None

    async def driving(self, start, goal):
        """start, goal은 (위도, 경도). 자동차 기준 {'driving_km', 'driving_min'}이며 실패하면 None."""
        if not self.configured:
            return None
        data = await self.get("/map-direction/v1/driving", {"start": f"{start[1]},{start[0]}", "goal": f"{goal[1]},{goal[0]}"})
        try:
            summary = data["route"]["traoptimal"][0]["summary"]
            return {"driving_km": round(summary["distance"] / 1000, 1), "driving_min": max(1, round(summary["duration"] / 60000))}
        except (TypeError, KeyError, IndexError, ValueError):
            return None

    async def add_driving(self, origins, items):
        """items의 각 장소에 대해 travel 항목마다 자동차 거리/시간을 채웁니다(있는 것만). 호출 수는 출발지 수 x 장소 수입니다."""
        by_name = {o["name"]: o for o in origins}
        jobs = []
        for item in items:
            for entry in item.get("travel", []):
                origin = by_name.get(entry["origin"])
                if origin and item.get("lat") is not None:
                    jobs.append((entry, self.driving((origin["lat"], origin["lng"]), (item["lat"], item["lng"]))))
        results = await asyncio.gather(*(job for _, job in jobs))
        for (entry, _), result in zip(jobs, results):
            if result:
                entry.update(result)
