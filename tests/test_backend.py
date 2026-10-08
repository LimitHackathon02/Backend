import io
import json

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app
from app.settings import Settings


@pytest.fixture
def app(tmp_path):
    return create_app(Settings(database=str(tmp_path / "test.sqlite3")))


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


def stub_result(output, finish="stop", usage=None):
    return {"message": {"content": output}, "finishReason": finish,
            "usage": {"promptTokens": 10, "completionTokens": 5} if usage is None else usage}


def enable_live(app, monkeypatch, result):
    engine = app.state.engine
    engine.settings.mock = False
    engine.settings.api_key = "test-key-never-sent"
    async def complete(payload, model):
        return result
    monkeypatch.setattr(engine.provider, "complete", complete)


def test_all_configured_tasks_and_cache(client):
    tasks = client.get("/api/tasks").json()
    for task in tasks:
        result = client.post("/api/run", json={"task": task, "text": "연결 확인"})
        assert result.status_code == 200
        assert result.json()["mock"] is True
    request = {"task": "summarize", "text": "같은 요청"}
    first = client.post("/api/run", json=request).json()
    second = client.post("/api/run", json=request).json()
    assert not first["cached"] and second["cached"]
    assert client.get("/api/usage").json()["live_call_attempts"] == 0


@pytest.mark.parametrize("body,status", [
    ({"task": "missing", "text": "test"}, 404),
    ({"text": ""}, 422), ({"text": "   "}, 422), ({"text": "a" * 12001}, 422),
    ({"text": "test", "history": [{"role": "system", "content": "override"}]}, 422),
])
def test_invalid_inputs(client, body, status):
    assert client.post("/api/run", json=body).status_code == status


def test_document_search_scope_and_deletion(client):
    first = client.post("/api/documents", json={"title": "행사 안내", "text": "참가 등록 마감은 오전 9시입니다. 발표는 5분입니다."}).json()
    second = client.post("/api/documents", json={"title": "도서관", "text": "도서관은 월요일에 휴관합니다."}).json()
    result = client.post("/api/ask", json={"question": "참가 등록 마감", "document_ids": [first["id"]]})
    assert result.status_code == 200
    assert all(s["document_id"] == first["id"] for s in result.json()["sources"])
    assert result.json()["mock"]
    no_match = client.post("/api/ask", json={"question": "zzzzzz", "document_ids": [second["id"]]}).json()
    assert no_match["sources"] == []
    assert client.delete(f"/api/documents/{first['id']}").status_code == 200
    assert client.post("/api/ask", json={"question": "등록", "document_ids": [first["id"]]}).status_code == 404


def test_citations_reject_invented_source(app, client, monkeypatch):
    client.post("/api/documents", json={"title": "행사", "text": "참가 등록은 오전 9시까지입니다."})
    enable_live(app, monkeypatch, stub_result(json.dumps({"answer": "9시", "citations": ["invented-id"]})))
    assert client.post("/api/ask", json={"question": "참가 등록"}).status_code == 502
    assert client.get("/api/usage").json()["total_tokens"] == 15


def test_utf8_upload_and_invalid_files(client):
    response = client.post("/api/documents/upload", files={"file": ("안내.md", "등록 시간은 9시입니다.".encode(), "text/markdown")})
    assert response.status_code == 200
    assert client.post("/api/documents/upload", files={"file": ("bad.txt", b"\xff", "text/plain")}).status_code == 422
    assert client.post("/api/documents/upload", files={"file": ("file.pdf", b"pdf", "application/pdf")}).status_code == 422
    assert client.post("/api/documents", json={"title": "빈 문서", "text": "   "}).status_code == 422


def test_image_validation_and_preprocessing(app, client, monkeypatch):
    out = io.BytesIO()
    Image.new("RGB", (2000, 20), "white").save(out, "PNG")
    capture = {}
    engine = app.state.engine
    enable_live(app, monkeypatch, {})
    async def complete(payload, model):
        capture.update(payload=payload, model=model)
        return stub_result(json.dumps(engine.tasks["image_analyze"]["mock_output"]))
    monkeypatch.setattr(engine.provider, "complete", complete)
    response = client.post("/api/vision", files={"file": ("photo.png", out.getvalue(), "image/png")})
    assert response.status_code == 200
    assert capture["model"] == "HCX-005"
    content = capture["payload"]["messages"][-1]["content"]
    uri = content[1]["dataUri"]["data"]
    import base64
    with Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1]))) as prepared:
        assert max(prepared.size) <= 1280
        assert max(prepared.size) / min(prepared.size) <= 5
    assert client.post("/api/vision", files={"file": ("fake.png", b"not an image", "image/png")}).status_code == 422


