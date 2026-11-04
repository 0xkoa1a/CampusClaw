# 异步批改：并发验证

## 本地结果

`.venv/bin/python -m scripts.verify_async_local --data-dir <本地隔离目录> --output reports/async-local.json` 对真实本机 HTTP 服务连续提交 20 次，均返回 `202`，响应体不含评分。P95 为 0.0038 秒，测试批改器固定等待 2 秒。消费者暂停时任务保持 pending，恢复后第一条任务成功；同一幂等键重提返回原任务。原始采样见 [async-local.json](async-local.json)。

应用级并发测试 `test_concurrent_same_key_creates_one_submission_task_and_outbox` 用 8 个线程重复提交 16 次，断言只有一份提交、一条任务和一条 outbox。重复投递测试断言已完成任务不再调用批改器，结果表唯一约束阻止第二份结果。

本地传输是内存替身，批改器为确定性替身。该结果验证接收接口不等待批改及应用幂等，不验证代理持久化。

## CLab 待验

- 在独立第八课 Compose 项目启动 RabbitMQ 和真实网关，使用合成账号与材料重复 20 次计时。
- `docker compose stop worker` 后提交，确认 pending；`start worker` 后确认无需重提交即可完成。
- 用代理重投或在 ACK 前终止消费者，确认最终结果只有一条、评分不变，并记录执行次数。
- 留存队列持久化、发布确认和重启后任务恢复证据。

消费者执行次数记录实际取得租约的尝试；已成功任务的重复消息直接确认，不额外增加模型执行次数。外部模型调用在崩溃恢复时可能重复，结果只生效一次。
