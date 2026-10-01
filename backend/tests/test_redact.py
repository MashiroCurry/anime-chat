"""日志脱敏单元测试：任何密钥形态都必须被替换，不得泄漏。"""

from app.core.logging import redact


def test_redact_sk_key():
    assert redact("key is sk-abcdef1234567890 here") == "key is <REDACTED> here"


def test_redact_bearer():
    assert redact("Authorization: Bearer abcdefghijklmnop") == "Authorization: <REDACTED>"


def test_redact_api_key_field():
    text = '{"api_key": "sk-1234567890abcdef"}'
    assert "sk-1234567890abcdef" not in redact(text)


def test_redact_preserves_normal_text():
    assert redact("hello world") == "hello world"
    assert redact("") == ""


def test_redact_multiple():
    text = "a=sk-1111111111111111 b=sk-2222222222222222"
    out = redact(text)
    assert "sk-1111111111111111" not in out
    assert "sk-2222222222222222" not in out
    assert out.count("<REDACTED>") == 2
