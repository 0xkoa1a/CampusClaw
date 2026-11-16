# 观测与持续告警

教师页面 `/monitoring` 展示三种技能调用量、按错误数/总数计算的错误率，以及 HTTP P95 和任务队列深度。时间窗可选 5 分钟、1 小时、6 小时、24 小时和 7 天。真实 CLab 结果和手机视图分别见[桌面截图](../docs/evidence/classroom/week10/04-CLab真实服务观测.png)、[手机截图](../docs/evidence/classroom/week10/05-CLab手机观测.png)及[原始面板数据](week10-local/clab-monitoring.json)。

告警条件是某技能错误率持续 300 秒高于 1%，动作是将通知写入教师面板的站内通知列表。判定由 `/api/monitoring` 查询驱动；持续观测要求在该窗口中定期查询，超过 75 秒的观测间隔会重新计时。当前没有独立后台告警调度器。

在 CLab 应用容器内启动隔离的故障测试进程，使用合成账号与可控模型失败，通过真实 HTTP 每约 2 秒发送问题并查询面板。模型由替身持续失败，告警逻辑、审计落库、计时和 HTTP 均实际执行。

| 观测项 | 实测值 |
| --- | --- |
| 技能 | 数学解题引导 |
| 持续时间 | 300.559 秒 |
| 失败调用 | 149 次 |
| 错误率 | 100% |
| 通知 | id=1，status=active，已写入教师站内列表 |

原始记录：[clab-alert-trigger.json](week10-local/clab-alert-trigger.json)。[告警与容器截图](../docs/evidence/classroom/week10/06-CLab告警与容器运行记录.png)是该 JSON 和实际容器数据的浏览器呈现。演练不使用邮件或外部消息；模型故障替身不代表课程网关发生故障。

日志以请求 ID、技能和班级关联模型事件；异步调用使用 `task:<任务编号>`。实际网关返回的 token 用量和未提供用量的 null 值均保留在 [clab-runtime.json](week10-local/clab-runtime.json)，不从文本长度估算用量。
