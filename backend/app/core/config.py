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
    # 记忆抽取指令（mem0 的 custom_instructions，注入抽取 prompt，优先级最高）。
    # mem0 默认 prompt 会「从 user 和 assistant 双方提取 + 把相对时间锚定到具体日期」，
    # 导致把对话流水账/角色扮演/寒暄都记成记忆。这里用强指令覆盖该倾向，只留持久事实。
    memory_custom_instructions: str = (
        "只提取关于「用户」的长期事实，不要记录对话过程本身。以下规则优先级最高：\n"
        "\n"
        "【要提取】\n"
        "1. 用户身份：名字、年龄、性别、职业、所在地。\n"
        "2. 用户偏好与喜恶：食物、影视、音乐、活动、品牌等。\n"
        "3. 用户人际关系：家人、伴侣、朋友、宠物。\n"
        "4. 用户目标与计划：近期打算、长期目标、待办。\n"
        "5. 用户重要人生事件：生日、纪念日、重大经历。\n"
        "\n"
        "【禁止提取】\n"
        "1. 对话流水账：不要记录「用户说了什么、助手回了什么」的过程。\n"
        "2. 助手/角色的言行、情绪或角色扮演内容。\n"
        "3. 寒暄、问候、日常闲聊、临时性话题。\n"
        "4. 无信息量的内容（如「在嘛」「嗯」「哈哈」）。\n"
        "\n"
        "【写法要求】\n"
        "1. 每条以「用户」为主语，简短、永恒、不加日期时间戳。\n"
        "   例：写「用户喜欢科幻电影」，不要写「10月1日用户说喜欢科幻电影」。\n"
        "2. 只有真正与日期绑定的信息（生日、纪念日）才保留日期。\n"
        "3. 对话里没有任何长期事实时，返回空列表，不要凑数。\n"
        "4. 不重复提取已有记忆里已存在的事实。\n"
        "5. 所有记忆内容用中文表述。"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
