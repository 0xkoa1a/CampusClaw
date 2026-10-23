# 运行与开发

在仓库根目录执行本文命令。Mac 保存源码和提交材料，通过 SSH 访问 CLab。CLab 是部署环境，GitHub 保存代码与文档版本；推送代码后，CLab 需要拉取并重建才能运行新版本。

## CLab 当前目录

远端项目统一放在 `/home/ubuntu/workspace/campusclaw/`。

| 相对目录 | 用途 |
| --- | --- |
| `verification/week06/` | 当前运行的第六课验收环境，端口 18086 |
| `deployments/campusclaw-yyx/` | 已停止的旧部署 |
| `backups/` | 数据备份与迁移前配置 |
| `archives/verification/`、`archives/evidence/` | 旧验收环境与历史证据 |
| `archives/packages/`、`archives/macos-metadata/` | 压缩包与 macOS 元数据归档 |

当前环境在 `verification/week06/` 运行 `sudo docker compose ps`、`sudo docker compose up -d --wait`。Compose 已固定项目名 `campusclaw-week06-20261021`，沿用原数据卷。旧部署项目名为 `campusclaw-yyx`，保持停止状态。目录内的 README 和 `relocation-20261023.json` 记录具体入口与旧新路径对应关系。

2026-10-23 迁移时逐项核对文件内容、权限和大小，全部保留；重建容器后，3 个账号、6 份材料、13 个切片、7 个应用、7 个技能、6 个会话、12 条消息、6 份调用记录和 3 条 MCP 审计计数一致。私有 `.env` 仍为 0600。迁移后登录、读取已有回答、刷新和退出验证通过，见[服务截图](evidence/deployment/remote-workspace.png)。历史验收文档中的旧路径保留为当时执行记录。

## 从零启动

需要 Python 3.10+、Docker Engine 与 Compose v2，在仓库根目录执行以下命令。初始化脚本生成随机密钥和三个独立的演示密码，`.env` 权限为 `0600`；已有文件时会拒绝覆盖。也可复制 `.env.example` 后手工填写。不要提交 `.env`。

```sh
python3 scripts/setup_env.py
# 在私有 .env 中填写课程网关提供的 EMBEDDING_API_KEY；不要提交或贴出密钥。
docker compose up --build -d --wait
docker compose ps
docker compose exec -T app python -m scripts.reindex_all
docker compose exec -T app python -m scripts.verify_retrieval
```

访问 <http://localhost:8080/login>。三个预置用户名为 `teacher_a`、`student_a1`、`student_b1`；密码是你在 `.env` 中分别设置的值。访问 <http://localhost:8080/health> 应得到 `{"status":"ok"}`。首次启动会建立 A/B 班、三个账号和两班可区分的材料。重复启动不会覆盖账号或上传内容。

