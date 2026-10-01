# AI 伴侣应用 · 技术方案文档

> 目标产品：类「爱语 AI 聊天」的 AI 伴侣应用
> 两大核心能力：**深度可定制的 AI 角色** · **永久记忆存储**
> 版本：v0.2（纯文本聊天；已放弃 Live2D，新增消息收发三层架构）

---

## 变更记录

- **v0.2（2026-10）**：**放弃 Live2D 渲染功能**，聚焦纯文本聊天；新增「消息收发三层架构」（MessageChannel / Adapter / ChatCoreService），预留微信接入接口。
- v0.1：初始方案（含 Live2D、语音等，后续均按实际演进调整）。

> 本文档中标记为「~~已放弃~~」的章节（Live2D、情绪/动作映射、语音）为历史内容，仅作留档，不再实施。

---

## 0. 决策摘要（TL;DR）

| 维度 | 选型 | 一句话理由 |
|---|---|---|
| 前端框架 | **Vue 3 + Vite + TypeScript** | 中文生态成熟、上手快、H5 移动端友好 |
| ~~Live2D 渲染~~ | ~~PixiJS + pixi-live2d-display~~ **已放弃** | 纯文本聊天，不渲染角色形象 |
| 后端框架 | **FastAPI + SQLAlchemy(async) + Pydantic v2** | 用户指定；原生 async、流式友好、自动 OpenAPI |
| 主数据库 | **PostgreSQL 16+** | 关系数据 + 事务 + JSONB 角色卡；向量能力由 pgvector 扩展提供 |
| 向量库 | **pgvector**（PostgreSQL 扩展） | 复用主库、少维护一个组件；规模上来再迁 Qdrant |
| 缓存 / 队列 / 实时 | **Redis** | 缓存、限流、发布订阅、流式背压 |
| 对象存储 | **MinIO / S3 兼容** | 头像、导出文件 |
| AI 模型接入 | **OpenAI 兼容协议 + new-api 网关** | 一套协议接任意厂商，密钥/配额/路由统一管理 |
| 记忆系统 | **mem0（自托管）** | 成熟稳定、生态全、原生支持 pgvector 后端与 OpenAI 兼容 LLM/embedding；经统一 `MemoryService` 抽象隔离 |
| 消息收发 | **三层架构**：MessageChannel / WebSocketAdapter·WeChatAdapter / ChatCoreService | 对话逻辑与传输渠道解耦，未来接微信零改动核心层 |
| 部署 | **Docker Compose → K8s** | 一条命令起全栈，后续可水平扩展 |

---

## 1. 需求分析

### 1.1 功能需求拆解

**核心 1：深度可定制的 AI 角色**

- 角色卡（Character Card）：人设、性格、背景故事、说话风格、示例对话（few-shot）、开场白、世界观、关系设定（与用户的关系）。
- 定制维度：语气/口头禅、记忆边界、敏感度/尺度、是否允许长短期记忆。
- 角色市场 / 导入导出：支持导入社区通行的角色卡格式（如 TavernAI / SillyTavern 的 PNG/JSON 卡、Character.AI 风格 JSON），便于生态迁移。
- 多角色：一个用户可持有/切换多个角色，每个角色拥有独立的记忆与人格。

~~**核心 2：Live2D 动态交互**~~（已放弃）

- ~~渲染 Live2D 模型、情绪/动作同步、点击互动等~~ —— 纯文本聊天，不渲染角色形象。

**核心 3：永久记忆存储**

- 短期记忆：当前会话上下文（窗口内）。
- 长期记忆：跨会话持久化的用户事实、偏好、约定、关系演进；按角色/用户隔离。
- 记忆检索：对话时按语义/关键词召回相关记忆注入 prompt。
- 记忆管理：用户可查看、编辑、删除被记住的内容（隐私透明）。

**周边功能（MVP 之后）**：语音（ASR 语音输入 / TTS 角色说话）、每日问候/主动触达（proactive）、角色分享、会员订阅、多语言、微信接入。

### 1.2 非功能需求

产品原则：**流畅、简洁、不打扰**。以下硬指标是最高优先级，架构选择须服从它们。

**A. 性能硬指标**（生产构建、本地测试）

| 指标 | 目标 |
|---|---|
| 首屏 LCP / TTI | < 1.5s / < 2s |
| 聊天输入到界面回显 | < 50ms |
| 消息列表 1000 条滚动 | 稳定 60fps，无长任务 > 50ms |
| 流式响应首字 | < 1.5s，逐字渲染不阻塞输入 |
| 连续聊天 30 分钟 | 堆内存增长 < 50MB |

**B. 界面简洁规则**

