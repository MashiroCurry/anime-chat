# anime-chat

一个可深度定制 AI 角色、带永久记忆的纯文本聊天应用。

设计目标只有三个词：**流畅、简洁、不打扰**。主界面常驻元素仅限角色区、消息流、输入框、发送按钮和设置入口图标——其余一律渐进披露。

> English version: [README.en.md](README.en.md)

## 功能特性

**可深度定制的 AI 角色。** 角色卡是 JSONB 结构：人设（身份 / 性格 / 说话风格 / 世界观 / 与用户的关系）、示例对话、开场白，以及每个角色独立的模型参数与记忆召回条数。支持增删改查与 JSON 导入。

**永久记忆。** 基于自托管 [mem0](https://github.com/mem0ai/mem0)，向量直接存 PostgreSQL 的 pgvector，不额外维护向量库。每轮对话结束异步抽取（不阻塞回复），下一轮开始前语义检索并注入 system prompt 末尾。检索 1.5s 超时、异常一律降级为空——embedding 服务挂掉不影响聊天；单条截断 200 字，注入总量 600 字。记忆可在设置抽屉中查看和清理。

**聊天记录持久化。** 一个角色一条长期会话，刷新页面、换浏览器、换手机都不会丢。服务端按 `character_id` 锚定会话，前端不需要记住 `conversation_id`；局域网下手机打开同一地址、选一次角色即可看到同一段对话。

**密钥自持（BYOK）。** 密钥只存在浏览器 localStorage，经 WebSocket 的 `auth` 帧发送，服务端仅在连接内存中持有，从不落盘、从不写日志。因此可接入任意 OpenAI 兼容 API（DeepSeek / OpenAI / SiliconFlow / 本地 Ollama），只需改 base_url 和模型名。

## 快速开始

前置：Docker Desktop、Python 3.11+ 与 [uv](https://github.com/astral-sh/uv)、Node.js 18+。

```bash
# 1. 基础设施：postgres(5432, 含 pgvector) / redis(6379) / new-api(3000)
docker compose up -d

# 2. 后端
cd backend
uv sync
[ -f .env ] || cp ../.env.example .env    # 仅首次；已存在就跳过，否则会覆盖已填的密钥
# 编辑 .env，填入 LLM_API_KEY（本地兜底）和 EMBEDDING_API_KEY
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000

# 3. 前端
cd frontend && npm install && npm run dev
```

打开 <http://localhost:5173>，在设置抽屉中填入 API 密钥即可开始聊天。健康检查：<http://127.0.0.1:8000/api/v1/health>。

配好 `backend/.env` 后，也可以用 `bash scripts/dev.sh` 一次拉起前后端——自动跳过已占用的端口（方便只重启其中一个），并打印手机可访问的局域网地址。

### 手机 / 局域网访问

vite 已监听 `0.0.0.0`，手机连同一个 Wi-Fi 即可访问 `http://<电脑局域网IP>:5173`（用 `ipconfig` 查，找 WLAN 适配器下的 IPv4）。

- 端口是 **5173**（前端），不是 8000——后端不暴露到局域网；协议是 **http**，不是 https
- 手机和电脑必须在**同一个** Wi-Fi（访客网络会隔离设备）

后端不需要监听 `0.0.0.0`，也不需要配 CORS：手机只跟 vite 打交道，`/api`（含 WebSocket）由 vite 在电脑本机代理到 `127.0.0.1:8000`，对浏览器始终是同源请求。连不上时依次排查：`netstat -ano | findstr :5173` 的监听地址是否为 `0.0.0.0`、是否连的同一个 Wi-Fi、Windows 防火墙是否放行 Node 的「专用网络」。

## 配置

通过环境变量或 `backend/.env` 读取（pydantic-settings）。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/companion` | 数据库连接串 |
| `LLM_BASE_URL` | `https://api.deepseek.com` | OpenAI 兼容端点 |
| `LLM_MODEL` | `deepseek-chat` | 默认模型 |
| `LLM_API_KEY` | 空 | 本地兜底密钥，正常走 BYOK。**也用作记忆抽取的 LLM**（mem0 单例不支持每请求覆盖密钥） |
| `EMBEDDING_PROVIDER` | `openai` | `openai`（兼容协议）或 `ollama` |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | 嵌入模型 |
| `EMBEDDING_BASE_URL` | `https://api.siliconflow.cn/v1` | 嵌入服务端点 |
| `EMBEDDING_API_KEY` | 空 | **未配置则记忆降级为 Noop，聊天不受影响** |
| `EMBEDDING_DIMS` | `1024` | bge-m3 维度。**换模型等于重建全表向量** |
| `MEMORY_SEARCH_ENABLED` | `true` | 记忆读路径开关 |
| `MEMORY_EXTRACT_ENABLED` | `true` | 记忆写路径开关 |
| `DEBUG` | `true` | 调试模式 |

> ⚠️ 嵌入维度是锁死的：`hnsw` / `ivfflat` 索引对 `vector` 类型上限 2000 维。换 embedding 模型必须重建全表向量，请提前定死。

## 开发者参考

| 层 | 选型 |
|---|---|
| 前端 | Vue 3 + Vite 6 + TypeScript，UI 组件仅用 Naive UI（按需引入） |
| 后端 | FastAPI + Python 3.11+ + SQLAlchemy 2.x（async）+ Pydantic v2 |
| 存储 | PostgreSQL 16 + pgvector、Redis 7 |
| 记忆 | 自托管 mem0（向量后端复用 pgvector） |
| 模型网关 | [new-api](https://github.com/Calcium-Ion/new-api)（OpenAI 兼容，已起好待用） |
| 迁移 / 测试 | Alembic、pytest + pytest-asyncio、Playwright |

> 前端组件预算是硬性约束：主界面常驻的 Naive UI 组件最多 2 个（`n-input` + `n-button`），浮层最多 5 个。消息列表和气泡全部手写，不使用组件库。

### 架构

核心对话逻辑与消息传输完全解耦，未来接入微信只需新增一个 Adapter，核心层零改动。

```
┌──────────────────────────────────────────────┐
│ ChatCoreService（核心层）                      │
│ LLM + 记忆 + 角色卡，不知道消息从哪来           │
│ handle_message(UnifiedMessage, api_key, ch)  │
└───────────────────┬──────────────────────────┘
                    │ 依赖 MessageChannel 接口
┌───────────────────┴──────────────────────────┐
│ MessageChannel：on_message +                  │
│ send_delta / send_done / send_error           │
└────────┬────────────────────────┬────────────┘
   ┌─────▼──────┐         ┌───────▼───────┐
   │ WebSocket  │         │ WeChat        │
   │ （已实现）  │         │ （预留骨架）   │
   └────────────┘         └───────────────┘
```

一次对话的链路：解析帧 → 载入角色卡 → 拉最近 20 条历史 → 落库用户消息 → 检索记忆注入 system prompt → LLM 流式生成（逐 token 下发）→ 落库助手消息 → `on_reply` 回调 → 异步投递记忆抽取。

两个值得注意的点：**流式收口在接口层**——核心层只调 `send_delta` / `send_done`，呈现差异由 Adapter 吸收（WebSocket 逐 token 推，微信则累积后一次性发送）；**`ChannelException`** 承载微信 48 小时窗口这类渠道限制，核心层识别后降级而非崩溃。身份映射 `IdentityService` 把外部 ID（微信 OpenID 等）转成内部 `user_id`，当前是单用户实现。

### WebSocket 协议

端点 `ws://127.0.0.1:8000/api/v1/ws/chat`。两侧契约由 Pydantic 判别联合定义（`backend/app/schemas/frames.py`），前端在 `frontend/src/api/frames.ts` 维护同构类型。

```jsonc
// 客户端 → 服务端
{ "type": "auth", "api_key": "sk-..." }   // 连接后必须发的第一帧
{ "type": "chat", "message": "你好", "character_id": "uuid", "conversation_id": "uuid" }
{ "type": "ping" }

// 服务端 → 客户端
{ "type": "delta", "text": "你" }
{ "type": "done", "message_id": "uuid", "conversation_id": "uuid", "usage": null }
{ "type": "error", "code": "llm_error", "message": "..." }   // message 已脱敏
```

密钥走 `auth` 帧而不是 URL query：浏览器 WebSocket API 无法设置自定义请求头，而 query 会被 access log 记录。

### REST API

前缀 `/api/v1`。

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/health` | 健康检查（含数据库连通性） |
| `GET` `POST` | `/characters` | 角色列表 / 新建 |
| `GET` `PUT` `DELETE` | `/characters/{id}` | 角色详情 / 更新 / 删除 |
| `POST` | `/characters/import` | 从 JSON 导入角色 |
| `GET` | `/memories` | 记忆列表（`character_id` 必填） |
| `DELETE` | `/memories/{id}` | 删除单条记忆 |
| `DELETE` | `/memories` | 清空全部记忆 |
| `GET` | `/conversations/messages` | 某角色会话的最近消息（`character_id` 可选，`limit` 默认 200 上限 500） |

## 项目结构

```
backend/
  app/
    api/v1/          REST + WS 路由
    core/            配置 / 日志脱敏 / messaging（三层架构 + 各渠道 Adapter）
    db/ models/     引擎、SQLAlchemy 模型
    schemas/         Pydantic 模型（含 WS 帧协议）
    services/       chat（核心层）/ character（角色卡→prompt）/ llm / memory（mem0 + Noop 降级）
  alembic/          数据库迁移
  tests/            53 个测试
frontend/
  src/
    components/     消息列表 / 气泡 / 输入框 / 设置抽屉 / 角色面板
    composables/    useChat.ts（流式渲染、历史恢复）
    api/            REST + WS 客户端
  e2e/              Playwright 验证脚本
scripts/dev.sh      一键启动后端 + 前端，并打印手机访问地址
screenshots/        各里程碑验证截图
```

## 测试

```bash
cd backend && uv run pytest -q     # 53 个测试
```

覆盖：WebSocket 端到端对话、核心层单测（不经过传输层）、上下文拼接不重复（含多轮回归）、会话持久化（同角色复用一条会话 / 角色间隔离 / 正序与 limit）、角色卡 CRUD 与导入、记忆服务与降级、三层架构（身份映射 / 渠道异常 / 微信签名校验）、日志密钥脱敏。

测试要求 PostgreSQL 已启动。`conftest.py` 会在读 `.env` 之前清空 `EMBEDDING_API_KEY`，避免触发真实 embedding 调用。

前端验证脚本（需先起前后端，密钥经 `COMPANION_API_KEY` 传入）：

```bash
cd frontend
npm run e2e:shot       # 各尺寸界面截图
npm run e2e:persist    # 持久化回归：发消息 → 刷新 → 记录仍在
```

## 说明

- 个人学习与自用项目，采用 BYOK 模式，不提供任何 API 密钥。**请勿将 `.env` 或密钥文件提交到版本库**（`.gitignore` 已排除）。
- 内容审核、限流、多租户等生产级能力尚未实现，请勿直接暴露到公网。
- 进度：M0 骨架与流式对话 ✅ / M1a 角色系统 ✅ / M1b 长期记忆 ✅ / M2 Live2D ❌ 已放弃 / M3 记忆管理面板与性能对齐 ⏳ / M4 内容审核、部署、微信接入 ⏳。
- 性能目标：首屏 LCP < 1.5s、TTI < 2s；输入到界面回显 < 50ms；1000 条消息滚动稳定 60fps；流式首字 < 1.5s；连续聊天 30 分钟堆内存增长 < 50MB。
