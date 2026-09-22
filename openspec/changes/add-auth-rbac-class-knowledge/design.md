# Design

## Context

仓库目前只有 README、项目规则和 OpenSpec 规划制品，没有业务应用代码。行为要求由 `specs/auth-upload/spec.md` 定义。后续 Apply 阶段将在同一仓库中实现 CampusClaw 的最小可运行系统。

## Goals / Non-Goals

**Goals:**

- 建立能够携带用户角色和班级身份的登录会话。
- 在服务端统一执行角色授权和班级隔离，覆盖列表查询、按 ID 访问和上传写入。
- 让教师上传的文本材料经过解析后，以同一事务写入材料表和知识库表。
- 提供可复现的双班样本数据、Docker Compose 启动方式和健康检查。

**Non-Goals:**

- 本设计不包含 proposal 中列出的检索问答、对话助手、作业流程、SSO 和生产高可用能力。
- 本次规划不实现代码，不启动 Docker Compose，也不归档 change。

## Decisions

### Flask 与 SQLite

应用采用 Flask 3.x 和 SQLite 3。Flask 负责页面、会话和接口，SQLite 将课程演示需要的业务数据保存在单个文件中。Compose 内使用 gunicorn 监听 `0.0.0.0:8080`，本地开发可以使用 Flask 开发服务器。

该方案适合当前单实例教学项目，部署和验收成本较低。Node.js、Express 和 better-sqlite3 可以实现等价行为，但会改变后续任务中的依赖与运行命令，因此本 change 固定使用 Python 技术栈。

### 服务端签名会话

登录成功后，服务端创建带 HttpOnly 和 `SameSite=Lax` 属性的签名 cookie。会话至少保存 `user_id`、`role` 和 `class_id`。受保护页面缺少有效会话时跳转到 `/login`，受保护接口返回 HTTP 401。

会话签名使用的 `SECRET_KEY` 只从环境变量读取。应用启动时必须检查该变量，缺少时直接失败。相比 JWT，服务端签名会话更适合当前单体应用，也减少了令牌刷新和撤销设计。

### 密码哈希

用户表只保存 `password_hash`。初始化脚本使用 Werkzeug 提供的密码哈希函数，登录时调用对应的验证函数。该选择减少额外依赖，并满足单向哈希和恒定时间比较要求。若后续改用 bcrypt 或 Argon2，需要同时更新依赖、种子脚本和验证测试。

### 服务端班级隔离

所有材料和知识库查询都从会话读取 `class_id`，客户端提供的同名参数不能覆盖会话。列表查询必须带班级条件；按材料 ID 访问时同时校验记录所属班级。跨班按 ID 访问统一返回 HTTP 404，以免泄露资源是否存在。

数据访问层提供按班级读取材料的统一入口，业务路由不直接接收客户端传入的班级作为授权依据。新记录的班级也只取自教师会话。

### 数据模型与样本数据

SQLite 至少包含 `classes`、`users`、`lectures`、`assignments`、`assistants`、`skills`、`materials` 和 `knowledge_entries`。`users`、`materials` 与 `knowledge_entries` 保存 `class_id`；知识库记录同时保存对应的 `material_id`。

初始化脚本写入班级 A/B、教师 A、学生 A1/B1，并为两个班级分别加入标题可区分的样本材料。讲义、作业、助手和技能表在本 change 中只要求建立结构，可以保留少量占位数据。

### 上传与入库事务

上传接口只接受教师会话和 `.txt`、`.md` 文件。系统先校验扩展名、文件大小与空文件，再将文件写入 `uploads/<class_id>/` 下的安全文件名。解析成功后，同一数据库事务写入材料记录和知识库正文记录；事务提交后返回 HTTP 201 和材料 ID。

解析或数据库操作失败时，系统回滚事务并删除已经写入的文件。材料列表从数据库查询，不通过扫描上传目录生成。首版将全文保存为知识库正文，切片与向量索引留给后续检索 change。

### Docker Compose 与健康检查

仓库在 Apply 阶段增加 Dockerfile、`docker-compose.yml` 和 `.env.example`。Compose 暴露 `8080:8080`，挂载 `./data:/app/data` 与 `./uploads:/app/uploads`，并通过 `.env` 注入 `SECRET_KEY`。

应用提供无需登录的 `GET /health`，成功时返回 HTTP 200 和 `{"status":"ok"}`。Compose healthcheck 使用该接口判断服务是否就绪。应用首次启动时仅在数据库不存在的情况下执行初始化脚本，以保留容器重建前的数据。

### 模块边界

- `app/auth.py` 负责登录、登出和会话检查。
- `app/materials.py` 负责本班材料列表、按 ID 读取和教师上传。
- `app/knowledge.py` 负责文本解析与知识库记录写入。
- `app/db.py` 负责数据库连接、事务和带班级条件的数据访问。
- `scripts/init_db.py` 负责建表和样本数据。

## Risks / Trade-offs

- [SQLite 不适合多实例并发写入] → 当前项目限定为单实例课程演示；需要水平扩展时再迁移到 PostgreSQL。
- [上传文件可能包含恶意内容] → 首版只接收 `.txt` 和 `.md`，限制文件大小，使用安全文件名，并将上传目录与应用源码分离。
- [跨班响应可能泄露资源存在性] → 按 ID 的跨班访问统一返回 HTTP 404，响应不包含材料元数据。
- [文件落盘与数据库事务无法形成单一原子事务] → 数据库失败时主动删除新文件，并用失败场景测试孤立文件。

## Migration Plan

项目从零开始，无历史数据迁移。Apply 阶段依次完成应用骨架、数据库与样本数据、登录、班级隔离、上传入库、Compose 和验收。若部署失败，停止容器并恢复到最近一次通过验收的 Git 提交；持久化目录保留，不随容器删除。
