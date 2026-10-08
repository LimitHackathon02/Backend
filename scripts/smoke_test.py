"""실제 키가 동작하는지 1분 점검. 실행: python -m scripts.smoke_test
MOCK_MODE 와 상관없이 실제 HCX·네이버를 1번씩 호출한다 (크레딧 아주 조금 사용)."""
import asyncio
import traceback

from app.config import settings

settings.MOCK_MODE = False  # 강제로 실제 호출

from app.clients import hcx_client as hcx  # noqa: E402
from app.clients import naver_client as naver  # noqa: E402


async def check(name, coro):
    try:
        result = await coro
        print(f"[OK]   {name}: {str(result)[:150]}")
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] {name}: {getattr(e, 'detail', e)}")
        traceback.print_exc(limit=1)


async def main():
    print("CLOVA 키:", "있음" if settings.CLOVA_API_KEY else "없음",
          "/ 네이버 검색 키:", "있음" if settings.NAVER_CLIENT_ID else "없음",
          "/ NCP Maps 키:", "있음" if settings.NCP_MAPS_KEY_ID else "없음")
    await check("HCX chat (가벼운 모델)", hcx.chat("한 단어로만 답해.", "안녕?", step="smoke"))
    await check("HCX structured (HCX-007)", hcx.structured(
        "사용자 문장에서 음식 이름만 뽑아라.", "파스타랑 피자 먹고 싶어",
        {"type": "object", "properties": {"foods": {"type": "array", "items": {"type": "string"}}},
         "required": ["foods"]}, step="smoke"))
    await check("네이버 지역검색", naver.local_search("강남역 파스타", display=3))
    await check("NCP 지오코딩", naver._ncp_get("/map-geocode/v2/geocode", {"query": "불정로 6"}))
    await check("NCP 리버스 지오코딩", naver.area_name(37.4765, 126.9816))
    await check("중간지점 지하철역", naver.nearest_station(37.4765, 126.9816))
    print("토큰 사용:", hcx.USAGE)


if __name__ == "__main__":
    asyncio.run(main())