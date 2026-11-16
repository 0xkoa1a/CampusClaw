# Review 03：脚本与验收判据复核

审阅方式：逐项核对执行脚本、保存的 JSON/命令输出和课堂截图。判据是脚本退出码及结构化结果符合本地验收条件。此记录属于脚本证据复核，不是人工同伴复测。

| 手段 | 检查内容 | 判据 | 结果 |
| --- | --- | --- | --- |
| `make check` | 完整本地测试套件 | 当前运行 295 项通过 | 本轮结果由执行者提供；门禁演练的独立输出见下行 |
| `scripts/gate_drill.py` 与 `gate-drill.json` | 在一次性副本中把未认证 `/api/me` 的期望状态改为 200，再改回 401 | 错误期望必须失败；修正期望退出 0 | 红灯为 1 failed、295 passed、退出码 2；绿灯为 296 passed、退出码 0。绿灯副本多出的 1 项是演练用例 |
| `make check-security` | 安全用例、secret scanner、pip-audit | 安全用例通过、扫描 0 命中、依赖无已知漏洞 | 本轮结果：64 项通过，scanner 0，pip-audit No known vulnerabilities。原始 pip-audit 本轮输出未保存；`reports/dependency-audit.json` 是 11 月 4 日旧结果 |
| `scripts/verify_delivery_local.py` 与 `security-http.json` | 本地 stub 模型上的真实 HTTP/SQLite 安全流程 | 202、教师覆盖、学生写入 403、跨班 404、注入/来源/CSRF 判据符合预期 | JSON 中列出的 HTTP 判据均为 true；JSON 的 XSS 浏览器字段仍为 pending，不能据此称 XSS 已验证 |
| `xss-dom.json` 与 `ui-result.json` | 浏览器 DOM 中的 XSS 文本转义、仪表板与审计查询 | escaped 为 true、无注入节点/意外对话框 | `escaped_dom_source=true`、`injected_script_node=false`、`unexpected_dialog=false`；UI 检查无错误 |
| 新增流式/安全/观测用例 | 对流式响应、安全边界、请求关联和日志脱敏执行回归 | 新增 33 项全部通过 | 本轮结果为 33 项通过；测试实现在 `tests/test_security_controls.py`、`tests/test_observability.py` 及相关流式用例 |

未验证项：GitHub Actions/远端 CI 尚无通过结果；主干保护尚未由团队设置；本地 stub HTTP 结果不等于 CLab 或真实模型结果；第三方用户反馈尚未收集。
