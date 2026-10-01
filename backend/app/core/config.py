"""应用配置：从环境变量 / .env 读取，pydantic-settings 管理。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置。所有字段均可被环境变量覆盖（大小写不敏感）。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 应用
    debug: bool = True
    app_name: str = "AI 伴侣后端"

    # 数据库
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/companion"

    # LLM（OpenAI 兼容协议）
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    # 仅本地开发兜底；正常走 BYOK（WS auth 帧传入，服务端不落盘）。
    # 也用作记忆抽取的全局 LLM（mem0 单例不支持每请求覆盖 LLM 密钥）。
    llm_api_key: str = ""

    # ---- 记忆（mem0，可插拔）----
    # embedding 提供方："openai"(OpenAI 兼容) | "ollama"
    embedding_provider: str = "openai"
    embedding_model: str = "BAAI/bge-m3"
    embedding_base_url: str = "https://api.siliconflow.cn/v1"
    embedding_api_key: str = ""
    embedding_dims: int = 1024  # bge-m3 维度
    # 读写独立开关：可「关抽取保留搜索」或反之
    memory_search_enabled: bool = True
    memory_extract_enabled: bool = True
    memory_table: str = "memories"
    # 记忆抽取指令（mem0 的 custom_instructions，注入抽取 prompt）
    memory_custom_instructions: str = "请用简体中文提取和记录记忆，所有记忆内容都使用中文表述。"


@lru_cache
def get_settings() -> Settings:
    return Settings()
