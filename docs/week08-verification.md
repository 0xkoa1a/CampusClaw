# 第 7、8 课实现与验证

## 已实现

- 第 7 课五类工程规范集中于 [engineering](engineering/README.md)，`AGENTS.md` 引用；沿用现有仓库与启动骨架。
- 教师在 `/assignments` 创建题目、参考答案、评分规程和可选批改技能；学生只见题目，提交后获得 `202` 和任务编号。
- SQLite 保存提交、任务、结果与事务发件箱；独立 worker 使用 RabbitMQ 持久消息、发布确认和手动 ACK。租约、唯一约束、有限重试与死信控制重复和故障恢复。
- 页面查询进度、显示结果、刷新恢复；网络失败后重试复用幂等键。新增接口由现有 OpenAPI/Swagger 描述。
- 第 6 课补漏：检查完整工具文本后截断，避免失效服务器产生无归属审计，调用次数及轮数可配置。

实施规约：[异步批改](../openspec/changes/add-classroom-async-grading/)、[MCP 边界](../openspec/changes/harden-mcp-result-boundaries/)。第 9、10 课暂缓。

本仓库只有批改这一类后台任务，输入通过 `submission_id` 关联，幂等键保存在提交表。课程失败状态中“次数耗尽”在此细分为 `dead`，永久错误为 `failed`；前者同时进入死信队列。

## 本地结果

| 检查 | 结果与证据 |
| --- | --- |
| `make check` | 245 项通过；包含旧数据迁移、DDL 回滚、权限、并发、重试、租约、消息确认契约和批改输出校验 |
| 新增验收脚本测试 | `tests/test_week08_verifier.py` 9 项通过，覆盖回环地址、状态文件、错误脱敏及日志采集 |
| OpenSpec strict | 两项 change 通过 |
| Compose | 新建合成私有配置，`docker compose --env-file <临时配置> config -q` 通过 |
| 20 次 HTTP 提交 | 全部 202、无评分字段；P95 0.0038 秒，相比两秒测试批改无需等待，见 [async-local.json](../reports/async-local.json) |
| 桌面与手机 | 教师创建、题目可见、pending→succeeded、刷新恢复、390px 无横向溢出，页面及控制台错误为零 |
| 完整 HTTP 脚本 | 16 项通过；包含新增三项作业接口，20 次提交 P95 0.010837 秒，响应与 SQLite 匹配，见[本地 API 报告](evidence/classroom/week08/api-local.html) |
| 安全基线 | SEC01–04 本地绿，SEC07 红；依赖发现一项 pytest 公告，密钥扫描与缺口见[安全基线](../reports/security-baseline.md) |

本地页面测试使用合成账号、内存传输和确定性批改器；成功卡片明确显示“本地测试替身”。Browser plugin not available，使用现有 Playwright/Chromium，视口 1280×960 与 390×844，地址 `http://127.0.0.1:18088/assignments`。截图和[机器记录](evidence/classroom/week08/ui-result.json)集中放在 [week08](evidence/classroom/week08/)；课堂派作业日期尚未确认，因此不猜测日期。

| 截图 | 内容 |
| --- | --- |
| [教师创建](evidence/classroom/week08/01-教师创建作业.png) | 真实浏览器填写、保存作业 |
| [暂停等待](evidence/classroom/week08/02-暂停消费者后等待处理.png) | 已接收，任务等待处理 |
| [恢复与刷新](evidence/classroom/week08/03-恢复消费并刷新保留结果.png) | 消费恢复后成功，刷新后结果仍在 |
| [手机布局](evidence/classroom/week08/04-手机作业与结果.png) | 窄屏表单、进度和结果 |

复现页面：先以全新临时目录运行 `python -m scripts.classroom_evidence_server --data-dir <临时目录>`，再设置 `FIXTURE_DATA_DIR`、`PLAYWRIGHT_MODULE` 执行 `node scripts/verify_classroom_ui.cjs`。脚本只访问回环地址。并发、事务、自查及 Review 分别见 [reports](../reports/) 下对应记录。

