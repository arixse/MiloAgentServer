# ===========================================================================
# MiloAgent — 多阶段 Docker 构建
# ===========================================================================
# Stage 1: 编译前端 (Node.js)
# Stage 2: 后端镜像 (Python)，嵌入前端构建产物
# ===========================================================================

# ---------------------------------------------------------------------------
# Stage 1 — 前端构建
# ---------------------------------------------------------------------------
FROM node:22-alpine AS frontend-builder

WORKDIR /app/client

# 仅复制依赖文件以利用 Docker 层缓存
COPY client/package.json client/package-lock.json ./
RUN npm install

# 复制前端源码并构建
COPY client/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2 — 后端生产镜像
# ---------------------------------------------------------------------------
FROM python:3.11-slim

LABEL org.opencontainers.image.title="MiloAgent"
LABEL org.opencontainers.image.description="Deep Agent based on LangGraph / DeepAgents"

# ---------------------------------------------------------------------------
# System dependencies
# ---------------------------------------------------------------------------
# - curl, git: general tooling / uv
# - build-essential: some Python packages may need compilation
# - Node.js (22.x): required for MCP tools that rely on `npx`
# - Playwright system deps: for headless browser automation
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    ca-certificates \
    gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
    | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" \
    > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Install uv (fast Python package manager)
# ---------------------------------------------------------------------------
RUN pip install --no-cache-dir uv

# ---------------------------------------------------------------------------
# Workdir & app files
# ---------------------------------------------------------------------------
WORKDIR /app

# Copy dependency manifests first for better layer caching
COPY pyproject.toml uv.lock ./

# Install Python dependencies (production only, no dev group)
RUN uv sync --frozen --no-dev

# Copy the rest of the backend project
COPY . .

# ---------------------------------------------------------------------------
# Copy frontend build from Stage 1
# ---------------------------------------------------------------------------
COPY --from=frontend-builder /app/client/dist ./client/dist

# ---------------------------------------------------------------------------
# Playwright browsers (for browser automation tools)
# ---------------------------------------------------------------------------
RUN uv run playwright install --with-deps chromium

# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------
EXPOSE 8000

# Use uvicorn to serve the FastAPI app (includes frontend static files)
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
