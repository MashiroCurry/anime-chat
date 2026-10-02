"""会话历史 API 测试：一个角色一条长期会话、跨「刷新」可恢复、角色隔离、limit。

核心回归目标：以前每刷新一次（前端 conversation_id 丢失）就新开一段对话，
现在服务端按 character_id 自动接回，历史不丢。
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.api.v1.conversations import get_conversation_messages
from app.db.session import async_session_factory
from app.main import app
from app.models import Conversation, Message

TEST_KEY = "sk-testkey-1234567890"


class FakeLLM:
    """按给定 chunks 顺序吐字的假 provider，不触网。"""

    def __init__(self, chunks: list[str]):
        self._chunks = chunks

    async def chat_stream(self, messages, api_key, **kw):
        for c in self._chunks:
            yield c


def _create(client: TestClient, name: str) -> str:
    r = client.post("/api/v1/characters", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _say(client: TestClient, text: str, character_id: str | None = None) -> str:
    """经 WS 发一条消息（刻意不带 conversation_id，模拟刷新后的首次发送）。

    返回 done 帧里的 conversation_id。
    """
    with client.websocket_connect("/api/v1/ws/chat") as ws:
        ws.send_json({"type": "auth", "api_key": TEST_KEY})
        frame: dict = {"type": "chat", "message": text}
        if character_id:
            frame["character_id"] = character_id
        ws.send_json(frame)
        while True:
            d = ws.receive_json()
            if d["type"] in ("done", "error"):
                assert d["type"] == "done", d
                return d["conversation_id"]


def _history(client: TestClient, character_id: str | None = None) -> dict:
    params = {"character_id": character_id} if character_id else {}
    r = client.get("/api/v1/conversations/messages", params=params)
    assert r.status_code == 200, r.text
    return r.json()


# ---- 会话复用（本次改动的核心回归）----


def test_same_character_reuses_one_conversation(monkeypatch):
    """同一角色连发两条，即使都不带 conversation_id，也落在同一条会话里。"""
    monkeypatch.setattr("app.main.get_llm_provider", lambda: FakeLLM(["好"]))
    with TestClient(app) as client:
        cid = _create(client, "小明")
        first = _say(client, "你好", cid)
        second = _say(client, "在吗", cid)

    assert first == second, "同角色第二次发送开了新会话，刷新后会丢历史"


def test_default_conversation_without_character(monkeypatch):
    """没有角色时用「无角色默认会话」，同样不因刷新而分裂。"""
    monkeypatch.setattr("app.main.get_llm_provider", lambda: FakeLLM(["好"]))
    with TestClient(app) as client:
        first = _say(client, "无角色第一句")
        second = _say(client, "无角色第二句")
        body = _history(client)

    assert first == second
    contents = [m["content"] for m in body["messages"]]
    assert sorted(contents) == sorted(["无角色第一句", "无角色第二句", "好", "好"])


def test_characters_are_isolated(monkeypatch):
    """不同角色各看各的历史，互不串台。"""
    monkeypatch.setattr("app.main.get_llm_provider", lambda: FakeLLM(["喵"]))
    with TestClient(app) as client:
        a = _create(client, "A")
        b = _create(client, "B")
        _say(client, "给A的", a)
        _say(client, "给B的", b)
        ra = _history(client, a)
        rb = _history(client, b)

    assert ra["conversation_id"] != rb["conversation_id"]
    ca = [m["content"] for m in ra["messages"]]
    cb = [m["content"] for m in rb["messages"]]
    assert "给A的" in ca and "给B的" not in ca
    assert "给B的" in cb and "给A的" not in cb


def test_history_survives_without_conversation_id(monkeypatch):
    """刷新场景：只凭 character_id 就能拿回历史（前端不需要记住会话 id）。"""
    monkeypatch.setattr("app.main.get_llm_provider", lambda: FakeLLM(["好"]))
    with TestClient(app) as client:
        cid = _create(client, "小明")
        _say(client, "第一句", cid)
        body = _history(client, cid)

    assert body["conversation_id"]
    contents = [m["content"] for m in body["messages"]]
    assert sorted(contents) == sorted(["第一句", "好"])
    assert all(m["role"] in ("user", "assistant") for m in body["messages"])


def test_no_conversation_returns_empty_state(monkeypatch):
    """没聊过是正常态：200 + 空列表，不是 404。"""
    with TestClient(app) as client:
        r = client.get(
            "/api/v1/conversations/messages", params={"character_id": "不存在"}
        )

    assert r.status_code == 200
    assert r.json() == {"conversation_id": None, "messages": []}


# ---- 排序与 limit（直接建数据，避免 SQLite 秒级时间戳导致的排序不确定）----


async def test_messages_ordered_ascending_and_limited():
    """返回时间正序，且 limit 取的是「最近」的若干条。"""
    async with async_session_factory() as s:
        conv = Conversation(character_id="c-order")
        s.add(conv)
        await s.flush()
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i, text in enumerate(["第一句", "第二句", "第三句"]):
            s.add(
                Message(
                    conversation_id=conv.id,
                    role="user",
                    content=text,
                    created_at=base + timedelta(seconds=i),
                )
            )
        await s.commit()

    async with async_session_factory() as s:
        out = await get_conversation_messages(
            character_id="c-order", limit=2, session=s
        )

    assert out.conversation_id == conv.id
    # 最近 2 条，且为正序
    assert [m.content for m in out.messages] == ["第二句", "第三句"]