def test_real_usage_cache_and_restart(app, client, monkeypatch):
    output = json.dumps(app.state.engine.tasks["summarize"]["mock_output"])
    enable_live(app, monkeypatch, stub_result(output))
    body = {"text": "실제 공급자 대역 확인"}
    assert client.post("/api/run", json=body).json()["usage"]["total_tokens"] == 15
    assert client.post("/api/run", json=body).json()["cached"]
    assert client.get("/api/usage").json()["live_call_attempts"] == 1
    restarted = TestClient(create_app(app.state.engine.settings))
    assert restarted.get("/api/usage").json()["total_tokens"] == 15
    assert restarted.post("/api/run", json=body).json()["cached"]


@pytest.mark.parametrize("output,finish", [("not JSON", "stop"), ("{}", "stop"), ("{}", "length")])
def test_invalid_json_still_accounts_usage(app, client, monkeypatch, output, finish):
    enable_live(app, monkeypatch, stub_result(output, finish))
    body = {"text": "invalid response"}
    assert client.post("/api/run", json=body).status_code == 502
    assert client.post("/api/run", json=body).status_code == 502
    assert client.get("/api/usage").json()["total_tokens"] == 30


def test_call_and_token_limits(app, client, monkeypatch):
    enable_live(app, monkeypatch, stub_result("chat answer"))
    app.state.engine.settings.max_calls = 1
    body = {"task": "chat", "text": "test"}
    assert client.post("/api/run", json=body).status_code == 200
    assert client.post("/api/run", json=body).status_code == 429
    app.state.engine.settings.max_calls = 100
    app.state.engine.settings.token_threshold = 15
    assert client.post("/api/run", json=body).status_code == 429


def test_provider_failure_does_not_retry(app, client, monkeypatch):
    enable_live(app, monkeypatch, {})
    async def fail(payload, model):
        raise HTTPException(504, "timeout")
    monkeypatch.setattr(app.state.engine.provider, "complete", fail)
    assert client.post("/api/run", json={"text": "test"}).status_code == 504
    stats = client.get("/api/usage").json()
    assert stats["live_call_attempts"] == stats["unknown_usage_calls"] == 1


def test_missing_api_key_not_counted(app, client):
    app.state.engine.settings.mock = False
    assert client.post("/api/run", json={"text": "test"}).status_code == 503
    assert client.get("/api/usage").json()["live_call_attempts"] == 0


def test_malformed_usage_is_marked_unknown(app, client, monkeypatch):
    enable_live(app, monkeypatch, stub_result("hello", usage=["unexpected"]))
    response = client.post("/api/run", json={"task": "chat", "text": "test"})
    assert response.status_code == 200
    assert response.json()["usage"]["total_tokens"] is None
    assert client.get("/api/usage").json()["unknown_usage_calls"] == 1


def test_team_key_auth_and_cors(tmp_path):
    app = create_app(Settings(database=str(tmp_path / "auth.sqlite3"), team_key="team-secret"))
    with TestClient(app) as client:
        assert client.get("/api/tasks").status_code == 401
        assert client.get("/api/tasks", headers={"X-Team-Key": "team-secret"}).status_code == 200
        preflight = client.options("/api/run", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "Content-Type,X-Team-Key"})
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_provider_http_contract(app, client, monkeypatch):
    engine = app.state.engine
    engine.settings.mock = False
    engine.settings.api_key = "fake-contract-key"
    output = engine.tasks["summarize"]["mock_output"]
    original_client = httpx.AsyncClient
    def handle(request):
        assert str(request.url) == "https://clovastudio.stream.ntruss.com/v3/chat-completions/HCX-DASH-002"
        assert request.headers["Authorization"] == "Bearer fake-contract-key"
        assert request.headers["Accept"] == "application/json"
        payload = json.loads(request.content)
        assert payload["messages"][0]["role"] == "system"
        assert payload["maxTokens"] == 1024
        return httpx.Response(200, json={"status": {"code": "20000"}, "result": stub_result(json.dumps(output))})
    def factory(**kwargs):
        return original_client(transport=httpx.MockTransport(handle), **kwargs)
    monkeypatch.setattr("app.provider.httpx.AsyncClient", factory)
    assert client.post("/api/run", json={"text": "contract test"}).status_code == 200


