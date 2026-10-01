"""渠道异常体系。

Adapter 遇到渠道限制（如微信 48 小时客服窗口、5 秒被动回复超时）时，
抛出 ChannelException。核心层（ChatCoreService）捕获后识别错误码，做降级处理
（如：仍返回结果，但标记「无法主动推送」，改由用户下次触发时被动回复）。
"""


class ChannelException(Exception):
    """渠道层异常。核心层据此识别并降级，不崩溃、不吞结果。"""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        self.code = code          # 机器可读错误码（见下方常量）
        self.message = message    # 人类可读描述
        self.retryable = retryable  # 是否可重试（如网络抖动可重试，48h 限制不可重试）
        super().__init__(f"[{code}] {message}")


# ---- 预定义错误码（未来微信适配器使用）----

# 微信 48 小时客服消息窗口已过，不能主动推送
CODE_WECHAT_48H_LIMIT = "wechat_48h_limit"

# 微信被动回复超过 5 秒，连接已被微信断开，只能转主动推送
CODE_WECHAT_TIMEOUT = "wechat_timeout"

# 语音/图片消息无法转文本（MediaId 下载失败或非文本内容）
CODE_MEDIA_CONVERT_FAILED = "media_convert_failed"

# 渠道不可用（临时网络故障等，可重试）
CODE_CHANNEL_UNAVAILABLE = "channel_unavailable"
