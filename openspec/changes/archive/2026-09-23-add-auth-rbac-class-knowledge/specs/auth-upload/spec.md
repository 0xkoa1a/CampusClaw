# Spec Delta

## Purpose

让教师与学生以各自角色登录 CampusClaw，以班级作为服务端数据边界隔离教学材料；教师上传的材料解析后写入知识库，本班成员通过材料列表查看，并拒绝未登录访问、学生上传和跨班访问。

## ADDED Requirements

### Requirement: 用户登录

系统 MUST 提供教师和学生两类角色的账号密码登录。登录成功后 MUST 建立会话；未登录用户访问受保护页面或接口时 MUST 被拒绝，且响应 MUST NOT 泄露业务数据。

#### Scenario: 教师与学生登录成功

- **WHEN** 教师 A、学生 A1 或学生 B1 使用有效账号和密码登录
- **THEN** 系统 MUST 建立有效会话
- **AND** 会话 MUST 记录用户标识、角色和所属班级

#### Scenario: 错误密码登录失败

- **WHEN** 用户使用存在的账号和错误密码登录
- **THEN** 系统 MUST 拒绝登录且 MUST NOT 建立有效会话
- **AND** 响应 MUST NOT 返回密码哈希或其他敏感认证信息

#### Scenario: 未登录访问受保护资源

- **WHEN** 未携带有效会话的用户访问材料列表页面或受保护接口
- **THEN** 页面请求 MUST 重定向到登录页
- **AND** 接口请求 MUST 返回 HTTP 401
- **AND** 响应 MUST NOT 包含任何班级的材料标题、正文或文件路径

#### Scenario: 登出使旧会话失效

- **WHEN** 用户登出后使用登出前保存的 cookie 请求受保护接口
- **THEN** 系统 MUST 返回 HTTP 401
- **AND** 旧 cookie MUST NOT 恢复会话

### Requirement: 角色权限

系统 MUST 根据会话中的角色执行服务端授权。教师可以上传和管理本班材料；学生只能查看本班材料；学生调用上传或管理接口时 MUST 被拒绝。

#### Scenario: 学生上传被拒绝

- **WHEN** 学生 A1 使用有效会话向材料上传接口提交文件
- **THEN** 系统 MUST 返回 HTTP 403
- **AND** 材料表与知识库表 MUST NOT 新增或修改记录
- **AND** 上传目录 MUST NOT 留下该请求产生的文件

#### Scenario: 教师上传被允许

- **WHEN** 教师 A 使用有效会话上传受支持的文件
- **THEN** 系统 MUST 执行材料上传与知识库入库流程
- **AND** 成功响应 MUST 返回 HTTP 201 和新材料标识

#### Scenario: 学生只能读取本班材料

- **WHEN** 学生 A1 打开本班材料列表
- **THEN** 系统 MUST 展示学生 A1 有权读取的 A 班材料
- **AND** 学生 A1 调用材料写接口时 MUST 被服务端拒绝

### Requirement: 班级隔离

班级是数据边界。系统 MUST 在服务端根据会话中的班级标识过滤材料、知识库条目及相关业务数据。A 班用户 MUST NOT 读取、修改或删除 B 班材料。

#### Scenario: 跨班按 ID 访问被拒绝

- **WHEN** A 班用户通过 URL、接口路径或请求体指定 B 班材料 ID
- **THEN** 系统 MUST 返回 HTTP 404
- **AND** 响应 MUST NOT 包含 B 班材料的标题、正文、文件路径或存储键

#### Scenario: 跨班下载与不存在资源同形

- **WHEN** A 班用户分别请求 B 班材料文件与一个不存在的材料文件
- **THEN** 两次请求 MUST 返回相同的 HTTP 404 响应
- **AND** 文件 MUST NOT 从静态上传路径直接访问

#### Scenario: A 班列表不泄露 B 班材料

- **WHEN** 学生 A1 请求材料列表
- **THEN** 返回集合中的所有记录 MUST 归属于 A 班
- **AND** 列表 MUST NOT 出现 B 班样本材料的可区分标题

#### Scenario: 客户端班级参数不能覆盖会话

- **WHEN** A 班用户在查询参数、表单或请求体中提交 B 班标识
- **THEN** 系统 MUST 忽略或拒绝客户端提供的班级标识
- **AND** 数据读取与写入 MUST 继续使用会话中的 A 班标识

### Requirement: 材料上传与知识库入库

