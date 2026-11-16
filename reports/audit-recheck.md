# 审计日志回查

本地教师界面已成功查询审计数据；UI 证据 JSON 标记 `audit_query=true`，截图展示脱敏后的教师查询结果。观测测试还验证了请求 ID、身份、HTTP 状态、动作、对象、技能、耗时、用量字段和敏感值脱敏。

复查入口为教师授权的 `GET /api/audit-events?limit=100`。需要筛选学生和时间窗时，可使用 `user_id`、`from`、`to` 参数；不在命令、报告或截图中保存 bearer token。接口对未登录用户返回 401，对学生返回 403。

本次可核对材料：

- [`tests/test_observability.py`](../tests/test_observability.py)：请求关联、日志七列、教师权限、空技能/用量值、网关与流式用量及敏感字段脱敏断言。
- [`docs/evidence/classroom/week09/02-教师查询脱敏审计.png`](../docs/evidence/classroom/week09/02-教师查询脱敏审计.png)：本地教师审计查询截图。
- [`docs/evidence/classroom/week10/ui-result.json`](../docs/evidence/classroom/week10/ui-result.json)：`audit_query=true`，本地 stub HTTP 环境。
- [`docs/evidence/classroom/week10/01-本地三技能观测面板.png`](../docs/evidence/classroom/week10/01-本地三技能观测面板.png) 与 [`02-手机观测面板.png`](../docs/evidence/classroom/week10/02-手机观测面板.png)：本地面板与手机视图。

截图和 UI JSON 来自本地合成数据，不表示 CLab 或真实用户的审计记录。回查命令的实时输出未另存为 JSON；后续课堂展示时应现场用教师账号查询并记录实际筛选条件。
