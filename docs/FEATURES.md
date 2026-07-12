# MiloAgent 产品功能文档

## 目录

1. [产品概述](#1-产品概述)
2. [用户认证系统](#2-用户认证系统)
3. [多模态对话引擎](#3-多模态对话引擎)
4. [文件处理系统](#4-文件处理系统)
5. [网络搜索与信息采集](#5-网络搜索与信息采集)
6. [代码执行沙盒](#6-代码执行沙盒)
7. [Skill 插件系统](#7-skill-插件系统)
8. [长期记忆系统](#8-长期记忆系统)
9. [子 Agent 协作系统](#9-子-agent-协作系统)
10. [线程管理系统](#10-线程管理系统)
11. [MCP 工具集成](#11-mcp-工具集成)
12. [容器化部署](#12-容器化部署)

---

## 1. 产品概述

MiloAgent 是一个基于 LangGraph / DeepAgents 框架的深度 AI Agent 服务，提供类 OpenAI/LangGraph 兼容的 REST API。核心能力包括：多模态对话、代码执行、文件处理、网络搜索、Skill 插件、长期记忆和子 Agent 协作。

### 技术架构

```
┌──────────────┐     ┌──────────────────────────────────────┐
│  React 前端   │────▶│  FastAPI 后端 (src/main.py)          │
│  (client/)   │     │  ├─ /api/threads/*  线程 & 对话       │
└──────────────┘     │  ├─ /api/auth/*     用户认证          │
                     │  └─ 静态资源托管（生产模式）           │
                     ├──────────────────────────────────────┤
                     │  Deep Agent 层                       │
                     │  ├─ DeepSeek 模型 (ChatOpenAI)       │
                     │  ├─ OpenSandbox 代码沙盒             │
                     │  ├─ 子 Agent 协作                    │
                     │  └─ Skill 插件 & MCP 工具            │
                     ├──────────────────────────────────────┤
                     │  基础设施                            │
                     │  ├─ MongoDB (checkpoint/store/线程)   │
                     │  ├─ Redis (sandbox 映射/skill 记录)  │
                     │  └─ MinIO (文件存储)                  │
                     └──────────────────────────────────────┘
```

---

## 2. 用户认证系统

### 功能描述

基于 JWT 的用户注册/登录系统，密码使用 bcrypt 哈希存储，用户数据持久化到 MongoDB。每个用户拥有独立的沙盒环境、线程列表和长期记忆。

### 预期效果

| 场景 | 预期行为 |
|------|----------|
| 新用户注册 | 创建唯一 `user_id`，密码 bcrypt 哈希后存入 MongoDB `users` 集合，用户名唯一索引防重复 |
| 用户登录 | 验证密码，返回 JWT access token（默认 24h 有效期） |
| 未认证访问 | 受保护 API 返回 401 Unauthorized |
| Token 过期 | 返回 401，前端自动跳转登录页 |
| 用户名重复 | 注册时返回 409 Conflict |

### API

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/api/auth/register` | 无 | 注册，返回 token |
| POST | `/api/auth/login` | 无 | 登录，返回 token |
| GET | `/api/auth/me` | Bearer | 获取当前用户信息 |

### 验证方法

```bash
# 1. 注册新用户
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test_user","password":"test123456"}'
# 预期: 返回 {"access_token":"eyJ...", "user_id":"uuid", "username":"test_user"}

# 2. 重复注册（验证唯一性）
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test_user","password":"other"}'
# 预期: 409 Conflict

# 3. 登录
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test_user","password":"test123456"}'
# 预期: 返回 JWT token

# 4. 获取用户信息
curl http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer <token>"
# 预期: {"user_id":"...","username":"test_user","created_at":"..."}

# 5. 错误密码
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test_user","password":"wrong"}'
# 预期: 401 Unauthorized
```

---

## 3. 多模态对话引擎

### 功能描述

提供两种对话模式：非流式（完整返回）和流式（SSE 逐字输出）。支持工具调用（tool calls）的实时推送。对话历史通过 MongoDB checkpoint 持久化，服务重启不丢失。

### 预期效果

| 场景 | 预期行为 |
|------|----------|
| 非流式对话 | 等待 Agent 完整执行后一次性返回所有消息 |
| 流式对话 (SSE) | 逐 chunk 推送文本内容，tool_call 实时通知前端展示工具执行状态 |
| 工具调用 | Agent 自动识别需要调用的工具，执行后展示结果 |
| 对话恢复 | 同一 thread_id 再次对话时可访问历史上下文 |
| 错误处理 | Agent 执行异常返回 500 及错误详情，流式模式推送 `{"type":"error"}` 事件 |

### API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/threads/{id}/runs` | 非流式运行 |
| POST | `/api/threads/{id}/runs/stream` | SSE 流式运行 |
| GET | `/api/threads/{id}/state` | 读取对话状态（消息历史） |

### 验证方法

```bash
# 1. 创建线程
thread_id=$(curl -s -X POST http://localhost:8000/api/threads \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' | jq -r '.thread_id')

# 2. 非流式对话
curl -X POST "http://localhost:8000/api/threads/$thread_id/runs" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"你好，请介绍一下你自己"}],"stream":false}'
# 预期: 返回 messages 数组，包含 assistant 的完整回复

# 3. 流式对话
curl -N -X POST "http://localhost:8000/api/threads/$thread_id/runs/stream" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"写一首关于AI的短诗"}],"stream":true}'
# 预期: 逐行输出 SSE 事件，最后收到 {"type":"done"}

# 4. 查看状态（验证历史持久化）
curl "http://localhost:8000/api/threads/$thread_id/state" \
  -H "Authorization: Bearer $TOKEN"
# 预期: 返回完整消息历史，包含之前的对话
```

---

## 4. 文件处理系统

### 功能描述

支持多种文件格式的读取和生成，所有操作在沙盒中执行。文件读取自动解析为纯文本供 Agent 理解，文件生成后可通过签名 URL 下载。

### 4.1 文件读取

| 格式 | 解析方式 |
|------|----------|
| `.pdf` | pdfplumber 逐页提取文本 |
| `.docx` | python-docx 提取段落 |
| `.xlsx` / `.xls` | openpyxl 逐 sheet 导出为 TSV |
| `.pptx` | python-pptx 逐 slide 提取文本 |
| `.md` / `.txt` / `.csv` / `.json` / `.py` 等 | UTF-8 解码 |

### 4.2 文件生成

| 格式 | 生成方式 | 特性 |
|------|----------|------|
| `.md` | 直接写入 | 保存 Agent 输出为 Markdown |
| `.pdf` | fpdf2 生成 | 自动检测 CJK 字体（中/日/韩），支持自动分页 |

### 4.3 文件下载

在沙盒内启动 HTTP 文件服务器，通过 OpenSandbox 的签名端点生成公网可访问的临时下载链接（1 小时有效）。

### 预期效果

| 场景 | 预期行为 |
|------|----------|
| 读取 PDF | 返回纯文本内容，保留原始排版结构 |
| 读取 Excel | 返回带 Sheet 名称的 TSV 格式文本 |
| 保存 Markdown | 文件写入沙盒 `/tmp/` 目录 |
| 保存 PDF | 生成可下载的 PDF，中文内容正常显示（有 CJK 字体时） |
| 生成下载链接 | 返回一个 HTTPS URL，1 小时内可直接下载文件 |
| 不支持的格式 | 尝试 UTF-8 解码，失败则报错 |

### 验证方法

```bash
# 在对话中测试（通过 Agent 的 read_file 工具）
# 发送消息让 Agent 读取一个测试 PDF/Excel 文件
curl -X POST "http://localhost:8000/api/threads/$thread_id/runs/stream" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"读取 /tmp/test.pdf 文件内容并总结"}],"stream":true}'

# 测试文件生成（让 Agent 生成报告并获取下载链接）
curl -X POST "http://localhost:8000/api/threads/$thread_id/runs/stream" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"生成一份关于AI发展的报告，保存为PDF并给我下载链接"}],"stream":true}'
```

---

## 5. 网络搜索与信息采集

### 功能描述

通过 Tavily API 进行网络搜索，支持关键词检索和网页内容抓取。搜索结果自动提取标题、URL 和摘要。网页抓取自动剥离 script/style/nav/footer 等无关内容，返回纯文本。

### 预期效果

| 场景 | 预期行为 |
|------|----------|
| 关键词搜索 | 返回最多 5 条结果，含标题、URL、内容摘要 |
| 网页抓取 | 返回页面正文纯文本，过滤掉脚本和导航栏 |
| 搜索无结果 | 返回 "未找到相关结果" |
| API Key 未配置 | 返回明确错误提示 |
| 网络异常 | 返回具体错误信息，不阻塞 Agent 继续执行 |

### 验证方法

```bash
# 通过 Agent 对话触发搜索
curl -X POST "http://localhost:8000/api/threads/$thread_id/runs/stream" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"搜索2024年诺贝尔物理学奖得主"}],"stream":true}'
# 预期: Agent 调用 search_tool → 返回搜索结果 → 基于结果生成回答

# 测试网页抓取
curl -X POST "http://localhost:8000/api/threads/$thread_id/runs/stream" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"打开 https://news.ycombinator.com 并总结今天的热门话题"}],"stream":true}'
# 预期: Agent 调用 fetch_content → 返回页面内容 → 总结热门话题
```

---

## 6. 代码执行沙盒

### 功能描述

基于阿里巴巴 OpenSandbox 的隔离代码执行环境。每个用户独享一个沙盒，支持 Python / Node.js / Java / Go 多语言执行。沙盒生命周期 24 小时，通过后台线程自动续期。文件系统在沙盒意外销毁后从 MongoDB 自动恢复。

### 核心能力

| 能力 | 说明 |
|------|------|
| 命令执行 | 在沙盒中执行任意 shell 命令，支持超时控制 |
| 文件读写 | 上传/下载沙盒内文件 |
| 多语言 | Python 3.11 / Node.js 20 / Java 17 / Go 1.24 |
| 自动续期 | 后台线程每 19.2h 自动续期（80% 存活时间） |
| 崩溃恢复 | 沙盒意外销毁后，从 Redis 映射重连或创建新实例，从 MongoDB 恢复文件 |

### 预期效果

| 场景 | 预期行为 |
|------|----------|
| 首次创建沙盒 | 约 30-60s（含镜像拉取），创建后初始化 pip/目录/AGENTS.md |
| 沙盒重连 | 服务重启后通过 Redis 映射重连已有沙盒，< 10s |
| 命令执行 | 超时自动中断，返回 exit_code 和输出 |
| 24h 自动续期 | 沙盒不会因超时被销毁 |
| pip 安装 | 自动检测并安装 pip（支持 apt-get / apk） |
| 沙盒销毁 | close() 自动备份关键文件到 MongoDB |

### 验证方法

```bash
# 1. 查看沙盒创建日志
# 服务启动后首次发送对话请求，观察日志输出：
# [milo.sandbox] 沙盒创建成功: <sandbox_id> timeout=24.0h
# [milo.sandbox] pip 已就绪: pip x.x.x
# [milo.sandbox] 已上传 AGENTS.md → /AGENTS.md

# 2. 测试代码执行（通过 Agent 对话）
curl -X POST "http://localhost:8000/api/threads/$thread_id/runs/stream" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"写一个Python函数计算斐波那契数列前20项并执行"}],"stream":true}'
# 预期: Agent 在沙盒中执行 Python 代码并返回结果

# 3. 验证沙盒重连（服务重启后）
# 重启服务 → 再次对话 → 观察日志：
# [milo.sandbox] 发现已有 sandbox 映射: user=xxx sandbox=xxx
# [milo.sandbox] 成功重连 sandbox: user=xxx sandbox=xxx
```

---

## 7. Skill 插件系统

### 功能描述

支持从三大平台安装 Skill 插件包，扩展 Agent 能力。Skill 安装记录持久化到 MongoDB，沙盒重建时自动恢复已安装的 Skill，无需重新下载。

### 支持的 Skill 来源

| 平台 | URL 示例 | 安装方式 |
|------|----------|----------|
| ClawHub | `https://clawhub.ai/chindden/skill-creator` | HTML 解析找 download 链接 |
| ModelScope | `https://modelscope.cn/skills/@anthropics/skill-creator` | Playwright 渲染页面后解析 |
| SkillHub | `https://skillhub.cn/skills/baidu-search` | 调用 API 获取下载链接 |

### 安装流程

```
下载 zip → 解析 SKILL.md 获取 skill name → 上传到沙盒解压
  → 持久化 zip 到 MongoDB → 记录到 Redis
  → 沙盒重建时自动从 MongoDB 恢复
```

### 预期效果

| 场景 | 预期行为 |
|------|----------|
| ClawHub 安装 | 自动识别页面下载链接，下载安装成功 |
| ModelScope 安装 | Playwright 渲染 JS 页面后提取链接，安装成功 |
| SkillHub 安装 | 通过 API 获取直链，安装成功 |
| 沙盒重建后 | 从 MongoDB 恢复所有已安装 Skill，无需重新下载 |
| 下载失败 | 返回具体错误信息，不阻塞 Agent |
| 无效链接 | 返回 "未找到 skill 下载链接" |

### 验证方法

```bash
# 通过 Agent 对话安装 Skill
curl -X POST "http://localhost:8000/api/threads/$thread_id/runs/stream" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"请从 https://clawhub.ai/... 安装这个 skill"}],"stream":true}'
# 预期: Agent 调用 install_skill_from_clawhub_url 工具 → 下载 → 安装成功

# 验证 Skill 恢复：删除 sandbox (或等其过期) → 新对话 → 检查 skill 是否自动恢复
```

---

## 8. 长期记忆系统

### 功能描述

基于 LangGraph StoreBackend，Agent 可以将关键信息持久化存储到 `/memories/` 目录。记忆按用户维度隔离，跨线程共享，存储在 MongoDB 中，不随沙盒销毁或服务重启而丢失。

### 预期效果

| 场景 | 预期行为 |
|------|----------|
| 写入记忆 | Agent 写入 `/memories/{user_id}/xxx.md`，持久化到 MongoDB Store |
| 读取记忆 | 不同线程、不同会话均可读取同一个用户的记忆 |
| 跨会话 | 用户关闭浏览器、重新打开后，记忆仍然可访问 |
| 用户隔离 | 用户 A 的记忆不能被用户 B 读取 |

### 验证方法

```bash
# 1. 线程A 中让 Agent 记住偏好
curl -X POST "http://localhost:8000/api/threads/$thread_A/runs" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"记住：我的名字是张三，我偏好简洁的回答风格"}],"stream":false}'

# 2. 新建线程B，验证跨线程记忆
curl -X POST "http://localhost:8000/api/threads/$thread_B/runs" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"我叫什么名字？我的回答风格偏好是什么？"}],"stream":false}'
# 预期: Agent 能准确回忆出"张三"和"简洁风格"
```

---

## 9. 子 Agent 协作系统

### 功能描述

内置 4 个专业子 Agent，Agent 在需要时自动将任务委派给子 Agent 执行：

| 子 Agent | 角色 | 职责 |
|----------|------|------|
| **researcher** (研究员) | 信息猎手 | 多跳推理，多轮深度搜索，提取原始信息 |
| **data_analyst** (数据分析师) | 数据大脑 | 多源交叉验证，数据推理，提炼核心洞察 |
| **report_writer** (报告撰写) | 笔杆子 | 按学术/商业报告格式撰写结构化长文 |
| **critic** (质检员) | 质量把关 | 事实核查，逻辑纠错，需求匹配评估 |

### 协作流程

```
用户请求 → 主 Agent 规划
  → researcher 搜集信息
    → data_analyst 分析提炼
      → report_writer 撰写报告
        → critic 审核 → 退回修改 / 批准发布
```

### 预期效果

| 场景 | 预期行为 |
|------|----------|
| 深度研究任务 | 主 Agent 自动调用 researcher 子 Agent 进行多轮搜索 |
| 数据分析任务 | data_analyst 对信息进行交叉验证和洞察提炼 |
| 报告生成 | report_writer 按学术格式输出结构化报告，含引用 |
| 质量把关 | critic 检查事实准确性和逻辑严密度，不合格则打回 |
| 简单任务 | 不触发子 Agent，主 Agent 直接回答 |

### 验证方法

```bash
# 触发深度研究流程
curl -X POST "http://localhost:8000/api/threads/$thread_id/runs/stream" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"帮我研究一下2024年AI Agent领域的主要进展，生成一份深度报告"}],"stream":true}'
# 预期:
# 1. SSE 流中看到子 Agent 的调用（tool_calls）
# 2. 最终输出包含结构化报告
# 3. 报告中包含信息来源引用
```

---

## 10. 线程管理系统

### 功能描述

完整的对话线程 CRUD，线程按用户隔离。元数据存储在 MongoDB 中，每个线程绑定到创建它的用户，跨请求进行归属校验。

### 预期效果

| 场景 | 预期行为 |
|------|----------|
| 创建线程 | 返回唯一 `thread_id`，绑定 `user_id`，写入 MongoDB |
| 列出线程 | 返回当前用户的所有线程（按创建时间倒序） |
| 查询线程 | 返回线程元数据 |
| 删除线程 | 清理 agent 缓存和 checkpoint，释放资源 |
| 跨用户访问 | 403 Forbidden（线程不属于当前用户） |
| 访问不存在的线程 | 404 Not Found |

### API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/threads` | 创建线程 |
| GET | `/api/threads` | 列出用户线程 |
| GET | `/api/threads/{id}` | 查询线程信息 |
| DELETE | `/api/threads/{id}` | 删除线程 |

### 验证方法

```bash
# 1. 创建线程
curl -X POST http://localhost:8000/api/threads \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"metadata":{"title":"测试对话"}}'
# 预期: {"thread_id":"uuid","user_id":"xxx","created_at":"...","metadata":{...}}

# 2. 列出线程
curl http://localhost:8000/api/threads \
  -H "Authorization: Bearer $TOKEN"
# 预期: 返回线程列表数组

# 3. 删除线程
curl -X DELETE "http://localhost:8000/api/threads/$thread_id" \
  -H "Authorization: Bearer $TOKEN"
# 预期: {"status":"deleted","thread_id":"xxx"}

# 4. 跨用户访问（用另一个用户的 token）
curl "http://localhost:8000/api/threads/$thread_id" \
  -H "Authorization: Bearer $OTHER_USER_TOKEN"
# 预期: 403 Forbidden
```

---

## 11. MCP 工具集成

### 功能描述

通过 MCP (Model Context Protocol) 协议集成外部工具。当前集成了 `@antv/mcp-server-chart` 图表生成工具，未来可扩展更多 MCP 服务。

### 预期效果

| 场景 | 预期行为 |
|------|----------|
| 图表生成 | Agent 自动调用 MCP chart 工具生成数据可视化图表 |
| MCP 服务不可用 | 工具调用返回错误，不阻塞 Agent 继续执行 |

### 验证方法

```bash
# 通过 Agent 对话触发图表生成
curl -X POST "http://localhost:8000/api/threads/$thread_id/runs/stream" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"生成一个柱状图展示2024年各季度AI融资数据：Q1=50亿 Q2=80亿 Q3=120亿 Q4=200亿"}],"stream":true}'
# 预期: Agent 调用 MCP chart 工具 → 返回图表
```

---

## 12. 容器化部署

### 功能描述

多阶段 Docker 构建 + Docker Compose 编排。前端使用 Bun 构建，后端 Python 3.11，通过 `docker compose` 一键部署。

### 服务组成

| 服务 | 镜像 | 端口 | 职责 |
|------|------|------|------|
| app | arixse/milo-agent | 8000 | FastAPI 应用（含前端静态资源） |
| redis | redis:7-alpine | 6379 | Sandbox 映射 & Skill 记录 |
| mongodb | mongo:7 | 27017 | Checkpoint / Store / 线程元数据 |

### 预期效果

| 场景 | 预期行为 |
|------|----------|
| 生产部署 | `docker compose up -d` 一键启动，服务自愈 (restart: unless-stopped) |
| 开发部署 | `docker compose -f docker-compose.dev.yml up -d --build` 本地构建 |
| 健康检查 | Redis/MongoDB 健康检查通过后 app 才启动 |
| 数据持久化 | Redis 和 MongoDB 数据挂载到 named volumes，重启不丢失 |

### 验证方法

```bash
# 1. 启动服务
docker compose up -d

# 2. 检查服务状态
docker compose ps
# 预期: 所有服务状态为 Up/healthy

# 3. 验证 API
curl http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"demo123"}'
# 预期: 正常返回

# 4. 查看日志
docker compose logs -f app
# 预期: 看到 MiloAgent 启动日志
```

---

## 附录：环境变量参考

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `MODEL_NAME` | ✅ | — | 模型名称 |
| `MODEL_BASE_URL` | ✅ | — | 模型 API 地址 |
| `MODEL_API_KEY` | ✅ | — | 模型 API 密钥 |
| `OPENSANDBOX_SERVER_URL` | ✅ | `http://182.254.183.29:8080` | 沙盒服务地址 |
| `OPENSANDBOX_API_KEY` | ✅ | — | 沙盒 API 密钥 |
| `SANDBOX_TIMEOUT_HOURS` | — | `24` | 沙盒存活时间 |
| `REDIS_HOST` | — | `localhost` | Redis 主机 |
| `REDIS_PORT` | — | `6379` | Redis 端口 |
| `REDIS_PASSWORD` | — | — | Redis 密码 |
| `MONGO_URI` | — | `mongodb://localhost:27017` | MongoDB 连接 |
| `MONGO_DB_NAME` | — | `MiloAgent` | 数据库名 |
| `JWT_SECRET_KEY` | ✅ | — | JWT 签名密钥 |
| `TAVILY_API_KEY` | — | — | 搜索 API 密钥 |
