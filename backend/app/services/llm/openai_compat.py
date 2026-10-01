"""基于官方 openai SDK 的 OpenAI 兼容实现。

base_url 来自配置（M0 = DeepSeek 官方），api_key 由调用方按连接传入。
代码中不出现任何厂商名，仅依赖 OpenAI 兼容的 /chat/completions 协议。

重试只作用于「建立流」这一步（连接/超时错误），流式迭代期间不重试——
tenacity 对异步生成器无法干净重试，硬包会产生难以理解的半截输出。
"""

from collections.abc import AsyncIterator, Sequence

import openai
from openai import AsyncOpenAI
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.services.llm.base import ChatMessage, LLMProvider

_RETRYABLE = (openai.APIConnectionError, openai.APITimeoutError)


class OpenAICompatProvider:
    """OpenAI 兼容后端。base_url/model 走配置，api_key 走入参。"""

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.llm_base_url
        self._model = settings.llm_model

    async def chat_stream(
        self,
        messages: Sequence[ChatMessage],
        api_key: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        client = AsyncOpenAI(base_url=self._base_url, api_key=api_key, timeout=60.0)
        try:
            stream = None
            # 仅对「建流」重试；连接/超时错误最多 3 次，指数退避
            retryer = AsyncRetrying(
                retry=retry_if_exception_type(_RETRYABLE),
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
                reraise=True,
            )
            async for attempt in retryer:
                with attempt:
                    stream = await client.chat.completions.create(
                        model=model or self._model,
                        messages=list(messages),
                        temperature=temperature,
                        stream=True,
                    )
                    break  # 成功拿到流，退出重试

            async for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content
        finally:
            # 密钥不进异常上下文；关闭客户端释放连接
            await client.close()


_impl: LLMProvider = OpenAICompatProvider()


def get_llm_provider() -> LLMProvider:
    return _impl