- 主界面常驻元素只保留：角色区、消息流、输入框、发送按钮、设置入口图标（定义见 C 节）。
- 单栏布局，移动优先，桌面最大宽度 720px 居中。
- 主色不超过 3 种 + 中性色；禁止堆叠渐变和阴影。
- 动画只用于状态反馈，时长 150–250ms，**必须可关闭**。
- 新功能默认隐藏，渐进披露，不增加主界面元素。
- 组件库：**仅允许 Naive UI**（Element Plus / Ant Design 禁止），定义、预算与硬性规则见下方 **C 节**。

**C. 主界面、浮层与组件预算**

仅允许 Naive UI，Element Plus / Ant Design 禁止。

**主界面**：应用启动后，用户不进行任何点击、悬停、滚动等交互，就常驻可见的区域。
- 包括：角色区、消息流、输入框、发送按钮、设置入口图标。
- 不包括：抽屉、弹窗、气泡、菜单、Toast、独立路由页面。

**浮层**：需要用户主动触发才出现，且覆盖或悬浮在主界面之上的临时 UI。
- 包括：`n-drawer`、`n-modal`、popover、tooltip、下拉菜单、通知。
- 浮层不计入「主界面常驻组件数」，但**计入全局组件库体积预算和性能预算**。

**组件使用预算**

| 区域 | Naive UI 组件预算 | 允许组件 |
|---|---|---|
| 主界面常驻 | ≤ 2 个 | `n-input`、`n-button` |
| 设置抽屉等浮层 | ≤ 5 个 | `n-drawer`、`n-switch`、`n-slider`、`n-select` |
| 全局打包体积 | Naive UI 相关 **< 50KB（gzip）** | 必须按需引入 |

**硬性规则**

- 主界面常驻 Naive UI 组件最多 2 个：`n-input`、`n-button`。
- 设置入口用 `n-button` → 主界面正好 `n-input` + `n-button`；设置入口自绘 SVG 图标 → 主界面只剩 `n-input` 一个。
- 消息列表、消息气泡**必须自己实现**，禁止使用组件库。
- **禁止把聊天、角色、消息流等核心功能藏进浮层。**
- 禁止使用 `n-data-table`、`n-form`、`n-modal`、`n-card`、`n-layout`。
- 所有 Naive UI 组件必须包裹在 `<n-config-provider>` 中，主题用 `darkTheme` 或自定义。
- 必须用 `unplugin-vue-components`（`NaiveUiResolver`）自动按需引入，**禁止全量引入**。

> **验收方式**：构建后跑 bundle 分析，确认 ①主界面常驻 Naive UI 组件数 ≤2；②浮层组件数 ≤5；③Naive UI 相关打包体积 < 50KB（gzip）；④未全量引入。若体积或 LCP 超标，**优先削减组件用量而非放宽指标**。
>
> 注：`n-modal` 出现在浮层的类型定义中（泛指这一类 UI），但本项目**禁用**，见硬性规则。

**D. 性能禁止项**

- 禁止把大型对象放入 Vue 深度响应式。
- 禁止每帧触发 Vue 组件重渲染。
- 禁止一次性渲染全部聊天记录（虚拟滚动 + 游标分页）。
- 禁止在主线程做大量 JSON 解析或 Base64 转换。

**E. 其他**

| 类别 | 要求 | 对架构的影响 |
|---|---|---|
| 并发 | 初期 1k–10k 在线 | FastAPI async + Redis 即可，无需过早微服务 |
| 隐私合规 | 用户与角色对话属敏感数据 | 全自托管、数据加密、记忆可删、脱敏日志 |
| 多模型 | 任意 OpenAI 兼容 API 可插拔 | LLM 统一抽象层 + new-api 网关 |
| 可移植 | Web 先行，可打包 App/桌面端 | 前后端分离 + PWA |
| 成本可控 | 自托管记忆降本 | mem0 本地化部署，无托管平台费用 |

> B/C/D 三节对架构有实质约束，不是 UI 细节：**「禁止一次性渲染全部记录」**直接决定了消息列表的虚拟滚动方案，须尽早落地，而非后期优化；**C 节的「消息列表、气泡必须自研」**则意味着这两块的性能优化空间完全由自己掌控，不能指望组件库兜底。
>
> C 节的「禁止把核心功能藏进浮层」还锁死了信息架构：**聊天、角色、消息流必须在主界面常驻可见**（对应主界面定义中的角色区、消息流、输入框、发送按钮、设置入口图标），不能做成抽屉里的二级页面。记忆管理、模型参数等二级功能则可以放进设置抽屉。这会影响路由与状态设计，需在 M0 阶段就确定。

