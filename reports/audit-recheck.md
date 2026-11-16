# 审计与告警复核

教师可通过 `GET /api/audit-events` 查询本班结构化审计，并用 `user_id`、`from`、`to` 限定筛选。未登录请求返回 401，学生查询返回 403。字段覆盖身份、时间、动作、对象、HTTP 状态、技能、耗时和用量；值脱敏及权限由观测测试覆盖。

CLab A 班教师通过审计接口查到本班 student user_id 2 的评分覆盖拒绝事件：PUT `/api/tasks/<string:identifier>/grade`，状态 403，记录 `username=student_a1`、`role=student`、`operation`、`object`、`skill`、`duration_ms`、`usage` 等字段。原始查询结果见 [`clab-audit-denied.json`](week10-local/clab-audit-denied.json)，真实界面见[第 9 课教师审计截图](../docs/evidence/classroom/week09/03-CLab教师审计回查.png)。手机流程复核显示 `foreign_class_audit_visible=false`，即 A 班教师看不到 B 班审计；见 [`clab-mobile-walkthrough.json`](week10-local/clab-mobile-walkthrough.json)。该真实手机提交返回 202，实际观察到状态从 `pending` 到 `succeeded`，没有观察到 `running`；[第 10 课截图 07](../docs/evidence/classroom/week10/07-手机提交与真实批改完成.png)记录了提交与完成界面。CLab MCP 回归 10 项检查、5 轮调用通过。

第 10 课真实运行截图： [桌面监控](../docs/evidence/classroom/week10/04-CLab真实服务观测.png)、[手机监控](../docs/evidence/classroom/week10/05-CLab手机观测.png)、[告警与容器状态](../docs/evidence/classroom/week10/06-CLab告警与容器运行记录.png)。应用 revision 为 `bd68f97143951041a6960fc627b750deb2dfc809`，运行摘要见 [`clab-runtime.json`](week10-local/clab-runtime.json)。

运行采集器从独立列读取 `request_id`、`user_id`，从 JSON 字段读取技能和用量。真实模型流式事件记录 prompt_tokens=233、completion_tokens=470、total_tokens=703；异步评分记录 251、83、334。两者均有用户、班级和请求关联，见 [`clab-runtime.json`](week10-local/clab-runtime.json)。

持续告警已在 CLab 稳定时钟演练并导出：[clab-alert-trigger.json](week10-local/clab-alert-trigger.json) 记录 300.559 秒、149 次失败、错误率 1.0，阈值为 0.01，通知状态为 `active`，并持久化至教师站内通知列表。该导出标记 `local-stub-controlled-failure-real-HTTP`，表示受控失败通过真实 HTTP 触发；CLab 实际监控当前导出见 [`clab-monitoring.json`](week10-local/clab-monitoring.json)。

门禁演练另见[红绿运行记录](gate-red-green.md)。远端检查、容器构建和对应提交见[根验收报告](../report.md)。
