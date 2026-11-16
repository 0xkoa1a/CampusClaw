# 门禁红绿验证

在当前工作树的隔离副本中，故意把未登录 `/api/me` 的预期状态改为 200。真实运行 `make check` 得到 1 failed、295 passed，退出码 2；失败点为接口实际返回 401。将断言恢复为 401 后，完整检查 296 passed、退出码 0。

| 阶段 | 结果 | 原始证据 |
| --- | --- | --- |
| 故意引入错误 | 1 failed、295 passed；退出码 2 | [gate-red.txt](week10-local/gate-red.txt) |
| 修正预期并重跑 | 296 passed；退出码 0 | [gate-green.txt](week10-local/gate-green.txt) |
| 可复核演练数据 | red/green 命令、预期状态和退出码 | [gate-drill.json](week10-local/gate-drill.json) |
| 页面化输出 | 红绿运行摘录 | [gate-output.html](../docs/evidence/classroom/week10/gate-output.html)、[截图](../docs/evidence/classroom/week10/03-门禁故意改坏与修复.png) |

红灯是对测试预期的隔离演练，不是产品代码回归失败。提交 `bd68f97` 的 GitHub Actions 检查与镜像构建均成功，记录见[根验收报告](../report.md)。