### 1.3 关键难点

1. **角色一致性**：长对话中人格漂移 → 依赖强 system prompt + 结构化角色卡 + 长期记忆注入。
2. **记忆质量 vs 延迟/成本**：记忆抽取（LLM 二次调用）会放大延迟与 token 消耗 → 抽取改为异步后台任务。
3. **多渠道接入**：微信/WS 消息格式差异 → 三层架构（UnifiedMessage 统一格式 + Adapter 隔离）。
4. **多租户隔离**：用户、角色、记忆三层隔离，避免串味/越权。

---

## 2. 总体架构

```
┌───────────────────────────── 客户端（Web SPA / PWA）─────────────────────────────┐
│  Vue 3 UI（聊天流 / 角色编辑 / 记忆管理 / 设置）                                   │
│      │                                                                            │
│  WebSocket 客户端（对话流）/ REST 客户端（角色/记忆/登录）                          │
└──────────────────────────────┬───────────────────────────────────────────────────┘
                               │ HTTPS / WSS
┌──────────────────────────────▼───────────────────────────────────────────────────┐
│                          FastAPI 后端（单体优先，模块化）                          │
│  ┌──────────┬──────────┬─────────────────────────────┬──────────┐                │
│  │ Auth/用户 │ 角色管理 │  消息收发层（三层）           │ 资产/上传 │                │
│  │ (JWT)    │ (Character)│ MessageChannel 接口        │(MinIO)   │                │
│  │          │          │  ├─ WebSocketAdapter(已实现) │          │                │
│  │          │          │  └─ WeChatAdapter(预留)      │          │                │
│  └──────────┴──────────┴──────────┬───────────────────┴──────────┘                │
│                                    │                                              │
│                          ChatCoreService（核心层）                                 │
│                          只处理 LLM + 记忆 + 角色卡                                 │
│                              │                                                     │
│  ┌───────────────────────────▼─────────────────────────────────────┐              │
│  │   LLM 接入层(抽象) + MemoryService(mem0 自托管)                 │              │
│  └───────┬───────────────────────────────────────┬────────────────┘              │
│          │                                       │                                │
│  ┌───────▼──────────────┐            ┌───────────▼───────────┐                    │
│  │ API 网关(new-api)     │            │ 向量检索 → 主库(pgvector)│                    │
│  └───────┬──────────────┘            └───────────────────────┘                    │
│          │                                                                         │
│          ▼  任意 OpenAI 兼容上游（DeepSeek / Qwen / GLM / Moonshot / Claude / 本地 vLLM）│
└───────────────────────────────────────────────────────────────────────────────────┘
                               │
      ┌────────────────────────┼────────────────────────┐
      │                        │                        │
┌─────▼──────────┐      ┌──────▼──────┐          ┌──────▼──────┐
│ PostgreSQL     │      │    Redis    │          │  MinIO/S3   │
│ 业务数据        │      │ 缓存/限流/Pub │          │ 资源文件     │
│ + pgvector 向量 │      └─────────────┘          └─────────────┘
└────────────────┘
```

**设计原则**：单体优先（模块化 monolith），核心链路（对话 + 记忆）先跑通，再按负载拆分。所有外部能力（LLM、记忆、存储）都通过接口抽象，便于替换。

---

## 3. 技术栈选型与理由

### 3.1 前端框架 —— Vue 3 + Vite + TypeScript + Pinia

**理由**

- 中文社区与文档生态强，对中文向产品开发效率高、资料易查。
- 移动端 H5 优先，后续可用 **Capacitor** 打包 iOS/Android，或 **Tauri** 打包桌面端，同一套代码复用。
- 组合式 API 状态管理适合「多角色 + 实时聊天流」这类复杂交互。

**UI 层约束（重要）**：组件库**仅允许 Naive UI**（Element Plus / Ant Design 禁止），且受 1.2 节 C 节约束。界面遵循「单栏、移动优先、桌面最大宽度 720px 居中、主色 ≤3 种 + 中性色、动画仅用于状态反馈且时长 150–250ms 可关闭」的简洁规则。

具体落到选型上：

| 区域 | 实现方式 | 预算 |
|---|---|---|
| 消息列表 / 消息气泡 | **完全自研**（原生 CSS / UnoCSS） | 禁止用组件库 |
| 主界面常驻（输入框、发送按钮、设置入口） | Naive UI：`n-input`、`n-button` | ≤ 2 个 |
| 设置抽屉等浮层 | Naive UI：`n-drawer`、`n-switch`、`n-slider`、`n-select` | ≤ 5 个 |

