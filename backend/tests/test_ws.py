"""WebSocket 对话链路测试：帧序列、鉴权、脱敏、落库。"""

from fastapi.testclient import TestClient

from app.main import app

TEST_KEY = "sk-testkey-1234567890"


class FakeLLM:
    """按给定 chunks 顺序吐字的假 provider，不触网。"""

    def __init__(self, chunks: list[str]):
        self._chunks = chunks

    async def chat_stream(self, messages, api_key, **kw):
        for c in self._chunks:
            yield c


class RaisingLLM:
    """抛异常且异常信息里夹带密钥，用于验证脱敏路径。

    注意：必须是异步生成器（含 yield），否则 async for 得到的是 coroutine，
    触发的是「got coroutine」而非我们想验证的异常内容。
    """

    async def chat_stream(self, messages, api_key, **kw):
        if False:  # 使其成为 async generator
            yield
        raise RuntimeError(f"upstream rejected {api_key}")


def _drive(ws, key: str = TEST_KEY, message: str = "你好呀") -> list[dict]:
    """发 auth + chat，收集所有帧直到 done/error 或结束。"""
    ws.send_json({"type": "auth", "api_key": key})
    ws.send_json({"type": "chat", "message": message})
    frames: list[dict] = []
    while True:
        d = ws.receive_json()
        frames.append(d)
        if d["type"] in ("done", "error"):
            break
    return frames


def test_ws_stream_flow(monkeypatch):
    monkeypatch.setattr("app.main.get_llm_provider", lambda: FakeLLM(["你", "好"]))
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/ws/chat") as ws:
            frames = _drive(ws)

    types = [f["type"] for f in frames]
    assert types == ["delta", "delta", "done"], types
    assert frames[0]["text"] == "你"
    assert frames[1]["text"] == "好"
    done = frames[-1]
    # done 携带落库后的 id，证明消息已成功 commit
    assert done["message_id"]
    assert done["conversation_id"]


def test_ws_requires_auth(monkeypatch):
    monkeypatch.setattr("app.main.get_llm_provider", lambda: FakeLLM(["x"]))
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/ws/chat") as ws:
            # 未 auth 直接 chat
            ws.send_json({"type": "chat", "message": "hi"})
            frame = ws.receive_json()
    assert frame["type"] == "error"
    assert frame["code"] == "unauthorized"


def test_ws_empty_api_key_rejected(monkeypatch):
    monkeypatch.setattr("app.main.get_llm_provider", lambda: FakeLLM(["x"]))
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/ws/chat") as ws:
            ws.send_json({"type": "auth", "api_key": ""})
            frame = ws.receive_json()
    assert frame["type"] == "error"
    assert frame["code"] == "no_api_key"


def test_ws_llm_error_is_redacted(monkeypatch):
    """LLM 异常夹带密钥时，返回给客户端的 error 帧必须已脱敏。"""
    monkeypatch.setattr("app.main.get_llm_provider", lambda: RaisingLLM())
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/ws/chat") as ws:
            ws.send_json({"type": "auth", "api_key": TEST_KEY})
            ws.send_json({"type": "chat", "message": "hi"})
            frame = ws.receive_json()
    assert frame["type"] == "error"
    assert TEST_KEY not in frame["message"]
    assert "<REDACTED>" in frame["message"]
