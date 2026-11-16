# 项目验收结论

本地测试与安全检查通过：完整套件 295 项通过，安全套件 64 项通过，secret scanner 0 命中，本次 pip-audit 报告 No known vulnerabilities。`reports/week10-local/` 的本地 HTTP/SQLite 安全检查通过；XSS DOM 单独确认输出已转义。此结果不代表远端 CI、CLab/真实模型或 MySQL 已验证。

任务列表索引前后压测使用同一接口、请求体、并发 4 和 40 次请求，任务数据量 20,001：P95 从 0.161642 秒降至 0.036879 秒，吞吐从 52.45 增至 265.22 req/s，失败均为 0。该数据来自本地 SQLite；不得作为 MySQL 或生产容量结论。其它并发样本显示并发 8 时三个接口的 P95 均升高；样本用于本地对照，不能据此声明达到生产饱和点。

CLab/真实模型 SEC-08 四步实验和三名真实用户反馈待完成。`main` 分支保护尚未由团队设置，远端 CI 尚未确认。

## 证据导航

- SEC-01～08 修复状态：[security-fix-log.md](reports/security-fix-log.md)；SEC-08 限定：[sec08-experiment.md](reports/sec08-experiment.md)；授权风险：[risk-authz.md](reports/risk-authz.md)。
- 审计回查：[audit-recheck.md](reports/audit-recheck.md)；AI 七类审阅：[review-02.md](reports/review-02.md)；脚本验收：[review-03.md](reports/review-03.md)。
- 用户反馈状态：[feedback.md](reports/feedback.md)，目前 0/3。
- 门禁红绿原始输出：[gate-red.txt](reports/week10-local/gate-red.txt)、[gate-green.txt](reports/week10-local/gate-green.txt)、[gate-drill.json](reports/week10-local/gate-drill.json)。
- 安全 HTTP 结果：[security-http.json](reports/week10-local/security-http.json)。其 XSS 浏览器项仍为 pending；DOM 实测为 [xss-dom.json](docs/evidence/classroom/week09/xss-dom.json)，并有[转义截图](docs/evidence/classroom/week09/01-XSS内容按文本呈现.png)。
- 查询基准原始数据：[索引前](reports/week10-local/query-before.json)、[索引后](reports/week10-local/query-after.json)；并发 1/4/8 的[查询](reports/week10-local/query-c1.json)、[检索](reports/week10-local/search-c1.json)、[提交](reports/week10-local/submit-c1.json)样本，以及对应的 `*-c4.json`、`*-c8.json`。本地面板截图：[桌面](docs/evidence/classroom/week10/01-本地三技能观测面板.png)、[手机](docs/evidence/classroom/week10/02-手机观测面板.png)；页面检查结果：[ui-result.json](docs/evidence/classroom/week10/ui-result.json)。
- 当前 `pip-audit` clean 结果由本轮执行者提供，未保存原始输出；仓库中的[旧审计 JSON](reports/dependency-audit.json)日期为 2026-11-04，不能代表本轮状态。
