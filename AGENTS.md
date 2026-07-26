# MiloAgent

## 项目概述

MiloAgent 是一个基于 LangGraph / DeepAgents 的深度 AI Agent 服务，集成 OpenSandbox 代码执行沙盒。你作为 Agent 运行在此沙盒环境中。

## 沙盒环境

- **操作系统**: Linux (Debian/Ubuntu)
- **Python**: 3.11（默认解释器）
- **Node.js**: 20
- **Go**: 1.24
- **Java**: 17
- **包管理器**: pip、npm、apt-get
- **工作目录**: `/`

## 文件约定

| 路径 | 用途 |
|------|------|
| `/home/user/` | 用户工作目录，建议在此创建项目文件 |
| `/tmp/` | 临时文件，沙盒销毁后不保留 |
| `/skills/` | 已安装的 Skill 目录（只读，由系统管理） |
| `/memories/` | 长期记忆目录（跨会话持久化，通过 MongoDB 备份恢复） |
| `/AGENTS.md` | 本文件 |

## 建议实践

- 优先使用 Python 编写脚本和工具，异步代码优先
- 安装 Python 包前先检查是否已安装：`python3 -c "import xxx"` 失败后再 pip install
- 生成的文件（PDF、Excel、图片等）放在 `/tmp/` 目录，便于用户下载
- Node.js 项目使用 `npm` 管理依赖，Go 项目使用 `go mod`
- 避免执行危险命令（rm -rf /、fork bomb、修改系统配置等）
- 长时间运行的任务注意设置合理的超时时间

## 工具与能力

你可以使用以下内置工具：

| 工具 | 说明 |
|------|------|
| 文件操作 | 读写沙盒中的文件 |
| 搜索工具 | Tavily 联网搜索 |
| 图表工具 | @antv/mcp-server-chart 生成图表 |
| Skill 安装 | 动态安装扩展技能包 |
| 文件下载 | 将沙盒中的文件提供给用户下载 |

## 长期记忆

`/memories/` 目录中的内容会在沙盒销毁后通过 MongoDB 持久化，重建沙盒时自动恢复。建议在此存储用户偏好、项目上下文等需要跨会话保留的信息。

## 约束

- 这是一个 Web 服务环境，避免直接访问宿主机文件系统
- 生成的下载链接通过 API 返回给用户，有效期与 JWT token 一致
- 沙盒有存活时间限制（默认 24 小时），后台线程会自动续期
