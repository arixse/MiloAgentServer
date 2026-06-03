# MiloAgent

基于 LangGraph 的 Deep Agent 服务，搭配 React 前端聊天界面。支持流式输出、工具调用可视化、代码沙盒执行和 Skill 动态安装。

## 架构

```
┌─────────────────────┐     SSE 流式      ┌──────────────────────────┐
│   React 前端 (Vite)  │ ◄──────────────► │   FastAPI 后端 (Python)   │
│   port 5173          │   REST + JWT     │   port 8000              │
└─────────────────────┘                   └──────────┬───────────────┘
                                                     │
                              ┌──────────────────────┼──────────────────────┐
                              │                      │                      │
                         ┌────▼────┐          ┌──────▼──────┐        ┌─────▼─────┐
                         │  Redis   │          │   MongoDB    │        │ OpenSandbox│
                         │ 元数据   │          │ checkpoint   │        │ 代码执行   │
                         │ sandbox  │          │ store/记忆   │        │ 沙盒      │
                         └─────────┘          └─────────────┘        └───────────┘
```

### 三层存储

| 存储层 | 技术 | 内容 | 持久化 |
|--------|------|------|--------|
| 线程元数据 | Redis | thread_id、user_id、sandbox 映射、skill 记录 | ✅ |
| 对话/记忆 | MongoDB | LangGraph checkpoint（消息历史）、Store（长期记忆） | ✅ |
| 进程内存 | Python dict | agent 实例热缓存、sandbox 后端引用 | ❌ 重启丢失 |

## 技术栈

