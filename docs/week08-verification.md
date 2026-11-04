# 第 7、8 课实现与本地验证

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

## 尚需真实环境

Mac Docker daemon 当前不可用。本地替身没有验证 RabbitMQ 持久化、真实代理重投或课程模型效果。下一步需要 VPN 访问 CLab，在 `/home/ubuntu/workspace/campusclaw/verification/week08/` 创建隔离环境，完成三条课程判据、真实网关批改及日志采样。现有第六课环境不作为新版已部署的证据。

第 6 课新增的成功/拒绝/错误页面展示和调用上限降级也待真实环境补图。独立复核证据未齐前保留待办，不归档变更。课堂派提交由本人完成。
