# anime-chat

A text-based chat app with deeply customizable AI characters and permanent memory.

The design goal comes down to three words: **fluid, minimal, unobtrusive**. The main screen keeps only a character area, message stream, input box, send button, and a settings icon — everything else is progressively disclosed.

> 中文版：[README.md](README.md)

---

## Table of Contents

- [Status](#status)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [WebSocket Protocol](#websocket-protocol)
- [REST API](#rest-api)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Roadmap](#roadmap)
- [Notes](#notes)

---

## Status

| Milestone | Scope | Status |
|---|---|---|
| M0 | Skeleton + minimal streaming chat loop | ✅ |
| M1a | Character system (card CRUD / import) | ✅ |
| M1b | Long-term memory (mem0 + pgvector) | ✅ |
| ~~M2~~ | ~~Live2D rendering~~ | ❌ Abandoned |
| M3 | Memory management panel + performance targets | ⏳ |
| M4 | Content moderation / deployment / WeChat integration | ⏳ |

**Live2D was dropped.** This project is text-only; all rendering pipeline and emotion-mapping code has been removed. The messaging layer for a future WeChat integration is already stubbed out (see [Architecture](#architecture)).

---

## Features

### Deeply customizable AI characters

A character card (`CharacterCard`) is a JSONB structure containing:

- **Persona** — identity, personality, speaking style, worldview, relationship with the user
- **Example dialogues** — few-shot turns that anchor tone
- **Greeting** — first message when a session starts
- **Model params** — each character can pin its own model and `temperature`
- **Memory params** — independent toggle and recall count `top_k`

Cards can be created, edited, deleted, or imported from JSON via the REST API.

### Permanent memory

Built on self-hosted [mem0](https://github.com/mem0ai/mem0), with vectors stored in PostgreSQL's `pgvector` extension — no separate vector database to maintain.

- **Write path** — after each turn, the user message + assistant reply are dispatched asynchronously for memory extraction (`fire-and-forget`, never blocks the reply)
- **Read path** — before each new turn, the user message is used for semantic search and recalled memories are appended to the end of the system prompt (higher recency weight)
- **Graceful degradation** — search times out at 1.5s and any exception degrades to empty; a dead embedding service never breaks chat
- **Token budget** — each memory truncated to 200 chars, 600 chars total injected
- **Chinese extraction** — `memory_custom_instructions` forces memories to be recorded in Simplified Chinese

Memories can be viewed and cleared from the settings drawer.

### Bring Your Own Key (BYOK)

API keys live **only in browser localStorage** and are sent in the WebSocket `auth` frame. The server holds them in connection memory only — **never persisted, never logged** (redaction lives in `backend/app/core/logging.py`).

This means you can point it at any OpenAI-compatible API — DeepSeek, OpenAI, SiliconFlow, local Ollama — by changing only the base URL and model name.

---

## Architecture

### Three-layer messaging

Core conversation logic is fully decoupled from transport. Adding WeChat later means adding one Adapter with zero changes to the core.

```
┌─────────────────────────────────────────────────────┐
│ ChatCoreService (core layer)                         │
│ LLM + memory + character cards. Knows nothing about  │
│ where the message came from.                         │
│ handle_message(UnifiedMessage, api_key, channel)     │
└────────────────────┬────────────────────────────────┘
                     │ depends on MessageChannel interface
┌────────────────────┴────────────────────────────────┐
│ MessageChannel (interface layer)                     │
│ on_message + send_delta / send_done / send_error      │
└────────────┬──────────────────────┬─────────────────┘
             │                      │
  ┌──────────▼──────────┐  ┌───────▼──────────┐
  │ WebSocketAdapter     │  │ WeChatAdapter     │
  │ (implemented)        │  │ (stub only)       │
  └─────────────────────┘  └───────────────────┘
```

Key design decisions:

- **`UnifiedMessage`** — the internal, channel-agnostic message shape carrying `user_id` / `session_id` / `content` / `channel_type` / `character_id`
- **Streaming absorbed at the interface layer** — the core only ever calls `send_delta` / `send_done`; presentation differences belong to the Adapter. WebSocket pushes token by token, WeChat would accumulate and send once
- **Async result callback** `on_reply(handler)` — after finishing a message, the core hands the complete reply to every listener, which is how a channel like WeChat gets full text for async push
- **Identity mapping** `IdentityService` — external IDs (WeChat OpenID, etc.) map to an internal `user_id`; the core only knows internal IDs. Currently single-user, swappable for a DB-backed implementation
- **`ChannelException`** — WeChat's 48-hour window limit and 5-second timeouts are raised as this type; the core recognizes it and degrades instead of crashing

### Data flow of one conversation

```
User input
  └─> WebSocketAdapter parses the frame into a UnifiedMessage
        └─> ChatCoreService.handle_message
              ├─ 1. Load character card (optional)
              ├─ 2. Fetch conversation history (last 20 messages)
              ├─ 3. Persist the user message
              ├─ 4. Retrieve memories and inject into the system prompt
              ├─ 5. Stream from the LLM → channel.send_delta per token
              ├─ 6. Persist the assistant message → channel.send_done
              ├─ 7. Fire on_reply callbacks with the complete result
              └─ 8. Dispatch memory extraction asynchronously
```

---

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | Vue 3 + Vite 6 + TypeScript; Naive UI only, auto-imported via `unplugin-vue-components` |
| Backend | FastAPI + Python 3.11+ + SQLAlchemy 2.x (async) + Pydantic v2 |
| Database | PostgreSQL 16 + pgvector |
| Cache/Queue | Redis 7 |
| Model gateway | [new-api](https://github.com/Calcium-Ion/new-api) (OpenAI-compatible; provisioned in M0, not yet on the critical path) |
| Memory | Self-hosted mem0 (vector backend reuses pgvector) |
| Migrations | Alembic |
| Testing | pytest + pytest-asyncio |
| Frontend E2E | Playwright |

**The frontend component budget is a hard constraint**: at most 2 resident Naive UI components on the main screen (`n-input` + `n-button`), at most 5 in overlays, and under 50KB gzip for the whole library. The message list and bubbles are hand-written — no component library.

---

## Getting Started

### Prerequisites

- **Docker Desktop** (for PostgreSQL / Redis / new-api)
- **Python 3.11+** with [uv](https://github.com/astral-sh/uv)
- **Node.js 18+**

### 1. Start infrastructure

```bash
docker compose up -d
```

Brings up three containers: `companion-postgres` (5432, with pgvector), `companion-redis` (6379), `companion-new-api` (3000).

> `docker-compose.yml` pins `name: companion` because the checkout directory has a non-ASCII name, which Compose can't use as a project name.

### 2. Start the backend

```bash
cd backend

# Install dependencies (uv creates .venv automatically)
uv sync

# Configure environment
cp ../.env.example .env
# Edit .env, set LLM_API_KEY (local fallback only) and EMBEDDING_API_KEY

# Run migrations
uv run alembic upgrade head

# Start the server
uv run uvicorn app.main:app --reload --port 8000
```

Health check: <http://127.0.0.1:8000/api/v1/health>

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173> and enter your API key in the settings drawer to start chatting.

The dev server proxies `/api` (including WebSockets) to `http://127.0.0.1:8000`.

---

## Configuration

Settings are read from environment variables or `backend/.env` (pydantic-settings).

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/companion` | Database DSN |
| `LLM_BASE_URL` | `https://api.deepseek.com` | OpenAI-compatible endpoint |
| `LLM_MODEL` | `deepseek-chat` | Default model |
| `LLM_API_KEY` | empty | Local fallback; normally BYOK. **Also used for memory extraction** (the mem0 singleton can't take a per-request key) |
| `EMBEDDING_PROVIDER` | `openai` | `openai` (compatible) or `ollama` |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | Embedding model |
| `EMBEDDING_BASE_URL` | `https://api.siliconflow.cn/v1` | Embedding endpoint |
| `EMBEDDING_API_KEY` | empty | **If unset, memory degrades to a Noop service; chat still works** |
| `EMBEDDING_DIMS` | `1024` | bge-m3 dimensions. **Changing models means rebuilding every vector** |
| `MEMORY_SEARCH_ENABLED` | `true` | Memory read path toggle |
| `MEMORY_EXTRACT_ENABLED` | `true` | Memory write path toggle |
| `DEBUG` | `true` | Debug mode |

> ⚠️ **Embedding dimensions are locked in**: `hnsw` / `ivfflat` indexes cap `vector` at 2000 dimensions. Switching embedding models requires rebuilding all vectors — decide before deploying.

---

## WebSocket Protocol

Endpoint: `ws://127.0.0.1:8000/api/v1/ws/chat`

### Client → Server

```jsonc
// Must be the first frame after connecting; carries the key
{ "type": "auth", "api_key": "sk-..." }

// Start a chat turn
{ "type": "chat", "message": "hello", "character_id": "uuid", "conversation_id": "uuid" }

// Keepalive
{ "type": "ping" }
```

### Server → Client

```jsonc
// Streaming delta
{ "type": "delta", "text": "he" }

// Turn finished
{ "type": "done", "message_id": "uuid", "conversation_id": "uuid", "usage": null }

// Error (message is already redacted)
{ "type": "error", "code": "llm_error", "message": "..." }
```

Both sides share a Pydantic discriminated union contract (`backend/app/schemas/frames.py`); the frontend mirrors it in `frontend/src/api/frames.ts`.

### Why does the key travel in an `auth` frame?

The browser WebSocket API can't set custom headers, and putting a key in the URL query would land it in access logs. So the key arrives in the first frame after connecting and is held only in connection memory.

---

## REST API

Prefix: `/api/v1`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check (includes DB connectivity) |
| `GET` | `/characters` | List characters |
| `POST` | `/characters` | Create a character |
| `GET` | `/characters/{id}` | Character detail |
| `PUT` | `/characters/{id}` | Update a character |
| `DELETE` | `/characters/{id}` | Delete a character |
| `POST` | `/characters/import` | Import a character from JSON |
| `GET` | `/memories` | List memories |
| `DELETE` | `/memories/{id}` | Delete one memory |
| `DELETE` | `/memories` | Clear all memories |

---

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/v1/              # REST + WS routes
│   │   ├── core/
│   │   │   ├── config.py        # pydantic-settings config
│   │   │   ├── logging.py       # loguru + secret redaction
│   │   │   └── messaging/       # the three-layer architecture
│   │   │       ├── types.py         # UnifiedMessage / ReplyResult
│   │   │       ├── channel.py       # MessageChannel interface
│   │   │       ├── exceptions.py    # ChannelException
│   │   │       ├── identity.py      # IdentityService
│   │   │       └── adapters/
│   │   │           ├── websocket.py # WebSocketAdapter (implemented)
│   │   │           └── wechat.py    # WeChatAdapter (stub)
│   │   ├── db/                  # engine / session / Base
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic models (incl. WS frame protocol)
│   │   └── services/
│   │       ├── chat/core.py     # ChatCoreService (core layer)
│   │       ├── character/       # character card → system prompt
│   │       ├── llm/             # OpenAI-compatible client
│   │       └── memory/          # mem0 wrapper + Noop fallback
│   ├── alembic/                 # database migrations
│   └── tests/                   # 46 tests
├── frontend/
│   ├── src/
│   │   ├── components/          # message list / bubble / input / settings drawer / character panel
│   │   ├── composables/useChat.ts
│   │   ├── api/                 # REST + WS clients
│   │   └── views/CharacterEditor.vue
│   └── e2e/                     # Playwright screenshot scripts
├── screenshots/                 # per-milestone verification screenshots
├── docker-compose.yml
├── CLAUDE.md                    # project constraints (for AI coding tools)
└── AI伴侣应用技术方案.md          # full technical design doc (Chinese)
```

---

## Testing

```bash
cd backend
uv run pytest -q
```

All **46 tests pass** today, covering:

- End-to-end WebSocket chat (`test_ws.py`)
- Core layer unit tests with no transport involved (`test_chat_core.py`)
- No duplicated context when assembling prompts (incl. multi-turn regression tests)
- Character card CRUD and import (`test_characters.py`)
- Memory service and degradation (`test_memories.py`)
- Three-layer architecture: identity mapping, channel exceptions, WeChat signature verification (`test_messaging.py`)
- Secret redaction in logs (`test_redact.py`)

> The suite requires PostgreSQL to be running. `conftest.py` blanks `EMBEDDING_API_KEY` before `.env` is read so tests never hit a real embedding API.

Frontend screenshots:

```bash
cd frontend
npm run e2e:shot
```

---

## Roadmap

| Milestone | Scope | Status |
|---|---|---|
| M0 | Skeleton + minimal streaming chat loop (FastAPI + DB + gateway) | ✅ |
| M1a | Character system (card CRUD / import) | ✅ |
| M1b | Memory (mem0 integration, Chinese extraction, retrieval injection, cleanup) | ✅ |
| ~~M2~~ | ~~Live2D rendering~~ | ❌ Abandoned |
| M3 | Memory management panel + performance targets | ⏳ |
| M4 | Character marketplace, content moderation, load testing, deployment, WeChat | ⏳ |

### Performance targets

- First contentful paint LCP < 1.5s, TTI < 2s
- Keystroke to on-screen echo < 50ms
- 60fps scrolling at 1000 messages, no long task > 50ms
- Time to first token < 1.5s
- Heap growth < 50MB over 30 minutes of continuous chat

---

## Notes

- This is a personal learning project using BYOK (Bring Your Own Key). No API keys are provided.
- Never commit `.env` or key files (already excluded by `.gitignore`).
- Content moderation, rate limiting, and multi-tenancy are not implemented — do not expose this directly to the public internet.