| 层 | 技术 |
|----|------|
| **后端框架** | FastAPI + Uvicorn |
| **Agent 框架** | LangGraph + DeepAgents |
| **LLM** | DeepSeek (可替换为任意 OpenAI-compatible 模型) |
| **沙盒** | [OpenSandbox](http://182.254.183.29:8080) |
| **持久化** | Redis + MongoDB |
| **认证** | JWT (access token) |
| **前端** | React 19 + TypeScript + Tailwind CSS 4 + Vite |
| **Markdown 渲染** | react-markdown + remark-gfm + rehype-highlight |
| **部署** | Docker Compose |

## 项目结构

```
├── src/
│   ├── main.py                          # FastAPI 入口 + 生命周期管理
│   ├── model_provider.py                # LLM 模型配置
│   ├── api/
│   │   └── chat.py                      # /threads, /runs, /state API
│   ├── auth/
│   │   ├── router.py                    # /auth 注册/登录
│   │   ├── security.py                  # JWT 生成与验证
│   │   ├── models.py                    # 用户模型
│   │   └── dependencies.py              # get_current_user 依赖
│   ├── deep_agent/
│   │   ├── graph.py                     # Agent 工厂、线程管理、MongoDB 持久化
│   │   ├── opensandbox_backend.py       # OpenSandbox 沙盒后端（创建/重连/清理）
│   │   ├── sandbox.py                   # LangSmith sandbox 后端（备选）
│   │   ├── sub_agents.py                # 子 agent 定义
│   │   └── test.py                      # OpenSandbox 测试脚本
│   ├── tools/
│   │   ├── file_tool.py                 # 文件读写、PDF/Markdown 保存、下载 URL
│   │   ├── install_skill.py             # Skill 动态下载安装
│   │   ├── search_tool.py               # 搜索工具
│   │   ├── mcp_tool.py                  # MCP 工具集成
│   │   └── sandbox_utils.py             # 沙盒获取、skill 记录管理
│   └── utils/
│       └── path.py                      # 项目根路径工具
├── client/                              # React 前端
│   └── src/
│       ├── components/chat/             # 聊天组件
│       │   ├── ChatArea.tsx             # 主区域（含工具调用开关）
│       │   ├── MessagesList.tsx         # 消息列表（按顺序渲染 blocks）
│       │   ├── AssistantMessage.tsx     # AI 消息（Markdown + 工具调用）
│       │   ├── HumanMessage.tsx         # 用户消息
│       │   ├── ToolCallDisplay.tsx      # 工具调用卡片（参数/结果展开）
│       │   ├── ChatInput.tsx            # 输入框（Enter 发送、停止按钮）
│       │   └── EmptyState.tsx           # 空状态
│       ├── contexts/
│       │   ├── StreamContext.tsx         # 流式消息状态管理（Block 模型）
│       │   └── ThreadContext.tsx         # 线程列表管理
│       ├── hooks/                       # useStream, useAutoScroll, useThreads
│       ├── api/                         # API 调用（fetch SSE stream）
│       └── lib/                         # 类型定义、工具函数
├── AGENTS.md                            # Agent 系统提示词
├── Dockerfile                           # 后端镜像构建
├── docker-compose.yml                   # 完整环境 (app + Redis + MongoDB)
└── .github/workflows/build-image.yml    # CI 自动构建镜像
```

## 前置条件

- **Python 3.11+** + [Poetry](https://python-poetry.org/) 或 pip
- **Redis** — 线程元数据、sandbox 映射、skill 记录
- **MongoDB** — LangGraph checkpoint + store 持久化
- **OpenSandbox** — 代码执行沙盒服务（地址配置在 `.env` 中）
- **Node.js 20+** — 前端开发

### 本地数据库

```
MySQL:      root:123456@localhost:3306
Redis:      localhost:6379
MongoDB:    localhost:27017
PostgreSQL: root:123456@localhost:5432
```

## 快速开始

### 1. 环境变量

复制并编辑 `.env`：

```bash
cp .env.example .env
```

关键配置项：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENSANDBOX_API_KEY` | OpenSandbox API 密钥 | — |
| `REDIS_HOST` | Redis 地址 | localhost |
| `MONGO_URI` | MongoDB 连接串 | mongodb://localhost:27017 |
| `USE_MONGO_PERSISTENCE` | 启用 MongoDB 持久化 | false |
| `JWT_SECRET_KEY` | JWT 签名密钥 | (自动生成) |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | — |
| `SANDBOX_TIMEOUT_HOURS` | 沙盒存活时间 | 24 |

### 2. Docker Compose（推荐）

```bash
docker compose up -d
```

启动后：
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

### 3. 本地开发

**后端**：

```bash
# 安装依赖
pip install -r requirements.txt

# 启动
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

**前端**：

```bash
cd client
npm install
npm run dev        # http://localhost:5173
```

## API 端点

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 用户注册 |
| POST | `/api/auth/login` | 用户登录（返回 JWT） |
| GET | `/api/auth/me` | 获取当前用户信息 |

### 线程

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/threads` | 创建新线程 |
| GET | `/api/threads` | 列出当前用户的线程 |
| GET | `/api/threads/{id}` | 查询线程信息 |
| DELETE | `/api/threads/{id}` | 删除线程（同时销毁沙盒） |

### 运行

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/threads/{id}/runs` | 非流式运行 agent |
| POST | `/api/threads/{id}/runs/stream` | **SSE 流式运行**（前端使用） |
| GET | `/api/threads/{id}/state` | 读取线程状态/消息历史 |

### SSE 事件类型

流式端点返回以下事件：

| type | 说明 |
|------|------|
| `message` | AI 文本增量 + 工具调用/工具调用增量 |
| `tool_result` | 工具执行结果 |
| `done` | 流结束 |
| `error` | 错误信息 |

## 前端功能

- **JWT 认证**：注册/登录，token 自动附带
- **线程管理**：创建、切换、删除对话线程
- **流式输出**：SSE 实时渲染 AI 回复（Markdown + 代码高亮）
- **工具调用可视化**：可展开查看参数和结果，支持三种状态（运行中/完成/错误）
- **按序穿插**：工具调用和 AI 文本按实际发生顺序交错显示
- **简洁模式**：一键开关工具调用显示，中间思考过程始终可见
- **自动滚动**：用户手动上滚时不强制跳底
- **停止生成**：随时中断 AI 回复

## 工具系统

Agent 可用的内置工具：

| 工具 | 说明 |
|------|------|
| `search` | 网络搜索 |
| `read_file` | 读取沙盒文件（支持 PDF/Markdown/DOCX/XLSX/PPTX/TXT） |
| `save_to_markdown` | 保存文本为 Markdown 文件 |
| `save_to_pdf` | 保存文本为 PDF 文件 |
| `generate_download_url` | 生成沙盒文件的公开下载链接 |
| `install_skill` | 从 URL 下载安装 Skill |
| MCP 工具 | 通过 MCP 协议集成的外部工具 |

### Skill 系统

- Skill 通过 `install_skill` 工具从 URL 下载 zip 包并解压到 `/skills/` 目录
- 安装记录按用户维度存储在 Redis 中
- 沙盒意外销毁重建后自动恢复该用户的所有已安装 Skill

## 沙盒

- 每个线程独占一个 OpenSandbox 沙盒实例
- 默认使用 `opensandbox/code-interpreter:v1.0.2` 镜像
- 沙盒初始化时自动确保 pip 可用（三层回退：内置 pip → ensurepip → apt-get）
- 支持通过 Redis 映射重连已有沙盒（服务重启后恢复）
- 后台线程自动续期，默认 24 小时超时
- 线程删除/服务关闭时自动清理沙盒

## 认证流程

```
用户注册/登录 → JWT access_token → 存入 localStorage
    ↓
所有 API 请求携带 Authorization: Bearer <token>
    ↓
后端 get_current_user 依赖校验 → 绑定 user_id
    ↓
线程/沙盒按 user_id 隔离，禁止跨用户访问
```
