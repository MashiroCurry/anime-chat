"""M1b 记忆测试：config 生成 + 注入预算 + 降级 + 隔离 + 管理 API。"""

import asyncio

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.services.chat.core import _MEMORY_ITEM_MAX_CHARS, _inject_memories
from app.main import _create_memory_service
from app.services.memory import NoopMemoryService
from app.services.memory.base import Memory
from app.services.memory.mem0_service import (
    Mem0MemoryService,
    _build_mem0_config,
    _to_memory_list,
)


# ---- _build_mem0_config ----


def test_build_mem0_config_openai():
    s = Settings(
        embedding_provider="openai",
        embedding_model="BAAI/bge-m3",
        embedding_base_url="https://api.siliconflow.cn/v1",
        embedding_api_key="sk-emb",
        llm_api_key="sk-llm",
        llm_base_url="https://api.deepseek.com",
    )
    cfg = _build_mem0_config(s)
    assert cfg["embedder"]["provider"] == "openai"
    assert cfg["embedder"]["config"]["openai_base_url"] == "https://api.siliconflow.cn/v1"
    # embedder 不传 embedding_dims（SiliconFlow 不支持 dimensions 参数）
    assert "embedding_dims" not in cfg["embedder"]["config"]
    assert cfg["llm"]["provider"] == "openai"
    assert cfg["llm"]["config"]["openai_base_url"] == "https://api.deepseek.com"
    assert cfg["vector_store"]["provider"] == "pgvector"
    assert cfg["vector_store"]["config"]["collection_name"] == "memories"
    # 维度单独给 pgvector 建表用
    assert cfg["vector_store"]["config"]["embedding_model_dims"] == 1024
    # 抽取语言指令注入
    assert "中文" in cfg["custom_instructions"]


def test_build_mem0_config_ollama():
    s = Settings(embedding_provider="ollama", embedding_base_url="http://localhost:11434")
    cfg = _build_mem0_config(s)
    assert cfg["embedder"]["provider"] == "ollama"
    assert cfg["embedder"]["config"]["ollama_base_url"] == "http://localhost:11434"


# ---- _to_memory_list ----


def test_to_memory_list(fake_mem0_search_result):
    mems = _to_memory_list(fake_mem0_search_result)
    assert len(mems) == 2
    assert mems[0].memory_id == "m1"
    assert mems[0].content == "用户叫小明"
    assert mems[0].score == 0.95


def test_to_memory_list_handles_list():
    mems = _to_memory_list([{"id": "x", "memory": "y", "score": 0.5}])
    assert len(mems) == 1


# ---- _inject_memories ----


def test_inject_memories_empty():
    assert _inject_memories("你是小明", []) == "你是小明"


def test_inject_memories_orders_by_score():
    mems = [
        Memory(memory_id="a", content="低分", score=0.3),
        Memory(memory_id="b", content="高分", score=0.9),
    ]
    out = _inject_memories("base", mems)
    assert out.index("高分") < out.index("低分")


def test_inject_memories_truncates_item():
    mems = [Memory(memory_id="a", content="长" * 500, score=0.9)]
    out = _inject_memories("base", mems)
    assert "你记得的关于用户的事" in out
    # 单条截断到 200 字
    assert out.count("长") <= _MEMORY_ITEM_MAX_CHARS


def test_inject_memories_budget():
    # 多条超长记忆，总预算 600 字
    mems = [
        Memory(memory_id=str(i), content=f"记忆{i}" * 100, score=1.0 - i * 0.01)
        for i in range(10)
    ]
    out = _inject_memories("base", mems)
    # 注入的记忆区块总字符数不超过预算（约 600 + 前缀）
    block = out.split("你记得的关于用户的事：\n")[1]
    assert len(block) <= 600 + 10  # 预算 + 换行/前缀余量


# ---- Mem0MemoryService：character_id 空跳过 ----


class FakeAsyncMemory:
    def __init__(self, config=None):
        self.config = config
        self.added: list[tuple] = []
        self.search_calls: list = []
        self.deleted: list = []
        self.search_result: dict = {"results": []}
        self.reset_called = False

    async def add(self, messages, *, user_id=None, agent_id=None, **kw):
        self.added.append((messages, user_id, agent_id))

    async def search(self, query, *, filters=None, top_k=None, **kw):
        self.search_calls.append((query, filters, top_k))
        return self.search_result

    async def get_all(self, *, filters=None, **kw):
        return self.search_result

    async def delete(self, memory_id):
        self.deleted.append(memory_id)

    async def reset(self):
        self.reset_called = True


def _make_service(monkeypatch) -> tuple[Mem0MemoryService, FakeAsyncMemory]:
    fake = FakeAsyncMemory()
    monkeypatch.setattr("app.services.memory.mem0_service.AsyncMemory", lambda config=None: fake)
    svc = Mem0MemoryService(Settings(embedding_api_key="sk-emb", llm_api_key="sk-llm"))
    return svc, fake


async def test_mem0_service_skips_empty_character_id(monkeypatch):
    svc, fake = _make_service(monkeypatch)
    await svc.add([{"role": "user", "content": "hi"}], user_id="local", character_id=None)
    assert fake.added == []  # 不落 default 桶

    res = await svc.search("hi", user_id="local", character_id=None)
    assert res == []
    assert fake.search_calls == []


async def test_mem0_service_add_uses_agent_id(monkeypatch):
    svc, fake = _make_service(monkeypatch)
    await svc.add([{"role": "user", "content": "hi"}], user_id="local", character_id="c1")
    assert fake.added == [([{"role": "user", "content": "hi"}], "local", "c1")]


async def test_mem0_service_search_filters(monkeypatch):
    svc, fake = _make_service(monkeypatch)
    fake.search_result = {"results": [{"id": "m1", "memory": "x", "score": 0.5}]}
    res = await svc.search("hi", user_id="local", character_id="c1", top_k=3)
    assert len(res) == 1
    assert res[0].content == "x"
    # search 用 filters + top_k
    assert fake.search_calls[0] == (
        "hi",
        {"user_id": "local", "agent_id": "c1"},
        3,
    )


# ---- 降级 ----


def test_create_memory_service_degrades_without_embedding_key():
    svc = _create_memory_service(Settings(embedding_api_key=""))
    assert isinstance(svc, NoopMemoryService)


async def test_mem0_service_reset(monkeypatch):
    svc, fake = _make_service(monkeypatch)
    await svc.reset()
    assert fake.reset_called is True


# ---- 管理 API ----


def test_memories_api():
    class FakeSvc:
        def __init__(self):
            self.deleted = None
            self.reset_called = False

        async def list(self, *, user_id, character_id=None):
            return [Memory(memory_id="m1", content="用户叫小明", score=0.9)]

        async def delete(self, memory_id, *, user_id):
            self.deleted = memory_id

        async def reset(self):
            self.reset_called = True

    from app.main import app as real_app

    with TestClient(real_app) as client:
        fake_svc = FakeSvc()
        client.app.state.memory = fake_svc  # type: ignore[attr-defined]

        r = client.get("/api/v1/memories", params={"character_id": "c1"})
        assert r.status_code == 200
        body = r.json()
        assert body[0]["memory_id"] == "m1"
        assert body[0]["content"] == "用户叫小明"

        r = client.delete("/api/v1/memories/m1")
        assert r.status_code == 204
        assert fake_svc.deleted == "m1"

        # 清空全部
        r = client.delete("/api/v1/memories")
        assert r.status_code == 204
        assert fake_svc.reset_called is True

        # character_id 空 → 400
        r = client.get("/api/v1/memories", params={"character_id": ""})
        assert r.status_code == 400