引入方式为 `unplugin-vue-components` + `NaiveUiResolver` 自动按需引入，配合 `<n-config-provider :theme="darkTheme">` 统一主题，Naive UI 相关打包体积控制在 **< 50KB（gzip）**。

> 这套约束与「流畅、简洁、不打扰」的产品原则一致：**核心交互路径（聊天、角色、消息流）全部自研**，组件库只用于边缘的输入控件与设置面板——既避免重型库拖累首屏 LCP，也保证了消息列表 60fps 滚动这类指标完全由自己掌控。

**备选**：React 18 + Zustand；团队熟悉度优先。

### 3.2 ~~Live2D 渲染~~（已放弃）

> 纯文本聊天，不渲染角色形象。原 PixiJS + pixi-live2d-display 选型作废，相关代码已清理。

### 3.3 后端 —— FastAPI + async SQLAlchemy + Pydantic v2（用户指定）

**理由**

- 用户已指定 FastAPI；原生 **async/await** 对 WebSocket 流式对话、长连接、并发 I/O 天然友好。
- `StreamingResponse` / `WebSocket` 原生支持 SSE 与 WS，做文本流式对话很直接。
- Pydantic v2 用于角色卡、记忆、配置的强类型校验，自动生成 OpenAPI 文档。

**配套**：Alembic（迁移）、SQLAlchemy 2.0 async + asyncpg、Uvicorn/Gunicorn、结构遵循 FastAPI 官方「大应用」目录风格。

### 3.4 数据库

| 存储 | 选型 | 理由 |
|---|---|---|
| 主库（关系 + 向量） | **PostgreSQL 16 + pgvector** | 事务、JSONB 存角色卡、全文检索、社区成熟；**向量能力以扩展形式内置**，省掉一个独立组件 |
| 向量库 | **pgvector**（默认） | 作为 PostgreSQL 扩展直接启用，**不额外维护独立组件**；向量与业务数据同库，可按 `user_id/character_id` 直接 JOIN 与事务回滚。mem0 原生支持 pgvector 后端。<br>**升级路径**：单表向量数达到千万级、或需要高级过滤/量化索引时再迁 Qdrant——迁移成本低，因为向量、embedding 模型、metadata 三者都已在库中，只需批量导出重灌；Qdrant 可作为「第二阶段」选型而非初始依赖 |
| 缓存/队列 | **Redis** | 会话缓存、限流（滑动窗口）、Pub/Sub 推送、短任务队列；后续 Celery/ARQ broker 复用 |
| 对象存储 | **MinIO（S3 兼容）** | 头像、导出文件；可平滑迁云（OSS/COS） |

**pgvector 落地注意（三条易踩的坑）**

1. **维度上限**：`hnsw`/`ivfflat` 索引对 `vector` 类型上限为 2000 维。选 embedding 时注意——`bge-m3`(1024)、`text-embedding-3-small`(1536) 可直接用；`text-embedding-3-large`(3072) 需降维到 1024/1536，或改用 `halfvec` 类型建索引。**换 embedding 模型等于重建全表向量**，务必在 M1 阶段就把模型定死并记入配置。
2. **索引与隔离**：向量表单独放 `memory` schema，建 HNSW 索引（比 IVFFlat 召回更稳、无需预先训练），并绑定 `user_id/character_id` 过滤条件走复合索引，避免全表扫描。
3. **容量与备份**：向量表是主库中增长最快的表，纳入 pg_dump/监控范围；数据量大时按 `character_id` 分区或冷热分离（老记忆归档）。

### 3.5 AI 模型接入 —— OpenAI 兼容协议 + 网关（核心要求）

**架构要点（满足「接入任何 OpenAI 兼容 API」）**