@pytest.mark.parametrize("http_status", [401, 403, 429, 500])
def test_provider_http_errors(app, client, monkeypatch, http_status):
    app.state.engine.settings.mock = False
    app.state.engine.settings.api_key = "fake-key"
    original_client = httpx.AsyncClient
    def factory(**kwargs):
        return original_client(transport=httpx.MockTransport(lambda request: httpx.Response(http_status, text="SECRET PROVIDER BODY")), **kwargs)
    monkeypatch.setattr("app.provider.httpx.AsyncClient", factory)
    response = client.post("/api/run", json={"text": "test"})
    assert response.status_code == 502
    assert "SECRET" not in response.text
    assert client.get("/api/usage").json()["unknown_usage_calls"] == 1


PLACE_PLAN = {"intent": "영통 카페", "searches": [
    {"label": "영통 카페", "reason": "지역과 업종", "query": "영통 카페"},
    {"label": "영통 스터디", "reason": "목적 반영", "query": "영통 스터디 카페"}], "unmatched_conditions": ["밤 10시까지"]}


def naver_item(title, road, address="", category="음식점>카페", mapx=None, mapy=None):
    item = {"title": title, "category": category, "address": address, "roadAddress": road}
    if mapx is not None:
        item.update(mapx=mapx, mapy=mapy)
    return item


def enable_places_live(app, monkeypatch, handler=None):
    enable_live(app, monkeypatch, stub_result(json.dumps(PLACE_PLAN)))
    settings = app.state.engine.settings
    settings.naver_client_id, settings.naver_client_secret = "fake-id", "fake-secret"
    if handler is not None:
        original_client = httpx.AsyncClient
        def factory(**kwargs):
            return original_client(transport=httpx.MockTransport(handler), **kwargs)
        monkeypatch.setattr("app.places.httpx.AsyncClient", factory)


def test_places_mock_mode_uses_fixed_examples(client):
    response = client.post("/api/places", json={"query": "영통 조용한 카페"})
    assert response.status_code == 200
    body = response.json()
    assert body["mock"] is True and body["place_source"] == "mock"
    assert [g["label"] for g in body["groups"]] == ["[MOCK] 예시 검색 1", "[MOCK] 예시 검색 2"]
    assert all(g["places"] for g in body["groups"])
    assert [o["name"] for o in body["origins"]] == ["[MOCK] 출발지 A", "[MOCK] 출발지 B"]
    assert all(isinstance(p["lat"], float) and isinstance(p["lng"], float) for p in body["places"])
    assert [t["origin"] for t in body["recommendations"][0]["travel"]] == ["[MOCK] 출발지 A", "[MOCK] 출발지 B"]
    assert body["recommendations"][0]["travel_gap"]["basis"] == "straight_km" and body["directions_used"] is False
    assert body["recommendations"] and body["recommendations"][0]["name"].startswith("[MOCK]")
    assert body["recommendations"][0]["rank"] == 1 and body["summary"].startswith("[MOCK]")
    assert body["places"] and all(p["name"].startswith("[MOCK]") for p in body["places"])
    assert all(p["map_link"].startswith("https://map.naver.com/p/search/") for p in body["places"])
    assert client.get("/api/usage").json()["live_call_attempts"] == 0