第 4 课配置见 `.env.example`：网关 Base URL 只到 `/v1`，向量模型 `course-embedding`，对话模型 `course-chat`，维度 `2048`。登录[课程网关](https://ai-gateway.devops.hello1023.com/)后将自己的 API Key 填入仓库根目录的私有 `.env`，保持文件权限 `0600`。升级第三课数据库时会自动增加切片表并为旧材料建立关键词索引；上面的 `reindex_all` 命令负责为旧材料生成向量。上传失败的向量索引可在教师界面重试，原始材料不会因此丢失。Qdrant 数据保存在独立命名 volume，不开放宿主机端口。

Qdrant 镜像默认来自[官方 GitHub Container Registry](https://github.com/qdrant/qdrant/pkgs/container/qdrant%2Fqdrant)。Docker Hub 不通时可使用该来源；如需其他来源，在 `.env` 设置 `QDRANT_IMAGE`。

`scripts.verify_retrieval` 使用预置 A/B 班演示材料和 `scripts.verify_deployment` 生成的合成材料检查真实网关、三种检索、引用、班级隔离及 Qdrant point；运行前会逐字核对材料正文，遇到其他材料立即退出，避免将真实课程材料用于验收查询。

Linux 用户若没有 Docker socket 权限，在 `docker` 命令前加 `sudo`。CLab 需要先运行 `clabcli connect` 登录校园网关。如果 Docker Hub 超时，可首次生成配置时使用 `python3 scripts/setup_env.py --python-image public.ecr.aws/docker/library/python:3.12-slim`；已有 `.env` 则只修改其中的 `PYTHON_IMAGE`，保留原密钥和密码。该来源是 [AWS 托管的 Docker 官方镜像](https://aws.amazon.com/blogs/containers/docker-official-images-now-available-on-amazon-elastic-container-registry-public/)。

服务只绑定宿主机 `127.0.0.1:8080`。在远程 Linux 上运行时，从自己的电脑建立 SSH 隧道（替换密钥路径和服务器地址）：

```sh
ssh -i /path/to/key.pem -N -L 18080:127.0.0.1:8080 ubuntu@SERVER_IP
```

保持终端开启，浏览器访问 <http://localhost:18080/login>。在服务器仓库目录用 `less .env` 查看演示账号密码。初始化后的密码保存在数据库哈希字段中，修改 `.env` 不会重置已有账号密码。

数据保存在 Compose 命名 volume `campusclaw_data`、`campusclaw_uploads` 和 `campusclaw_vectors` 中，实际名称默认带项目名前缀。`docker compose down` 后再 `docker compose up -d --wait` 不会删除数据。不要使用 `down -v` 做持久化验证；该命令会删除 volume 中的数据。

## 容器验收

在服务健康后执行，`before` 会上传一份合成 Markdown 验收材料并保存校验信息；`after` 检查三个账号、材料正文、下载哈希和知识库记录在重建后保留。每次重新运行 `before` 会新增一份验收材料。

```sh
docker compose exec -T app python -m scripts.verify_deployment before
docker compose down
docker compose up -d --wait
docker compose exec -T app python -m scripts.verify_deployment after
```

两阶段还会检查未登录 401、学生上传 403 且无副作用、非法格式 400、班级参数篡改无效、跨班详情与下载 404，以及本班列表可见。结果输出为 `PASS`；详细实测及同学交叉验收事项见 [第三课验收记录](week03-verification.md)。

## MCP 与应用配置

新增安装会自动生成 `MCP_AUTH_TOKEN`；已有 `.env` 需补一个独立随机值。Compose 将该值注入主应用和 MCP 服务，MCP 不对宿主机开放端口。主应用只允许登记 `MCP_ALLOWED_BASE_URLS` 中的地址，默认是 `http://mcp-demo:8090`。新增服务器可使用独立的 `MCP_...` 令牌环境变量，需同时注入应用容器。

教师在 `/conversations` 点击“安装内置应用与技能”，重复安装不会覆盖已有同名配置。在 `/mcp` 登记服务器名 `campus-tools` 和上述地址，令牌变量名填 `MCP_AUTH_TOKEN`。连接成功应看到 `calculate`、`unit_convert`；将 `calculate@campus-tools` 或 `unit_convert@campus-tools` 写入技能工具字段，再把技能绑定到应用。

教师可以在 `/mcp` 查看本班工具审计。用户在会话侧栏展开调用记录，查看自己的实际模型请求与返回；该记录可能包含个人提问和材料片段，只在合成验收环境导出到 Git。外部工具记录与最终生成都由服务端鉴权，前端不保存 MCP 令牌。

第六课的 HTTP 服务是 tools 能力教学子集，提供 initialize、tools/list、tools/call，没有实现 resources、prompts、远端采样和完整会话恢复。真实合成验证入口为 `scripts.verify_week06` 与 `scripts.verify_week06_rag_scope`，前者要求全新的测试数据，不能在正式资料上运行。

## 本地开发与测试

使用 Python 3.10+，安装 `requirements-dev.txt` 后设置同样的环境变量。`python -m pytest -q` 运行所有自动化验收；`python -m flask --app wsgi run --port 8080` 在本机启动开发服务器。首次运行需要三个预置密码。需要单独初始化时，从仓库根目录运行 `python -m scripts.init_db`；该命令重复执行不会复制样本数据。`openspec validate --all --strict` 校验当前正式规格。

正式规格入口见[仓库首页](../README.md#规约与目录)，检索实测见[第四课验收记录](week04-verification.md)。

受保护接口为 `GET /api/me`、`GET/POST /api/materials`、`GET /api/materials/<id>`、`GET /api/materials/<id>/file`。登录使用 `POST /api/login`，登出使用 `POST /api/logout`。上传表单字段名为 `file`。未登录访问接口返回 401，未登录访问材料页面重定向到登录页。数据库故障时业务接口返回 503；`/health` 仍只检查进程存活。文件只能经鉴权接口下载，`uploads/` 不作为静态目录暴露。单文件上限由 `MAX_UPLOAD_BYTES` 控制。

网页登录通过 JSON 请求 `auth_mode=bearer`，取得 JWT 并在 API 请求中发送 `Authorization: Bearer ...`。token 保存在当前标签页的 sessionStorage；Cookie 继续支持页面和普通下载链接。服务端校验 JWT 后还查询有效 session，权限来自数据库；退出时同时撤销旧 JWT 和 Cookie。API 登录省略 auth_mode 时仍使用 Cookie，没有 JavaScript 的表单登录也保留。规范见 [Bearer 认证](../openspec/specs/bearer-auth/spec.md)。

## 提交材料维护

更新截图或报告后运行同步脚本；五份文字答案直接维护在提交目录。文件映射保存在 [submission-manifest.json](classroom/submission-manifest.json)，上传入口见[提交材料](classroom/提交材料/README.md)。

```sh
python3 scripts/prepare_classroom_submission.py
python3 scripts/prepare_classroom_submission.py --check
```

## 检索 API

第 4 课接口：`POST /api/search` 接受 `{"q":"...","mode":"keyword|vector|hybrid","limit":10,"offset":0}`，默认为混合检索；`POST /api/ask` 接受问题和可选 `history`；教师用 `POST /api/materials/<id>/reindex` 传入可选的 `strategy`（`type` 为 `auto`、`delimiter` 或 `markdown`，`max_chars` 为 100–2000，`overlap` 不超过 50%）。检索和回答只访问会话所属班级。网关或 Qdrant 故障时关键词检索仍能使用，向量、混合和回答返回 503。

当前 Compose 通过 SSH 隧道访问；学期最终的互联网部署要求见[课程要求](classroom/requirements.md#学期项目交付)。
