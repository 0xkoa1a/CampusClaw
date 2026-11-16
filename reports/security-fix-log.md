# 安全修复记录

当前验证包括本地自动化与 HTTP、CLab MCP 回归、GitHub Actions 和镜像构建。课程 MySQL 示例目前沿用 SQLite 事务与持久化语义，未宣称完成 MySQL 迁移。

| 项目 | 当前验证 | 证据 |
| --- | --- | --- |
| SEC-01 身份与 CSRF | 未登录受保护接口拒绝；同源 API 写请求不再被 CSRF 来源检查误拦。 | `tests/test_bearer.py`、`tests/test_security_controls.py`、[security-http.json](week10-local/security-http.json) |
| SEC-02 归属与输入 | 跨班资源读取 404；SQL 注入搜索无结果。 | [security-http.json](week10-local/security-http.json) |
| SEC-03 角色授权 | 学生写受限资源 403；服务端按会话角色和班级鉴权。 | [security-http.json](week10-local/security-http.json)、`tests/test_security_controls.py` |
| SEC-04 作业写入 | 学生不能覆盖教师评分；跨班任务不可见；本地 HTTP 检查覆盖教师改分。 | [security-http.json](week10-local/security-http.json)、`tests/test_assignments.py` |
| SEC-05 密钥扫描 | scanner 0 命中。 | `make check-security` 对应的 [CI run](https://github.com/0xkoa1a/CampusClaw/actions/runs/43905787819) |
| SEC-06 依赖 | pip-audit：No known vulnerabilities。 | 同一 [CI run](https://github.com/0xkoa1a/CampusClaw/actions/runs/43905787819)；仓库内 `dependency-audit.json` 是 2026-11-04 的旧记录 |
| SEC-07 审计与观测 | 结构化审计可按教师权限查询；CLab MCP 回归 10 项检查、5 轮调用通过。教师查询到学生改分 403 事件及审计字段。 | `tests/test_observability.py`、[CLab 拒绝审计](week10-local/clab-audit-denied.json)、[第 9 课截图](../docs/evidence/classroom/week09/03-CLab教师审计回查.png) |
| SEC-08 提示注入 | CLab 真实模型实验通过：恶意材料标记未进入模型请求；正常流式回答成功；三条指令均 400 且 trace 未增加。评分任务真实网关成功，越权改分 403、跨班读取 404。 | [真实验收 JSON](week10-local/clab-security-real.json)、[SEC08 实验记录](sec08-experiment.md) |

最终补齐 SQL/XSS 回归后，完整测试套件 297 项、安全套件 66 项通过，原始输出为 [final-check.txt](week10-local/final-check.txt)、[final-security-gate.txt](week10-local/final-security-gate.txt)。此前 `bd68f97` 的安全 CI run `43905787819` 成功；容器 run `43905786752` 的 gates 和 build jobs 均成功。两者均包含 `make check` 与 `make check-security` 成功记录。

修复提交 `bd68f97`（`fix(SEC-07): scope worker audit and bound monitoring time windows`）收紧 worker 审计归属并限制监控时间窗。该 revision 已部署至 CLab 并完成复验；运行信息见 [clab-runtime.json](week10-local/clab-runtime.json)。

XSS DOM 检查确认恶意内容以转义文本呈现，见 [DOM 结果](../docs/evidence/classroom/week09/xss-dom.json)和[截图](../docs/evidence/classroom/week09/01-XSS内容按文本呈现.png)。告警实测由受控失败触发，300.559 秒内记录 149 次失败并生成 active 通知，见 [CLab 告警导出](week10-local/clab-alert-trigger.json)。真实桌面监控、手机视图及告警运行截图见[04](../docs/evidence/classroom/week10/04-CLab真实服务观测.png)、[05](../docs/evidence/classroom/week10/05-CLab手机观测.png)、[06](../docs/evidence/classroom/week10/06-CLab告警与容器运行记录.png)。

SQL、XSS、CSRF 三种反例已纳入 `apitest/cases/api/security/POST.py`，单 case 通过真实本机 HTTP 复验，见 [security-case-http.json](week10-local/security-case-http.json)。XSS 用例检查上传文件名的转义结果确实存在，不能只以页面未出现恶意字符串作为通过判据。讲义标题 `<script>alert(1)</script>` 的常驻 pytest 另行覆盖服务端转义，截图使用隔离测试库中的同样标题。

修复中曾发现技能字段为 `None` 时的审计处理问题，以及 CSRF 检查误拦同源 API 的回归；当前相关回归用例通过。没有记录修复耗时。
