"""日志配置：核心是「密钥脱敏」，保证任何 API key 都不进入日志。

BYOK 模式下密钥经 WS auth 帧传入，服务端只在连接内存中持有。若上游报错时
openai SDK 把 Authorization 头或请求体打进异常堆栈，日志就会泄漏密钥。
因此用 loguru 的 filter 在写日志前统一脱敏——不能只靠「写代码时记得别打」。
"""

import re
import sys

from loguru import logger

# 匹配常见密钥形态：sk- / Bearer 后的长串、sk-xxx 通用 OpenAI 兼容 key
_SECRET_PATTERNS = [
    re.compile(r"(sk-[A-Za-z0-9_\-]{8,})"),
    re.compile(r"(Bearer\s+[A-Za-z0-9_\-\.]{8,})"),
    re.compile(r"(\bapi_key['\"]?\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{8,})"),
]

REDACTED = "<REDACTED>"


def redact(text: str) -> str:
    """把 text 中的密钥替换为占位符，返回脱敏后的字符串。"""
    if not text:
        return text
    for pat in _SECRET_PATTERNS:
        text = pat.sub(REDACTED, text)
    return text


def redact_record(record: dict) -> bool:
    """loguru filter：在写入前就地替换 record 的 message。

    注意：exception 的堆栈文本需要调用方在 logger.exception 前先 redact。
    本项目的 LLM 调用路径已显式 redact 后再 log（见 api/v1/ws.py）。
    """
    record["message"] = redact(record["message"])
    return True


def configure_logging(debug: bool = True) -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        filter=redact_record,
        level="DEBUG" if debug else "INFO",
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan> - <level>{message}</level>"
        ),
    )
