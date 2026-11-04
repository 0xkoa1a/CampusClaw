# 工程规范

本目录把第 7 课工程规范落成个人仓库可执行的检查条目，适用于现有 Flask、SQLite、Qdrant、MCP，以及规约中的 RabbitMQ 异步批改计划。

- [product.md](product.md)：用户、页面、状态和交互验收。
- [backend.md](backend.md)：Flask API、SQLite 事务、Qdrant/MCP/队列边界。
- [security.md](security.md)：身份、逐资源授权、输入与输出处理、密钥边界。
- [testing.md](testing.md)：pytest 用例组织、隔离、故障与验收判据。
- [operations.md](operations.md)：环境配置、日志、部署、备份与回滚。

## 适用状态

- 当前仓库约束以 `AGENTS.md`、已有实现和正式 OpenSpec 为准；本目录不替代或修改它们。
- 第 8 课异步批改以已 strict 验收的 `openspec/changes/add-classroom-async-grading/` 为实施规约。源码存在、规约通过和真实部署验收是不同状态；RabbitMQ 持久化、消费者停机恢复及三条判据只有在相应验证记录出现后才能标为已验证。
- 本轮第 8 课基线执行 SEC-01 至 SEC-07：记录实际身份、操作、结果与证据，不修复发现项；SEC-08 只准备恶意文档和诱导问题素材，不执行测试。第 9、10 课的修复暂缓；CSRF 覆盖仍待核实，不声称已实现或已通过检查。

所有条目都须能由代码审查、自动化用例或明确的运行记录判定。未验证的能力记录为待办，不能写成已通过。
