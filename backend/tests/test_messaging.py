"""消息收发层框架测试：IdentityService / ChannelException / WeChat 签名校验。"""

import hashlib

import pytest

from app.core.messaging.adapters.wechat import WeChatAdapter
from app.core.messaging.exceptions import (
    CODE_WECHAT_48H_LIMIT,
    ChannelException,
)
from app.core.messaging.identity import SingleUserIdentityService


@pytest.mark.anyio
async def test_identity_resolve_single_user():
    svc = SingleUserIdentityService()
    # 不同渠道的外部 ID 都映射到唯一本地用户
    assert await svc.resolve("wechat", "openid_abc123") == "local"
    assert await svc.resolve("ws", "whatever") == "local"


def test_channel_exception_fields():
    e = ChannelException(CODE_WECHAT_48H_LIMIT, "已超 48 小时", retryable=False)
    assert e.code == "wechat_48h_limit"
    assert e.message == "已超 48 小时"
    assert e.retryable is False
    assert "wechat_48h_limit" in str(e)


def test_wechat_verify_signature():
    adapter = WeChatAdapter(SingleUserIdentityService())
    token = "mytoken"
    timestamp = "1234567890"
    nonce = "abcdef"
    # 微信标准：sha1(sort([token, timestamp, nonce]))
    correct = hashlib.sha1("".join(sorted([token, timestamp, nonce])).encode()).hexdigest()
    assert adapter.verify_signature(correct, timestamp, nonce, token) is True
    assert adapter.verify_signature("wrong_signature", timestamp, nonce, token) is False
