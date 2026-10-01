"""身份映射：外部渠道 ID → 内部用户 ID。

核心层只认 internalUserId，绝不接触微信 OpenID 等外部标识。
Adapter 收到外部消息后，先经 IdentityService 解析成内部 ID，再构造 UnifiedMessage。
"""

from typing import Protocol

# 当前单用户模式：所有渠道的外部 ID 都映射到这一个内部用户。
# 与 app.models.character.DEFAULT_OWNER_ID 保持一致。
_DEFAULT_INTERNAL_USER = "local"


class IdentityService(Protocol):
    """外部 ID → 内部 ID 的映射接口。"""

    async def resolve(self, channel_type: str, external_id: str) -> str:
        """解析外部 ID（如微信 OpenID）为内部 ID。不存在则创建映射并返回。"""
        ...


class SingleUserIdentityService:
    """单用户实现（当前）：所有外部 ID 映射到唯一本地用户。

    未来多用户时替换为 DBIdentityService：建 identities 表存
    (channel_type, external_id) → internal_id 的映射，首次解析时落库。
    """

    async def resolve(self, channel_type: str, external_id: str) -> str:
        return _DEFAULT_INTERNAL_USER
