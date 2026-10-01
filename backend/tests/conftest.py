"""测试夹具：用 SQLite（aiosqlite）跑，不依赖 Docker / PostgreSQL。

关键：必须在导入任何 app 模块之前设置 DATABASE_URL 环境变量，
否则 session.py 会以默认 PostgreSQL URL 建引擎。
"""

import os
import tempfile

# 在导入 app 之前设置测试数据库 URL（临时 SQLite 文件）
_TMP_DB = os.path.join(tempfile.gettempdir(), "companion_test.db")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"
os.environ["LLM_BASE_URL"] = "https://api.deepseek.com"
os.environ["LLM_MODEL"] = "deepseek-chat"
# 空 key 覆盖 .env 里的真实 key：测试降级 Noop，不真连 embedding/LLM
os.environ["EMBEDDING_API_KEY"] = ""
os.environ["LLM_API_KEY"] = ""

import pytest  # noqa: E402

import app.models  # noqa: E402, F401  确保所有表注册到 Base.metadata
from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402


@pytest.fixture(autouse=True)
async def _reset_db():
    """每个测试前重建表，保证测试间数据隔离（共享同一个 SQLite 文件）。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture
def fake_mem0_search_result():
    """镜像 mem0 2.2.1 的 search/get_all 返回结构，集中维护。

    search 返回 {"results": [ {id, memory, score, metadata, ...} ]}。
    跨版本字段若有差异，只改这里，避免单测过了线上崩。
    """
    return {
        "results": [
            {
                "id": "m1",
                "memory": "用户叫小明",
                "score": 0.95,
                "metadata": {"user_id": "local", "agent_id": "char_1"},
            },
            {
                "id": "m2",
                "memory": "用户喜欢猫",
                "score": 0.7,
                "metadata": {"user_id": "local", "agent_id": "char_1"},
            },
        ]
    }
