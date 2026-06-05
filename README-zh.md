# MiloAgent

你的私人 AI 助手。像聊天一样让它帮你搜索信息、处理文件、编写代码、撰写报告——复杂任务自动分解、逐步执行，结果实时呈现。

[![CI](https://github.com/arixse/MiloAgentServer/actions/workflows/build-image.yml/badge.svg)](https://github.com/arixse/MiloAgentServer/actions/workflows/build-image.yml)

## 功能特性

- **Deep Agent** — 多步骤推理，支持工具调用、子代理、文件读写和持久化记忆
- **流式聊天** — 基于 SSE 的实时流式输出，支持 Markdown 渲染和语法高亮
- **沙盒执行** — 通过 OpenSandbox 提供隔离的代码执行环境，自动配置 pip
- **工具调用可视化** — 可展开的工具调用卡片，按实际顺序展示参数和执行结果
- **Skill 系统** — 支持从 URL 动态安装 Skill，沙盒重建后自动恢复
- **JWT 认证** — 用户注册/登录，线程级别数据隔离
- **持久化存储** — Redis 存储线程元数据，MongoDB 存储对话历史和长期记忆
- **Docker 优先** — 多阶段构建将前后端打包为单一镜像

## 架构

```
┌──────────────────────┐     SSE + REST       ┌──────────────────────────┐
│  React 前端 (Vite)     │ ◄─────────────────► │   FastAPI 服务端           │
│  端口 5173 (仅开发)     │                     │  端口 8000               │
└──────────────────────┘                       └────────┬─────────────────┘
                                                        │
                              ┌─────────────────────────┼─────────────────────┐
                              │                         │                     │
                         ┌────▼────┐             ┌──────▼──────┐       ┌─────▼──────┐
                         │  Redis   │             │   MongoDB    │       │ OpenSandbox │
                         │ 元数据    │             │ checkpoint   │       │ 代码执行    │
                         │ sandbox  │             │ store/记忆   │       │ 沙盒       │
                         └─────────┘             └─────────────┘       └────────────┘
```

| 层 | 技术 | 用途 |
|-------|-----------|---------|
| 前端 | React 19 + TypeScript + Tailwind CSS 4 | 聊天界面，Markdown 渲染，工具调用卡片，流式输出 |
| API | FastAPI + Uvicorn | REST 接口，SSE 流式，JWT 认证 |
| Agent | LangGraph + DeepAgents | 多步骤推理，工具编排，子代理 |
| 模型 | DeepSeek (兼容 OpenAI) | 可替换为任意兼容 OpenAI 的模型 |
| Checkpoint | MongoDB | 对话历史，Agent 状态持久化 |
| 记忆 | MongoDB Store | 用户长期偏好，存储在 `/memories/` |
| 元数据 | Redis | 线程列表，sandbox 映射，Skill 记录 |
| 沙盒 | OpenSandbox | 隔离的命令执行、文件读写、代码运行 |

## 快速开始

### 前置条件

- Python 3.11+ + [uv](https://docs.astral.sh/uv/) 或 pip
- Redis（任意版本）
- MongoDB 7+
- [OpenSandbox](http://182.254.183.29:8080) 服务
- Node.js 22+（仅前端开发需要）

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 API 密钥和连接信息
```

### 2. 本地开发

**后端：**

```bash
uv sync
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

**前端**（另一个终端）：

```bash
cd client
npm install
npm run dev       # → http://localhost:5173
```

Vite 开发服务器将 `/api` 请求代理到 `localhost:8000`，前端热更新，后端提供 API。

## API 参考

所有端点前缀为 `/api`。受保护端点需携带 `Authorization: Bearer <token>`。

### 认证

| 方法 | 路径 | 认证 | 说明 |
|--------|------|------|-------------|
| `POST` | `/auth/register` | 否 | 注册新用户 |
| `POST` | `/auth/login` | 否 | 登录，返回 JWT |
| `GET` | `/auth/me` | 是 | 获取当前用户信息 |

### 线程

| 方法 | 路径 | 认证 | 说明 |
|--------|------|------|-------------|
| `POST` | `/threads` | 是 | 创建新线程 |
| `GET` | `/threads` | 是 | 列出用户线程 |
| `GET` | `/threads/{id}` | 是 | 查询线程元数据 |
| `DELETE` | `/threads/{id}` | 是 | 删除线程及对应沙盒 |

### 运行

| 方法 | 路径 | 认证 | 说明 |
|--------|------|------|-------------|
| `POST` | `/threads/{id}/runs` | 是 | 非流式运行 |
| `POST` | `/threads/{id}/runs/stream` | 是 | **SSE 流式运行** |
| `GET` | `/threads/{id}/state` | 是 | 读取线程状态/消息历史 |

### SSE 流事件

流式端点发送以下事件：

| `type` | 内容 | 说明 |
|--------|---------|-------------|
| `message` | `content`, `tool_calls`, `tool_call_chunks` | AI 文本增量 和/或 工具调用信息 |
| `tool_result` | `tool_call_id`, `name`, `content` | 工具执行结果 |
| `done` | `thread_id` | 流正常结束 |
| `error` | `detail` | 错误信息 |

## 内置工具

Agent 内置了可在沙盒中使用的工具集：

| 工具 | 说明 |
|------|-------------|
| `search` | 通过 Tavily 进行网络搜索 |
| `read_file` | 读取沙盒文件（支持 PDF、Markdown、DOCX、XLSX、PPTX、TXT） |
| `save_to_markdown` | 将文本保存为 Markdown 文件 |
| `save_to_pdf` | 将文本保存为 PDF 文件 |
| `generate_download_url` | 生成沙盒文件的签名下载链接 |
| `install_skill` | 从 URL 下载并安装 Skill |
| `utc_now` | 获取当前 UTC 时间戳 |

可通过 MCP（Model Context Protocol）集成更多工具。

## 项目结构

```
├── src/
│   ├── main.py                              # FastAPI 入口
│   ├── model_provider.py                    # 模型配置
│   ├── api/
│   │   └── chat.py                          # 线程、运行、状态接口
│   ├── auth/
│   │   ├── router.py                        # 注册和登录接口
│   │   ├── security.py                      # JWT 编解码
│   │   ├── models.py                        # 用户数据模型
│   │   └── dependencies.py                  # get_current_user 依赖
│   ├── deep_agent/
│   │   ├── graph.py                         # Agent 工厂、缓存、持久化
│   │   ├── opensandbox_backend.py           # OpenSandbox 后端（创建、重连、清理）
│   │   └── sub_agents.py                    # 子代理定义
│   ├── tools/
│   │   ├── file_tool.py                     # 文件读写/转换工具
│   │   ├── install_skill.py                 # Skill 动态安装
│   │   ├── search_tool.py                   # 搜索工具
│   │   ├── mcp_tool.py                      # MCP 集成
│   │   └── sandbox_utils.py                # 沙盒辅助和 Skill 记录管理
│   └── utils/
│       └── path.py                          # 项目根路径工具
├── client/                                  # React 前端（独立构建）
│   └── src/
│       ├── components/chat/                 # 聊天界面组件
│       ├── contexts/                        # StreamContext、ThreadContext
│       ├── hooks/                           # useStream、useAutoScroll、useThreads
│       ├── api/                             # API 客户端 + SSE 流解析
│       └── lib/                             # TypeScript 类型和工具
├── AGENTS.md                                # Agent 系统提示词和规范
├── Dockerfile                               # 多阶段构建（前端 + 后端）
├── docker-compose.yml                       # 全栈部署（app + Redis + MongoDB）
└── .github/workflows/build-image.yml        # CI：GitHub Release 时构建镜像
```

## 部署

Dockerfile 使用**多阶段构建**：

1. **阶段 1** (`node:22-alpine`) — 将 React 前端构建为 `client/dist/`
2. **阶段 2** (`python:3.11-slim`) — 安装 Python 依赖，复制前端构建产物，由 Uvicorn 统一提供服务

生产环境中，前端由 FastAPI 直接托管 — 无需单独的 Web 服务器。

### 方式 1：Docker Compose（推荐）

拉取预构建镜像或本地构建，一键启动全栈：

```bash
# 克隆仓库
git clone https://github.com/arixse/MiloAgentServer.git
cd MiloAgentServer

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 API 密钥

# 启动所有服务（app + Redis + MongoDB）
docker compose up -d
```

应用访问地址：**http://localhost:8000**。compose 文件包含：

| 服务 | 镜像 | 端口 |
|---------|-------|------|
| `app` | `milo-agent:latest`（本地构建） | 8000 |
| `redis` | `redis:7-alpine` | 6379 |
| `mongodb` | `mongo:7` | 27017 |

所有服务通过内部 `milo-net` 桥接网络通信。Redis 和 MongoDB 数据保存在命名卷中。

更新到新版本：

```bash
git pull
docker compose up -d --build
```

### 方式 2：使用 GHCR 预构建镜像

创建 [GitHub Release](https://github.com/arixse/MiloAgentServer/releases) 会触发自动构建，将镜像推送到 GHCR。使用预构建镜像部署：

```bash
# 拉取镜像
docker pull ghcr.io/arixse/milo-agent-server:latest

# 分别启动 Redis 和 MongoDB
docker run -d --name milo-redis -p 6379:6379 redis:7-alpine
docker run -d --name milo-mongo -p 27017:27017 mongo:7

# 启动应用
docker run -d \
  --name milo-agent \
  -p 8000:8000 \
  --env-file .env \
  -e REDIS_HOST=host.docker.internal \
  -e MONGO_URI=mongodb://host.docker.internal:27017 \
  ghcr.io/arixse/milo-agent-server:latest
```

> [!NOTE]
> Linux 系统请将 `host.docker.internal` 替换为宿主机 IP，或使用 `--network host`。

### 方式 3：手动部署

**前置条件：** Python 3.11+、Node.js 22+、Redis、MongoDB。

```bash
# 构建前端
cd client
npm install && npm run build
cd ..

# 安装 Python 依赖
uv sync --no-dev

# 启动服务
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

建议在前面放置反向代理（nginx、Caddy）以提供 TLS：

```nginx
# nginx 配置示例
server {
    listen 443 ssl;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;  # SSE 流式必须关闭缓冲
    }
}
```

> [!IMPORTANT]
> SSE 流式输出需要关闭代理缓冲（nginx 使用 `proxy_buffering off`，其他代理需设置 `X-Accel-Buffering: no` 头）。

### 环境变量

| 变量 | 必填 | 默认值 |
|----------|----------|---------|
| `MODEL_API_KEY` | 是 | — |
| `MODEL_NAME` | 否 | 模型名称 |
| `MODEL_BASE_URL` | 否 | 模型地址 |
| `OPENSANDBOX_SERVER_URL` | 是 | OpenSandbox 地址 |
| `OPENSANDBOX_API_KEY` | 是 | — |
| `REDIS_HOST` | 否 | `localhost` |
| `REDIS_PORT` | 否 | `6379` |
| `MONGO_URI` | 否 | `mongodb://localhost:27017` |
| `MONGO_DB_NAME` | 否 | `MiloAgent` |
| `USE_MONGO_PERSISTENCE` | 否 | `false` |
| `JWT_SECRET_KEY` | 否 | 开发环境自动生成 |
| `JWT_ALGORITHM` | 否 | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 否 | `1440` |
| `SANDBOX_TIMEOUT_HOURS` | 否 | `24` |
| `TAVILY_API_KEY` | 否 | — |

## 沙盒生命周期

- 每个线程独享一个隔离的 OpenSandbox 实例（`opensandbox/code-interpreter:v1.0.2`）
- 沙盒在后台自动续期（默认 24 小时超时）
- 服务重启时通过 Redis 映射重连已有沙盒
- 删除线程或关闭服务时自动清理对应沙盒
- 沙盒初始化时通过三层回退自动安装 **pip**（内置 pip → `ensurepip` → `apt-get`）

## Skill 系统

Skill 是安装到沙盒 `/skills/` 目录的 zip 包：

1. Agent 调用 `install_skill`，传入 Skill 名称和下载链接
2. zip 包下载后上传到沙盒并解压
3. 安装记录按用户维度存储在 Redis 中
4. 沙盒销毁重建后自动恢复该用户的所有已安装 Skill

> [!NOTE]
> Skill 产生的系统状态（如 `apt-get install`）不会在沙盒重建后保留 — 仅保留安装记录，需要重新执行系统级操作。

