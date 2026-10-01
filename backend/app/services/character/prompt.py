"""角色卡 → system prompt 渲染。这是「深度定制角色」的核心落点。"""

from app.schemas.character import CharacterCard


def build_system_prompt(name: str, card: CharacterCard) -> str:
    """把角色卡渲染成 system prompt。空字段自动省略。"""
    lines: list[str] = [f"你是{name}。", ""]

    p = card.persona
    # 字段顺序即渲染顺序，空字段跳过
    field_labels = [
        ("identity", "身份"),
        ("personality", "性格"),
        ("speaking_style", "说话风格"),
        ("worldview", "世界观"),
        ("relationship", "与用户的关系"),
    ]
    for field, label in field_labels:
        value = getattr(p, field)
        if value:
            lines.append(f"【{label}】{value}")

    if card.examples:
        lines.append("")
        lines.append("【对话示例】")
        for ex in card.examples:
            lines.append(f"用户：{ex.user}")
            lines.append(f"你：{ex.assistant}")

    lines.append("")
    lines.append("遵守以上人设，用自然、符合角色的口吻回应，不要跳出角色。")

    return "\n".join(lines)
