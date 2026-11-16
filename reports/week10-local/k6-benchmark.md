# k6 接口压测

使用 Grafana k6 v1.8.2，每项 20 VU、60 秒，对本地 `127.0.0.1:18090` 合成环境发送真实 HTTP。模型和向量为确定性替身；检索使用 keyword。任务数据初始为 20,000 行，提交测试继续增加记录，因此这组三接口样本不用于索引前后对照。

| 接口 | 请求数 | 吞吐（次/秒） | 接口 P95 | 业务检查失败 | 原始指标 |
| --- | ---: | ---: | ---: | ---: | --- |
| 提交 | 16,661 | 276.685 | 274.846 ms | 0 | [k6-submit-final.json](k6-submit-final.json) |
| 查询 | 21,449 | 356.575 | 204.938 ms | 0 | [k6-query.json](k6-query.json) |
| 检索 | 28,706 | 476.991 | 145.972 ms | 0 | [k6-search.json](k6-search.json) |

提交每次生成独立幂等键，衡量持久接收速度，不衡量批改吞吐。每轮独立登录，结束后退出并验证旧令牌返回 401。查询和检索的初次导出将预期的登出后 401 各计入一次 `http_req_failed`，业务请求检查均通过；提交最终轮已使用正确的预期响应分类。

提交首轮 summary 曾被后续中断运行覆盖，最终单独重跑提交并保存完整指标。导出已移除 k6 自动附带的 `setup_data` 和测试令牌，`metrics`、`root_group` 原值保留。测试会话已撤销。

脚本为 [benchmark-k6.js](../../scripts/benchmark-k6.js)。通过环境变量设置 `CAMPUSCLAW_K6_PASSWORD` 和 `CAMPUSCLAW_K6_MODE=submit|query|search`，运行 k6 并指定 `--summary-export`。可配置 base URL、并发、持续时间、账号、作业 ID 和检索词；只接受 loopback 目标。入库前移除导出的 setup 数据。

本组只有一个并发档位，未确定饱和点。索引前后改进使用独立且参数相同的 Python 采样，见[性能基准](../bench.md)。