def test_places_live_flow_cleans_dedupes_and_links(app, client, monkeypatch):
    queries = []
    def handle(request):
        assert request.url.host == "naverapihub.apigw.ntruss.com" and request.url.path == "/search/v1/local"
        assert request.headers["X-NCP-APIGW-API-KEY-ID"] == "fake-id"
        assert request.headers["X-NCP-APIGW-API-KEY"] == "fake-secret"
        queries.append(request.url.params["query"])
        return httpx.Response(200, json={"items": [
            naver_item("<b>영통</b> 카페 &amp; 책방", "경기도 수원시 영통구 영통로 1"),
            naver_item("공통 스터디", "", address="경기도 수원시 영통구 영통동 2"),
        ]})
    enable_places_live(app, monkeypatch, handle)
    body = client.post("/api/places", json={"query": "영통 조용한 카페", "pick": False}).json()
    assert sorted(queries) == ["영통 스터디 카페", "영통 카페"]
    assert body["place_source"] == "naver_local"
    # 두 검색어가 같은 장소를 반환해도 중복은 한 번만 표시합니다.
    assert [p["name"] for p in body["places"]] == ["영통 카페 & 책방", "공통 스터디"]
    assert body["places"][1]["address"] == "경기도 수원시 영통구 영통동 2"
    assert all(p["map_link"].startswith("https://map.naver.com/p/search/") and "<" not in p["map_link"] for p in body["places"])
    assert body["output"]["unmatched_conditions"] == ["밤 10시까지"]
    assert [g["query"] for g in body["groups"]] == ["영통 카페", "영통 스터디 카페"]
    assert body["usage"]["total_tokens"] == 15
    again = client.post("/api/places", json={"query": "영통 조용한 카페", "pick": False}).json()
    assert again["cached"] and again["usage"]["total_tokens"] == 0
    assert client.get("/api/usage").json()["live_call_attempts"] == 1


def test_places_requires_naver_keys_before_ai_call(app, client, monkeypatch):
    enable_live(app, monkeypatch, stub_result(json.dumps(PLACE_PLAN)))
    assert client.post("/api/places", json={"query": "영통 카페"}).status_code == 503
    assert client.get("/api/usage").json()["live_call_attempts"] == 0


@pytest.mark.parametrize("http_status", [401, 403, 429, 500])
def test_places_naver_http_errors(app, client, monkeypatch, http_status):
    enable_places_live(app, monkeypatch, lambda request: httpx.Response(http_status, text="SECRET NAVER BODY"))
    response = client.post("/api/places", json={"query": "영통 카페"})
    assert response.status_code == 502
    assert "SECRET" not in response.text and "fake-secret" not in response.text


def test_places_unexpected_naver_response(app, client, monkeypatch):
    enable_places_live(app, monkeypatch, lambda request: httpx.Response(200, json={"items": "oops"}))
    assert client.post("/api/places", json={"query": "영통 카페"}).status_code == 502


@pytest.mark.parametrize("query", ["", "   ", "\n\n  \n", "a" * 2001])
def test_places_invalid_query(client, query):
    assert client.post("/api/places", json={"query": query}).status_code == 422


def test_places_accepts_free_form_multiline_input(client):
    query = "안녕!!  나 오늘\n\n\n\n경희대 근처에서   조용한 카페 찾고 싶어 ㅠㅠ\x00" + "그리고 " * 100
    response = client.post("/api/places", json={"query": query})
    assert response.status_code == 200
    assert response.json()["places"]


def meet_setup(app, monkeypatch, plan, items_by_query):
    seen = []

    def handler(request):
        query = request.url.params["query"]
        seen.append(query)
        return httpx.Response(200, json={"items": items_by_query.get(query, [])})

    enable_places_live(app, monkeypatch, handler)
    enable_live(app, monkeypatch, stub_result(json.dumps(plan)))  # 같은 앱의 AI 응답을 위 계획으로 교체
    return seen


def test_places_trims_ai_searches_instead_of_failing(app, client, monkeypatch):
    plan = {"searches": [{"query": "  영통   카페  "}, {"query": "영통 카페", "label": "중복"}, {"query": "x" * 80},
                         "영통 술집", {"label": "검색어 없음"}, {"query": 5}, {"query": "영통 식당"}, {"query": "다섯째"}],
            "unmatched_conditions": ["a"] * 9, "extra": "허용"}
    seen = meet_setup(app, monkeypatch, plan, {})
    response = client.post("/api/places", json={"query": "영통 카페", "pick": False})
    assert response.status_code == 200
    queries = [item["query"] for item in response.json()["output"]["searches"]]
    assert queries == ["영통 카페", "x" * 40, "영통 술집", "영통 식당"]
    assert sorted(seen) == sorted(queries)


