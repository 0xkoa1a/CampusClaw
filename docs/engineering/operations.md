# 部署运维规范

## 配置与环境

- 从仓库根目录按 `docs/running.md` 配置和启动；私有 `.env` 不提交，权限保持 `0600`。新环境优先用 `python3 scripts/setup_env.py`，已有 `.env` 不覆盖。
- 当前 `.env.example` 包含 `RABBITMQ_USER`、`RABBITMQ_PASSWORD`、`TASK_MAX_ATTEMPTS`、`TASK_LEASE_SECONDS` 和 `TASK_RETRY_BASE_SECONDS`；`RABBITMQ_PASSWORD` 必须由部署者填入私有配置。应用可读 `RABBITMQ_URL`，也可由用户名、密码和 `RABBITMQ_HOST` 组成连接地址；启动前核对 app、worker 与 Compose 的配置映射。
- 必需 key 缺失或格式错误时启动失败并指出变量名，不打印其值。密钥轮换后同步更新应用与相应 MCP/队列服务，再验证旧凭据失效。
- Flask、SQLite、Qdrant、MCP 与 RabbitMQ 各自使用外置配置；服务地址用 Compose 内部 DNS，凭据用环境变量/私有密钥文件，不写入镜像层。
- 现有 `/health` 只表示 Flask 进程存活，不代表 Qdrant、网关、MCP 或 RabbitMQ 可用。各依赖故障应在对应功能和 worker 运行状态中单独观察。

## 日志与观测

- 新增异步路径输出一行一条 JSON，至少含时间、级别、请求/任务标识、事件名、耗时和结果状态；不得写令牌、Cookie、密钥或完整学生正文。
- 当前差距：Flask HTTP 错误日志标为**红**。源码中的数据库异常处理器调用 `app.logger.error("database unavailable: %s", error)`，未见 JSON 字段或请求标识；运行时采样待补。只有捕获实际日志并核对字段后才能更新判定。
- 监测 Flask 错误、SQLite 故障、Qdrant/MCP 依赖错误；异步路径另监测队列长度、消费速率、任务耗时、重试次数、过期租约和死信数。
- 告警阈值按部署环境配置并记录。队列持续增长或死信增加时保留样例任务 ID 与错误类别，避免把“容器启动”当作业务成功。

## 发布、备份与回滚

- 发布前记录版本/镜像摘要、目标 Compose 项目与目录；先在隔离环境启动并检查 `/health`、登录、核心读写和依赖连接，再安排目标环境更新。
- 部署前执行 `docker compose config -q`；验收后用 `docker compose up --build -d --wait` 发布并记录 `docker compose ps`。目标部署目录、Compose 项目名和当前运行镜像摘要必须明确。
- 更新 SQLite schema 前备份一致数据库快照、上传文件、当前镜像标识和私有 `.env`；备份放在部署目录之外的新目录并限制访问。恢复演练核对表计数与文件哈希。
- `scripts/backup_deployment.py` 接受明确的 `--deployment-dir`、`--backup-dir`、`--container`；它目前写入固定的历史镜像标签 `before-week05-20261014`。使用前先确认该标签不会覆盖或冒充当前回滚点，并核对 `manifest.json` 中镜像摘要和备份内容。
- 迁移采用可重复的增量步骤。发布失败时先停新 worker，恢复记录的上一版源码/镜像及必要的数据快照，再执行 `docker compose up -d --build --wait`，验证 `/health`、登录和核心读写；不得用 `docker compose down -v` 回滚。
- CLab 当前第六课验收环境位于 `verification/week06/`。未经隔离验收和备份，不覆盖该环境或旧数据卷；课程新版本的目标目录与 Compose 项目须在发布记录中明确。
- 发布记录写明操作者、时间、版本、备份位置、迁移结果、健康检查、回滚点和未完成验证。第 8 课 SEC-01 至 SEC-07 基线只记录观察结果；第 9、10 课修复标为暂缓。