教师上传教学材料后，系统 MUST 保存文件、解析文本并以同一事务写入材料记录和知识库记录。两类记录 MUST 关联上传教师所属班级；本班材料列表 MUST 从数据库读取，上传成功后刷新列表 MUST 显示新记录。

#### Scenario: 上传后知识库与材料列表可查

- **WHEN** 教师 A 上传合法的 `.md` 或 `.txt` 文件且解析成功
- **THEN** 材料表 MUST 新增一条关联 A 班且标题可辨的记录
- **AND** 知识库表 MUST 新增一条关联该材料和 A 班的正文记录
- **AND** 教师 A 刷新本班材料列表时 MUST 看到新材料

#### Scenario: 上传后本班学生只读可见

- **WHEN** 教师 A 成功上传材料后，学生 A1 刷新本班材料列表
- **THEN** 学生 A1 MUST 看到该材料
- **AND** 学生 A1 MUST NOT 修改、删除或上传覆盖该材料

#### Scenario: 上传失败不产生脏数据

- **WHEN** 上传文件格式不受支持、文件为空或内容解析失败
- **THEN** 系统 MUST 返回 HTTP 400
- **AND** 材料表和知识库表 MUST NOT 留下不完整记录
- **AND** 系统 MUST 清理已写入但未关联成功的文件

#### Scenario: 超限上传被拒绝

- **WHEN** 教师上传超过配置大小上限的文件
- **THEN** 系统 MUST 返回 HTTP 413
- **AND** 材料表、知识库表与上传目录 MUST 保持不变

### Requirement: 预置核心数据

系统 MUST 建立班级、用户、讲义、作业、助手和技能六类核心数据结构，并预置能够验证登录与班级隔离的双班样本数据。

#### Scenario: 种子数据包含双班用户

- **WHEN** 首次执行数据库初始化或种子脚本
- **THEN** 数据库 MUST 包含班级 A 和班级 B
- **AND** 数据库 MUST 包含归属 A 班的教师 A、学生 A1，以及归属 B 班的学生 B1
- **AND** 每个预置用户 MUST 具有可登录的用户名和密码哈希

#### Scenario: 双班材料可区分

- **WHEN** 种子脚本执行完成
- **THEN** 数据库 MUST 至少包含一条标题可识别为 A 班的材料和一条标题可识别为 B 班的材料
- **AND** 讲义、作业、助手和技能的数据结构 MUST 已建立

### Requirement: 密码与会话密钥安全

系统 MUST 使用单向密码哈希保存用户密码。会话签名密钥 MUST 只通过服务端环境变量或 Docker Compose 注入，并且 MUST NOT 写入源码或提交到版本库。

#### Scenario: 数据库不保存明文密码

- **WHEN** 验收人员查询用户表中的密码字段
- **THEN** 字段值 MUST NOT 等于任何预置账号的明文密码
- **AND** 字段值 MUST 符合所选密码哈希算法的格式

#### Scenario: 登录使用哈希验证

- **WHEN** 用户输入正确密码
- **THEN** 系统 MUST 通过密码哈希验证并建立会话
- **AND** 同一用户输入错误密码时 MUST 验证失败且不建立会话

#### Scenario: 缺少会话密钥时启动失败

- **WHEN** 运行环境未提供必需的会话签名密钥
- **THEN** 应用 MUST 拒绝启动并报告缺少配置
- **AND** `.env.example` MUST 列出所需变量名且 MUST NOT 包含真实密钥

### Requirement: Docker Compose 部署与健康检查

系统 MUST 使用 Docker Compose 作为标准启动方式，并提供无需登录的 `GET /health`。数据库文件和上传目录 MUST 持久化，使容器重建后数据仍然存在。

#### Scenario: Compose 启动后服务可访问

- **WHEN** 操作者按照 README 配置环境变量并执行 Docker Compose 启动命令
- **THEN** 登录页 MUST 可以通过 README 指定的地址访问
- **AND** `GET /health` MUST 返回 HTTP 200 和表示服务可用的 JSON 响应

#### Scenario: 健康检查不需要登录

- **WHEN** 未携带会话 cookie 的请求访问 `GET /health`
- **THEN** 系统 MUST 返回 HTTP 200
- **AND** 系统 MUST NOT 将请求重定向到登录页

#### Scenario: 重建容器后数据仍在

- **WHEN** 系统已有预置数据或上传记录，操作者停止并重新创建容器且未删除持久化数据
- **THEN** 预置用户 MUST 仍能登录
- **AND** 已上传材料与知识库记录 MUST 仍能由本班用户查询
