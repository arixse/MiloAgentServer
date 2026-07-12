# MiloAgent 项目指南

## 项目概述

MiloAgent 是一个基于 LangGraph / DeepAgents 的深度 AI Agent 服务，集成 OpenSandbox 代码执行沙盒。提供兼容 LangGraph API 标准的 REST 接口，前端使用 React + TypeScript。

## 技术栈

| 层 | 技术 |
|---|------|
| 后端框架 | FastAPI (Python 3.11+) |
| Agent 框架 | LangGraph + DeepAgents |
| 模型 | ChatOpenAI 兼容接口 |
| 代码沙盒 | OpenSandbox (阿里巴巴) |
| 前端 | React + TypeScript + Vite + Bun |
| 数据库 | MongoDB (checkpoint / store / 线程元数据) |
| 缓存 | Redis (sandbox 映射 / skill 记录) |
| 对象存储 | MinIO |
| 认证 | JWT (python-jose + bcrypt) |
| 包管理 | uv |

## 项目结构

```
MiloAgent/
├── src/
│   ├── main.py                          # FastAPI 入口，生命周期管理
│   ├── model_provider.py                # DeepSeek 模型配置
│   ├── api/
│   │   └── chat.py                      # REST API (/api/threads, /api/.../runs)
│   ├── auth/
│   │   ├── router.py                    # 认证路由 (register/login)
│   │   ├── dependencies.py              # get_current_user 依赖注入
│   │   ├── security.py                  # JWT 创建/验证，密码哈希
│   │   └── models.py                    # 用户数据模型
│   ├── deep_agent/
│   │   ├── graph.py                     # Agent 工厂，thread 缓存，MongoDB 持久化
│   │   ├── opensandbox_backend.py       # OpenSandbox 后端（BackendProtocol 实现）
│   │   ├── sub_agents.py                # 子 Agent 定义（研究员/分析师/报告/审查）
│   │   └── sandbox.py                   # 旧版 sandbox 工具
│   ├── tools/
│   │   ├── file_tool.py                 # 文件操作工具
│   │   ├── mcp_tool.py                  # MCP 工具（@antv/mcp-server-chart）
│   │   ├── search_tool.py               # Tavily 搜索工具
│   │   ├── install_skill.py             # Skill 安装工具
│   │   └── sandbox_utils.py             # Sandbox 获取 & skill 追踪
│   └── utils/
│       └── path.py                      # 项目根路径工具
├── client/                              # React 前端
│   └── src/
│       ├── components/                  # UI 组件（chat/auth/layout/thread/ui）
│       ├── contexts/                    # React Context（Auth/Stream/Thread）
│       ├── hooks/                       # 自定义 hooks
│       └── api/                         # API 客户端
├── docker-compose.yml                   # 生产部署（app + redis + mongodb）
├── docker-compose.dev.yml               # 开发部署（本地构建）
├── Dockerfile                           # 多阶段构建（Bun 前端 + Python 后端）
├── pyproject.toml                       # Python 依赖 & 构建配置
└── .env                                 # 环境变量（不入库）
```

## 分支策略

- **`main`** — 生产主分支，只接受来自 `dev` 的合并
- **`dev`** — 开发分支，所有新功能在此开发，完成后合并入 `main`

```bash
# 开始新功能
git checkout dev
git checkout -b feature/xxx    # 可选：复杂功能开 feature 分支

# 开发完成后
git checkout main
git merge dev
git push origin main
```

## 核心架构

### Agent 生命周期

```
用户请求 → get_or_create_agent(thread_id, user_id)
  ├── 检查 _agent_cache（按 thread_id 缓存）
  ├── 未命中 → _build_agent(user_id)
  │     ├── get_or_create_sandbox(user_id)     # 每个用户一个 sandbox
  │     │     ├── 内存缓存 _backends
  │     │     ├── Redis 映射 → 尝试重连
  │     │     └── 都不行 → 创建新 sandbox + 初始化文件系统
  │     ├── CompositeBackend(
  │     │     default=OpenSandboxBackend,       # 代码执行
  │     │     routes={"/memories/": StoreBackend}  # 长期记忆
  │     │   )
  │     └── create_deep_agent(...)
  └── 返回 agent 实例
```

### Sandbox 持久化策略

1. **内存缓存** — `_backends: dict[user_id, OpenSandboxBackend]`，进程级缓存
2. **Redis 映射** — `user_id → sandbox_id`，用于跨重启重连
3. **MongoDB 备份** — 关键文件（AGENTS.md, memories/）在 sandbox 销毁前备份

### 线程归属

- 线程创建时绑定 `user_id` 写入 MongoDB
- 每次 API 请求通过 `_require_owner(thread_id, user_id)` 校验归属

## 本地开发

### 环境准备

```bash
# 安装依赖
uv sync

# 启动前端开发服务器（可选）
cd client && bun install && bun run dev
```

### 必需的外部服务

开发时 `.env` 指向远程服务器（`43.155.181.215`），也可以启动本地服务：

```bash
# 仅 API 模式（不启动前端）
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### 环境变量 (.env)

关键配置项（详见 `.env.example`）：
- `MODEL_NAME` / `MODEL_BASE_URL` / `MODEL_API_KEY` — 模型配置
- `OPENSANDBOX_SERVER_URL` / `OPENSANDBOX_API_KEY` — 沙盒服务
- `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` — Redis
- `MONGO_URI` / `MONGO_USERNAME` / `MONGO_PASSWORD` — MongoDB
- `JWT_SECRET_KEY` — JWT 签名密钥
- `TAVILY_API_KEY` — 搜索工具
- `MINIO_ENDPOINT` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` — 文件存储

## 代码约定

- 优先使用 async/await，工具和 I/O 操作都应是异步的
- 新工具应该低依赖、适合在远程服务器上运行
- 日志使用 `logging.getLogger("milo.xxx")` 命名空间
- API 端点设计对齐 LangGraph 标准接口（threads / runs / state）
- 类型注解使用 `from __future__ import annotations`

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/threads` | 创建线程 |
| GET | `/api/threads` | 列出用户线程 |
| GET | `/api/threads/{id}` | 查询线程信息 |
| DELETE | `/api/threads/{id}` | 删除线程 |
| POST | `/api/threads/{id}/runs` | 非流式运行 agent |
| POST | `/api/threads/{id}/runs/stream` | 流式运行 agent (SSE) |
| GET | `/api/threads/{id}/state` | 读取线程状态 |
| POST | `/auth/register` | 用户注册 |
| POST | `/auth/login` | 用户登录 |

## Docker 部署

```bash
# 生产模式（拉取镜像）
docker compose up -d

# 开发模式（本地构建）
docker compose -f docker-compose.dev.yml up -d --build
```