1. **统一协议**：后端只依赖 OpenAI 兼容的 `/v1/chat/completions`（含 `stream=true`），使用官方 `openai` Python SDK，`base_url`、`api_key`、`model` 全部来自配置（DB 或环境变量），代码中**零硬编码厂商**。
2. **API 网关：new-api（唯一选型）**。部署 [new-api](https://github.com/Calcium-Ion/new-api)，把 DeepSeek、Qwen（通义）、GLM（智谱）、Moonshot（Kimi）、Claude、Gemini、本地 vLLM/Ollama 等**统一成 OpenAI 兼容出口**，集中管理密钥、配额、计费、渠道负载均衡与故障转移。后端只对网关一个 `base_url` 说话。

   **为什么是 new-api 而不是 one-api**：new-api 是 one-api 的活跃 fork，用法与数据可平滑迁移，但补齐了本项目真正需要的能力——
   - **多协议互转**：能把 Claude Messages、Gemini 等**非 OpenAI 原生协议**在上游侧转成 OpenAI 格式。这是"零改动接入任意模型"能成立的关键：后端只认 OpenAI 协议，异构性全部由网关吸收。
   - **渠道类型更全**：除主流文本模型外，还覆盖 Rerank、多模态等渠道，后续加图片等能力时不用再换网关。
   - **维护更活跃**：one-api 更新节奏放缓，new-api 迭代更快、issue 响应更好。

   > 具体渠道清单与功能以 [new-api 仓库 README](https://github.com/Calcium-Ion/new-api) 当前版本为准。
3. **模型路由**：角色卡可指定 `provider` / `model`；网关按 `model` 前缀路由到对应上游（如 `deepseek-chat` → DeepSeek 渠道）。支持 A/B 与降级。
4. **LLM 抽象层**：后端封装 `LLMProvider` 接口（`chat_stream(messages, tools, ...)`），便于未来加供应商特有参数或替换 SDK。

**角色扮演模型建议（可插拔，仅参考）**：DeepSeek-V3/R1、Qwen 系列、GLM-4、Moonshot，长上下文 + 指令遵循优先；本地可用 vLLM/Ollama 部署 Qwen 做隐私/降本场景。

### 3.6 记忆系统 —— mem0（自托管，唯一选型）

**选型结论**：使用 mem0 自托管（`mem0ai/mem0`），不引入第二套记忆框架。

| 维度 | 说明 |
|---|---|
| 存储后端 | **pgvector**（与主库同实例）；mem0 亦支持 Qdrant / Chroma 等 |
| 图记忆（可选） | Neo4j，用于表达「用户-角色关系进展」这类关系型记忆 |
| 检索方式 | 向量语义检索 + 可选图检索 |
| LLM 接入 | 支持自定义 `base_url`，复用 new-api 网关出口 |
| embedding | 需要（可走 OpenAI 兼容 embedding 接口，或本地 `bge-m3`） |
| 隐私 | 全自托管，数据不出境 |
| 成本 | 抽取 + embedding 涉及多次 LLM 调用，是主要成本项 |

**选择理由**：生产级稳定、API 成熟、社区与排障资料多；图记忆对「关系型伴侣记忆」表达力强；原生支持 pgvector 后端，与主库方案契合；经 LiteLLM 支持自定义 `base_url`，能直接复用 new-api 出口。

- **关键工程决策**：后端定义 `MemoryService` 抽象接口（**async 接口**：`await add / search / list / delete`），mem0 是其唯一实现。抽象层的价值不在于「预留第二个记忆框架」，而在于**隔离 mem0 的版本升级与 API 变更**——记忆层是最容易随上游迭代而返工的部分，上层调用方不应感知底层细节。

**记忆分层设计（自建薄层，包在 mem0 之上）**

```
记忆分层
 ├─ L0 会话上下文：当前对话最近 N 轮（Redis / 内存，不进记忆库）
 ├─ L1 短期：mem0 默认条目，语义检索 + 时间衰减
 ├─ L2 长期事实：显式「记住」的用户事实/偏好/约定（高优先级，可编辑删除）
 ├─ L3 关系/状态：用户-角色关系、称呼、进度（可走 Neo4j 图记忆）
 └─ 用户可见面板：全部记忆可查/改/删（隐私透明，满足合规）
```

- 抽取时机：每轮对话**异步**触发（后台任务），不阻塞首字；`add` 调用放 Redis 队列由 worker 消费，避免拖慢流式响应。
- 注入时机：每轮对话前 `search` top-k，拼进 system prompt 的「你记得的关于用户的事」区块。
- 隐私：记忆按 `(user_id, character_id)` 强隔离；提供删除接口并同步清理向量库与历史库。

**异步调用约束（必须遵守，否则会拖垮整个服务）**

FastAPI 是异步框架，请求处理跑在**同一个事件循环**上。mem0 的同步 `Memory` 类内部是阻塞 I/O（调 LLM 做抽取、调 embedding 服务、读写向量库），在 `async def` 里直接调用会**阻塞整个事件循环**——症状不是"这个请求慢"，而是**所有并发请求一起变慢甚至超时**，且 CPU 占用不高、极难排查。

因此：**请求路径上一律使用 `AsyncMemory`，禁止使用同步 `Memory`。**

```python
from mem0 import AsyncMemory
from mem0.configs.base import MemoryConfig

memory = AsyncMemory(config=MemoryConfig(...))          # 进程内自托管实现

await memory.add(messages, user_id=uid, agent_id=char_id)
hits = await memory.search(query, filters={"user_id": uid, "agent_id": char_id})
```

配套要求：

1. **单例复用**：`AsyncMemory` 在 FastAPI 的 `lifespan` 启动钩子里创建一次，挂到 `app.state`，**不要每个请求 new 一个**——初始化会建连接、加载配置，开销大。
2. **不要混淆 `AsyncMemoryClient`**：`AsyncMemory` = 自托管、进程内（本项目用这个）；`AsyncMemoryClient` = 连 mem0 托管平台。两者 API 相似但语义完全不同。
3. **兜底而非首选**：若某条路径确实只有同步实现，用 `await asyncio.to_thread(...)` 包一层，别写裸调用。
4. **`MemoryService` 抽象层应为 async 接口**：`async def add/search/list/delete`。这样 mem0 的 async 实现、以及未来同步实现的 `to_thread` 包装都能挂在同一契约下，调用方无感知。
5. **worker 里不必强行 async**：ARQ/Celery 的 worker 进程没有事件循环约束，用同步 `Memory` 反而更简单直接。

> 注意区分两件事：`AsyncMemory` 解决的是「**不阻塞事件循环**」，不解决「**慢**」。记忆抽取本身就是多次 LLM 调用（数百毫秒到数秒），所以**写路径仍必须丢给后台 worker**；请求路径上只保留 `search` 这一件事。

### 3.7 消息收发 —— 三层架构（核心设计）

对话服务与消息传输解耦，未来接微信/QQ 只需新增 Adapter，核心逻辑零改动。

```
ChatCoreService（核心层）── 只处理 LLM + 记忆 + 角色卡，不感知渠道
        │ 依赖 MessageChannel 接口
MessageChannel（接口层）── 统一收发标准：on_message + send_delta/done/error
        │
WebSocketAdapter（已实现）│ WeChatAdapter（预留骨架）
```

**UnifiedMessage（内部统一消息）**：微信/WS/QQ 外部格式完全不同，核心层只认这一种：

```python
@dataclass
class UnifiedMessage:
    user_id: str          # 统一用户 ID（跨平台核心）
    session_id: str|None  # 会话 ID（= conversation_id，首轮 None）
    content: str
    timestamp: float
    channel_type: str     # 'ws' | 'wechat' | 'qq'
    character_id: str|None = None  # 角色（对话参数，非渠道概念）
```

**关键约定**：

- **流式**：核心层统一用 `send_delta/send_done` 输出；WS 逐帧推，微信累积后发完整消息，呈现差异由 Adapter 吸收。
- **BYOK 密钥**：`api_key` 不进 UnifiedMessage，由 Adapter 解析后传给核心层（WS 从 auth 帧拿，微信从服务端配置拿）。

**现有 WS 帧协议**（仅 WebSocketAdapter 使用）：`{ type: "delta"|"done"|"error" }`，客户端发 `auth`/`chat`/`ping`。

### 3.8 任务队列 —— ARQ / Celery（+ Redis）

- 记忆抽取、向量写入、问候推送等**慢任务**异步化。
- **队列存在的原因之一**：记忆抽取是多次 LLM 调用，即便用 `AsyncMemory` 也只是不阻塞事件循环、并不变快。请求路径只做 `search`，`add` 一律投队列。
- worker 进程无事件循环约束，此处的 mem0 调用**用同步 `Memory` 即可**，无需强行 async。
- 初期可用 FastAPI `BackgroundTasks` 起步（注意：它仍在同一进程内，重任务会挤占 API 进程资源，只适合极轻场景），量上来再上 **ARQ**（轻量、async 原生、Redis）或 Celery（独立进程）。

### 3.9 部署与工程

- **Docker Compose**（一键起：FastAPI + PostgreSQL(**pgvector 镜像**) + Redis + MinIO + 网关）→ 规模扩大后迁 **K8s**。
  - PostgreSQL 直接用官方扩展镜像 `pgvector/pgvector:pg16`，或在自建镜像里加装 `pgvector` 扩展；建库后执行一次 `CREATE EXTENSION vector;` 即可，无需额外服务。
- **反向代理**：Nginx/Caddy（TLS、WSS 升级、静态资源）。
- **可观测**：OpenTelemetry + Prometheus/Grafana，Sentinel/日志脱敏。
- **安全**：JWT 鉴权、RBAC、数据加密、接口限流、内容审核（可选，合规）。

---

## 4. 角色系统设计（深度定制）

### 4.1 角色卡 Schema（核心字段示意）

```jsonc
{
  "id": "char_xxx",
  "owner_id": "user_xxx",
  "visibility": "private | public",        // 是否上架角色市场
  "name": "角色名",
  "avatar": "s3://...",
  // "live2d": { ... }  ← 已删除（放弃 Live2D）
  "persona": {                               // 人格
    "identity": "身份/背景故事",
    "personality": "性格标签与描述",
    "speaking_style": "说话风格/口头禅/语气",
    "worldview": "世界观设定",
    "relationship": "与用户的关系设定"
  },
  "examples": [ {"user": "...", "assistant": "..."} ],  // few-shot
  "greeting": "开场白",
  "llm": { "provider": "gateway", "model": "deepseek-chat", "temperature": 0.8 },
  "memory": { "enabled": true, "priority": ["facts", "relationship"], "top_k": 8 },
  "safety": { "nsfw_level": "...", "allowed_topics": [] }
}
```

- 导出/导入：支持 **Character Card 通用格式**（PNG 内嵌 JSON / 纯 JSON），兼容 SillyTavern 等生态，降低冷启动成本。
- 定制入口：Web 端可视化「角色工坊」+ 支持直接粘贴/导入 JSON。

---

## 5. 关键链路设计

### 5.1 对话链路（一次用户发言）

```
Adapter 收到外部消息（WS 帧 / 微信回调）
  → 转成 UnifiedMessage，交给 ChatCoreService
  → 载入角色卡 + 短期上下文
  → await MemoryService.search(...)            // AsyncMemory，不阻塞事件循环
  → 组装 system prompt（角色卡 + 记忆区块）
  → LLMProvider.chat_stream()                  // OpenAI 兼容、stream=true
       ├─ 逐 token 经 channel.send_delta 输出（type: delta）
       └─ 流结束 → channel.send_done + 本轮完整回复
  → 落库 messages（PostgreSQL）
  → 投递队列：MemoryService.add(本轮对话)      // fire-and-forget，请求路径不等待
```

### 5.2 ~~情绪 → Live2D 映射~~（已放弃）

- ~~LLM 结构化输出情绪标签 → 映射到 Live2D 表情/动作组~~ —— 纯文本聊天，不做情绪驱动形象。

### 5.3 永久记忆链路

- **写**：对话轮次结束后，**投递队列**，由 worker 调 `MemoryService.add()`（mem0 抽取要点 → 写入 pgvector）。worker 内可用同步 `Memory`。
- **读**：每轮对话前 `await MemoryService.search(top_k)` 注入 prompt（用 `AsyncMemory`，走请求路径，必须非阻塞）。
- **管理**：`GET /memories?character_id=` 列表、`DELETE /memories/{id}` 删除（同步清理底层存储）、`PATCH` 编辑。

---

## 6. 数据模型（关系库，简化）

```
users(id, email, password_hash, nickname, created_at, settings jsonb)
characters(id, owner_id, visibility, name, avatar_url, card jsonb,
           created_at, updated_at)          -- live2d 字段已删除
conversations(id, user_id, character_id, title, created_at, last_message_at)
messages(id, conversation_id, role, content, tokens_used,
         created_at)                       -- 分区/归档策略按时间；无 emotion 字段
memories(id, user_id, character_id, memory_id, content, priority, source,
         created_at)                       -- 与底层 mem0 存储的映射索引
```

> 记忆的**原始数据**存 mem0 的内部存储（pgvector 表），PostgreSQL 存**索引与用户可见元数据**，两者可对账、可重建。
>
> 注意：采用 pgvector 后，向量表与业务表在**同一个 PostgreSQL 实例**内。建议为向量表单独建 schema（如 `memory`）并独立配置索引与维护窗口，避免向量索引膨胀影响业务查询；容量规划时把向量表纳入主库监控。

---

## 7. API 概要（FastAPI，前缀 `/api/v1`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/auth/register` `/auth/login` | 注册登录（JWT） |
| GET/POST | `/characters` | 角色列表 / 创建 |
| GET/PUT/DELETE | `/characters/{id}` | 角色详情 / 更新 / 删除 |
| POST | `/characters/import` | 导入角色卡（JSON/PNG） |
| POST | `/conversations` | 新建会话 |
| GET | `/conversations/{id}/messages` | 历史消息（游标分页） |
| WS | `/ws/chat` | 对话流（delta/done/error） |
| GET/POST | `/memories` | 记忆查询/管理（按角色过滤） |
| DELETE | `/memories/{id}` | 删除记忆 / 清空全部 |
| POST | `/uploads` | 资源上传（头像） |

---

## 8. 目录结构规划（后端 + 前端）

```
chat-companion/
├─ backend/
│  ├─ app/
│  │  ├─ main.py                 # FastAPI 入口 + lifespan（core 单例）
│  │  ├─ core/
│  │  │  ├─ config.py            # 配置
│  │  │  ├─ logging.py           # 日志脱敏
│  │  │  └─ messaging/           # ★ 消息收发层
│  │  │     ├─ types.py          #   UnifiedMessage
│  │  │     ├─ channel.py        #   MessageChannel 接口
│  │  │     └─ adapters/         #   WebSocketAdapter / WeChatAdapter
│  │  ├─ models/                 # SQLAlchemy 模型
│  │  ├─ schemas/                # Pydantic
│  │  ├─ api/v1/                 # 路由（characters/chat/memories）
│  │  ├─ services/
│  │  │  ├─ chat/                # ★ ChatCoreService（核心对话层）
│  │  │  ├─ llm/                 # LLMProvider 抽象（openai 兼容）
│  │  │  ├─ memory/              # MemoryService 抽象 + mem0 实现
│  │  │  └─ character/           # 角色卡 → system prompt
│  │  └─ db/                     # session、迁移
│  ├─ alembic/                   # 迁移
│  ├─ tests/
│  └─ pyproject.toml / Dockerfile
├─ frontend/
│  ├─ src/
│  │  ├─ views/                  # 聊天页 / 角色工坊 / 记忆管理 / 设置
│  │  ├─ components/             # MessageList / MessageBubble / ChatInput
│  │  ├─ composables/            # useChat
│  │  └─ api/                    # REST + WS 客户端
│  └─ vite.config.ts
├─ docker-compose.yml            # 全栈编排
└─ docs/
```

---

## 9. 开发路线图（里程碑）

| 阶段 | 目标 | 产出 |
|---|---|---|
| M0（1–2 周） | ✅ 骨架 + 最小对话闭环 | FastAPI + DB + 网关接一个模型，REST/WS 流式对话 |
| M1（2–4 周） | ✅ 角色系统 + 记忆 | 角色卡 CRUD/导入；mem0 接入，记忆读写注入跑通 |
| ~~M2~~ | ~~Live2D 集成~~ **已放弃** | ~~PixiJS 渲染、情绪→表情/动作、口型同步~~ |
| M3（2 周） | 记忆管理面板 + 性能达标 | 记忆可视化增删改；对齐 1.2 节全部性能硬指标 |
| M4（持续） | 打磨 + 合规 + 部署 + 微信接入 | 角色市场、内容审核、压测、上云；实现 WeChatAdapter |

---

## 10. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| mem0 上游 API 变更 / 版本升级 | 记忆层返工 | 统一 `MemoryService` 抽象隔离；锁定 mem0 版本，升级走独立验证 |
| 记忆抽取放大延迟与成本 | 首字慢、贵 | 异步后台抽取 + 抽样（非每轮）+ 本地小模型做抽取 |
| 同步阻塞调用混入 async 路径 | 事件循环被卡死，全站并发雪崩 | 记忆层强制 `AsyncMemory`；`MemoryService` 定义为 async 接口；code review 禁止 `async def` 内裸调同步 I/O |
| 角色人格漂移 | 体验崩塌 | 强角色卡 + few-shot + 记忆注入 + 定期「人格回归」评估 |
| pgvector 与业务库同实例，向量膨胀拖慢主库 | 业务查询变慢 | 向量表独立 schema + HNSW 索引 + 独立维护窗口；预留「导出→灌 Qdrant」的迁移脚本 |
| 隐私/合规（敏感对话） | 法律风险 | 全自托管、数据加密、记忆可删、脱敏日志、可选内容审核 |
| 单点网关故障 | 全站不可用 | 网关多实例 + 多上游渠道故障转移 |

---

## 11. 成本估算（自托管，初期）

| 项 | 估算 | 说明 |
|---|---|---|
| 云主机 | 2–4 核 8G × 1–2 台 | FastAPI + PostgreSQL(pgvector) + Redis，省去独立向量库的机器与运维 |
| 模型 API | 按 token 计费 | 网关统一配额；可选本地 vLLM 降本 |
| embedding | 本地 `bge-m3` 或 OpenAI 兼容 embedding 接口 | mem0 必需，是长期运行的主要成本项之一 |
| 存储/流量 | 低 | 头像/模型资源走 CDN |

---

## 12. 参考链接（来源）

- mem0：https://github.com/mem0ai/mem0 ｜ 自托管配置：https://docs.mem0.ai/open-source/configuration ｜ LLM 配置：https://docs.mem0.ai/components/llms/config ｜ Embedder：https://docs.mem0.ai/components/embedders/config ｜ **异步接口 AsyncMemory**：https://docs.mem0.ai/open-source/features/async-memory
- new-api（网关）：https://github.com/Calcium-Ion/new-api
