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

### 2. Local development

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

The Dockerfile uses a **multi-stage build**:

1. **Stage 1** (`node:22-alpine`) — builds the React frontend into `client/dist/`
2. **Stage 2** (`python:3.11-slim`) — installs Python dependencies, copies the frontend build, and serves everything with Uvicorn on port 8000

In production, the frontend is served directly by FastAPI — no separate web server needed.

### Option 1: Docker Compose (recommended)

Pull the pre-built image or build locally, then start the full stack:

```bash
# Clone the repository
git clone https://github.com/arixse/MiloAgentServer.git
cd MiloAgentServer

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Start all services (app + Redis + MongoDB)
docker compose up -d
```

The app is available at **http://localhost:8000**. The compose file includes:

| Service | Image | Port |
|---------|-------|------|
| `app` | `milo-agent:latest` (built locally) | 8000 |
| `redis` | `redis:7-alpine` | 6379 |
| `mongodb` | `mongo:7` | 27017 |

All services are connected via an internal `milo-net` bridge network. Redis and MongoDB data are persisted in named volumes.

To update to a new version:

```bash
git pull
docker compose up -d --build
```

### Option 2: Pre-built image from GHCR

Creating a [GitHub Release](https://github.com/arixse/MiloAgentServer/releases) triggers an automatic build and push to GHCR. To deploy with the pre-built image:

```bash
# Pull the image
docker pull ghcr.io/arixse/milo-agent-server:latest

# Start Redis and MongoDB separately
docker run -d --name milo-redis -p 6379:6379 redis:7-alpine
docker run -d --name milo-mongo -p 27017:27017 mongo:7

# Start the app
docker run -d \
  --name milo-agent \
  -p 8000:8000 \
  --env-file .env \
  -e REDIS_HOST=host.docker.internal \
  -e MONGO_URI=mongodb://host.docker.internal:27017 \
  ghcr.io/arixse/milo-agent-server:latest
```

> [!NOTE]
> On Linux, replace `host.docker.internal` with the host machine's IP or use `--network host`.

### Option 3: Manual deployment

**Prerequisites:** Python 3.11+, Node.js 22+, Redis, MongoDB.

```bash
# Build the frontend
cd client
npm install && npm run build
cd ..

# Install Python dependencies
uv sync --no-dev

# Start the server
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Place the app behind a reverse proxy (nginx, Caddy) for TLS termination:

```nginx
# Example nginx configuration
server {
    listen 443 ssl;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;  # Required for SSE streaming
    }
}
```

> [!IMPORTANT]
> SSE streaming requires disabling proxy buffering (`proxy_buffering off` in nginx, `X-Accel-Buffering: no` header otherwise).

### Environment variables

| Variable                      | Required | Default |
|-------------------------------|----------|--|
| `MODEL_API_KEY`               | Yes | — |
| `MODEL_NAME`                  | No | |
| `MODEL_BASE_URL`              | No | |
| `OPENSANDBOX_SERVER_URL`      | Yes |  |
| `OPENSANDBOX_API_KEY`         | Yes | — |
| `REDIS_HOST`                  | No | `localhost` |
| `REDIS_PORT`                  | No | `6379` |
| `MONGO_URI`                   | No | `mongodb://localhost:27017` |
| `MONGO_DB_NAME`               | No | `MiloAgent` |
| `USE_MONGO_PERSISTENCE`       | No | `false` |
| `JWT_SECRET_KEY`              | No | auto-generated |
| `JWT_ALGORITHM`               | No | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `1440` |
| `SANDBOX_TIMEOUT_HOURS`       | No | `24` |
| `TAVILY_API_KEY`              | No | — |

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
