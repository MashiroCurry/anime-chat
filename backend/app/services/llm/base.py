"""LLM 接入抽象。

BYOK 模式的关键差别：api_key 是「每次调用」的入参，而不是全局配置。
这样每个连接用自己的密钥，服务端不持有任何用户的密钥。
"""

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any, Protocol


class ChatMessage(Mapping[str, Any]):
    """一条对话消息，即 OpenAI 兼容的 {role, content}。"""


class LLMProvider(Protocol):
    """任意 OpenAI 兼容后端的流式对话接口。"""

    async def chat_stream(
        self,
        messages: Sequence[ChatMessage],
        api_key: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """流式返回生成文本的每个增量块。

        抛出异常时由调用方捕获并转为 ErrorFrame；异常信息须已脱敏。
        """
        ...
