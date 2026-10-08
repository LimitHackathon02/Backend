"""CLOVA Studio(HyperCLOVA X) 호출 담당.
- chat():       일반 대화 (가벼운 모델, 요약 한 줄 등)
- structured(): JSON 스키마를 지키도록 강제 (HCX-007 Structured Outputs)
호출할 때마다 토큰 사용량을 USAGE 에 쌓는다 (/api/usage 에서 보여줌)."""
import json
import uuid

import httpx

from app.config import settings
from app.errors import ApiError

USAGE = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "by_step": {}}


def _record(step: str, usage: dict) -> None:
    USAGE["calls"] += 1
    USAGE["prompt_tokens"] += usage.get("promptTokens", 0)
    USAGE["completion_tokens"] += usage.get("completionTokens", 0)
    USAGE["by_step"][step] = USAGE["by_step"].get(step, 0) + 1


async def _post(model: str, body: dict, step: str) -> str:
    url = f"{settings.CLOVA_BASE_URL}/v3/chat-completions/{model}"
    headers = {
        "Authorization": f"Bearer {settings.CLOVA_API_KEY}",
        "X-NCP-CLOVASTUDIO-REQUEST-ID": uuid.uuid4().hex,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.post(url, headers=headers, json=body)
    except httpx.HTTPError as e:
        raise ApiError(502, "AI_ERROR", f"AI 서버에 연결하지 못했어요: {e}")

    if res.status_code != 200:
        print(f"[HCX ERROR] {step} {res.status_code} {res.text[:500]}")  # 터미널에서 원인 확인용
        raise ApiError(502, "AI_ERROR", "AI가 잠시 바빠요. 다시 시도해 주세요.")

    data = res.json()
    result = data.get("result") or {}
    _record(step, result.get("usage") or {})
    return (result.get("message") or {}).get("content", "")


def _parse_json(text: str) -> dict:
    """```json ... ``` 같은 껍데기가 붙어 와도 JSON만 꺼낸다."""
    cleaned = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                pass
    print(f"[HCX JSON PARSE FAIL] {text[:500]}")
    raise ApiError(502, "AI_ERROR", "AI 응답을 해석하지 못했어요. 다시 시도해 주세요.")


async def chat(system: str, user: str, step: str, temperature: float = 0.3,
               max_tokens: int = 300) -> str:
    body = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "topP": 0.8,
        "maxTokens": max_tokens,
    }
    return (await _post(settings.HCX_LIGHT_MODEL, body, step)).strip()


async def structured(system: str, user: str, schema: dict, step: str,
                     temperature: float = 0.1, max_tokens: int = 2000) -> dict:
    body = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "topP": 0.8,
        "maxCompletionTokens": max_tokens,
        "thinking": {"effort": "none"},          # Structured Outputs 는 thinking 끄고 사용
        "responseFormat": {"type": "json", "schema": schema},
    }
    content = await _post(settings.HCX_MODEL, body, step)
    return _parse_json(content)