"""角色系统测试：CRUD + 导入（JSON/PNG）+ system prompt + 对话集成。"""

import base64
import json
import struct

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.character import CharacterCard, Example, Persona
from app.services.character import build_system_prompt, parse_character_card


# ---- build_system_prompt 单元测试 ----


def test_build_system_prompt_full():
    card = CharacterCard(
        persona=Persona(
            identity="一只会说话的猫",
            personality="傲娇",
            speaking_style="句尾带喵",
            worldview="现代都市",
            relationship="你的宠物",
        ),
        examples=[Example(user="你好", assistant="哼，才不是想理你喵")],
        greeting="喵？",
    )
    text = build_system_prompt("小咪", card)
    assert "你是小咪" in text
    assert "【身份】一只会说话的猫" in text
    assert "【说话风格】句尾带喵" in text
    assert "用户：你好" in text
    assert "你：哼，才不是想理你喵" in text


def test_build_system_prompt_skips_empty():
    card = CharacterCard(persona=Persona(identity="机器人"))
    text = build_system_prompt("R2", card)
    assert "【身份】机器人" in text
    assert "【性格】" not in text  # 空字段省略
    assert "【对话示例】" not in text  # 无示例


# ---- parse_character_card 单元测试 ----


def test_parse_json_card():
    payload = json.dumps(
        {
            "spec": "chara_card_v2",
            "spec_version": "2.0",
            "data": {
                "name": "测试角色",
                "description": "一个测试",
                "personality": "友好",
                "scenario": "测试场景",
                "first_mes": "你好呀",
                "mes_example": "<START>\n{{user}}: hi\n{{char}}: hello\n",
            },
        }
    )
    name, card = parse_character_card(payload)
    assert name == "测试角色"
    assert card.persona.identity == "一个测试"
    assert card.persona.personality == "友好"
    assert card.persona.worldview == "测试场景"
    assert card.greeting == "你好呀"
    assert len(card.examples) == 1
    assert card.examples[0].user == "hi"
    assert card.examples[0].assistant == "hello"


def _make_png_with_chara(data: dict) -> bytes:
    """构造一个只含 tEXt(chara) 块的最小 PNG（parse 只读 tEXt，不看图像数据）。"""
    chara = base64.b64encode(json.dumps(data).encode()).decode()
    chunk_data = b"chara\x00" + chara.encode()
    length = struct.pack(">I", len(chunk_data))
    crc = b"\x00\x00\x00\x00"  # 不校验
    return b"\x89PNG\r\n\x1a\n" + length + b"tEXt" + chunk_data + crc


def test_parse_png_card():
    png = _make_png_with_chara(
        {"spec": "chara_card_v2", "spec_version": "2.0", "data": {"name": "PNG角色", "description": "来自PNG"}}
    )
    name, card = parse_character_card(png)
    assert name == "PNG角色"
    assert card.persona.identity == "来自PNG"


def test_parse_invalid():
    try:
        parse_character_card(b"not a card")
        assert False, "应抛出 ValueError"
    except ValueError:
        pass


# ---- CRUD API 测试 ----


def _create(client: TestClient, name: str = "小明") -> dict:
    r = client.post(
        "/api/v1/characters",
        json={"name": name, "card": {"persona": {"identity": "测试身份"}}},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_character_crud():
    with TestClient(app) as client:
        # 创建
        created = _create(client, "小明")
        assert created["name"] == "小明"
        cid = created["id"]

        # 列表
        r = client.get("/api/v1/characters")
        assert r.status_code == 200
        assert any(c["id"] == cid for c in r.json())

        # 详情
        r = client.get(f"/api/v1/characters/{cid}")
        assert r.status_code == 200
        assert r.json()["card"]["persona"]["identity"] == "测试身份"

        # 更新
        r = client.put(
            f"/api/v1/characters/{cid}",
            json={"name": "小明2", "card": {"persona": {"identity": "改过的身份"}}},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "小明2"
        assert r.json()["card"]["persona"]["identity"] == "改过的身份"

        # 删除
        r = client.delete(f"/api/v1/characters/{cid}")
        assert r.status_code == 204

        # 删除后详情 404
        r = client.get(f"/api/v1/characters/{cid}")
        assert r.status_code == 404


def test_character_import_json():
    with TestClient(app) as client:
        content = base64.b64encode(
            json.dumps({"spec": "chara_card_v2", "data": {"name": "导入角色", "description": "导入的"}}).encode()
        ).decode()
        r = client.post("/api/v1/characters/import", json={"content_base64": content})
        assert r.status_code == 201, r.text
        assert r.json()["name"] == "导入角色"


def test_character_import_png():
    with TestClient(app) as client:
        png = _make_png_with_chara(
            {"spec": "chara_card_v2", "data": {"name": "PNG导入", "description": "图里来的"}}
        )
        content = base64.b64encode(png).decode()
        r = client.post("/api/v1/characters/import", json={"content_base64": content})
        assert r.status_code == 201, r.text
        assert r.json()["name"] == "PNG导入"


# ---- 对话集成测试 ----


class CaptureLLM:
    """捕获 chat_stream 收到的 messages，返回固定回复。"""

    def __init__(self):
        self.messages: list[dict] = []

    async def chat_stream(self, messages, api_key, **kw):
        self.messages = list(messages)
        yield "好"


def test_chat_uses_character_prompt(monkeypatch):
    # 先建角色（第一个 lifespan）
    with TestClient(app) as client:
        created = _create(client, "傲娇猫")
        cid = created["id"]

    # monkeypatch 后重新进 lifespan，让 core 用 fake LLM（重构后 llm 在 lifespan 里创建）
    fake = CaptureLLM()
    monkeypatch.setattr("app.main.get_llm_provider", lambda: fake)

    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/ws/chat") as ws:
            ws.send_json({"type": "auth", "api_key": "sk-test-1234567890"})
            ws.send_json({"type": "chat", "character_id": cid, "message": "你好"})
            frames = []
            while True:
                d = ws.receive_json()
                frames.append(d)
                if d["type"] in ("done", "error"):
                    break

        assert frames[-1]["type"] == "done", frames
        # mock LLM 收到的 system prompt 应包含角色名与人设
        system = fake.messages[0]
        assert system["role"] == "system"
        assert "傲娇猫" in system["content"]
