# 第 9、10 课验收

CLab 运行验收版本为 `bd68f97`。最终补齐 SQL/XSS 常驻回归后，本地全量 297 项、安全回归 66 项通过；secret scanner 0 命中，pip-audit 未发现已知漏洞。原始输出见 [final-check.txt](reports/week10-local/final-check.txt) 和 [final-security-gate.txt](reports/week10-local/final-security-gate.txt)。`bd68f97` 的 GitHub Actions 检查 run [43905787819](https://github.com/0xkoa1a/CampusClaw/actions/runs/43905787819) 成功；容器 run [43905786752](https://github.com/0xkoa1a/CampusClaw/actions/runs/43905786752) 的门禁和镜像构建成功。

同参数本地任务列表基准（SQLite、20,001 条任务、并发 4、40 请求）P95 为 0.161642→0.036879 秒，吞吐为 52.446→265.224 req/s，失败均为 0。持续告警 CLab 受控演练记录 300.559 秒、149 次失败并生成 active 通知。CLab MCP 回归 10 项检查、5 轮调用通过。

CLab 真实 SEC08 验收通过：poison marker 未进入模型请求，真实流式回答成功；三条直接指令均 400 且 trace 未增加；真实网关批改成功得 100 分，学生改分 403 且分数不变，B 班读取 404，教师查到拒绝审计事件。证据见 [clab-security-real.json](reports/week10-local/clab-security-real.json)。`bd68f97` 已重新部署并通过复验，运行与审计证据见 [clab-runtime.json](reports/week10-local/clab-runtime.json) 和 [clab-audit-denied.json](reports/week10-local/clab-audit-denied.json)。

小组级后续项：真实用户反馈、同学复现和主干分支保护仍由团队推进，不作为个人必备项。当前使用 SQLite 事务和持久化，未迁移或验证 MySQL。

## 证据导航

- [安全修复与 CI/容器记录](reports/security-fix-log.md)
- [四项技能行为检查](reports/skill-checks.md)
- [门禁红绿演练](reports/gate-red-green.md)；原始输出：[red](reports/week10-local/gate-red.txt)、[green](reports/week10-local/gate-green.txt)、[结构化数据](reports/week10-local/gate-drill.json)
- [性能基准](reports/bench.md)；原始采样：[before](reports/week10-local/query-before.json)、[after](reports/week10-local/query-after.json)、并发 1/4/8 的查询、检索和提交 JSON 位于 `reports/week10-local/`
- [SEC08 实验状态](reports/sec08-experiment.md)；[真实验收 JSON](reports/week10-local/clab-security-real.json)
- [审计与告警复核](reports/audit-recheck.md)；[拒绝事件](reports/week10-local/clab-audit-denied.json)、[运行时](reports/week10-local/clab-runtime.json)、[告警导出](reports/week10-local/clab-alert-trigger.json)
- 手机真实提交与批改证据：[clab-mobile-walkthrough.json](reports/week10-local/clab-mobile-walkthrough.json)、[截图 07](docs/evidence/classroom/week10/07-手机提交与真实批改完成.png)；实际观察到 `pending → succeeded`
- [换目录启动与容器复现](reports/boot-reproduce.md)、[CI 与镜像流水线](reports/pipeline.md)、[观测与持续告警](reports/observe-alert.md)
- [本地安全 HTTP 结果](reports/week10-local/security-http.json)、[XSS DOM 检查](docs/evidence/classroom/week09/xss-dom.json)及[转义截图](docs/evidence/classroom/week09/01-XSS内容按文本呈现.png)
