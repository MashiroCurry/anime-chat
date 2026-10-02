# anime-chat

一个可深度定制 AI 角色、带永久记忆的纯文本聊天应用。

设计目标只有三个词：**流畅、简洁、不打扰**。主界面常驻元素仅限角色区、消息流、输入框、发送按钮和设置入口图标——其余功能一律渐进披露。

> English version: [README.en.md](README.en.md)

---

## 目录

- [当前进度](#当前进度)
- [功能特性](#功能特性)
- [架构](#架构)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [配置](#配置)
- [WebSocket 协议](#websocket-协议)
- [REST API](#rest-api)
- [项目结构](#项目结构)
- [测试](#测试)
- [开发路线图](#开发路线图)
- [说明](#说明)

---

## 当前进度

| 里程碑 | 内容 | 状态 |
|---|---|---|
| M0 | 骨架 + 最小对话闭环（流式） | ✅ |
| M1a | 角色系统（角色卡 CRUD / 导入） | ✅ |
| M1b | 长期记忆（mem0 + pgvector） | ✅ |
| M3 | 记忆管理面板 + 性能对齐 | ⏳ 待做 |
| M4 | 内容审核 / 部署 / 微信接入 | ⏳ 待做 |

**已放弃 Live2D**：本项目聚焦纯文本聊天，所有渲染管线与情绪映射代码已移除。未来的微信消息收发层接口已预留（见[架构](#架构)）。

---

## 功能特性

### 可深度定制的 AI 角色

角色卡（`CharacterCard`）是一个 JSONB 结构，包含：

- **人设**：身份、性格、说话风格、世界观、与用户的关系
- **示例对话**：少样本对话，用于锚定语气
- **开场白**：新建会话时的第一条消息
- **模型参数**：每个角色可独立指定模型与 `temperature`
- **记忆参数**：独立开关与召回条数 `top_k`

角色卡可通过 REST 接口创建、编辑、删除，或从 JSON 导入。

### 永久记忆

基于自托管的 [mem0](https://github.com/mem0ai/mem0)，向量存储直接复用 PostgreSQL 的 `pgvector` 扩展——不额外维护向量数据库。

- **写路径**：一轮对话结束后，用户消息 + 助手回复异步投递给 mem0 抽取记忆（`fire-and-forget`，不阻塞回复）
- **读路径**：新一轮对话前，用用户消息做语义检索，把召回的记忆追加到 system prompt 末尾（末尾权重更高）
- **降级保护**：检索超时 1.5s、异常一律降级为空，embedding 服务挂掉不影响聊天
- **Token 预算**：单条记忆截断 200 字，注入总量上限 600 字
- **中文抽取**：通过 `memory_custom_instructions` 强制用简体中文记录记忆

记忆可在设置抽屉中查看和清理。

### 密钥自持（BYOK）

API 密钥只存在**浏览器 localStorage** 里，通过 WebSocket 连接的 `auth` 帧发送，服务端仅在连接内存中持有，**从不落盘、从不写日志**（日志脱敏见 `backend/app/core/logging.py`）。

因此你可以接入任意 OpenAI 兼容的 API——DeepSeek、OpenAI、SiliconFlow、本地 Ollama 等，只改 base_url 和模型名即可。

---

## 架构

### 三层消息收发

核心对话逻辑与消息传输完全解耦。未来接入微信，只需新增一个 Adapter，核心层零改动。

```
┌─────────────────────────────────────────────────────┐
│ ChatCoreService（核心层）                             │
│ 只处理 LLM + 记忆 + 角色卡，不知道消息从哪来            │
│ handle_message(UnifiedMessage, api_key, channel)     │
└────────────────────┬────────────────────────────────┘
                     │ 依赖 MessageChannel 接口
┌────────────────────┴────────────────────────────────┐
│ MessageChannel（接口层）                              │
│ on_message + send_delta / send_done / send_error      │
└────────────┬──────────────────────┬─────────────────┘
             │                      │
  ┌──────────▼──────────┐  ┌───────▼──────────┐
  │ WebSocketAdapter     │  │ WeChatAdapter     │
  │ （已实现）            │  │ （预留骨架）       │
  └─────────────────────┘  └───────────────────┘
```

几个关键设计点：

- **统一消息体** `UnifiedMessage`：跨渠道的内部消息格式，携带 `user_id` / `session_id` / `content` / `channel_type` / `character_id`
- **流式收口在接口层**：核心层统一调用 `send_delta` / `send_done`，呈现差异由 Adapter 吸收——WebSocket 逐 token 推，微信则累积后一次性发送
- **异步结果回调** `on_reply(handler)`：核心层处理完一条消息后，把完整回复抛给所有监听者，供微信这类需要完整文本的渠道异步推送
- **身份映射** `IdentityService`：外部 ID（微信 OpenID 等）→ 内部 `user_id`，核心层只认内部 ID。当前为单用户实现，未来替换为数据库实现
- **渠道异常** `ChannelException`：微信 48 小时窗口限制、5 秒超时等场景向上抛出，核心层识别后降级而非崩溃

### 一次对话的数据流

```
用户输入
  └─> WebSocketAdapter 解析帧，转成 UnifiedMessage
        └─> ChatCoreService.handle_message
              ├─ 1. 载入角色卡（可选）
              ├─ 2. 拉取历史上下文（最近 20 条）
              ├─ 3. 落库用户消息
              ├─ 4. 检索记忆并注入 system prompt
              ├─ 5. LLM 流式生成 → channel.send_delta 逐 token 输出
              ├─ 6. 落库助手消息 → channel.send_done
              ├─ 7. on_reply 回调抛出完整结果
              └─ 8. 异步投递记忆抽取
```

---

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | Vue 3 + Vite 6 + TypeScript，UI 组件仅用 Naive UI（`unplugin-vue-components` 按需引入） |
| 后端 | FastAPI + Python 3.11+ + SQLAlchemy 2.x（async）+ Pydantic v2 |
| 数据库 | PostgreSQL 16 + pgvector |
| 缓存/队列 | Redis 7 |
| 模型网关 | [new-api](https://github.com/Calcium-Ion/new-api)（OpenAI 兼容，M0 仅起好待用） |
| 记忆 | mem0 自托管（向量后端复用 pgvector） |
| 迁移 | Alembic |
| 测试 | pytest + pytest-asyncio |
| 前端 E2E | Playwright |

**前端组件预算是硬性约束**：主界面常驻的 Naive UI 组件最多 2 个（`n-input` + `n-button`），浮层最多 5 个，打包体积 < 50KB gzip。消息列表和消息气泡全部手写，不使用组件库。

---

## 快速开始

### 前置要求

- **Docker Desktop**（跑 PostgreSQL / Redis / new-api）
- **Python 3.11+** 与 [uv](https://github.com/astral-sh/uv)

  ```bash
  # Windows (PowerShell)
  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
  # macOS / Linux
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

- **Node.js 18+**

### 1. 启动基础设施

```bash
docker compose up -d
```

启动三个容器：`companion-postgres`（5432，含 pgvector）、`companion-redis`（6379）、`companion-new-api`（3000）。

> `docker-compose.yml` 里写死了 `name: companion`——因为仓库目录名是中文，Compose 无法用目录名作项目名。

### 2. 启动后端

```bash
cd backend

# 安装依赖（uv 会自动创建 .venv）
uv sync

# 配置环境变量（仅首次。已存在就跳过，否则会覆盖掉里面已填的密钥）
[ -f .env ] || cp ../.env.example .env
# 编辑 .env，填入 LLM_API_KEY（仅本地开发兜底用）和 EMBEDDING_API_KEY

# 执行数据库迁移
uv run alembic upgrade head

# 启动服务
uv run uvicorn app.main:app --reload --port 8000
```

健康检查：<http://127.0.0.1:8000/api/v1/health>

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

打开 <http://localhost:5173>，在设置抽屉里填入你的 API 密钥即可开始聊天。

前端开发服务器已配置代理，`/api`（含 WebSocket）转发到 `http://127.0.0.1:8000`。

### 一键启动（可选，替代步骤 2–3）

配好 `backend/.env` 后，可以用脚本一次拉起后端和前端：

```bash
bash scripts/dev.sh
```

脚本会检测端口占用（已占用则跳过，方便只重启其中一个），并打印出手机可访问的局域网地址。`Ctrl+C` 停止全部。

### 手机 / 局域网访问

vite 已配置监听 `0.0.0.0`，手机连同一个 Wi-Fi 即可访问：

```bash
# 查看电脑的局域网 IP（找「无线局域网适配器 WLAN」下的 IPv4 地址）
ipconfig
```

手机浏览器打开 `http://<局域网IP>:5173`，例如 `http://192.168.0.107:5173`。

注意三点：

- 端口是 **5173**（前端），不是 8000——后端不直接暴露到局域网
- 协议是 **http**，不是 https
- 手机和电脑必须在**同一个** Wi-Fi（访客网络会隔离设备，连不通）

后端不需要监听 `0.0.0.0`，也不需要配 CORS：手机只跟 vite 打交道，`/api`（含 WebSocket）由 vite 在电脑本机代理到 `127.0.0.1:8000`，对浏览器而言始终是同源请求。

手机连不上时按顺序排查：

1. `netstat -ano | findstr :5173` 确认监听地址是 `0.0.0.0` 而不是 `127.0.0.1`
2. 确认手机和电脑在同一个 Wi-Fi
3. Windows 防火墙若为开启状态，首次运行 Node 时需允许「专用网络」访问

---

## 配置

配置通过环境变量或 `backend/.env` 读取（pydantic-settings）。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/companion` | 数据库连接串 |
| `LLM_BASE_URL` | `https://api.deepseek.com` | OpenAI 兼容端点 |
| `LLM_MODEL` | `deepseek-chat` | 默认模型 |
| `LLM_API_KEY` | 空 | 本地兜底密钥；正常走 BYOK。**也用作记忆抽取的 LLM**（mem0 单例不支持每请求覆盖密钥） |
| `EMBEDDING_PROVIDER` | `openai` | `openai`（OpenAI 兼容）或 `ollama` |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | 嵌入模型 |
| `EMBEDDING_BASE_URL` | `https://api.siliconflow.cn/v1` | 嵌入服务端点 |
| `EMBEDDING_API_KEY` | 空 | **未配置则记忆功能自动降级为 Noop，聊天不受影响** |
| `EMBEDDING_DIMS` | `1024` | bge-m3 维度。**换模型等于重建全表向量** |
| `MEMORY_SEARCH_ENABLED` | `true` | 记忆读路径开关 |
| `MEMORY_EXTRACT_ENABLED` | `true` | 记忆写路径开关 |
| `DEBUG` | `true` | 调试模式 |

> ⚠️ **嵌入模型维度锁死**：`hnsw` / `ivfflat` 索引对 `vector` 类型上限为 2000 维。换 embedding 模型必须重建全表向量，请在部署前定死。

---

## WebSocket 协议

端点：`ws://127.0.0.1:8000/api/v1/ws/chat`

### 客户端 → 服务端

```jsonc
// 连接后必须发的第一帧，携带密钥
{ "type": "auth", "api_key": "sk-..." }

// 发起一次对话
{ "type": "chat", "message": "你好", "character_id": "uuid", "conversation_id": "uuid" }

// 心跳
{ "type": "ping" }
```

### 服务端 → 客户端

```jsonc
// 流式增量
{ "type": "delta", "text": "你" }

// 本轮结束
{ "type": "done", "message_id": "uuid", "conversation_id": "uuid", "usage": null }

// 错误（message 已脱敏）
{ "type": "error", "code": "llm_error", "message": "..." }
```

两侧契约由 Pydantic 判别联合定义（`backend/app/schemas/frames.py`），前端在 `frontend/src/api/frames.ts` 维护同构类型。

### 为什么密钥走 auth 帧？

浏览器的 WebSocket API 无法设置自定义请求头，密钥放 URL query 又会被 access log 记录。因此密钥走「连接后第一帧 auth」，服务端仅在连接内存中持有。

---

## REST API

前缀 `/api/v1`。

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/health` | 健康检查（含数据库连通性） |
| `GET` | `/characters` | 角色列表 |
| `POST` | `/characters` | 新建角色 |
| `GET` | `/characters/{id}` | 角色详情 |
| `PUT` | `/characters/{id}` | 更新角色 |
| `DELETE` | `/characters/{id}` | 删除角色 |
| `POST` | `/characters/import` | 从 JSON 导入角色 |
| `GET` | `/memories` | 记忆列表 |
| `DELETE` | `/memories/{id}` | 删除单条记忆 |
| `DELETE` | `/memories` | 清空全部记忆 |

---

## 项目结构

```
.
├── backend/
│   ├── app/
│   │   ├── api/v1/              # REST + WS 路由
│   │   ├── core/
│   │   │   ├── config.py        # pydantic-settings 配置
│   │   │   ├── logging.py       # loguru + 密钥脱敏
│   │   │   └── messaging/       # 三层架构
│   │   │       ├── types.py         # UnifiedMessage / ReplyResult
│   │   │       ├── channel.py       # MessageChannel 接口
│   │   │       ├── exceptions.py    # ChannelException
│   │   │       ├── identity.py      # IdentityService
│   │   │       └── adapters/
│   │   │           ├── websocket.py # WebSocketAdapter（已实现）
│   │   │           └── wechat.py    # WeChatAdapter（预留骨架）
│   │   ├── db/                  # 引擎 / 会话 / Base
│   │   ├── models/              # SQLAlchemy 模型
│   │   ├── schemas/             # Pydantic 模型（含 WS 帧协议）
│   │   └── services/
│   │       ├── chat/core.py     # ChatCoreService（核心层）
│   │       ├── character/       # 角色卡 → system prompt
│   │       ├── llm/             # OpenAI 兼容客户端
│   │       └── memory/          # mem0 封装 + Noop 降级
│   ├── alembic/                 # 数据库迁移
│   └── tests/                   # 46 个测试
├── frontend/
│   ├── src/
│   │   ├── components/          # 消息列表 / 气泡 / 输入框 / 设置抽屉 / 角色面板
│   │   ├── composables/useChat.ts
│   │   ├── api/                 # REST + WS 客户端
│   │   └── views/CharacterEditor.vue
│   └── e2e/                     # Playwright 截图脚本
├── scripts/
│   └── dev.sh                   # 一键启动后端 + 前端，并打印手机访问地址
├── screenshots/                 # 各里程碑验证截图
├── docker-compose.yml
├── CLAUDE.md                    # 项目约束（给 AI 编码工具看）
└── AI伴侣应用技术方案.md          # 完整技术方案文档
```

---

## 测试

```bash
cd backend
uv run pytest -q
```

当前 **46 个测试全部通过**，覆盖：

- WebSocket 端到端对话（`test_ws.py`）
- 核心层单元测试，不经过传输层（`test_chat_core.py`）
- 上下文拼接不重复（含多轮回归测试）
- 角色卡 CRUD 与导入（`test_characters.py`）
- 记忆服务与降级（`test_memories.py`）
- 三层架构：身份映射、渠道异常、微信签名校验（`test_messaging.py`）
- 日志密钥脱敏（`test_redact.py`）

> 测试要求 PostgreSQL 已启动。`conftest.py` 会在 `.env` 之前清空 `EMBEDDING_API_KEY`，避免测试触发真实 embedding 调用。

前端截图：

```bash
cd frontend
npm run e2e:shot
```

---

## 开发路线图

| 里程碑 | 内容 | 状态 |
|---|---|---|
| M0 | 骨架 + 最小对话闭环（FastAPI + DB + 网关 + 流式对话） | ✅ |
| M1a | 角色系统（角色卡 CRUD / 导入） | ✅ |
| M1b | 记忆系统（mem0 接入、中文抽取、检索注入、清理） | ✅ |
| ~~M2~~ | ~~Live2D 渲染~~ | ❌ 已放弃 |
| M3 | 记忆管理面板 + 性能硬指标对齐 | ⏳ |
| M4 | 角色市场、内容审核、压测上云、微信接入 | ⏳ |

### 性能硬指标（目标）

- 首屏 LCP < 1.5s，TTI < 2s
- 输入到界面回显 < 50ms
- 消息列表 1000 条时滚动稳定 60fps，无长任务 > 50ms
- 流式响应首字 < 1.5s
- 连续聊天 30 分钟，堆内存增长 < 50MB

---

## 说明

- 本项目为个人学习与自用项目，采用 BYOK（Bring Your Own Key）模式，不提供任何 API 密钥。
- 请勿将 `.env`、密钥文件提交到版本库（`.gitignore` 已排除）。
- 内容审核、限流、多租户等生产级能力尚未实现，请勿直接暴露到公网。
