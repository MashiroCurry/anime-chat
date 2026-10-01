"""内部统一消息格式（跨渠道标准）。

微信 / WebSocket / QQ 的外部数据格式完全不同，核心层只认 UnifiedMessage。
Adapter 负责把外部消息转成这个结构。
"""

from dataclasses import dataclass


@dataclass
class UnifiedMessage:
    """一条跨渠道的统一消息。

    character_id 是对话参数（用哪个角色卡），不是渠道概念，故放在这里。
    api_key（BYOK 密钥）不放这里——它是「渠道鉴权」，由 Adapter 解析后单独传给核心层。
    user_id 是 **internalUserId**（身份映射后的内部 ID），不是外部渠道 ID。
    """

    user_id: str                       # 内部用户 ID（经 IdentityService 映射）
    session_id: str | None             # 会话 ID（= conversation_id，首轮为 None）
    content: str                       # 文本内容
    timestamp: float                   # 时间戳（epoch 秒）
    channel_type: str                  # 'ws' | 'wechat' | 'qq'
    character_id: str | None = None    # 角色 ID（对话参数）


@dataclass
class ReplyResult:
    """核心层处理完一条消息后的完整结果。

    经 ChatCoreService.on_reply 回调抛出，供需要「完整回复」的渠道（如微信）
    异步推送使用；流式渠道（WS）走 MessageChannel.send_delta 逐 token 输出。
    """

    user_id: str        # 内部用户 ID
    content: str        # 完整回复文本
    message_id: str     # 落库后的消息 id
    session_id: str     # 会话 id（= conversation_id）
