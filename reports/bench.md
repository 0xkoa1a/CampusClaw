# 本地性能基准

基准使用 `scripts/benchmark_http.py` 对本地 SQLite 应用发起真实 HTTP 请求。索引前后对照固定为 `GET /api/tasks`、空请求体、并发 4、40 次请求、2 秒超时；任务量为 20,001，两个样本失败数均为 0。

| 指标 | 索引前 | 索引后 |
| --- | ---: | ---: |
| P95 延迟 | 0.161642 秒 | 0.036879 秒 |
| 吞吐 | 52.446 req/s | 265.224 req/s |
| 失败 | 0 | 0 |

原始采样：[索引前 JSON](week10-local/query-before.json)、[索引后 JSON](week10-local/query-after.json)。两份记录的目标、方法、请求体 SHA-256、并发、请求数和超时参数相同。

另有并发 1、4、8 下查询、检索和作业提交的 HTTP 样本：`query-c1/c4/c8.json`、`search-c1/c4/c8.json`、`submit-c1/c4/c8.json`。这些是本地对照样本；并发 8 时三个端点的 P95 均高于较低并发样本，不据此推断生产容量或饱和阈值。

课程示例涉及 MySQL；当前实现仍使用 SQLite 的事务与持久化语义，没有完成 MySQL 迁移或 MySQL 性能验收。

课程指定的 k6 脚本为 `scripts/benchmark-k6.js`；提交、查询、检索分别完成 20 VU、60 秒测试，业务检查均无失败，完整指标见 [k6 记录](week10-local/k6-benchmark.md)。该组用于较高并发下的接口采样，不与上表不同参数的索引对照混合计算改善幅度。
