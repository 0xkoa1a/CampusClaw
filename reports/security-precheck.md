# 安全自查

环境：2026-11-04，本地临时 SQLite、合成 A/B 班账号，Flask test client。复现：`.venv/bin/python -m scripts.verify_security_precheck --output reports/security-precheck-local.json`。

| 项目 | 操作与观察 | 结论 |
| --- | --- | --- |
| SEC-01 身份 | 未登录 GET `/api/me`、`/api/materials`、`/api/agents`、`/api/skills`、`/api/conversations`、`/api/assignments`、`/api/tasks`，全部 401 | 本地绿 |
| SEC-02 隔离 | B 班读取 A 班材料详情、下载均 404；B 班关键词检索没有 A 班材料 | 本地绿 |
| SEC-03 配置写权限 | 学生直接 POST `/api/agents`、`/api/skills`、`/api/assignments`，全部 403 | 本地绿 |
| SEC-04 绕过页面 | 学生直接写作业返回 403；不存在的结果写入口返回 404；前后数据库计数一致 | 本地绿 |
| SEC-05 密钥 | 当前源文件、可达历史的高置信模式扫描，范围和输出见[安全基线](security-baseline.md) | 按基线报告判定 |
| SEC-06 依赖 | 依赖审计结果见[安全基线](security-baseline.md) | 按基线报告判定 |
| SEC-07 可观测性 | `mcp_audit` 有用户、工具、状态和时间，没有耗时与用量字段；HTTP 数据库错误日志仍为普通文本 | 红 |

逐接口结果：[security-precheck-local.json](security-precheck-local.json)。本地自动化另覆盖同班他人任务 404、学生响应不含参考答案和评分规程、事务回滚无孤儿记录。

受保护写操作还包括资料上传、技能更新、智能体更新、会话消息提交、MCP 服务器配置。以上未逐项重复做人工接口自查，回归覆盖情况见测试文件。

SEC-08 的恶意讲义与三条诱导问题已[准备](sec08-preparation.md)，未执行注入实验。CLab 运行日志采样、真实服务重验和独立复核待完成；本轮只记录发现项，第 9、10 课修复暂缓。
