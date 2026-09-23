# CampusClaw · 迭代 1

CampusClaw 集中管理班级教学材料。本版本建立身份、角色和班级数据边界，为后续检索与智能助手提供可靠数据基础。

教师可登录、查看并上传本班 `.txt` / `.md` 材料；学生只可查看和下载本班材料。正文与材料记录保存在 SQLite，列表来自数据库查询。班级与角色由服务端会话判定，客户端提交的 `class_id` 不改变结果。跨班按 ID 读取或下载统一返回 404，与不存在的材料同形；学生上传返回 403。

## 从零启动

需要 Python 3.10+、Docker Engine 与 Compose v2，在仓库根目录执行以下命令。初始化脚本生成随机密钥和三个独立的演示密码，`.env` 权限为 `0600`；已有文件时会拒绝覆盖。也可复制 `.env.example` 后手工填写。不要提交 `.env`。

```sh
python3 scripts/setup_env.py
docker compose up --build -d --wait
docker compose ps
```

访问 <http://localhost:8080/login>。三个预置用户名为 `teacher_a`、`student_a1`、`student_b1`；密码是你在 `.env` 中分别设置的值。访问 <http://localhost:8080/health> 应得到 `{"status":"ok"}`。首次启动会建立 A/B 班、三个账号和两班可区分的材料。重复启动不会覆盖账号或上传内容。

Linux 用户若没有 Docker socket 权限，在 `docker` 命令前加 `sudo`。CLab 需要先运行 `clabcli connect` 登录校园网关。如果 Docker Hub 超时，可首次生成配置时使用 `python3 scripts/setup_env.py --python-image public.ecr.aws/docker/library/python:3.12-slim`；已有 `.env` 则只修改其中的 `PYTHON_IMAGE`，保留原密钥和密码。该来源是 [AWS 托管的 Docker 官方镜像](https://aws.amazon.com/blogs/containers/docker-official-images-now-available-on-amazon-elastic-container-registry-public/)。

服务只绑定宿主机 `127.0.0.1:8080`。在远程 Linux 上运行时，从自己的电脑建立 SSH 隧道（替换密钥路径和服务器地址）：

```sh
ssh -i /path/to/key.pem -N -L 18080:127.0.0.1:8080 ubuntu@SERVER_IP
```

保持终端开启，浏览器访问 <http://localhost:18080/login>。在服务器仓库目录用 `less .env` 查看演示账号密码。初始化后的密码保存在数据库哈希字段中，修改 `.env` 不会重置已有账号密码。

数据保存在 Compose 命名 volume `campusclaw_data` 和 `campusclaw_uploads` 中，实际名称默认带项目名前缀。`docker compose down` 后再 `docker compose up -d --wait` 不会删除数据。不要使用 `down -v` 做持久化验证；该命令会删除 volume 中的数据。

## 容器验收

在服务健康后执行，`before` 会上传一份合成 Markdown 验收材料并保存校验信息；`after` 检查三个账号、材料正文、下载哈希和知识库记录在重建后保留。每次重新运行 `before` 会新增一份验收材料。

```sh
docker compose exec -T app python -m scripts.verify_deployment before
docker compose down
docker compose up -d --wait
docker compose exec -T app python -m scripts.verify_deployment after
```

两阶段还会检查未登录 401、学生上传 403 且无副作用、非法格式 400、班级参数篡改无效、跨班详情与下载 404，以及本班列表可见。结果输出为 `PASS`；详细实测及同学交叉验收事项见 [第三课验收记录](docs/week03-verification.md)。

## 本地开发与测试

使用 Python 3.10+，安装 `requirements-dev.txt` 后设置同样的环境变量。`python -m pytest -q` 运行所有自动化验收；`python -m flask --app wsgi run --port 8080` 在本机启动开发服务器。首次运行需要三个预置密码。需要单独初始化时，从仓库根目录运行 `python -m scripts.init_db`；该命令重复执行不会复制样本数据。`openspec validate --all --strict` 校验当前正式规格。

迭代 1 已完成 Apply、Verify、Sync 与 Archive，正式规格见 [auth-upload](openspec/specs/auth-upload/spec.md)，规划、设计及 26 项完成任务见 [归档变更](openspec/changes/archive/2026-09-23-add-auth-rbac-class-knowledge/)。

受保护接口为 `GET /api/me`、`GET/POST /api/materials`、`GET /api/materials/<id>`、`GET /api/materials/<id>/file`。登录使用 `POST /api/login`，登出使用 `POST /api/logout`。上传表单字段名为 `file`。未登录访问接口返回 401，未登录访问材料页面重定向到登录页。数据库故障时业务接口返回 503；`/health` 仍只检查进程存活。文件只能经鉴权接口下载，`uploads/` 不作为静态目录暴露。单文件上限由 `MAX_UPLOAD_BYTES` 控制。

本版本为单实例 Compose 演示。本学期不做家长端、多校区运营和学科交易市场；本次迭代不做检索问答、RAG、对话助手、作业提交与批改、注册与 SSO、平台超级管理员、PDF/Word/图片解析、多副本或公网部署。
