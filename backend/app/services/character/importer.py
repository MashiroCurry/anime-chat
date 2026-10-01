"""Character Card 导入解析。

支持两种格式：
1. 纯 JSON（Character Card v2）
2. PNG 内嵌 JSON（PNG 的 tEXt 块里 chara 字段，SillyTavern 标准）

不引入 Pillow，用 struct + base64 手写 PNG chunk 解析。
"""

import base64
import json
import struct

from app.schemas.character import CharacterCard, Example, Persona

# PNG 签名
_PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _parse_mes_example(raw: str) -> list[Example]:
    """解析 SillyTavern 的 mes_example 格式。

    形如：
        <START>
        {{user}}: 你好
        {{char}}: 你好呀
        <START>
        ...
    """
    examples: list[Example] = []
    if not raw:
        return examples

    blocks = raw.split("<START>")
    for block in blocks:
        user_lines: list[str] = []
        char_lines: list[str] = []
        for line in block.splitlines():
            line = line.strip()
            if line.startswith("{{user}}:"):
                user_lines.append(line[len("{{user}}:") :].strip())
            elif line.startswith("{{char}}:"):
                char_lines.append(line[len("{{char}}:") :].strip())
        # 逐对配对 user/char
        for u, c in zip(user_lines, char_lines):
            if u or c:
                examples.append(Example(user=u, assistant=c))
    return examples


def _card_from_data(data: dict) -> tuple[str, CharacterCard]:
    """把 Character Card 的 data 块映射到我们的 CharacterCard。"""
    name = data.get("name") or "未命名角色"
    persona = Persona(
        identity=data.get("description", ""),
        personality=data.get("personality", ""),
        worldview=data.get("scenario", ""),
        # speaking_style / relationship 在标准 Character Card 里无直接字段，留空
    )
    card = CharacterCard(
        persona=persona,
        examples=_parse_mes_example(data.get("mes_example", "")),
        greeting=data.get("first_mes", ""),
    )
    return name, card


def parse_character_card(content: bytes) -> tuple[str, CharacterCard]:
    """解析角色卡，返回 (name, CharacterCard)。

    content 可为 JSON 文本（str/bytes）或 PNG 二进制。解析失败抛 ValueError。
    """
    # 若为 bytes，先判断是否是 PNG
    if isinstance(content, bytes) and content.startswith(_PNG_SIG):
        content = _extract_png_chara(content)

    # 此时应是 JSON 文本
    if isinstance(content, bytes):
        text = content.decode("utf-8")
    else:
        text = content

    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"角色卡不是合法 JSON：{e}") from e

    # Character Card v2：{spec, spec_version, data:{...}}
    if isinstance(obj, dict) and "data" in obj and isinstance(obj["data"], dict):
        return _card_from_data(obj["data"])

    # 兜底：直接是 data 结构
    if isinstance(obj, dict):
        return _card_from_data(obj)

    raise ValueError("无法识别的角色卡格式")


def _extract_png_chara(png: bytes) -> str:
    """从 PNG 二进制里提取 tEXt 块中的 chara 字段（base64 编码的 JSON）。"""
    pos = len(_PNG_SIG)
    while pos + 8 <= len(png):
        (length,) = struct.unpack(">I", png[pos : pos + 4])
        chunk_type = png[pos + 4 : pos + 8]
        data_start = pos + 8
        data_end = data_start + length
        if data_end + 4 > len(png):
            break
        if chunk_type == b"tEXt":
            data = png[data_start:data_end]
            # tEXt data = keyword \0 text
            if b"\x00" in data:
                keyword, text = data.split(b"\x00", 1)
                if keyword == b"chara":
                    # SillyTavern 把 JSON base64 编码后写入
                    return base64.b64decode(text).decode("utf-8")
        pos = data_end + 4  # 跳过 CRC
    raise ValueError("PNG 中未找到角色卡数据（chara 字段）")