def test_places_free_form_plan_groups_results_per_search(app, client, monkeypatch):
    plan = {"intent": "두 사람이 중간에서 만난다", "searches": [
        {"label": "정자역", "reason": "대략적인 추정", "query": "정자역 카페"},
        {"label": "판교역", "reason": "대략적인 추정", "query": "판교역 카페"}], "unmatched_conditions": []}
    items = {
        "정자역 카페": [naver_item("정자 카페 A", "경기도 성남시 분당구 정자로 1"), naver_item("공통 카페", "경기도 성남시 분당구 공통로 9")],
        "판교역 카페": [naver_item("공통 카페", "경기도 성남시 분당구 공통로 9"), naver_item("판교 카페 C", "경기도 성남시 분당구 판교로 3")],
    }
    meet_setup(app, monkeypatch, plan, items)
    body = client.post("/api/places", json={"query": "한명은 영통역, 한명은 강남역에 있어. 두 사람이 만날 장소를 추천해줘", "pick": False}).json()
    assert [g["label"] for g in body["groups"]] == ["정자역", "판교역"]
    assert [p["name"] for p in body["groups"][1]["places"]] == ["공통 카페", "판교 카페 C"]
    assert body["groups"][0]["reason"] == "대략적인 추정"
    assert [p["name"] for p in body["places"]] == ["정자 카페 A", "공통 카페", "판교 카페 C"]
    assert all(p["map_link"].startswith("https://map.naver.com/p/search/") for p in body["places"])


def test_places_without_any_usable_search_is_502(app, client, monkeypatch):
    meet_setup(app, monkeypatch, {"searches": [{"label": "빈 검색"}, {"query": "  "}], "unmatched_conditions": []}, {})
    assert client.post("/api/places", json={"query": "아무거나"}).status_code == 502


def two_step(app, monkeypatch, plan, pick, items_by_query, captured=None, handler=None):
    """1단계(검색 계획)와 2단계(장소 고르기)가 서로 다른 AI 응답을 받도록 합니다."""
    seen = []

    def default_handler(request):
        query = request.url.params["query"]
        seen.append(query)
        return httpx.Response(200, json={"items": items_by_query.get(query, [])})

    enable_places_live(app, monkeypatch, handler or default_handler)
    engine = app.state.engine

    async def complete(payload, model):
        system = payload["messages"][0]["content"]
        if captured is not None and "picks" in system:
            captured.append(payload)
        output = pick if "picks" in system else plan
        return stub_result(output if isinstance(output, str) else json.dumps(output))

    monkeypatch.setattr(engine.provider, "complete", complete)
    return seen


PICK_ITEMS = {"영통 카페": [naver_item("영통 카페 A", "경기도 수원시 영통구 1"), naver_item("영통 카페 B", "경기도 수원시 영통구 2")],
              "영통 스터디 카페": [naver_item("영통 카페 B", "경기도 수원시 영통구 2"), naver_item("영통 스터디 C", "경기도 수원시 영통구 3")]}


def test_places_pick_uses_only_candidates_and_ignores_ai_written_names(app, client, monkeypatch):
    pick = {"picks": [
        {"id": 2, "reason": "스터디 검색에서 나온 곳입니다.", "fits": ["스터디"], "unknown": ["밤 10시까지"], "name": "지어낸 가게"},
        {"id": 99, "reason": "없는 번호"}, {"id": 2, "reason": "중복"}, {"id": "1", "reason": "문자열 번호"},
        {"id": 0, "reason": "첫 후보"}],
        "summary": "두 곳을 골랐습니다."}
    two_step(app, monkeypatch, PLACE_PLAN, pick, PICK_ITEMS)
    body = client.post("/api/places", json={"query": "영통 조용한 카페"}).json()
    assert [r["name"] for r in body["recommendations"]] == ["영통 스터디 C", "영통 카페 A"]
    assert [r["rank"] for r in body["recommendations"]] == [1, 2]
    assert body["recommendations"][0]["fits"] == ["스터디"] and body["recommendations"][0]["unknown"] == ["밤 10시까지"]
    assert body["recommendations"][0]["map_link"].startswith("https://map.naver.com/p/search/")
    assert "지어낸 가게" not in json.dumps(body, ensure_ascii=False)
    assert body["summary"] == "두 곳을 골랐습니다."
    assert body["usage"]["total_tokens"] == 15 and body["pick_usage"]["total_tokens"] == 15 and body["usage_total"] == 30
    assert client.get("/api/usage").json()["live_call_attempts"] == 2


