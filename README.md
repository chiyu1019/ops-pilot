# OpsPilot

> 企业级智能对话和运维助手，支持 RAG 知识库问答和 AIOps 智能诊断

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![LangChain](https://img.shields.io/badge/LangChain-latest-orange.svg)](https://www.langchain.com/)

## ✨ 核心特性

- 🤖 **智能对话** - LangChain 多轮对话 + 流式输出
- 📚 **RAG 问答** - 向量检索增强，支持文档上传、自动建立向量索引、自动更新知识库
- 🔧 **AIOps 诊断** - Plan-Execute-Replan 自动故障诊断和根因分析
- 🌐 **Web 界面** - 现代化 UI，支持多种对话模式：快速问答/流式对话
- 🔌 **MCP 集成** - 日志查询和监控数据工具接入

## 🛠️ 技术栈

- **框架**: FastAPI + LangChain + LangGraph
- **LLM**: 阿里云 DashScope (通义千问)
- **向量库**: Milvus
- **工具协议**: MCP (Model Context Protocol)

## 🚀 快速开始

### 环境要求
- Python 3.10+
- 阿里云 DashScope API Key ([获取地址](https://dashscope.aliyun.com/))

### 安装和启动

#### Linux/macOS 环境

```bash
# 1. 克隆项目
git clone <repository_url>
cd super_biz_agent_py

# 2. 安装依赖（推荐使用 uv）
# 方式 1: 使用 uv（推荐，更快）
pip install uv
uv venv
source .venv/bin/activate
uv pip install -e .

# 方式 2: 使用 pip
pip install -e .

# 3. 编辑配置文件
# 首次使用需要编辑 .env 文件，填入你的 DASHSCOPE_API_KEY
vim .env  # 或使用其他编辑器

# 4. 一键初始化（启动 Docker + 服务 + 上传文档）
make init

# 5. 一键启动
make start
```

#### Windows 环境（PowerShell/CMD）

如果Windows 不支持 `make` 命令，可以手动执行以下步骤以启动服务：

```powershell
# 1. 克隆项目
git clone <repository_url>
cd super_biz_agent_py

# 2. 创建虚拟环境并安装依赖
# 方式 1: 使用 uv（推荐，更快）
pip install uv
# 创建虚拟环境
uv venv
# 激活虚拟环境
.venv\Scripts\activate
# 安装所有依赖
uv pip install -e .

# 方式 2: 使用 pip
python -m venv .venv
.venv\Scripts\activate
pip install -e .

# 3. 编辑配置文件
# 使用记事本或其他编辑器打开 .env 文件，填入你的 DASHSCOPE_API_KEY
notepad .env

# 4. 启动 Docker Desktop
# 确保 Docker Desktop 已安装并正在运行

# 5. 启动 Milvus 向量数据库（Docker Compose）
docker compose -f vector-database.yml up -d

# 6. 等待 Milvus 启动完成（约 5-10 秒）
timeout /t 10

# 7. 启动 MCP 服务
# 启动 CLS 日志查询服务（新开一个 PowerShell 窗口）
python mcp_servers/cls_server.py

# 启动 Monitor 监控服务（新开一个 PowerShell 窗口）
python mcp_servers/monitor_server.py

# 8. 启动 FastAPI 主服务（新开一个 PowerShell 窗口）
# 注意：日志会自动输出到 logs\app_YYYY-MM-DD.log
python -m uvicorn app.main:app --host 0.0.0.0 --port 9900

# 9. 上传文档到向量库（新开一个 PowerShell 窗口）
# 等待服务启动完成后执行
timeout /t 5
python -c "import requests, os, time; [requests.post('http://localhost:9900/api/upload', files={'file': open(f'aiops-docs/{f}', 'rb')}) or time.sleep(1) for f in os.listdir('aiops-docs') if f.endswith('.md')]"
```

**Windows 一键启动脚本**（推荐）

使用启动脚本：

```powershell
# 启动所有服务
.\start-windows.bat

# 停止所有服务
.\stop-windows.bat
```

### 访问服务
- **Web 界面**: http://localhost:9900
- **API 文档**: http://localhost:9900/docs

## 📡 API 接口

### 核心接口

| 功能 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 普通对话 | POST | `/api/chat` | 一次性返回 |
| 流式对话 | POST | `/api/chat_stream` | SSE 流式输出 |
| AIOps 诊断 | POST | `/api/aiops` | 自动故障诊断（流式） |
| 文件上传 | POST | `/api/upload` | 上传并索引文档 |
| 健康检查 | GET | `/api/health` | 服务状态检查 |

### 使用示例

```bash
# 普通对话
curl -X POST "http://localhost:9900/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"Id":"session-123","Question":"你好"}'

# 流式对话
curl -X POST "http://localhost:9900/api/chat_stream" \
  -H "Content-Type: application/json" \
  -d '{"Id":"session-123","Question":"你好"}' \
  --no-buffer

# AIOps 诊断
curl -X POST "http://localhost:9900/api/aiops" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"session-123"}' \
  --no-buffer
```

## 📁 项目结构

```
super_biz_agent_py/
├── app/                                    # 应用核心
│   ├── __init__.py                         # 包初始化（自动加载日志配置）
│   ├── main.py                             # FastAPI 应用入口
│   ├── config.py                           # 配置管理（环境变量、MCP 服务器配置）
│   ├── api/                                # API 路由层
│   │   ├── __init__.py
│   │   ├── chat.py                         # 对话接口（RAG 聊天）
│   │   ├── aiops.py                        # AIOps 接口（故障诊断）
│   │   ├── file.py                         # 文件管理（文档上传）
│   │   └── health.py                       # 健康检查（服务状态）
│   ├── services/                           # 业务服务层
│   │   ├── __init__.py
│   │   ├── rag_agent_service.py            # RAG Agent（LangGraph 状态图）
│   │   ├── aiops_service.py                # AIOps 服务（计划-执行-重规划）
│   │   ├── vector_store_manager.py         # 向量存储管理器
│   │   ├── vector_embedding_service.py     # 向量embedding服务
│   │   ├── vector_index_service.py         # 向量索引服务
│   │   ├── vector_search_service.py        # 向量检索服务
│   │   └── document_splitter_service.py    # 文档分割服务
│   ├── agent/                              # Agent 模块
│   │   ├── __init__.py
│   │   ├── mcp_client.py                   # MCP 客户端（工具调用）
│   │   └── aiops/                          # AIOps 核心逻辑
│   │       ├── __init__.py
│   │       ├── planner.py                  # 计划制定器
│   │       ├── executor.py                 # 步骤执行器
│   │       ├── replanner.py                # 重规划器
│   │       ├── state.py                    # 状态定义
│   │       └── utils.py                    # 工具函数
│   ├── models/                             # 数据模型层
│   │   ├── __init__.py
│   │   ├── aiops.py                        # AIOps 模型
│   │   ├── document.py                     # 文档模型
│   │   ├── request.py                      # 请求模型
│   │   └── response.py                     # 响应模型
│   ├── tools/                              # Agent 工具集
│   │   ├── __init__.py
│   │   ├── knowledge_tool.py               # 知识库查询工具
│   │   └── time_tool.py                    # 时间工具
│   ├── core/                               # 核心组件
│   │   ├── __init__.py
│   │   ├── llm_factory.py                  # LLM 工厂（模型管理）
│   │   └── milvus_client.py                # Milvus 客户端
│   └── utils/                              # 工具类
│       ├── __init__.py
│       └── logger.py                       # 日志配置（Loguru）
├── static/                                 # Web 前端（纯静态）
│   ├── index.html                          # 主页面
│   ├── app.js                              # 前端逻辑
│   └── styles.css                          # 样式表
├── mcp_servers/                            # MCP 服务器
│   ├── cls_server.py                       # CLS 日志查询服务
│   ├── monitor_server.py                   # 监控数据服务
│   └── README.md                           # MCP 服务说明
├── aiops-docs/                             # 运维知识库（Markdown 文档）
├── logs/                                   # 日志目录（Loguru 自动创建）
│   └── app_YYYY-MM-DD.log                  # 按天轮转的日志文件
├── uploads/                                # 上传文件临时目录
├── volumes/                                # Milvus 数据持久化目录
├── .env                                    # 环境变量配置（需手动创建）
├── Makefile                                # 项目管理命令（Linux/macOS）
├── start-windows.bat                       # Windows 启动脚本
├── stop-windows.bat                        # Windows 停止脚本
├── vector-database.yml                     # Milvus Docker Compose 配置
├── pyproject.toml                          # 项目配置（依赖、元数据）
├── uv.lock                                 # uv 依赖锁定文件
├── pyrightconfig.json                      # Pyright 类型检查配置
└── README.md                               # 项目说明
```

## ⚙️ 配置说明

通过 `.env` 文件配置：

```bash
# 阿里云LLM DashScope 配置（必填）
# 秘钥管理： https://bailian.console.aliyun.com/cn-beijing/?spm=5176.29597918.J_SEsSjsNv72yRuRFS2VknO.2.61ac133ccTVQLw&tab=demohouse#/api-key
DASHSCOPE_API_KEY=your-api-key （配置你自己的秘钥）
DASHSCOPE_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1  # 不配置则默认会使用新加坡站点
DASHSCOPE_MODEL=qwen-max

# Milvus 配置
MILVUS_HOST=localhost
MILVUS_PORT=19530

# RAG 配置
RAG_TOP_K=3
CHUNK_MAX_SIZE=800
CHUNK_OVERLAP=100
```

## 🎯 AIOps 智能运维

基于 **Plan-Execute-Replan** 模式实现自动故障诊断。

### 核心特性
- ✅ 自动制定诊断计划（Planner）
- ✅ 智能工具调用（Executor）
- ✅ 动态调整步骤（Replanner）
- ✅ 流式输出诊断过程
- ✅ 生成结构化报告

### 快速测试

```bash
# 服务已通过 make init 自动启动
# 如需重启服务：make restart

# 访问 Web 界面，点击"智能运维与诊断工具"
# 或使用 API
curl -X POST "http://localhost:9900/api/aiops" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test"}' \
  --no-buffer
```

### 诊断流程
```
1. Planner 制定计划 → 生成 4-6 个诊断步骤
2. Executor 执行步骤 → 调用 MCP 工具（日志查询、监控数据）
3. Replanner 评估结果 → 决定继续/调整/生成报告
4. 输出诊断报告 → 根因分析 + 运维建议
```

## 📝 开发指南

### 常用命令

```bash
# 项目管理
make init              # 一键初始化（Docker + 服务 + 文档）
make start             # 启动所有服务
make stop              # 停止所有服务
make restart           # 重启所有服务

# 依赖管理
make install-dev       # 安装开发依赖
make sync              # 同步依赖

# Docker 管理
make up                # 启动 Docker 容器
make down              # 停止 Docker 容器

# 代码质量
make format            # 格式化代码
make lint              # 代码检查
```


## 🐛 常见问题

### Windows 环境问题

#### 1. `make` 命令不可用
Windows 不支持 `make` 命令，请使用提供的批处理脚本：
```powershell
# 启动服务
.\start-windows.bat

# 停止服务
.\stop-windows.bat
```

#### 2. PowerShell 执行策略限制
如果遇到 "无法加载文件，因为在此系统上禁止运行脚本" 错误：
```powershell
# 临时允许脚本执行（管理员权限）
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

# 或者使用 CMD 而不是 PowerShell
cmd
.\start-windows.bat
```

#### 3. 端口被占用（Windows）
```powershell
# 查看占用端口的进程
netstat -ano | findstr :9900

# 结束进程（替换 PID 为实际进程 ID）
taskkill /F /PID <PID>
```

### 通用问题

### API Key 错误
```bash
# 检查环境变量
cat .env | grep DASHSCOPE_API_KEY    # Linux/macOS
type .env | findstr DASHSCOPE_API_KEY  # Windows
```

### Milvus 连接失败
```bash
# 确保本机有 Docker 服务并且已经启动（可以使用 Docker Desktop）

# 检查 Milvus 状态
docker ps | grep milvus

# 重启 Milvus（使用 docker compose）
docker compose -f vector-database.yml restart

# 或者重启单个服务
docker compose -f vector-database.yml restart standalone
```

### 服务无法启动

**Linux/macOS:**
```bash
# 查看服务日志
tail -f logs/app_$(date +%Y-%m-%d).log  # FastAPI 主服务（Loguru 日志）
tail -f mcp_cls.log                      # CLS MCP 服务
tail -f mcp_monitor.log                  # Monitor MCP 服务

# 检查端口占用
lsof -i :9900  # FastAPI
lsof -i :8003  # CLS MCP
lsof -i :8004  # Monitor MCP
```

**Windows:**
```powershell
# 查看服务日志（获取今天的日期）
$today = Get-Date -Format "yyyy-MM-dd"
type logs\app_$today.log  # FastAPI 主服务（Loguru 日志）
type mcp_cls.log          # CLS MCP 服务
type mcp_monitor.log      # Monitor MCP 服务

# 或者查看最新的日志文件
Get-ChildItem logs\*.log | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Get-Content -Tail 50

# 检查端口占用
netstat -ano | findstr :9900  # FastAPI
netstat -ano | findstr :8003  # CLS MCP
netstat -ano | findstr :8004  # Monitor MCP
```

## 📚 参考资源

- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [LangChain 文档](https://python.langchain.com/)
- [LangGraph Plan-Execute](https://langchain-ai.github.io/langgraph/tutorials/plan-and-execute/)
- [阿里云 DashScope](https://dashscope.aliyun.com/)
- [MCP 协议](https://modelcontextprotocol.io/)

## 📄 许可证
author： chiyu1019

MIT License

## 🧪 测试与评测

```bash
# 单元测试（无需 Milvus / API Key，纯逻辑）
make test          # 或 .venv\Scripts\python -m pytest tests/

# 集成测试（需要 Milvus 已启动；未启动时自动跳过）
.venv\Scripts\python -m pytest tests/ -m "" 

# RAG 检索准确率评测（需要 Milvus + 已上传文档 + 有效 API Key）
python scripts/eval_rag.py                          # 默认 top_k=3
python scripts/eval_rag.py --sweep-topk 1,2,3,5,8   # TopK 参数扫描对比
python scripts/eval_rag.py --min-accuracy 0.85      # 低于 85% 以非零码退出
```

## 🐳 Docker 一键部署

```bash
# 1. 配置环境变量（参考 .env.example，填入 DASHSCOPE_API_KEY）
copy .env.example .env

# 2. 一键启动全栈（Milvus + 2×MCP + FastAPI）
docker compose up -d --build

# 3. 访问
# Web 界面: http://localhost:9900
# API 文档: http://localhost:9900/docs

# 停止
docker compose down
```

> 注意：
> - `docker compose up` 与 `docker compose -f vector-database.yml up` 不要同时运行
> - Milvus 单机版需要约 4GB+ 内存，低配云主机需评估
> - 容器内 MCP 服务通过 `MCP_HOST` / `MCP_PORT` 环境变量监听

## 🔐 安全说明

- `.env` 已加入 `.gitignore`，禁止提交；API Key 只写在本地 `.env`
- 首次克隆后执行 `copy .env.example .env` 并填写真实值
- 若曾误提交过密钥，请立即在云控制台轮换该 Key

## 📌 当前状态说明

- **对话 / RAG**：真实实现（Milvus + DashScope embedding + LangChain Agent + 多轮记忆）
- **AIOps 诊断**：Plan-Execute-Replan 真实编排；CLS 日志与监控 MCP 当前返回模拟数据，可替换为真实 API（见 `mcp_servers/README.md`）；Prometheus 告警查询为真实 HTTP 调用
- **会话记忆**：支持 memory / redis / postgres 三种后端（`MEMORY_BACKEND` 切换），生产环境可用 Redis / Postgres 持久化

## 🚀 推送到 GitHub

```bash
# 1. 在 GitHub 网页创建空仓库（不要勾选 README/LICENSE），例如命名为 ops-pilot
# 2. 关联远程仓库（二选一）
git remote add origin https://github.com/<你的用户名>/ops-pilot.git
# 或 SSH：git remote add origin git@github.com:<你的用户名>/ops-pilot.git

# 3. 推送
git branch -M main
git push -u origin main

# 之后每次修改
git add -A
git commit -m "描述本次改动"
git push
```

> 安全提醒：`.env` 已加入 `.gitignore`，推送前可用 `git check-ignore .env` 确认密钥不会被提交。


## 🧠 会话记忆持久化（Redis / Postgres）

默认使用进程内 MemorySaver（重启后丢失）。需要持久化时切换后端：

**1. Redis（推荐，轻量）**

- `.env` 设置 `MEMORY_BACKEND=redis`
- Docker 模式已内置 Redis Stack（`opspilot-redis`，宿主机端口 6380，容器内 `redis://redis:6379/0`）
- 注意：`langgraph-checkpoint-redis` 依赖 RediSearch，必须使用 Redis Stack 镜像；本地模式需自行安装并配置 `REDIS_URL`

**2. Postgres（生产级）**

- `.env` 设置 `MEMORY_BACKEND=postgres`
- Docker 模式已内置 Postgres（`opspilot-postgres`，`POSTGRES_DSN=postgresql://postgres:postgres@postgres:5432/langgraph`）
- 首次启动会自动创建 checkpoint 数据表

改完 `.env` 后执行 `docker compose up -d` 重建应用即可生效。

验证方式：聊天产生会话后 `docker compose restart app`，再次打开同一会话，历史仍在（对话与 AIOps 使用独立命名空间，互不覆盖）。


## 🚨 自动响应与闭环沉淀

**自动响应**：应用启动后后台轮询 Prometheus（每 `ALERT_POLL_INTERVAL` 秒），发现新的 firing 告警自动触发 AIOps 诊断；也支持 Alertmanager/云监控 Webhook 推送（`POST /api/webhook/alerts`）。同一告警在 `ALERT_COOLDOWN_SECONDS` 冷却期内不重复诊断，侧边栏"自动响应"面板通过 SSE 实时展示"收到告警 -> 自动诊断 -> 报告完成"。

**闭环沉淀**：每次诊断成功生成报告后，自动把「告警信息 + 执行步骤 + 工具结果 + 报告」总结成 Markdown 知识条目写入向量库（`generated/<告警名>-<指纹>.md`，同指纹覆盖更新）。下一次同类告警进来时，planner 会检索到这份经验，诊断更快更准——系统越用越聪明。

### 快速验证

```bash
# 1. 查看/推送告警事件（页面侧边栏"自动响应"面板实时显示）
curl http://localhost:9900/api/alerts/events
curl -N http://localhost:9900/api/alerts/stream

# 2. Webhook 推送一条新告警（自动触发诊断，约 1-2 分钟出报告）
curl -X POST http://localhost:9900/api/webhook/alerts -H "Content-Type: application/json" -d '{"status":"firing","alerts":[{"labels":{"alertname":"ServiceUnavailable","severity":"critical","instance":"checkout-service"},"annotations":{"description":"服务不可用"}}]}'

# 3. 向 mock Prometheus 注入一条新告警（下一次轮询自动触发）
curl -X POST http://localhost:9090/api/v1/alerts/trigger -H "Content-Type: application/json" -d '{"alertname":"DiskFull","instance":"log-service"}'

# 4. 验证闭环沉淀：诊断完成后检索知识库
docker compose exec app python -c "from app.services.vector_store_manager import vector_store_manager; docs = vector_store_manager.similarity_search('HighCPUUsage 告警处理经验', k=10); print([d.metadata.get('_source') for d in docs if d.metadata.get('_generated')])"
```

> 关闭开关：`.env` 中 `AUTO_RESPONSE_ENABLED=false` / `KNOWLEDGE_DISTILL_ENABLED=false`。


## 🔀 混合检索（向量 + BM25 + RRF 融合）

单一向量检索的短板：告警名、错误码、指标名这类精确 token 容易被"语义近似"带偏。
因此知识检索走**双路召回 + 融合重排**：

```
query ─┬─> Milvus 向量召回（语义，cosine/L2）  ─┐
       └─> Elasticsearch BM25 召回（关键词）   ─┴─> RRF / 归一化融合 ─> Top-K ─> LLM
```

- **融合方式一：RRF（推荐）** `score = Σ w_i / (k + rank_i)`，默认 `k=60`；
  不需要跨检索器对齐分数尺度，对异常分数鲁棒
- **融合方式二：归一化** 向量距离转相似度 → min-max 归一化 → `alpha*向量 + (1-alpha)*BM25`，
  可以按业务侧重某一路
- **降级策略**：ES 不可用或 BM25 召回失败时自动退回纯向量检索，问答不中断
- **索引同步**：文档上传与闭环沉淀（诊断经验回写）都会同时写入 Milvus 与 ES；
  重复上传先按来源删除旧分片再写新分片

### 配置

```bash
HYBRID_ENABLED=true          # 关闭则退化为纯向量检索
ES_URL=http://localhost:9200 # Docker 模式由 compose 注入 http://elasticsearch:9200
ES_INDEX=opspilot_knowledge
HYBRID_FUSION=rrf            # rrf | normalize
HYBRID_RRF_K=60              # RRF 常数
HYBRID_RECALL_K=10           # 每路候选数量（融合前）
HYBRID_VECTOR_WEIGHT=0.7     # RRF 中向量权重（BM25 占 1-0.7）
HYBRID_ALPHA=0.5             # normalize 模式下向量权重
```

### 实测数据（本项目，2026-09-22）

评测环境：真实 Milvus + Elasticsearch 索引（含 15 篇强干扰文档），
配置 `HYBRID_FUSION=rrf`、`HYBRID_VECTOR_WEIGHT=0.7`、`HYBRID_RECALL_K=10`。

**Golden Set（45 题，`tests/data/golden_set_45.json`）**

| 模式 | Recall@1 | Recall@3 | Recall@5 | Recall@8 | 平均耗时 |
|------|----------|----------|----------|----------|----------|
| vector（纯向量） | 82.22% | 97.78% | 100.0% | 100.0% | 211ms |
| bm25（纯关键词） | 53.33% | 86.67% | 88.89% | 91.11% | 56ms |
| hybrid-rrf（向量权重 0.7） | 84.44% | 95.56% | 100.0% | 100.0% | 220ms |

**高难度集（14 题，`tests/data/hard_queries.json`：改写型 / 易混淆型 / 多跳型）**

| 模式 | Recall@1 | Recall@3 | Recall@5 | Recall@8 | 平均耗时 |
|------|----------|----------|----------|----------|----------|
| vector（纯向量） | 81.82% | 100.0% | 100.0% | 100.0% | 299ms |
| bm25（纯关键词） | 18.18% | 18.18% | 18.18% | 54.55% | 64ms |
| hybrid-rrf（向量权重 0.7） | 45.45% | 54.55% | 90.91% | 100.0% | 194ms |

**向量权重扫描（高难度集，`--modes hybrid-rrf`）**

| HYBRID_VECTOR_WEIGHT | 0.5 | 0.7 | 0.85 | 0.95 |
|----------------------|-----|-----|------|------|
| Recall@3 | 63.64% | 72.73% | 72.73% | 100.0% |

调参结论：

- 45 题 Golden Set 上三种模式 **Recall@5 都是 100%**，指标已饱和、看不出差异；换成改写型 / 易混淆型的高难度集差距才暴露出来
- **BM25 延迟最低（约 56ms，只有向量检索的 1/4）**，但高难度集 Recall@3 只有 18.18%，改写型提问基本失效，只能作为召回补充，不能当主力
- **混合检索会被 BM25 的噪声拖累**：高难度集向量权重 0.7 时 Recall@3 只有 54.55%（低于纯向量 100%），把 `HYBRID_VECTOR_WEIGHT` 提到 0.95 才追平纯向量（100%）。当前默认仍是 0.7（通用场景更均衡），高难度场景可在 `.env` 中调高
- 单次运行存在 1~2 题的波动（Recall@1 最明显，权重扫描那行与上表 0.7 行的差异即来自两次运行），结论看趋势、不看单点

> 早先的 11 题语义集（`tests/data/rag_eval_questions.json`）与 8 题关键词集（`tests/data/hybrid_eval_keyword.json`）仍保留在仓库，可用 `--questions` 参数复现。

复现命令：

```bash
python scripts/eval_recall.py --save
python scripts/eval_recall.py --questions tests/data/hard_queries.json --save

# 权重扫描（Windows PowerShell 用 $env:HYBRID_VECTOR_WEIGHT="0.95"）
HYBRID_VECTOR_WEIGHT=0.95 python scripts/eval_recall.py --questions tests/data/hard_queries.json --modes hybrid-rrf
```

## 🔔 飞书通知（告警自动诊断结果推送）

诊断完成后可自动把结构化诊断结果推送到飞书群，形成「**告警 → Agent诊断 → 飞书通知 → 人工处理**」的闭环。

### 触发规则（重要）

| 入口 | source | 是否推送飞书 |
|---|---|---|
| 告警自动响应（Webhook / 轮询触发） | `alert_auto` | ✅ 推送 |
| 前端 Chat / 智能运维按钮（用户主动） | `user_chat` | ❌ 只返回前端展示 |

### 配置

```bash
# 飞书群 → 设置 → 群机器人 → 添加机器人 → 自定义机器人 → 复制 Webhook 地址
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxx
# 若机器人开启了"签名校验"，填写密钥；否则留空
FEISHU_SECRET=
FEISHU_TIMEOUT=5.0
NOTIFICATION_ENABLED=true
# 幂等窗口（秒）：同一会话 + 同一告警 + 同一状态在该窗口内只发一次
NOTIFICATION_IDEMPOTENCY_TTL=900
```

未配置 `FEISHU_WEBHOOK_URL` 时：打 warning 日志、跳过发送、**不影响 Agent 运行**。

### 消息形态

优先使用 **interactive 卡片**，包含 9 个字段：告警名称 / 告警级别 / 影响服务 / 故障现象 / 分析结论 / 关键证据 / 处理建议 / Agent执行状态 / 生成时间。

- 卡片头部颜色按级别映射（critical=红、warning=橙、info=蓝）
- 状态为 `hypothesis` / `safe_report` 时头部置灰并在标题标注，提示人工复核
- 关键证据来自证据链 `evidence_id` 映射（可追溯到具体工具调用）
- 长文本自动截断，避免超出飞书长度限制

### 架构

```
Agent（Planner/Executor/Replanner/Diagnose）
        │  仅 alert_auto 触发
        ▼
notification/          ← 独立通知模块（不侵入 Agent 节点）
├── __init__.py        # 导出 notification_service
├── schemas.py         # DiagnosisNotification / NotificationResult
├── feishu.py          # 卡片渲染 + Webhook 发送 + 签名
└── service.py         # 渠道注册 / 来源过滤 / 幂等保护
        ▼
FeishuWebhook
```

- 注入点：`aiops_service.execute()` 收尾处（与知识沉淀并列），**不在 Planner/Executor/Replanner/MCP 阶段发送**
- 通知异常全部被捕获：日志 `feishu notification failed`，主流程照常返回诊断报告
- 幂等保护：同一 (来源, 会话, 告警, 状态) 在 TTL 窗口内只发送一次
- 日志关键字：成功 `feishu notification sent successfully`，失败 `feishu notification failed`（便于接入 Langfuse 观测）

### 验证

```bash
pytest tests/test_feishu_notification.py tests/test_notification_integration.py -q
```