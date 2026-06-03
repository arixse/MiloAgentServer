# MiloAgent

A self-hosted Deep Agent server powered by [LangGraph](https://github.com/langchain-ai/langgraph) and [DeepAgents](https://github.com/langchain-ai/deepagents), with a React chat interface, streaming responses, sandboxed code execution, and dynamic skill installation.

[![CI](https://github.com/arixse/MiloAgentServer/actions/workflows/build-image.yml/badge.svg)](https://github.com/arixse/MiloAgentServer/actions/workflows/build-image.yml)

## Features

- **Deep Agent** — multi-step reasoning with tool use, subagents, file I/O, and persistent memory
- **Streaming chat** — real-time SSE streaming with Markdown rendering and syntax highlighting
- **Sandbox execution** — isolated code execution via OpenSandbox, with automatic pip setup
- **Tool call visualization** — expandable tool call cards show args and results inline, in chronological order
- **Skill system** — dynamic skill installation from URLs, auto-restored on sandbox rebuild
- **JWT authentication** — user registration/login with thread-level isolation
- **Persistent storage** — Redis for thread metadata, MongoDB for conversation history and long-term memory
- **Docker-first** — multi-stage build bundles frontend and backend into a single image

## Architecture

```
┌──────────────────────┐     SSE + REST       ┌──────────────────────────┐
│  React frontend (Vite) │ ◄─────────────────► │   FastAPI server          │
│  Port 5173 (dev only)  │                     │   Port 8000              │
└──────────────────────┘                       └────────┬─────────────────┘
                                                        │
                              ┌─────────────────────────┼─────────────────────┐
                              │                         │                     │
                         ┌────▼────┐             ┌──────▼──────┐       ┌─────▼──────┐
                         │  Redis   │             │   MongoDB    │       │ OpenSandbox │
                         │ metadata │             │ checkpoints  │       │ code exec   │
                         │ sandbox  │             │ store/memory │       │ sandbox     │
                         └─────────┘             └─────────────┘       └────────────┘
```

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React 19 + TypeScript + Tailwind CSS 4 | Chat UI with Markdown, tool call cards, streaming |
| API | FastAPI + Uvicorn | REST endpoints, SSE streaming, JWT auth |
| Agent | LangGraph + DeepAgents | Multi-step reasoning, tool orchestration, subagents |
| LLM | DeepSeek (OpenAI-compatible) | Model provider (configurable) |
| Checkpoint | MongoDB | Conversation history, agent state persistence |
| Memory | MongoDB Store | Long-term user preferences at `/memories/` |
| Metadata | Redis | Thread list, sandbox mappings, skill records |
| Sandbox | OpenSandbox | Isolated shell commands, file I/O, code execution |

## Quick start

### Prerequisites

- Python 3.11+ with [uv](https://docs.astral.sh/uv/) or pip
- Redis (any version)
- MongoDB 7+
- [OpenSandbox](http://182.254.183.29:8080) server
- Node.js 22+ (frontend development only)

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys and connection strings
```

Key variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DEEPSEEK_API_KEY` | DeepSeek API key | — |
| `DEEPSEEK_MODEL_NAME` | Model name | `deepseek-v4-flash` |
| `OPENSANDBOX_SERVER_URL` | OpenSandbox endpoint | `http://182.254.183.29:8080` |
| `OPENSANDBOX_API_KEY` | OpenSandbox API key | — |
| `REDIS_HOST` | Redis host | `localhost` |
| `MONGO_URI` | MongoDB connection string | `mongodb://localhost:27017` |
| `USE_MONGO_PERSISTENCE` | Enable MongoDB persistence | `false` |
| `JWT_SECRET_KEY` | JWT signing key | auto-generated dev key |

### 2. Start with Docker Compose

```bash
docker compose up -d
```

This starts the full stack — app, Redis, and MongoDB — on port **8000**. Open [http://localhost:8000](http://localhost:8000) to use the app.

### 3. Local development

**Backend:**

```bash
uv sync
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend** (in a separate terminal):

```bash
cd client
npm install
npm run dev       # → http://localhost:5173
```

The Vite dev server proxies `/api` requests to `localhost:8000`, so you get hot module replacement for the frontend while the backend handles API calls.

## API reference

All endpoints are prefixed with `/api`. Protected endpoints require `Authorization: Bearer <token>`.

### Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/register` | No | Register a new user |
| `POST` | `/auth/login` | No | Login, returns JWT |
| `GET` | `/auth/me` | Yes | Get current user info |

### Threads

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/threads` | Yes | Create a new thread |
| `GET` | `/threads` | Yes | List user's threads |
| `GET` | `/threads/{id}` | Yes | Get thread metadata |
| `DELETE` | `/threads/{id}` | Yes | Delete thread and its sandbox |

### Runs

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/threads/{id}/runs` | Yes | Non-streaming run |
| `POST` | `/threads/{id}/runs/stream` | Yes | **SSE streaming run** |
| `GET` | `/threads/{id}/state` | Yes | Read thread state / messages |

### SSE stream events

The streaming endpoint emits the following events:

| `type` | Payload | Description |
|--------|---------|-------------|
| `message` | `content`, `tool_calls`, `tool_call_chunks` | AI text delta and/or tool call information |
| `tool_result` | `tool_call_id`, `name`, `content` | Tool execution result |
| `done` | `thread_id` | Stream completed successfully |
| `error` | `detail` | Error message |

## Built-in tools

The agent comes with a set of built-in tools accessible from the sandbox:

| Tool | Description |
|------|-------------|
| `search` | Web search via Tavily |
| `read_file` | Read files from sandbox (supports PDF, Markdown, DOCX, XLSX, PPTX, TXT) |
| `save_to_markdown` | Save text as a Markdown file in the sandbox |
| `save_to_pdf` | Save text as a PDF in the sandbox |
| `generate_download_url` | Generate a signed download URL for a sandbox file |
| `install_skill` | Download and install a skill from a URL |
| `utc_now` | Get current UTC timestamp |

Additional tools can be integrated via MCP (Model Context Protocol).

## Project structure

```
├── src/
│   ├── main.py                              # FastAPI app entry point
│   ├── model_provider.py                    # LLM configuration
│   ├── api/
│   │   └── chat.py                          # Thread, run, and state endpoints
│   ├── auth/
│   │   ├── router.py                        # Registration and login endpoints
│   │   ├── security.py                      # JWT encode / decode
│   │   ├── models.py                        # User data models
│   │   └── dependencies.py                  # get_current_user dependency
│   ├── deep_agent/
│   │   ├── graph.py                         # Agent factory, caching, persistence
│   │   ├── opensandbox_backend.py           # OpenSandbox backend (create, reconnect, cleanup)
│   │   └── sub_agents.py                    # Subagent definitions
│   ├── tools/
│   │   ├── file_tool.py                     # File read/write/convert tools
│   │   ├── install_skill.py                 # Dynamic skill installation
│   │   ├── search_tool.py                   # Web search tool
│   │   ├── mcp_tool.py                      # MCP integration
│   │   └── sandbox_utils.py                # Sandbox helpers and skill records
│   └── utils/
│       └── path.py                          # Project root path helper
├── client/                                  # React frontend (built separately)
│   └── src/
│       ├── components/chat/                 # Chat UI components
│       ├── contexts/                        # StreamContext, ThreadContext
│       ├── hooks/                           # useStream, useAutoScroll, useThreads
│       ├── api/                             # API client + SSE stream parser
│       └── lib/                             # TypeScript types and helpers
├── AGENTS.md                                # Agent system prompt and conventions
├── Dockerfile                               # Multi-stage build (frontend + backend)
├── docker-compose.yml                       # Full stack (app + Redis + MongoDB)
└── .github/workflows/build-image.yml        # CI: build on GitHub Release
```

## Deployment

### Docker image

The Dockerfile uses a **multi-stage build**:

1. **Stage 1** (`node:22-alpine`) — builds the React frontend into `client/dist/`
2. **Stage 2** (`python:3.11-slim`) — installs Python dependencies, copies the frontend build, and serves everything with Uvicorn

```bash
docker build -t milo-agent:latest .
docker run -p 8000:8000 --env-file .env milo-agent:latest
```

### GitHub Actions

Creating a [GitHub Release](https://github.com/arixse/MiloAgentServer/releases) triggers an automatic build that pushes the image to GHCR:

```bash
docker pull ghcr.io/arixse/milo-agent-server:latest
docker pull ghcr.io/arixse/milo-agent-server:1.0.0  # specific version
```

## Sandbox lifecycle

- Each thread gets its own isolated OpenSandbox instance (`opensandbox/code-interpreter:v1.0.2`)
- Sandboxes are automatically renewed in the background (default 24h timeout)
- On server restart, sandboxes are reconnected via Redis mappings
- Thread deletion or server shutdown cleans up the associated sandbox
- **pip** is automatically installed during sandbox initialization via a three-tier fallback (built-in pip → `ensurepip` → `apt-get`)

## Skill system

Skills are zip archives installed into the sandbox's `/skills/` directory:

1. Agent calls `install_skill` with a skill name and download URL
2. The zip is downloaded, uploaded to the sandbox, and extracted
3. Installation records are persisted in Redis per user
4. If a sandbox is destroyed and recreated, all skills are automatically restored

> [!NOTE]
> Skill state does not persist across sandbox rebuilds — only the installation records are kept. Skills that modify system state (e.g., `apt-get install`) will need to be re-run.

## Authentication flow

```
POST /auth/register  →  create user in MongoDB
POST /auth/login     →  verify credentials, return JWT access token
         ↓
  All subsequent requests include Authorization: Bearer <token>
         ↓
  get_current_user extracts user_id from JWT
         ↓
  Threads and sandboxes are scoped to the authenticated user
```
