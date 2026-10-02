# anime-chat

A text-based chat app with deeply customizable AI characters and permanent memory.

The design goal comes down to three words: **fluid, minimal, unobtrusive**. The main screen keeps only a character area, message stream, input box, send button, and a settings icon — everything else is progressively disclosed.

> 中文版：[README.md](README.md)

## Features

**Deeply customizable AI characters.** A character card is a JSONB structure: persona (identity, personality, speaking style, worldview, relationship with the user), example dialogues, greeting, plus per-character model params and memory recall count. Full CRUD and JSON import.

**Permanent memory.** Built on self-hosted [mem0](https://github.com/mem0ai/mem0) with vectors stored in PostgreSQL's pgvector — no separate vector database to maintain. After each turn the exchange is extracted asynchronously (never blocking the reply); before the next turn the user message drives a semantic search whose results are appended to the system prompt. Search times out at 1.5s and any exception degrades to empty, so a dead embedding service never breaks chat; each memory is truncated to 200 chars with a 600-char total budget. Memories can be viewed and cleared from the settings drawer.

**Persistent chat history.** One long-lived conversation per character — a page reload, a different browser, or a phone on the same Wi-Fi never loses the thread. The server anchors the conversation by `character_id`, so the frontend never has to remember a `conversation_id`; open the same LAN address on a phone, pick the character once, and you see the same conversation.

**Bring Your Own Key (BYOK).** The key lives only in browser localStorage and travels in the WebSocket `auth` frame. The server holds it in connection memory only — never persisted, never logged. That means you can point it at any OpenAI-compatible API (DeepSeek, OpenAI, SiliconFlow, local Ollama) by changing only the base URL and model name.

## Getting Started

Prerequisites: Docker Desktop, Python 3.11+ with [uv](https://github.com/astral-sh/uv), Node.js 18+.

```bash
# 1. Infrastructure: postgres(5432, with pgvector) / redis(6379) / new-api(3000)
docker compose up -d

# 2. Backend
cd backend
uv sync
[ -f .env ] || cp ../.env.example .env    # first run only; skip if it exists or you'll overwrite your keys
# Edit .env, set LLM_API_KEY (local fallback) and EMBEDDING_API_KEY
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000

# 3. Frontend
cd frontend && npm install && npm run dev
```

Open <http://localhost:5173> and enter your API key in the settings drawer to start chatting. Health check: <http://127.0.0.1:8000/api/v1/health>.

Once `backend/.env` is in place, `bash scripts/dev.sh` starts both processes at once — it skips any port already in use (so you can restart just one side) and prints the LAN address for phone access.

### Phone / LAN access

Vite listens on `0.0.0.0`, so a phone on the same Wi-Fi can reach `http://<your-LAN-IP>:5173` (find it with `ipconfig`, the IPv4 address under the WLAN adapter).

- The port is **5173** (frontend), not 8000 — the backend is not exposed to the LAN; the scheme is **http**, not https
- Phone and computer must be on the **same** Wi-Fi (guest networks isolate devices)

The backend does not need to listen on `0.0.0.0`, and no CORS setup is required: the phone only ever talks to Vite, which proxies `/api` (including WebSockets) to `127.0.0.1:8000` on the host machine, so every request is same-origin from the browser's point of view. If the phone can't connect, check in order: whether `netstat -ano | findstr :5173` reports `0.0.0.0` rather than `127.0.0.1`, whether both devices are on the same Wi-Fi, and whether Windows Firewall allows Node on private networks.

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

> ⚠️ Embedding dimensions are locked in: `hnsw` / `ivfflat` indexes cap `vector` at 2000 dimensions. Switching embedding models requires rebuilding all vectors — decide before deploying.

## Developer Reference

| Layer | Choice |
|---|---|
| Frontend | Vue 3 + Vite 6 + TypeScript; Naive UI only, auto-imported on demand |
| Backend | FastAPI + Python 3.11+ + SQLAlchemy 2.x (async) + Pydantic v2 |
| Storage | PostgreSQL 16 + pgvector, Redis 7 |
| Memory | Self-hosted mem0 (vector backend reuses pgvector) |
| Model gateway | [new-api](https://github.com/Calcium-Ion/new-api) (OpenAI-compatible; provisioned, not yet on the critical path) |
| Migrations / Testing | Alembic, pytest + pytest-asyncio, Playwright |

> The frontend component budget is a hard constraint: at most 2 resident Naive UI components on the main screen (`n-input` + `n-button`) and at most 5 in overlays. The message list and bubbles are hand-written — no component library.

### Architecture

Core conversation logic is fully decoupled from transport. Adding WeChat later means adding one Adapter with zero changes to the core.

```
┌──────────────────────────────────────────────┐
│ ChatCoreService (core layer)                  │
│ LLM + memory + character cards. Knows nothing │
│ about where the message came from.            │
│ handle_message(UnifiedMessage, api_key, ch)   │
└───────────────────┬──────────────────────────┘
                    │ depends on MessageChannel
┌───────────────────┴──────────────────────────┐
│ MessageChannel: on_message +                  │
│ send_delta / send_done / send_error           │
└────────┬────────────────────────┬────────────┘
   ┌─────▼──────┐         ┌───────▼───────┐
   │ WebSocket  │         │ WeChat        │
   │ (implemented)        │ (stub only)   │
   └────────────┘         └───────────────┘
```

The path of one conversation: parse the frame → load the character card → fetch the last 20 messages → persist the user message → retrieve and inject memories → stream from the LLM (token by token) → persist the assistant message → fire `on_reply` callbacks → dispatch memory extraction asynchronously.

Two things worth noting: **streaming is absorbed at the interface layer** — the core only calls `send_delta` / `send_done`, and presentation differences belong to the Adapter (WebSocket pushes token by token, WeChat would accumulate and send once); and **`ChannelException`** carries channel-specific limits like WeChat's 48-hour window, which the core recognizes and degrades on rather than crashing. The `IdentityService` maps external IDs (WeChat OpenID, etc.) to an internal `user_id`; it's a single-user implementation today.

### WebSocket Protocol

Endpoint: `ws://127.0.0.1:8000/api/v1/ws/chat`. Both sides share a Pydantic discriminated union contract (`backend/app/schemas/frames.py`); the frontend mirrors it in `frontend/src/api/frames.ts`.

```jsonc
// Client → Server
{ "type": "auth", "api_key": "sk-..." }   // must be the first frame after connecting
{ "type": "chat", "message": "hello", "character_id": "uuid", "conversation_id": "uuid" }
{ "type": "ping" }

// Server → Client
{ "type": "delta", "text": "he" }
{ "type": "done", "message_id": "uuid", "conversation_id": "uuid", "usage": null }
{ "type": "error", "code": "llm_error", "message": "..." }   // message is already redacted
```

The key travels in the `auth` frame rather than the URL query because the browser WebSocket API can't set custom headers, and a query string would land in access logs.

### REST API

Prefix: `/api/v1`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check (includes DB connectivity) |
| `GET` `POST` | `/characters` | List / create characters |
| `GET` `PUT` `DELETE` | `/characters/{id}` | Detail / update / delete a character |
| `POST` | `/characters/import` | Import a character from JSON |
| `GET` | `/memories` | List memories (`character_id` required) |
| `DELETE` | `/memories/{id}` | Delete one memory |
| `DELETE` | `/memories` | Clear all memories |
| `GET` | `/conversations/messages` | Recent messages of a character's conversation (`character_id` optional, `limit` defaults to 200, max 500) |

## Project Structure

```
backend/
  app/
    api/v1/         REST + WS routes
    core/           config / log redaction / messaging (three-layer architecture + adapters)
    db/ models/     engine, SQLAlchemy models
    schemas/        Pydantic models (incl. the WS frame protocol)
    services/       chat (core layer) / character (card → prompt) / llm / memory (mem0 + Noop fallback)
  alembic/          database migrations
  tests/            53 tests
frontend/
  src/
    components/     message list / bubble / input / settings drawer / character panel
    composables/    useChat.ts (streaming render, history restore)
    api/            REST + WS clients
  e2e/              Playwright verification scripts
scripts/dev.sh      start backend + frontend, print the phone-accessible URL
screenshots/        per-milestone verification screenshots
```

## Testing

```bash
cd backend && uv run pytest -q     # 53 tests
```

Covering: end-to-end WebSocket chat, core-layer unit tests with no transport involved, no duplicated context when assembling prompts (incl. multi-turn regressions), conversation persistence (one conversation reused per character / isolation between characters / ordering and `limit`), character card CRUD and import, memory service and degradation, the three-layer architecture (identity mapping / channel exceptions / WeChat signature verification), and secret redaction in logs.

The suite requires PostgreSQL to be running. `conftest.py` blanks `EMBEDDING_API_KEY` before `.env` is read so tests never hit a real embedding API.

Frontend verification scripts (both servers must be running; the key is passed via the `COMPANION_API_KEY` env var):

```bash
cd frontend
npm run e2e:shot       # UI screenshots at each viewport
npm run e2e:persist    # persistence regression: send → reload → history still there
```

## Notes

- A personal learning and self-hosting project using BYOK. No API keys are provided. **Never commit `.env` or key files** (already excluded by `.gitignore`).
- Content moderation, rate limiting, and multi-tenancy are not implemented — do not expose this directly to the public internet.
- Progress: M0 skeleton and streaming chat ✅ / M1a character system ✅ / M1b long-term memory ✅ / M2 Live2D ❌ abandoned.
- This is a **personal, single-user project**: future work is limited to what its owner actually uses. Multi-user support, content moderation, rate limiting, a character marketplace, and public deployment are out of scope.
- Performance targets: LCP < 1.5s and TTI < 2s; keystroke to on-screen echo < 50ms; 60fps scrolling at 1000 messages; time to first token < 1.5s; heap growth < 50MB over 30 minutes of continuous chat.