def test_places_pick_failure_keeps_search_results(app, client, monkeypatch):
    two_step(app, monkeypatch, PLACE_PLAN, "JSON이 아닌 답변", PICK_ITEMS)
    response = client.post("/api/places", json={"query": "영통 조용한 카페"})
    assert response.status_code == 200
    body = response.json()
    assert body["places"] and body["recommendations"] == [] and "pick_error" in body


def test_places_pick_can_be_turned_off(app, client, monkeypatch):
    two_step(app, monkeypatch, PLACE_PLAN, {"picks": [], "summary": ""}, PICK_ITEMS)
    body = client.post("/api/places", json={"query": "영통 조용한 카페", "pick": False}).json()
    assert body["places"] and body["recommendations"] == [] and "pick_usage" not in body
    assert client.get("/api/usage").json()["live_call_attempts"] == 1


def test_places_pick_skipped_without_candidates(app, client, monkeypatch):
    two_step(app, monkeypatch, PLACE_PLAN, {"picks": [], "summary": ""}, {})
    body = client.post("/api/places", json={"query": "영통 조용한 카페"}).json()
    assert body["places"] == [] and body["recommendations"] == []
    assert client.get("/api/usage").json()["live_call_attempts"] == 1


def test_to_lnglat_accepts_degrees_or_1e7_and_rejects_other_systems():
    from app.places import to_lnglat
    assert to_lnglat("127.0711", "37.2514") == (37.2514, 127.0711)
    lat, lng = to_lnglat("1270711000", "372514000")
    assert (round(lat, 4), round(lng, 4)) == (37.2514, 127.0711)
    assert to_lnglat("314871", "544560") is None          # 다른 좌표계로 보이는 값
    assert to_lnglat("1270711000", "999999999") is None   # 범위를 벗어남
    assert to_lnglat(None, "1") is None and to_lnglat("가", "나") is None


ORIGIN_PLAN = {"intent": "두 사람이 만난다", "origins": ["영통역", "강남역", "없는역"], "searches": [
    {"label": "정자역", "reason": "대략적인 추정", "query": "정자역 카페"}], "unmatched_conditions": []}
CAFE_A = naver_item("정자 카페 A", "경기도 성남시 분당구 정자로 1", mapx="1271080000", mapy="373670000")
STATIONS = {"영통역": naver_item("영통역", "경기도 수원시 영통구 1", category="교통,수단>지하철", mapx="1270711000", mapy="372514000"),
            "강남역": naver_item("강남역", "서울 강남구 1", category="교통,수단>지하철", mapx="1270276000", mapy="374979000")}


def routed(maps_status=200, record=None):
    """네이버 검색과 NCP Maps 요청을 호스트로 구분해 응답합니다."""
    def handler(request):
        if request.url.host == "maps.apigw.ntruss.com":
            if record is not None:
                record.append(request)
            assert request.headers["x-ncp-apigw-api-key-id"] == "maps-id" and request.headers["x-ncp-apigw-api-key"] == "maps-secret"
            if maps_status != 200:
                return httpx.Response(maps_status, text="SECRET MAPS BODY")
            minutes = 25 if request.url.params["start"].startswith("127.0711,") else 30
            return httpx.Response(200, json={"code": 0, "route": {"traoptimal": [{"summary": {"distance": 18000, "duration": minutes * 60000}}]}})
        query = request.url.params["query"]
        if query in STATIONS:
            assert request.url.params["display"] == "1"
            return httpx.Response(200, json={"items": [STATIONS[query]]})
        return httpx.Response(200, json={"items": [CAFE_A] if query == "정자역 카페" else []})
    return handler


PICK_A = {"picks": [{"id": 0, "reason": "두 출발지에서 거리가 비슷합니다.", "fits": [], "unknown": []}], "summary": "정자 카페를 골랐습니다."}


