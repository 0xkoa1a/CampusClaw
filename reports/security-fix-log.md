# 安全修复记录

范围：当前本地代码、合成账号、真实 HTTP/SQLite 检查及已保存课堂证据。课程要求 MySQL 的事务和持久化语义目前由 SQLite 实现；本轮没有迁移或验收 MySQL。

| 项目 | 修复后实际 | 判定 | 证据 |
| --- | --- | --- | --- |
| SEC-01 身份 | 未登录受保护接口由服务端拒绝；CSRF 来源检查曾误拦同源 API 写请求，已修正。 | 本地测试通过 | `tests/test_bearer.py`、`tests/test_security_controls.py`、`reports/week10-local/security-http.json` |
| SEC-02 归属 | 跨班资源读取返回 404；注入搜索返回空结果。 | 本地 HTTP 检查通过 | `reports/week10-local/security-http.json`：`cross_class_404`、`sql_injection_empty` 均为 true |
| SEC-03 角色 | 学生直接写智能体等受限资源返回 403。 | 本地 HTTP/单测通过 | `security-http.json`：`student_write_403`；`tests/test_security_controls.py` |
| SEC-04 写入边界 | 学生不能覆盖教师评分；教师覆盖流程成功；跨班任务读取返回 404。 | 本地 HTTP 检查通过 | `security-http.json`：`teacher_override`、`student_write_403`、`cross_class_404` 均为 true |
| SEC-05 密钥 | 当前扫描结果为 0 命中。 | 本地扫描通过 | `make check-security` 执行的 scanner；本次扫描原始输出未另存到允许写入的报告文件中 |
| SEC-06 依赖 | 本次 `pip-audit` 结果为 No known vulnerabilities。 | 本地审计通过 | 本次结果由执行者提供；仓库内 `reports/dependency-audit.json` 是 2026-11-04 的旧报告，仍记录当时的 pytest 公告，不能代表本次结果 |
| SEC-07 审计 | 结构化事件可按教师权限查询；字段包含请求身份、时间、动作、对象、状态、技能、耗时和用量。 | 本地检查通过 | `tests/test_observability.py`、`docs/evidence/classroom/week09/02-教师查询脱敏审计.png`、`docs/evidence/classroom/week10/ui-result.json` |
| SEC-08 提示词注入 | 显式索要提示词/越权指令在本地入口返回 400；恶意材料上下文过滤单测通过。真实模型四步实验尚未完成。 | 部分完成 | `security-http.json`：`three_explicit_injections_400`；`tests/test_security_controls.py`；详情见 [`sec08-experiment.md`](sec08-experiment.md) |

本轮修复过程中曾暴露 `skill=None` 审计字段处理问题和 CSRF 误拦 API 回归。当前测试覆盖空技能字段与 API/Form CSRF 行为；修复耗时没有记录，本报告不补写时长。

本地回归记录：完整套件 295 项通过；安全套件 64 项通过，其中新增流式、安全与观测用例 33 项通过。`make check` 故意引入的门禁红灯为 1 failed、295 passed，退出码 2；修复后的演练副本为 296 passed、退出码 0。详情见 [`review-03.md`](review-03.md) 与 `reports/week10-local/gate-*`。

> 当前代码和本地 HTTP 检查不能证明 CLab、真实模型实验、远端 CI 或团队主干保护已通过。仓库中的旧依赖审计 JSON 尚未更新。