完整 HTTP 验收沿用 `apitest/run_all.py`；按 [apitest 运行说明](../apitest/README.md) 配置三个测试密码和同一实例的 SQLite 路径。报告的 20 次计时与上面的暂停消费者实验是独立轮次。

## CLab 真实验收

部署目录 `/home/ubuntu/workspace/campusclaw/verification/week08/`，Compose 项目 `campusclaw-week08-20261104`，仅绑定 `127.0.0.1:18088`。业务源码为 `8f82774`；新增验收脚本在宿主机执行。原第六课服务使用独立目录、项目及数据卷。

| 课程判据 | 真实观察 | 证据 |
| --- | --- | --- |
| 提交不等待批改 | 暂停 worker 后连续 20 次提交均为 202，无评分字段；P95 为 7.24 ms。实际批改耗时中位数 1895 ms，范围 1100–5081 ms | [提交采样](evidence/classroom/week08/clab-acceptance.json)、[工作日志事件](evidence/classroom/week08/worker-events.json) |
| 停止后恢复 | 20 条消息发布获确认；重启 RabbitMQ 后仍有 20 条。恢复 worker 后全部成功，结果来源均为真实课程网关 | [代理重启](evidence/classroom/week08/broker-restart.json)、[20 份结果](evidence/classroom/week08/clab-grading.json) |
| 重复只保留一份结果 | 同键重提返回原任务；向真实代理重投已完成任务，执行次数和结果不变。运行中 SIGKILL 消费者后重启，任务第二次执行成功，结果仍只有一份 | [崩溃恢复](evidence/classroom/week08/clab-crash-recovery.json)、[唯一性核对](evidence/classroom/week08/clab-uniqueness.json) |
| 应用重建 | 3 个用户、5 份材料、21 份提交/任务/结果及其余业务表重建前后计数一致 | [逐表计数](evidence/classroom/week08/clab-restart.json) |

20 份合成答案均正确，模型均给出 100 分。手机与桌面页面显示“课程网关”，刷新后保留结果；见[真实等待截图](evidence/classroom/week08/05-CLab真实队列等待处理.png)、[真实批改截图](evidence/classroom/week08/06-CLab真实网关批改结果.png)、[手机截图](evidence/classroom/week08/07-CLab手机批改结果.png)。浏览器仍使用 Playwright/Chromium，通过 SSH 隧道访问，无页面或控制台错误。

RabbitMQ 实测为 4.4.0。Docker Hub 超时后，采用 AWS 托管的官方镜像，并在私有配置中固定为 `public.ecr.aws/docker/library/rabbitmq:4-alpine@sha256:21577d148f4f7563a87d761862fa353f59348a094833ca8b1b1a46a8102dffce`。镜像、数据卷与日志扫描摘要见[运行元数据](evidence/classroom/week08/runtime-metadata.json)。

数据库一致性快照和合成上传文件位于远端 `backups/week08-20261104-data/`，目录权限 0700。未额外备份私有 `.env`。应用包审计覆盖实际安装的 18 个包，pip 25.0.1 有 6 项去重公告；[安全基线](../reports/security-baseline.md)记录发现项，本轮不升级依赖。

复现顺序为：`scripts.prepare_week08_acceptance` 建立全新环境；停止 worker 后执行 `scripts.verify_week08 prepare`；确认发布消息并重启代理；启动 worker 后执行 `verify`。故障验证执行 `crash-prepare`、`crash-wait-running`，在 running 时终止并启动 worker，再执行 `verify-crash`。脚本 state 只存合成任务标识，登录 token 仅在内存中使用，结束时撤销。

## 待办

第六课真实 MCP 回归的 10 项检查和 5 次会话已通过，见[摘要](evidence/classroom/week06-supplement/real-regression.json)。另实测服务停机时记录 error 并完成错误说明；恢复服务后，在一轮一次配额下只发生一次规划、一次 MCP 调用，最终回答完成。截图与摘要见[补充验收](evidence/classroom/week06-supplement/README.md)。

MCP 服务已恢复，当前 app、MCP 和 RabbitMQ 健康探针通过，worker 运行中；[最新元数据](evidence/classroom/week08/runtime-current.json)的日志扫描无密钥命中。独立复核证据未齐前不归档 change；课堂派由本人提交。