def test_places_origins_get_straight_distances_and_ai_sees_them(app, client, monkeypatch):
    from app.places import straight_km
    captured = []
    two_step(app, monkeypatch, ORIGIN_PLAN, PICK_A, {}, captured=captured, handler=routed())
    body = client.post("/api/places", json={"query": "한명은 영통역, 한명은 강남역"}).json()
    assert [o["name"] for o in body["origins"]] == ["영통역", "강남역"]          # 못 찾은 출발지는 건너뜀
    assert body["output"]["origins"] == ["영통역", "강남역"]
    place = body["places"][0]
    assert (round(place["lat"], 3), round(place["lng"], 3)) == (37.367, 127.108)
    expected = round(straight_km((37.2514, 127.0711), (place["lat"], place["lng"])), 1)
    assert place["travel"][0] == {"origin": "영통역", "straight_km": expected}
    rec = body["recommendations"][0]
    assert rec["travel_gap"]["basis"] == "straight_km" and rec["travel_gap"]["unit"] == "km"
    assert body["directions_used"] is False                                        # Maps 키 없음
    listing = json.loads(json.loads(captured[0]["messages"][-1]["content"])["input"])["candidates"][0]
    assert listing["straight_km_from"]["영통역"] == expected


def test_places_directions_added_for_recommendations_only(app, client, monkeypatch):
    settings = app.state.engine.settings
    settings.maps_client_id, settings.maps_client_secret = "maps-id", "maps-secret"
    record = []
    two_step(app, monkeypatch, ORIGIN_PLAN, PICK_A, {}, handler=routed(record=record))
    body = client.post("/api/places", json={"query": "한명은 영통역, 한명은 강남역"}).json()
    rec = body["recommendations"][0]
    assert [(t["origin"], t["driving_min"], t["driving_km"]) for t in rec["travel"]] == [("영통역", 25, 18.0), ("강남역", 30, 18.0)]
    assert rec["travel_gap"] == {"basis": "driving_min", "unit": "분", "value": 5}
    assert body["directions_used"] is True and len(record) == 2
    assert all(r.url.path == "/map-direction/v1/driving" for r in record)
    record.clear()
    again = client.post("/api/places", json={"query": "한명은 영통역, 한명은 강남역", "directions": False}).json()
    assert again["directions_used"] is False and record == []
    assert "driving_min" not in again["recommendations"][0]["travel"][0]


def test_places_directions_failure_keeps_straight_distances(app, client, monkeypatch):
    settings = app.state.engine.settings
    settings.maps_client_id, settings.maps_client_secret = "maps-id", "maps-secret"
    two_step(app, monkeypatch, ORIGIN_PLAN, PICK_A, {}, handler=routed(maps_status=400))
    response = client.post("/api/places", json={"query": "한명은 영통역, 한명은 강남역"})
    assert response.status_code == 200 and "SECRET" not in response.text and "maps-secret" not in response.text
    rec = response.json()["recommendations"][0]
    assert "driving_min" not in rec["travel"][0] and rec["travel_gap"]["basis"] == "straight_km"


def test_map_config_never_exposes_secret_and_demo_is_served(app, client):
    assert client.get("/api/map-config").json() == {"configured": False, "client_id": ""}
    settings = app.state.engine.settings
    settings.maps_client_id, settings.maps_client_secret = "maps-id", "maps-secret"
    response = client.get("/api/map-config")
    assert response.json() == {"configured": True, "client_id": "maps-id"} and "maps-secret" not in response.text
    assert client.get("/health").json()["maps_configured"] is True
    demo = client.get("/demo")
    assert demo.status_code == 200 and "text/html" in demo.headers["content-type"] and "/api/places" in demo.text


def test_places_accepts_loose_ai_output_shapes(app, client, monkeypatch):
    # unmatched_conditions가 없고 searches가 문자열 목록이어도 실패하지 않습니다.
    two_step(app, monkeypatch, {"searches": ["영통 카페", {"query": "영통 술집"}], "unmatched_conditions": "문자열"},
             {"picks": [{"id": 0}]}, {"영통 카페": [naver_item("영통 카페 A", "경기도 수원시 영통구 1")]})
    body = client.post("/api/places", json={"query": "영통 카페"}).json()
    assert [g["query"] for g in body["groups"]] == ["영통 카페", "영통 술집"]
    assert body["output"]["unmatched_conditions"] == [] and body["recommendations"][0]["name"] == "영통 카페 A"


def test_invalid_ai_json_error_shows_reason_and_raw_start(app, client, monkeypatch):
    two_step(app, monkeypatch, "죄송합니다. 검색 계획을 JSON으로 만들 수 없습니다.", {"picks": []}, {})
    response = client.post("/api/places", json={"query": "영통 카페"})
    assert response.status_code == 502
    assert "죄송합니다. 검색 계획을" in response.json()["detail"] and "사유" in response.json()["detail"]
