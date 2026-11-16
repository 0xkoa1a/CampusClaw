# 高风险复核：身份与授权

## 本地结果

本地 HTTP/SQLite 检查使用合成教师和学生账号。服务端会话提供身份与班级范围；学生写受限资源返回 403，跨班任务读取返回 404，学生不能覆盖教师评分。安全检查 JSON 中 `student_write_403`、`cross_class_404`、`teacher_override` 均为 true。登录来源、表单 CSRF 与 Cookie `SameSite=Lax` 的本地判据也通过。

跨班和写权限结果见 [`reports/week10-local/security-http.json`](week10-local/security-http.json)、`tests/test_security_controls.py` 和 [`reports/security-precheck-local.json`](security-precheck-local.json)。XSS DOM 输出另见 [`docs/evidence/classroom/week09/xss-dom.json`](../docs/evidence/classroom/week09/xss-dom.json) 与课堂截图。

## 数据与持久化范围

课程材料使用 MySQL 举例。本轮沿用项目 SQLite 实现，依据现有字段、外键、唯一约束和事务完成本地验证；没有声称 MySQL 已配置、迁移或通过同等测试。20001 条任务查询基准也是本地 SQLite 结果，不可外推到 MySQL 或部署容量。

## 远端复验与后续

- GitHub Actions 功能、安全门禁与容器构建均已通过，见 [pipeline.md](pipeline.md)。
- 团队尚未设置或确认 `main` 分支保护。
- CLab 真实网关批改后，学生覆盖成绩返回 403、成绩不变，跨班读取返回 404；教师可回查本班拒绝事件。直接恶意指令由输入层拦截，未用于诱导模型执行写工具，见 [sec08-experiment.md](sec08-experiment.md)。
- 三名真实用户的使用反馈尚未收集，见 [`feedback.md`](feedback.md)。
